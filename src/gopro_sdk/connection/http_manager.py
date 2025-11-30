"""HTTP/COHN connection manager.

Responsible for establishing, disconnecting HTTP connections and COHN configuration.
"""

from __future__ import annotations

__all__ = ["HttpConnectionManager"]

import asyncio
import logging
import ssl
from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiohttp

from ..config import CohnCredentials, TimeoutConfig
from ..exceptions import HttpConnectionError

logger = logging.getLogger(__name__)


class HttpConnectionManager:
    """HTTP/COHN connection manager.

    Responsibilities:
    - Establish and disconnect HTTP sessions
    - Configure SSL context (support COHN self-signed certificates)
    - Send HTTP requests and handle responses
    """

    def __init__(
        self,
        target: str,
        timeout_config: TimeoutConfig,
        credentials: CohnCredentials | None = None,
    ) -> None:
        """Initialize HTTP connection manager.

        Args:
            target: Last four digits of camera serial number
            timeout_config: Timeout configuration
            credentials: COHN credentials (optional, can be set later)
        """
        self.target = target
        self._timeout = timeout_config
        self._credentials = credentials

        # HTTP session
        self._session: aiohttp.ClientSession | None = None
        self._ssl_context: ssl.SSLContext | None = None

        # State
        self._is_connected = False
        self._error_count = 0

    @property
    def is_connected(self) -> bool:
        """Whether HTTP is connected."""
        return self._is_connected

    @property
    def base_url(self) -> str:
        """HTTP base URL.

        Multi-camera scenarios must use COHN mode (each camera has independent IP).

        Returns:
            COHN mode: https://{ip_address} (default port 443)

        Raises:
            HttpConnectionError: COHN credentials not configured
        """
        if not self._credentials:
            raise HttpConnectionError(
                f"Camera {self.target} has not configured COHN credentials. Multi-camera scenarios must use COHN mode."
            )
        # COHN mode: HTTPS + independent IP
        return f"https://{self._credentials.ip_address}"

    def set_credentials(self, credentials: CohnCredentials) -> None:
        """Set COHN credentials.

        Args:
            credentials: COHN credentials
        """
        self._credentials = credentials

    async def connect(self) -> None:
        """Establish HTTP connection (COHN mode).

        Multi-camera scenarios must use COHN mode: HTTPS + SSL + authentication

        Raises:
            HttpConnectionError: HTTP connection failed or COHN credentials not configured
        """
        if self._is_connected:
            logger.debug(f"Camera {self.target} HTTP already connected, skipping")
            return

        if not self._credentials:
            raise HttpConnectionError(
                f"Camera {self.target} has not configured COHN credentials. Multi-camera scenarios must use COHN mode. Please run camera management to configure COHN first."
            )

        try:
            # COHN mode: HTTPS + SSL + authentication
            logger.info(f"Starting HTTP (COHN) connection to camera {self.target}: {self._credentials.ip_address}")

            # Create SSL context (for self-signed certificate)
            self._ssl_context = ssl.create_default_context()
            self._ssl_context.check_hostname = False  # Don't check hostname (IP address)
            self._ssl_context.verify_mode = ssl.CERT_NONE  # Don't verify certificate (self-signed)

            # Still load certificate (for encryption, not verification)
            try:
                self._ssl_context.load_verify_locations(cadata=self._credentials.certificate)
            except Exception as cert_error:
                logger.warning(f"Failed to load certificate, continuing with unverified mode: {cert_error}")

            # Create HTTP session (with authentication)
            timeout = aiohttp.ClientTimeout(total=self._timeout.http_request_timeout)
            auth = aiohttp.BasicAuth(self._credentials.username, self._credentials.password)

            self._session = aiohttp.ClientSession(
                timeout=timeout,
                auth=auth,
                connector=aiohttp.TCPConnector(ssl=self._ssl_context),
            )

            # Test connection (with retry, ensure HTTPS service is ready)
            await self._wait_for_https_ready()

            self._is_connected = True
            logger.info(f"✅ HTTP (COHN) connection to camera {self.target} successful")

        except Exception as e:
            msg = f"HTTP connection to camera {self.target} failed: {e}"
            logger.error(msg)

            # Hint possible solutions
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["disconnected", "timeout", "refused", "unreachable"]):
                logger.warning(
                    f"💡 Connection failure may be due to expired IP address or camera sleep. Try deleting old credentials for camera {self.target}:"
                )
                logger.warning(f"   python scripts/manage_cohn_credentials.py delete {self.target}")
                logger.warning("   Then re-run to automatically configure new COHN credentials")

            raise HttpConnectionError(msg) from e

    async def quick_connectivity_check(self) -> bool:
        """Quickly check if IP is reachable (without waiting too long).

        Returns:
            True if connection is possible, False otherwise
        """
        if not self._credentials:
            return False

        try:
            # Use temporary session with short timeout
            async with (
                aiohttp.ClientSession() as temp_session,
                temp_session.get(
                    f"https://{self._credentials.ip_address}/gopro/version",
                    timeout=aiohttp.ClientTimeout(total=self._timeout.http_initial_check_timeout),
                    ssl=self._ssl_context if self._ssl_context else False,
                ) as resp,
            ):
                return resp.status == 200
        except Exception:
            return False

    async def _wait_for_https_ready(self, max_retries: int | None = None, retry_interval: float | None = None) -> None:
        """Wait for HTTPS service to be ready (with retry).

        After configuring COHN or switching WiFi, the camera's HTTPS service may take time to start.
        Uses active probing with exponential backoff retry strategy, more robust than fixed waiting.

        Optimization strategy (compared to the Open GoPro SDK implementation):
        - Reduced initial retry interval (faster response)
        - Increased single request timeout (more lenient)
        - Reduced maximum retry count (avoids excessive waiting)
        - Quick detection of unreachable IP for early failure

        Args:
            max_retries: Maximum retry count, defaults to configured value
            retry_interval: Base retry interval (seconds, uses exponential backoff), defaults to configured value

        Raises:
            HttpConnectionError: HTTPS service startup timeout
        """
        if max_retries is None:
            max_retries = self._timeout.http_keepalive_max_retries
        if retry_interval is None:
            retry_interval = self._timeout.http_keepalive_retry_interval

        # After first few attempts fail, check if IP is unreachable
        consecutive_timeouts = 0

        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(
                    f"Testing HTTPS connection (attempt {attempt}/{max_retries}): {self.base_url}/gopro/version"
                )
                # Give camera more time to respond
                async with self._session.get(
                    f"{self.base_url}/gopro/version",
                    timeout=aiohttp.ClientTimeout(total=self._timeout.http_keep_alive_timeout),
                ) as resp:
                    if resp.status == 200:
                        logger.debug(f"✅ HTTPS service ready (succeeded on attempt {attempt})")
                        return
                    else:
                        logger.debug(f"HTTP status code: {resp.status}, continuing retry...")
                        consecutive_timeouts = 0  # Reset counter

            except Exception as e:
                error_str = str(e).lower()
                error_type = type(e).__name__

                # Retryable error types (type-based detection is more reliable)
                retryable_types = (
                    asyncio.TimeoutError,
                    TimeoutError,
                    aiohttp.ClientConnectionError,
                    aiohttp.ClientConnectorError,
                    aiohttp.ServerDisconnectedError,
                    ConnectionRefusedError,
                    ConnectionResetError,
                )

                # Retryable error keywords (as fallback detection)
                retryable_keywords = [
                    "connection",
                    "timeout",
                    "refused",
                    "unreachable",
                    "reset",
                    "network",
                ]

                is_retryable = isinstance(e, retryable_types) or any(
                    keyword in error_str for keyword in retryable_keywords
                )

                if is_retryable:
                    if attempt < max_retries:
                        # Track consecutive timeout count
                        if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
                            consecutive_timeouts += 1
                        else:
                            consecutive_timeouts = 0

                        # If consecutive timeouts reach threshold, early determination that IP may be unreachable
                        if consecutive_timeouts >= self._timeout.http_keepalive_timeout_threshold:
                            logger.warning(
                                f"⚠️ {consecutive_timeouts} consecutive timeouts, "
                                f"IP {self._credentials.ip_address if self._credentials else '(none)'} "
                                f"may be unreachable or camera is powered off"
                            )
                            # Don't fail immediately, but give strong warning
                            if consecutive_timeouts >= self._timeout.http_keepalive_fatal_threshold:
                                raise HttpConnectionError(
                                    f"IP {self._credentials.ip_address if self._credentials else '(none)'} "
                                    f"has {consecutive_timeouts} consecutive timeouts, determined to be unreachable.\n"
                                    f"Possible causes:\n"
                                    f"  1. IP address has expired (camera obtained new IP)\n"
                                    f"  2. Camera is powered off or in sleep mode\n"
                                    f"  3. Camera disconnected from WiFi\n"
                                    f"Suggestion: Delete old credentials and reconnect"
                                ) from e

                        # Use progressive backoff strategy (quick retries first, gradually increase interval)
                        # First 3 quick retries (1.5s), then exponential backoff
                        wait_time = retry_interval if attempt <= 3 else retry_interval * (attempt - 2)

                        logger.debug(
                            f"HTTPS not ready ({error_type}: {e or '(no details)'}), retrying after {wait_time:.1f}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise HttpConnectionError(
                            f"HTTPS service startup timeout (failed after {max_retries} attempts). "
                            f"Error type: {error_type}, last error: {e or '(no details)'}. "
                            f"Possible causes: camera HTTPS service not started or IP address error."
                        ) from e

                # Non-retryable error (e.g., SSL certificate issues)
                else:
                    raise HttpConnectionError(f"HTTPS connection failed: {error_type}: {e or '(no details)'}") from e

        raise HttpConnectionError(f"HTTPS service startup timeout (attempted {max_retries} times)")

    async def disconnect(self) -> None:
        """Disconnect HTTP connection."""
        if not self._is_connected:
            logger.debug(f"HTTP for camera {self.target} not connected, skipping")
            return

        try:
            if self._session:
                await self._session.close()
                self._session = None

            self._is_connected = False
            logger.info(f"HTTP for camera {self.target} disconnected")

        except Exception as e:
            logger.warning(f"Error disconnecting HTTP for camera {self.target}: {e}")

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> _AutoConnectContext:
        """Send GET request (returns async context manager).

        Note:
        - This method is synchronous, returns an async context manager
        - Will automatically establish HTTPS connection on first call
        - Usage: async with self.get(...) as resp:

        Args:
            endpoint: API endpoint (relative path, e.g., "gopro/camera/state")
            params: Query parameters

        Returns:
            Async context manager for HTTP response (_AutoConnectContext)

        Raises:
            HttpConnectionError: Request failed

        Usage example:
            async with self.get("gopro/camera/state") as resp:
                data = await resp.json()
        """
        return _AutoConnectContext(self, endpoint, params, method="GET")

    def put(self, endpoint: str, data: Any = None) -> _AutoConnectContext:
        """Send PUT request (returns async context manager).

        Note:
        - This method is synchronous, returns an async context manager
        - Will automatically establish HTTPS connection on first call
        - Usage: async with self.put(...) as resp:

        Args:
            endpoint: API endpoint
            data: Request data

        Returns:
            Async context manager for HTTP response (_AutoConnectContext)

        Raises:
            HttpConnectionError: Request failed

        Usage example:
            async with self.put("gopro/camera/setting", data=...) as resp:
                result = await resp.json()
        """
        return _AutoConnectContext(self, endpoint, data, method="PUT")

    async def download(
        self,
        endpoint: str,
        destination: str,
        chunk_size: int = 8192,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Download file.

        Args:
            endpoint: API endpoint
            destination: Destination file path
            chunk_size: Chunk size
            progress_callback: Progress callback function (downloaded: int, total: int) -> None

        Returns:
            Number of bytes downloaded

        Raises:
            HttpConnectionError: Download failed
        """
        # Lazy connection: automatically establish connection on first request
        if not self._is_connected:
            await self.connect()

        if not self._session:
            raise HttpConnectionError("HTTP session not created")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"DOWNLOAD {url} -> {destination}")

        try:
            downloaded = 0
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    raise HttpConnectionError(f"Download failed: HTTP {resp.status}")

                # Get total file size
                total_size = int(resp.headers.get("Content-Length", 0))

                with Path(destination).open("wb") as f:
                    async for chunk in resp.content.iter_chunked(chunk_size):
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Call progress callback
                        if progress_callback:
                            progress_callback(downloaded, total_size)

            return downloaded

        except Exception as e:
            self._error_count += 1
            raise HttpConnectionError(f"Failed to download file: {e}") from e


class _AutoConnectContext:
    """Async context manager for automatic connection.

    Wraps HTTP requests to automatically establish connection when entering context (if not already connected).
    """

    def __init__(
        self,
        manager: HttpConnectionManager,
        endpoint: str,
        data: Any,
        method: str,
    ) -> None:
        """Initialize automatic connection context.

        Args:
            manager: HTTP connection manager
            endpoint: API endpoint
            data: Request data (params for GET, body for PUT)
            method: HTTP method ("GET" or "PUT")
        """
        self.manager = manager
        self.endpoint = endpoint
        self.data = data
        self.method = method
        self._context = None

    async def __aenter__(self):
        """Enter async context: automatically connect and initiate request."""
        # Lazy connection: automatically establish connection on first request
        if not self.manager._is_connected:
            await self.manager.connect()

        if not self.manager._session:
            raise HttpConnectionError("HTTP session not created")

        url = f"{self.manager.base_url}/{self.endpoint.lstrip('/')}"

        try:
            if self.method == "GET":
                logger.debug(f"GET {url} params={self.data}")
                self._context = self.manager._session.get(url, params=self.data)
            elif self.method == "PUT":
                logger.debug(f"PUT {url}")
                self._context = self.manager._session.put(url, json=self.data)
            else:
                raise ValueError(f"Unsupported HTTP method: {self.method}")

            return await self._context.__aenter__()
        except Exception as e:
            raise HttpConnectionError(f"HTTP {self.method} request failed: {e}") from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context: clean up resources."""
        if self._context:
            return await self._context.__aexit__(exc_type, exc_val, exc_tb)
        return False
