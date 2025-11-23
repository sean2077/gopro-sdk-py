"""Simplified GoPro client implementation.

Uses composition and delegation patterns to split complex functionality into independent modules:
- connection/: BLE and HTTP connection management
- commands/: BLE, HTTP, media, and webcam command implementations

The client acts as an "assembler", providing a unified and concise API.
"""

from __future__ import annotations

__all__ = ["GoProClient", "OfflineModeError"]

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import open_gopro.models.proto.cohn_pb2 as cohn_proto
import open_gopro.models.proto.response_generic_pb2 as response_proto
from open_gopro.models.constants import ActionId, FeatureId, StatusId
from open_gopro.models.constants.settings import VideoResolution

from .ble_uuid import GoProBleUUID
from .commands import (
    BleCommands,
    HttpCommands,
    MediaCommands,
    MediaFile,
    WebcamCommands,
)
from .config import CohnConfigManager, CohnCredentials, TimeoutConfig
from .connection import (
    BleConnectionManager,
    HealthCheckMixin,
    HttpConnectionManager,
)
from .exceptions import BleConnectionError, HttpConnectionError
from .state_parser import get_status_value, parse_camera_state

logger = logging.getLogger(__name__)


class OfflineModeError(Exception):
    """Offline mode error: attempted to call a function that requires online mode."""

    pass


class GoProClient(HealthCheckMixin):
    """GoPro client.

    Design principles:
    - Supports offline mode (BLE only) and online mode (BLE+WiFi)
    - Offline mode is default (suitable for no WiFi or slow WiFi scenarios)
    - Composition over inheritance (holds command interface instances)
    - Delegation pattern (provides concise API)
    - Single responsibility (separates connection management and command execution)

    Usage examples:
        Method 1 - Offline mode (default, BLE only, recommended for no WiFi or slow WiFi):
        >>> async with GoProClient("1332") as client:  # offline_mode=True (default)
        ...     await client.start_recording()  # ✅ Control via BLE
        ...     await client.set_date_time()    # ✅ Sync time via BLE
        ...     # await client.start_preview()  # ❌ Not supported in offline mode

        Method 2 - Online mode (BLE+WiFi, supports preview, download, etc.):
        >>> async with GoProClient("1332", offline_mode=False,
        ...                        wifi_ssid="MyWiFi", wifi_password="pass") as client:
        ...     await client.start_recording()   # ✅ Control via BLE
        ...     await client.start_preview()     # ✅ Preview via HTTP
        ...     await client.download_media(...) # ✅ Download via HTTP

        Method 3 - Dynamic mode switching:
        >>> async with GoProClient("1332") as client:  # Start in offline mode
        ...     await client.start_recording()  # Via BLE
        ...     # Switch to online mode when preview needed
        ...     await client.switch_to_online_mode(wifi_ssid="MyWiFi", wifi_password="pass")
        ...     await client.start_preview()    # Preview now available

        Method 4 - Camera already connected to WiFi (online mode, simplest):
        >>> async with GoProClient("1332", offline_mode=False) as client:
        ...     await client.start_preview()  # Directly use already connected WiFi
    """

    def __init__(
        self,
        target: str,
        offline_mode: bool = True,
        timeout_config: TimeoutConfig | None = None,
        config_manager: CohnConfigManager | None = None,
        wifi_ssid: str | None = None,
        wifi_password: str | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            target: Camera serial number last four digits
            offline_mode: Whether to use offline mode (default True)
                - True: BLE only, no WiFi connection, no preview/download support (suitable for no WiFi scenarios)
                - False: BLE+WiFi, supports all features (requires WiFi network)
            timeout_config: Timeout configuration
            config_manager: COHN configuration manager
            wifi_ssid: WiFi SSID (optional, for automatic connection with async with, only effective in online mode)
            wifi_password: WiFi password (optional, used together with wifi_ssid)

        Note:
            - In offline mode, wifi_ssid/wifi_password will be ignored
            - In online mode, if WiFi info is not provided, camera must already be connected to WiFi
            - Can dynamically switch to online mode via switch_to_online_mode()

        Raises:
            ValueError: Provided wifi_ssid but not wifi_password
        """
        if wifi_ssid is not None and wifi_password is None:
            raise ValueError("Provided wifi_ssid but not wifi_password")

        self.target = target
        self._offline_mode = offline_mode
        self._timeout = timeout_config or TimeoutConfig()
        self._config_manager = config_manager or CohnConfigManager()
        self._wifi_ssid = wifi_ssid
        self._wifi_password = wifi_password

        # Connection managers
        self.ble = BleConnectionManager(target, self._timeout)
        self.http = HttpConnectionManager(target, self._timeout)

        # Command interfaces (composition)
        self.ble_commands = BleCommands(self.ble)
        self.http_commands = HttpCommands(self.http)
        self.media_commands = MediaCommands(self.http)
        self.webcam_commands = WebcamCommands(self.http)

        # Health check configuration
        self._enable_auto_reconnect = True
        self._max_reconnect_attempts = self._timeout.max_reconnect_attempts
        self._last_health_check: float | None = None

        mode_str = "Offline mode (BLE only)" if offline_mode else "Online mode (BLE+WiFi)"
        logger.info(f"Initializing GoProClient, target camera: {target}, mode: {mode_str}")

    async def __aenter__(self) -> GoProClient:
        """Async context manager entry point (automatically calls open).

        If WiFi credentials were provided in the constructor, they will be automatically passed to open().
        """
        await self.open(wifi_ssid=self._wifi_ssid, wifi_password=self._wifi_password)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit point (automatically calls close)."""
        await self.close()

    # ==================== Connection Management ====================

    async def open(self, wifi_ssid: str | None = None, wifi_password: str | None = None) -> None:
        """Establish connection to the camera.

        The connection method is determined by offline_mode:
        - **Offline mode (offline_mode=True)**: BLE only, WiFi parameters ignored
        - **Online mode (offline_mode=False)**: BLE + WiFi/COHN setup + HTTP initialization

        Online mode workflow:
        1. Connect via BLE
        2. If WiFi credentials provided:
           - Query current camera WiFi status
           - If not connected or connected to different WiFi, reconfigure WiFi
           - If already connected to target WiFi, skip configuration
        3. Attempt to load saved COHN credentials
        4. If no credentials exist, configure COHN (camera auto-connects to remembered WiFi)
        5. Initialize HTTP client (lazy connection)

        WiFi parameter behavior (online mode only):
        - **No WiFi credentials**: Assumes camera is already on WiFi, directly configures COHN
          - If configuration fails, hints that WiFi credentials are needed
        - **WiFi credentials provided**: Actively connects to specified WiFi
          - Camera remembers WiFi password, next time can auto-connect with only SSID

        Important notes:
        - **Computer and camera must be on the same WiFi network**, otherwise HTTP (COHN) connection will fail
        - Parameters passed to this method override constructor parameters
        - WiFi parameters are ignored in offline mode

        Args:
            wifi_ssid: WiFi SSID (optional, only effective in online mode, overrides constructor parameter)
            wifi_password: WiFi password (optional, used with wifi_ssid)

        Raises:
            BleConnectionError: BLE connection failed or WiFi/COHN configuration failed
            HttpConnectionError: HTTP connection failed (online mode only)
            ValueError: wifi_ssid provided but wifi_password missing

        Examples:
            Offline mode:
            >>> async with GoProClient("1332") as client:  # offline_mode=True (default)
            ...     await client.start_recording()  # Works via BLE only

            Online mode:
            >>> async with GoProClient("1332", offline_mode=False,
            ...                        wifi_ssid="MyWiFi", wifi_password="pass") as client:
            ...     await client.start_preview()  # Works via HTTP
        """
        mode_str = "Offline mode (BLE only)" if self._offline_mode else "Online mode (BLE+WiFi)"
        logger.info(f"Starting connection to camera {self.target}, mode: {mode_str}")

        # Merge parameters: open() method parameters take precedence over constructor parameters
        final_wifi_ssid = wifi_ssid if wifi_ssid is not None else self._wifi_ssid
        final_wifi_password = wifi_password if wifi_password is not None else self._wifi_password

        # Parameter validation
        if final_wifi_ssid is not None and final_wifi_password is None:
            raise ValueError("wifi_ssid provided but wifi_password is missing")

        # Step 1: Connect BLE
        await self.ble.connect()

        # In offline mode, only connect BLE, skip WiFi/COHN configuration
        if self._offline_mode:
            logger.info(f"✅ Camera {self.target} connected (offline mode, BLE only)")
            logger.info("💡 Note: Offline mode does not support preview, download, etc.")
            logger.info("   To use these features, call switch_to_online_mode()")
            return

        # ========== Online mode workflow below ==========

        # Step 2: If WiFi credentials provided, connect to WiFi
        if final_wifi_ssid is not None:
            # Check if COHN credentials exist (determines connection method)
            credentials = self._config_manager.load(self.target)
            has_cohn_credentials = (
                credentials is not None and credentials.certificate and credentials.username and credentials.password
            )
            logger.debug(f"[camera {self.target}] COHN credentials check: has_credentials={has_cohn_credentials}")
            await self.setup_wifi(
                final_wifi_ssid,
                final_wifi_password,
                has_cohn_credentials=has_cohn_credentials,
            )

        # Step 3: Get or refresh COHN credentials
        # Note:
        # - RequestConnectNew automatically creates COHN certificate, no need to call configure_cohn()
        # - Root CA certificate is valid for 1 year, no need to recreate when IP changes
        # - Only need to recreate certificate after "Reset Network Settings" on camera (reset_cohn)
        credentials = self._config_manager.load(self.target)

        # Check if credentials are complete (need certificate)
        has_valid_credentials = (
            credentials is not None and credentials.certificate and credentials.username and credentials.password
        )

        if not has_valid_credentials:
            # Step 3.1: New camera or credentials incomplete → Get credentials (do not clear certificate!)
            logger.info("COHN credentials do not exist or are incomplete, fetching from camera...")

            try:
                # Get COHN status and certificate (RequestConnectNew already created it)
                credentials = await self._get_cohn_credentials_from_camera()
                self._config_manager.save(self.target, credentials)
                logger.info(f"✅ COHN credentials fetched successfully, IP: {credentials.ip_address}")

            except Exception as e:
                # Failed to get credentials
                error_msg = (
                    f"Failed to get COHN credentials: {e}\n"
                    f"Possible causes:\n"
                    f"1. Camera not connected to WiFi network\n"
                    f"2. Router DHCP has not assigned IP address\n"
                    f"\n"
                    f"Solutions:\n"
                    f"- Ensure WiFi credentials are provided when calling open()\n"
                    f"- Check router DHCP configuration (address pool, lease, etc.)\n"
                    f"- If problem persists, call client.reset_cohn() to reset certificate"
                )
                logger.error(error_msg)
                raise BleConnectionError(error_msg) from e
        else:
            # Step 3.2: Already have credentials (certificate), refresh IP address
            # WiFi network may have changed, IP will change, but certificate remains valid
            logger.info("COHN already configured, refreshing network info...")

            try:
                status = await self.ble_commands.get_cohn_status()
                state_name = cohn_proto.EnumCOHNNetworkState.Name(status.state)
                has_ip = bool(status.ipaddress) and bool(status.ipaddress.strip())

                logger.debug(
                    f"COHN status: state={state_name}, "
                    f"ip={status.ipaddress or '(empty)'}, "
                    f"username={status.username or '(empty)'}"
                )

                # If connecting and has no IP, wait for it to complete connection
                if status.state == cohn_proto.EnumCOHNNetworkState.COHN_STATE_ConnectingToNetwork and not has_ip:
                    logger.info(f"⏳ Camera connecting to WiFi (state: {state_name}), waiting to get IP...")
                    # Poll for IP address (maximum 15 seconds)
                    for attempt in range(5):
                        await asyncio.sleep(3)
                        status = await self.ble_commands.get_cohn_status()
                        has_ip = bool(status.ipaddress) and bool(status.ipaddress.strip())
                        if has_ip:
                            logger.info(f"✅ Camera got IP: {status.ipaddress}")
                            break
                        logger.debug(
                            f"Still waiting for IP (attempt {attempt + 1}/5), state: {cohn_proto.EnumCOHNNetworkState.Name(status.state)}"
                        )

                # Check if successfully got IP
                if not has_ip:
                    logger.warning(
                        f"⚠️ Camera failed to get IP address (state: {state_name}). "
                        f"Possible causes:\n"
                        f"  1. Camera not connected to WiFi\n"
                        f"  2. WiFi signal too weak\n"
                        f"  3. Router DHCP service error"
                    )
                    # Use saved old credentials (with warning)
                    logger.warning(
                        f"Will attempt to use saved IP address: {credentials.ip_address}\n"
                        f"If connection fails, consider reconfiguring COHN (delete old credentials)."
                    )
                    # Don't refresh credentials, use old ones
                else:
                    # Successfully got IP, refresh credentials
                    credentials = CohnCredentials(
                        username=status.username,
                        password=status.password,
                        ip_address=status.ipaddress,
                        certificate=credentials.certificate,  # Keep old certificate
                    )
                    self._config_manager.save(self.target, credentials)
                    logger.info(f"✅ COHN credentials refreshed, IP: {status.ipaddress}")

            except Exception as e:
                logger.warning(
                    f"⚠️ Unable to get status via BLE: {e}\n"
                    f"Will attempt HTTP connection using saved credentials (IP: {credentials.ip_address}).\n"
                    f"Note: Ensure computer and camera are on the same WiFi network, otherwise HTTP connection will fail."
                )

        # Step 4: Initialize HTTP credentials (lazy connection, auto-connect on first request)
        # Note: Don't actively connect HTTPS, because camera may still be starting HTTPS service
        # HTTP connection will be automatically established when sending the first request
        self.http.set_credentials(credentials)
        logger.info(f"✅ COHN credentials configured: https://{credentials.ip_address}")

        logger.info(f"✅ Camera {self.target} connected successfully (BLE + COHN configured)")

    async def connect(self, wifi_ssid: str | None = None, wifi_password: str | None = None) -> None:
        """Establish connection. Alias for open().

        This method is kept for compatibility. Using open() is recommended.

        Args:
            wifi_ssid: WiFi SSID (optional)
            wifi_password: WiFi password (optional)

        Raises:
            BleConnectionError: BLE connection failed
            HttpConnectionError: HTTP connection failed
        """
        await self.open(wifi_ssid, wifi_password)

    async def close(self) -> None:
        """Close all connections."""
        await self.http.disconnect()
        await self.ble.disconnect()
        logger.info(f"All connections to camera {self.target} closed")

    # ==================== Mode Management ====================

    @property
    def offline_mode(self) -> bool:
        """Get current mode.

        Returns:
            True for offline mode, False for online mode
        """
        return self._offline_mode

    @property
    def is_online(self) -> bool:
        """Check if in online mode.

        Returns:
            True for online mode, False for offline mode
        """
        return not self._offline_mode

    def _require_online_mode(self, feature_name: str = "This feature") -> None:
        """Check if in online mode, raise exception in offline mode.

        Args:
            feature_name: Feature name (for error message)

        Raises:
            OfflineModeError: Currently in offline mode
        """
        if self._offline_mode:
            raise OfflineModeError(
                f"❌ {feature_name} requires online mode (BLE+WiFi) to use\n"
                f"Solutions:\n"
                f"  1. Set offline_mode=False when creating client\n"
                f"     >>> client = GoProClient('{self.target}', offline_mode=False)\n"
                f"  2. Or switch to online mode at runtime\n"
                f"     >>> await client.switch_to_online_mode(wifi_ssid='...', wifi_password='...')\n"
                f"\n"
                f"Offline mode only supports basic features via BLE:\n"
                f"  ✅ start_recording() / stop_recording()\n"
                f"  ✅ set_date_time()\n"
                f"  ✅ tag_hilight()\n"
                f"  ❌ Preview (start_preview)\n"
                f"  ❌ Download media (download_media)\n"
                f"  ❌ Manage files (list_media, delete_media)"
            )

    async def switch_to_online_mode(self, wifi_ssid: str | None = None, wifi_password: str | None = None) -> None:
        """Switch to online mode (dynamic switching).

        If the client was initialized with offline mode, this method can switch to online mode
        to use features that require WiFi, such as preview and download.

        Args:
            wifi_ssid: WiFi SSID (optional, not needed if camera is already on WiFi)
            wifi_password: WiFi password (optional, used with wifi_ssid)

        Raises:
            BleConnectionError: WiFi/COHN configuration failed
            ValueError: wifi_ssid provided but wifi_password missing

        Examples:
            >>> async with GoProClient("1332") as client:  # Default offline mode
            ...     await client.start_recording()  # Works via BLE
            ...     # Switch to online mode when preview is needed
            ...     await client.switch_to_online_mode(wifi_ssid="MyWiFi", wifi_password="pass")
            ...     await client.start_preview()  # Now preview works
        """
        if not self._offline_mode:
            logger.info("✅ Already in online mode, no need to switch")
            return

        logger.info("🔄 Switching to online mode...")

        # Parameter validation
        if wifi_ssid is not None and wifi_password is None:
            raise ValueError("wifi_ssid provided but wifi_password is missing")

        # Merge parameters
        final_wifi_ssid = wifi_ssid if wifi_ssid is not None else self._wifi_ssid
        final_wifi_password = wifi_password if wifi_password is not None else self._wifi_password

        # Ensure BLE is connected
        if not self.ble.is_connected:
            raise BleConnectionError("BLE not connected, cannot switch to online mode")

        # Execute online mode configuration workflow (same as steps 2-4 in open() method)
        # Step 1: If WiFi credentials provided, connect to WiFi
        if final_wifi_ssid is not None:
            credentials = self._config_manager.load(self.target)
            has_cohn_credentials = (
                credentials is not None and credentials.certificate and credentials.username and credentials.password
            )
            await self.setup_wifi(
                final_wifi_ssid,
                final_wifi_password,
                has_cohn_credentials=has_cohn_credentials,
            )

        # Step 2: Get or refresh COHN credentials
        credentials = self._config_manager.load(self.target)
        has_valid_credentials = (
            credentials is not None and credentials.certificate and credentials.username and credentials.password
        )

        if not has_valid_credentials:
            logger.info("COHN credentials do not exist or are incomplete, fetching from camera...")
            try:
                credentials = await self._get_cohn_credentials_from_camera()
                self._config_manager.save(self.target, credentials)
                logger.info(f"✅ COHN credentials fetched successfully, IP: {credentials.ip_address}")
            except Exception as e:
                error_msg = (
                    f"Failed to get COHN credentials: {e}\n"
                    f"Please ensure:\n"
                    f"1. Camera is connected to WiFi\n"
                    f"2. WiFi credentials were provided when calling switch_to_online_mode()"
                )
                logger.error(error_msg)
                raise BleConnectionError(error_msg) from e
        else:
            logger.info("COHN already configured, refreshing network info...")
            try:
                status = await self.ble_commands.get_cohn_status()
                has_ip = bool(status.ipaddress) and bool(status.ipaddress.strip())

                if has_ip:
                    credentials = CohnCredentials(
                        username=status.username,
                        password=status.password,
                        ip_address=status.ipaddress,
                        certificate=credentials.certificate,
                    )
                    self._config_manager.save(self.target, credentials)
                    logger.info(f"✅ COHN credentials refreshed, IP: {status.ipaddress}")
                else:
                    logger.warning(f"⚠️ Camera didn't get IP, using saved IP: {credentials.ip_address}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to get status: {e}, using saved credentials")

        # Step 3: Initialize HTTP credentials
        self.http.set_credentials(credentials)
        logger.info(f"✅ COHN credentials configured: https://{credentials.ip_address}")

        # Switch mode flag
        self._offline_mode = False
        logger.info("✅ Switched to online mode (BLE+WiFi)")

    # ==================== Recording Control (BLE/HTTP based on mode) ====================

    async def set_shutter(self, enable: bool) -> None:
        """Control recording shutter.

        Uses BLE in offline mode, HTTP in online mode.

        Args:
            enable: True to start recording, False to stop recording
        """
        if self.offline_mode:
            # Offline mode: control via BLE
            await self.ble_commands.set_shutter(enable)
        else:
            # Online mode: control via HTTP
            await self.http_commands.set_shutter(enable)

    async def start_recording(self) -> None:
        """Start recording. Convenience wrapper for set_shutter(True)."""
        await self.set_shutter(True)

    async def stop_recording(self) -> None:
        """Stop recording. Convenience wrapper for set_shutter(False)."""
        await self.set_shutter(False)

    async def set_preview_stream(self, enable: bool, port: int | None = None) -> None:
        """Control preview stream.

        Args:
            enable: True to enable, False to disable
            port: Preview stream port (only needed when enabling)

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Preview stream control")
        await self.http_commands.set_preview_stream(enable, port)

    async def start_preview(self, port: int = 8554) -> str:
        """Start preview stream.

        Args:
            port: Preview stream port, default 8554

        Returns:
            Preview stream URL (udp://ip:port)

        Raises:
            GoproError: Preview stream unavailable or failed to start

        Note:
            Optimization logic:
            1. Check preview stream status first, return directly if already running (avoid unnecessary restart)
            2. If not running or camera busy, execute full start procedure

            Causes of HTTP 409 error:
            - Camera will reject starting preview stream when in BUSY (Status ID 8) state
            - Camera will reject starting preview stream when in ENCODING (Status ID 10) state
            - Camera will reject restarting preview stream when PREVIEW_STREAM (Status ID 32) = True
        """
        # Step 1: Check current preview stream status
        try:
            raw_state = await self.get_camera_state()
            parsed_state = parse_camera_state(raw_state)

            is_busy = get_status_value(parsed_state, StatusId.BUSY)
            is_encoding = get_status_value(parsed_state, StatusId.ENCODING)
            is_preview_active = get_status_value(parsed_state, StatusId.PREVIEW_STREAM)

            # If preview stream is already running and camera state is normal, return URL directly
            if is_preview_active and not is_busy and not is_encoding:
                logger.info(f"📹 [{self.target}] Preview stream already running, no need to restart")
                return f"udp://127.0.0.1:{port}"

            # If preview stream started but camera busy, need to restart
            if is_preview_active and (is_busy or is_encoding):
                logger.debug(
                    f"[{self.target}] Preview stream started but camera busy (BUSY={is_busy}, ENCODING={is_encoding}), need to restart"
                )
        except Exception as e:
            logger.debug(
                f"[{self.target}] Failed to query preview stream status: {e}, will execute full start procedure"
            )

        # Step 2: Stop preview stream (if needed)
        # Only need to stop when preview stream is running
        try:
            await self.set_preview_stream(False)
            # Give camera some time to update PREVIEW_STREAM status
            await asyncio.sleep(0.3)
        except Exception:
            pass  # Ignore stop failure errors (possibly already stopped)

        # Step 3: Stop recording (if recording)
        # This step is critical! GoPro camera cannot start preview stream while recording
        try:
            await self.set_shutter(False)
            logger.debug(f"[{self.target}] Ensured camera stopped recording")
        except Exception as e:
            logger.debug(f"[{self.target}] Failed to stop recording (possibly not recording): {e}")

        # Step 4: Wait for camera ready (not in BUSY, ENCODING state, and preview stream stopped)
        # This is the key to fixing HTTP 409 error!
        # GoPro camera will reject starting preview stream in following states (returns 409):
        #   - BUSY = True (Status ID 8)
        #   - ENCODING = True (Status ID 10)
        #   - PREVIEW_STREAM = True (Status ID 32) <-- Previously missed this check!
        await self._wait_for_camera_ready(timeout=self._timeout.camera_ready_timeout)

        # Step 5: Now start preview stream
        await self.set_preview_stream(True, port)

        # Build and return preview stream URL
        # GoPro pushes stream via UDP to local port, receive from localhost
        stream_url = f"udp://127.0.0.1:{port}"

        return stream_url

    async def _wait_for_camera_ready(self, timeout: float | None = None, poll_interval: float | None = None) -> None:
        """Wait for camera to be ready (not in BUSY, ENCODING state, and preview stream stopped).

        Args:
            timeout: Timeout duration (seconds), defaults to configured value
            poll_interval: Polling interval (seconds), defaults to configured value

        Raises:
            HttpConnectionError: Timeout or query failed
        """
        if timeout is None:
            timeout = self._timeout.camera_ready_timeout
        if poll_interval is None:
            poll_interval = self._timeout.camera_ready_poll_interval
        logger.debug(f"[{self.target}] waitcameraready...")
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise HttpConnectionError(
                    f"Wait for camera ready timeout ({timeout} seconds): camera still in BUSY, ENCODING or PREVIEW_STREAM state"
                )

            try:
                # Query camera status
                raw_state = await self.get_camera_state()
                parsed_state = parse_camera_state(raw_state)

                # Check critical status
                # - BUSY (Status ID 8): camera busy
                # - ENCODING (Status ID 10): recording
                # - PREVIEW_STREAM (Status ID 32): whether preview stream is enabled
                is_busy = get_status_value(parsed_state, StatusId.BUSY)
                is_encoding = get_status_value(parsed_state, StatusId.ENCODING)
                is_preview_active = get_status_value(parsed_state, StatusId.PREVIEW_STREAM)

                logger.debug(
                    f"[{self.target}] Camera status: BUSY={is_busy}, ENCODING={is_encoding}, PREVIEW_STREAM={is_preview_active}"
                )

                # If not busy and preview stream stopped, camera is ready
                # Note: Preview stream must be completely stopped (False) to restart, otherwise returns HTTP 409
                if not is_busy and not is_encoding and not is_preview_active:
                    logger.info(f"✅ [{self.target}] Camera ready (took {elapsed:.1f}s)")
                    return

                # Otherwise continue waiting
                logger.debug(f"[{self.target}] Camera still busy, continue waiting... ({elapsed:.1f}s / {timeout}s)")
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.warning(f"⚠️ [{self.target}] Failed to query camera status: {e}, continue retry...")
                await asyncio.sleep(poll_interval)

    async def stop_preview(self) -> None:
        """Stop preview stream. Convenience wrapper for set_preview_stream(False)."""
        await self.set_preview_stream(False)

    async def tag_hilight(self) -> None:
        """Tag highlight (during recording)."""
        await self.http_commands.tag_hilight()

    # ==================== Camera Status (delegated to http_commands) ====================

    async def get_camera_state(self) -> dict[str, Any]:
        """Get complete camera status (raw format).

        Returns:
            Raw status dictionary in format:
                {
                    "status": {"10": 0, "32": 1, ...},
                    "settings": {"2": 1, "3": 8, ...}
                }

        Note:
            Returns raw format (integer IDs). To parse as enum types,
            use the `get_parsed_state()` method.

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Get camera status")
        return await self.http_commands.get_camera_state()

    async def get_status(self) -> dict[str, Any]:
        """Get complete camera status. Alias for get_camera_state().

        Returns:
            Raw status dictionary
        """
        return await self.get_camera_state()

    async def get_parsed_state(self):
        """Get parsed camera status (enum format).

        Returns:
            Parsed status dictionary using StatusId/SettingId enums as keys,
            in format:
                {
                    StatusId.ENCODING: False,
                    StatusId.PREVIEW_STREAM: True,
                    SettingId.VIDEO_RESOLUTION: VideoResolution.NUM_4K,
                    ...
                }

        Examples:
            >>> state = await client.get_parsed_state()
            >>> if state[StatusId.ENCODING]:
            ...     print("🔴 Camera is recording")
        """

        raw_state = await self.get_camera_state()
        return parse_camera_state(raw_state)

    async def get_camera_info(self) -> dict[str, Any]:
        """Get camera information.

        Returns:
            Camera information dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Get camera info")
        return await self.http_commands.get_camera_info()

    async def set_keep_alive(self) -> None:
        """Send keep-alive signal.

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Keep-alive signal")
        await self.http_commands.set_keep_alive()

    # ==================== Date Time (delegated to http_commands) ====================

    async def set_date_time(self, dt: datetime | None = None, tz_offset: int = 0, is_dst: bool = False) -> None:
        """Set camera date and time.

        Args:
            dt: Datetime object, defaults to current time
            tz_offset: Timezone offset (hours)
            is_dst: Whether daylight saving time

        Note:
            Uses BLE command in offline mode, HTTP command in online mode
        """
        if self._offline_mode:
            # Offline mode: use BLE command
            await self.ble_commands.set_date_time(dt, tz_offset, is_dst)
        else:
            # Online mode: use HTTP command
            await self.http_commands.set_date_time(dt, tz_offset, is_dst)

    async def get_date_time(self) -> datetime:
        """Get camera date and time.

        Returns:
            Datetime object

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Get camera time")
        return await self.http_commands.get_date_time()

    # ==================== Settings Management (delegated to http_commands) ====================

    async def get_setting(self, setting_id: int) -> Any:
        """Get the value of specified setting.

        Args:
            setting_id: Setting ID

        Returns:
            Setting value

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Get setting")
        return await self.http_commands.get_setting(setting_id)

    async def set_setting(self, setting_id: int, value: int) -> None:
        """Modify the value of specified setting.

        Args:
            setting_id: Setting ID
            value: Setting value

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Set parameter")
        await self.http_commands.set_setting(setting_id, value)

    # ==================== Preset Management (delegated to http_commands) ====================

    async def get_preset_status(self, include_hidden: bool = False) -> dict[str, Any]:
        """Get preset status.

        Args:
            include_hidden: Whether to include hidden presets

        Returns:
            Preset status dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Get preset status")
        return await self.http_commands.get_preset_status(include_hidden)

    async def load_preset(self, preset_id: int) -> None:
        """Load specified preset.

        Args:
            preset_id: Preset ID

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Load preset")
        await self.http_commands.load_preset(preset_id)

    async def load_preset_group(self, group_id: int) -> None:
        """Load preset group.

        Args:
            group_id: Preset group ID

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Load preset group")
        await self.http_commands.load_preset_group(group_id)

    # ==================== Other Controls (delegated to http_commands) ====================

    async def set_digital_zoom(self, percent: int) -> None:
        """Set digital zoom.

        Args:
            percent: Zoom percentage (0-100)

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Digital zoom")
        await self.http_commands.set_digital_zoom(percent)

    async def reboot(self) -> None:
        """Reboot camera.

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Reboot camera")
        await self.http_commands.reboot()

    # ==================== Media Management (delegated to media_commands) ====================

    async def get_media_list(self):
        """List all media files.

        Returns:
            List of media files (MediaFile objects)

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Media file list")
        return await self.media_commands.get_media_list()

    async def list_media(self) -> list[MediaFile]:
        """List all media files. Alias for get_media_list().

        Returns:
            List of media files (MediaFile objects)
        """
        return await self.get_media_list()

    async def download_file(
        self,
        media_file: MediaFile | str,
        save_path: str | Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Download media file.

        Args:
            media_file: MediaFile object or file path
            save_path: Save path
            progress_callback: Progress callback function (downloaded: int, total: int) -> None

        Returns:
            Number of bytes downloaded

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Media download")
        return await self.media_commands.download_file(media_file, save_path, progress_callback)

    async def download_media(self, media_file: MediaFile | str, save_path: str | Path) -> int:
        """Download media file. Alias for download_file().

        Args:
            media_file: MediaFile object or file path
            save_path: Save path

        Returns:
            Number of bytes downloaded
        """
        return await self.download_file(media_file, save_path)

    async def delete_file(self, path: str) -> None:
        """Delete single media file.

        Args:
            path: File path

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Delete media file")
        await self.media_commands.delete_file(path)

    async def delete_media(self, path: str) -> None:
        """Delete single media file. Alias for delete_file().

        Args:
            path: File path
        """
        await self.delete_file(path)

    async def delete_all_media(self) -> None:
        """Delete all media files.

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Delete all media")
        await self.media_commands.delete_all_media()

    async def get_media_metadata(self, path: str) -> dict[str, Any]:
        """Get media file metadata.

        Args:
            path: File path

        Returns:
            Metadata dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Get media metadata")
        return await self.media_commands.get_media_metadata(path)

    async def get_last_captured_media(self) -> dict[str, Any]:
        """Get last captured media file information.

        Returns:
            Media information dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Get last captured media")
        return await self.media_commands.get_last_captured_media()

    async def set_turbo_mode(self, enable: bool) -> None:
        """Enable/disable Turbo transfer mode.

        Args:
            enable: True to enable, False to disable

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Turbo transfer mode")
        await self.media_commands.set_turbo_mode(enable)

    # ==================== Webcam Mode (delegated to webcam_commands) ====================

    async def webcam_start(
        self,
        resolution: int | None = None,
        fov: int | None = None,
        port: int | None = None,
        protocol: str | None = None,
    ) -> dict[str, Any]:
        """Start Webcam mode.

        Args:
            resolution: Resolution
            fov: Field of view
            port: Port
            protocol: Protocol

        Returns:
            Webcam response

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Webcam mode")
        return await self.webcam_commands.webcam_start(resolution, fov, port, protocol)

    async def start_webcam(
        self,
        resolution: int = VideoResolution.NUM_720,
        fov: int = 0,
    ) -> dict[str, Any]:
        """Start Webcam mode with common parameters.

        Args:
            resolution: Resolution, default 12 (720p)
            fov: Field of view, default 0 (Wide)

        Returns:
            Webcam response

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Webcam mode")
        return await self.webcam_start(resolution, fov)

    async def webcam_stop(self) -> dict[str, Any]:
        """Stop Webcam mode.

        Returns:
            Webcam response

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Webcam mode")
        return await self.webcam_commands.webcam_stop()

    async def stop_webcam(self) -> dict[str, Any]:
        """Stop Webcam mode. Alias for webcam_stop().

        Returns:
            Webcam response
        """
        return await self.webcam_stop()

    async def webcam_status(self) -> dict[str, Any]:
        """Get Webcam status.

        Returns:
            Webcam status dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Webcam status")
        return await self.webcam_commands.webcam_status()

    async def webcam_preview(self) -> dict[str, Any]:
        """Start Webcam preview.

        Returns:
            Webcam response

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Webcam preview")
        return await self.webcam_commands.webcam_preview()

    async def webcam_exit(self) -> dict[str, Any]:
        """Exit Webcam mode.

        Returns:
            Webcam response

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Webcam mode")
        return await self.webcam_commands.webcam_exit()

    async def get_webcam_version(self) -> str:
        """Get Webcam implementation version.

        Returns:
            Version string

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        self._require_online_mode("Webcam version")
        return await self.webcam_commands.get_webcam_version()

    # ==================== COHN Configuration (delegated to ble_commands) ====================

    async def _get_cohn_credentials_from_camera(self) -> CohnCredentials:
        """Get COHN credentials from camera and create certificate.

        Note: RequestConnectNew does not automatically create COHN certificate!
        Need to manually call REQUEST_CREATE_COHN_CERT to create certificate.

        Workflow:
        1. Check if certificate exists (query COHN status)
        2. If no certificate → create new certificate
        3. Wait for PROVISIONED
        4. Get credentials

        Returns:
            COHN credentials

        Raises:
            BleConnectionError: Failed to get credentials
            TimeoutError: Wait for IP timeout
        """
        logger.info("Getting COHN credentials from camera...")

        # Step 1: Check current COHN status
        status = await self.ble_commands.get_cohn_status()
        is_provisioned = status.status == cohn_proto.EnumCOHNStatus.COHN_PROVISIONED

        # Step 2: If not configured, create certificate
        if not is_provisioned:
            logger.info("Camera has not configured COHN certificate, starting creation...")

            # Create new certificate (don't clear old certificate, as it may not exist)
            create_request = cohn_proto.RequestCreateCOHNCert()
            create_request.override = True  # Overwrite if old certificate exists
            await self.ble_commands._send_protobuf_command(
                feature_id=FeatureId.COMMAND,
                action_id=ActionId.REQUEST_CREATE_COHN_CERT,
                request_proto=create_request,
                response_proto_class=response_proto.ResponseGeneric,
                uuid=GoProBleUUID.CQ_COMMAND,
            )

            logger.info("⏳ Waiting for COHN certificate generation...")

        # Step 3: Wait for COHN configuration complete
        await self.ble_commands._wait_for_cohn_provisioned(timeout=self._timeout.cohn_wait_provisioned_timeout)

        # Step 4: Get certificate (Note: this is a QUERY operation, not COMMAND)
        cert_request = cohn_proto.RequestCOHNCert()
        cert_response = await self.ble_commands._send_protobuf_command(
            feature_id=FeatureId.QUERY,  # Fix: getting certificate is QUERY operation
            action_id=ActionId.REQUEST_GET_COHN_CERT,
            request_proto=cert_request,
            response_proto_class=cohn_proto.ResponseCOHNCert,
            uuid=GoProBleUUID.CQ_QUERY,  # Fix: QUERY operation uses CQ_QUERY
        )

        # Get status
        status_request = cohn_proto.RequestGetCOHNStatus()
        status_request.register_cohn_status = False
        status_response = await self.ble_commands._send_protobuf_command(
            feature_id=FeatureId.QUERY,
            action_id=ActionId.REQUEST_GET_COHN_STATUS,
            request_proto=status_request,
            response_proto_class=cohn_proto.NotifyCOHNStatus,
            uuid=GoProBleUUID.CQ_QUERY,
        )

        # Assemble credentials
        credentials = CohnCredentials(
            ip_address=status_response.ipaddress,
            username=status_response.username,
            password=status_response.password,
            certificate=cert_response.cert,
        )

        # Validate credentials completeness
        if not all(
            [
                credentials.ip_address,
                credentials.username,
                credentials.password,
                credentials.certificate,
            ]
        ):
            raise BleConnectionError(
                f"Credentials incomplete: "
                f"ip={bool(credentials.ip_address)}, "
                f"username={bool(credentials.username)}, "
                f"password={bool(credentials.password)}, "
                f"cert={bool(credentials.certificate)}"
            )

        logger.info(
            f"✅ Credentials fetched successfully: IP={credentials.ip_address}, username={credentials.username}"
        )
        return credentials

    async def reset_cohn(self) -> CohnCredentials:
        """Reset COHN configuration (clear certificate and recreate).

        ⚠️ Only use in these special cases:
        1. **Camera executed "Reset Network Settings"** (certificate cleared)
        2. **Certificate expired** (Root CA certificate valid for 1 year)
        3. **Certificate corrupted** (validation failed)
        4. **Failed to get credentials and cannot be fixed via open()**

        ✅ No need to call this method in normal cases:
        - Changed WiFi network → certificate still valid, only need to refresh IP
        - Router reset → certificate still valid, IP change handled automatically
        - Camera reboot → certificate still valid, COHN configuration applied automatically

        Important:
            This method only resets the COHN certificate. It does NOT clear the camera's
            network cache. If experiencing COHN timeout due to cached network connections,
            you must manually reset via camera menu:
            Preferences → Connections → Reset Connections

        Note: This operation clears existing certificate, camera must be connected to WiFi to complete configuration.

        Returns:
            New COHN credentials

        Raises:
            BleConnectionError: Configuration failed (camera not connected to WiFi, etc.)
        """
        logger.warning("🔄 Resetting COHN configuration (clearing and recreating certificate)...")
        credentials = await self.ble_commands.configure_cohn()
        self._config_manager.save(self.target, credentials)
        logger.info(f"✅ COHN reset successful, IP: {credentials.ip_address}")
        return credentials

    async def configure_cohn(self) -> CohnCredentials:
        """Configure COHN (first-time configuration).

        Returns:
            Successfully configured COHN credentials
        """
        credentials = await self.ble_commands.configure_cohn()
        self._config_manager.save(self.target, credentials)
        return credentials

    # ==================== WiFi Configuration (delegated to ble_commands) ====================

    async def setup_wifi(
        self,
        ssid: str,
        password: str,
        timeout: float | None = None,
        has_cohn_credentials: bool = False,
    ) -> None:
        """Configure camera to connect to specified WiFi network.

        Strategy (based on COHN credentials):
        1. **Has COHN credentials**: Indicates camera connected before
           → Try RequestConnect first (no password)
           → Fallback to RequestConnectNew if failed (with password)

        2. **No COHN credentials**: First-time configuration
           → Directly use RequestConnectNew (with password)

        Args:
            ssid: WiFi SSID
            password: WiFi password
            timeout: Connection timeout (seconds), defaults to configured value
            has_cohn_credentials: Whether has COHN credentials (passed by caller)

        Raises:
            BleConnectionError: Connection failed

        Examples:
            >>> async with GoProClient("1332") as client:
            ...     await client.setup_wifi("MyHomeWiFi", "password123")
        """
        try:
            await self.ble_commands.connect_to_wifi(ssid, password, timeout, has_cohn_credentials=has_cohn_credentials)
        except TimeoutError as e:
            # Provide more detailed error information
            error_msg = (
                f"WiFi connection timeout ({timeout} seconds). Possible causes:\n"
                f"1. ❌ WiFi name incorrect: '{ssid}' (check spelling)\n"
                f"2. ❌ WiFi password incorrect\n"
                f"3. ❌ Router signal too weak\n"
                f"4. ❌ Camera too far from router\n"
                f"5. ℹ️ Camera may have connected but BLE disconnected (COHN mode)\n"
                f"\n"
                f"Suggestions:\n"
                f"- Check WiFi configuration is correct\n"
                f"- Ensure camera is within router signal range\n"
                f"- If repeatedly fails, try manually resetting network settings on camera"
            )
            logger.error(error_msg)
            raise BleConnectionError(error_msg) from e

    async def scan_wifi_networks(self, timeout: float | None = None):
        """Scan WiFi networks.

        Note: Camera must be in AP mode (not connected to any network) to scan.

        Args:
            timeout: Scan timeout (seconds), defaults to configured value

        Returns:
            List of WiFi networks

        Raises:
            BleConnectionError: Scan failed (possibly camera already connected to network)
        """
        return await self.ble_commands.scan_wifi_networks(timeout)

    async def connect_to_wifi(self, ssid: str, password: str | None = None, timeout: float | None = None) -> None:
        """Connect to WiFi network.

        Args:
            ssid: WiFi SSID
            password: WiFi password (can be None if already configured)
            timeout: Connection timeout (seconds), defaults to configured value
        """
        await self.ble_commands.connect_to_wifi(ssid, password, timeout)
