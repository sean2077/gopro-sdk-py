"""Webcam mode command implementation.

Implements Webcam mode related commands:
- Start Webcam
- Stop Webcam
- Query Webcam status
- Webcam preview
"""

from __future__ import annotations

__all__ = ["WebcamCommands"]

import logging
from typing import Any

from ..connection.http_manager import HttpConnectionManager
from ..exceptions import HttpConnectionError
from .base import with_http_retry

logger = logging.getLogger(__name__)


class WebcamCommands:
    """Webcam mode command interface."""

    def __init__(self, http_manager: HttpConnectionManager) -> None:
        """Initialize Webcam command interface.

        Args:
            http_manager: HTTP connection manager
        """
        self.http = http_manager
        self._http_error_count = 0  # HTTP error counter (for retry decorator)

    @with_http_retry(max_retries=3)
    async def webcam_start(
        self,
        resolution: int | None = None,
        fov: int | None = None,
        port: int | None = None,
        protocol: str | None = None,
    ) -> dict[str, Any]:
        """Start Webcam mode.

        Args:
            resolution: Resolution (4=480p, 7=720p, 12=1080p)
            fov: Field of view (0=Wide, 2=Linear, 3=Narrow)
            port: Port (default 8554)
            protocol: Protocol (default "TS")

        Returns:
            Webcam response

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"📹 Starting Webcam mode (camera {self.http.target})...")

        endpoint = "gopro/webcam/start"
        params = {}
        if resolution is not None:
            params["res"] = str(resolution)
        if fov is not None:
            params["fov"] = str(fov)
        if port is not None:
            params["port"] = str(port)
        if protocol is not None:
            params["protocol"] = protocol

        async with self.http.get(endpoint, params=params or None) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to start Webcam (HTTP {resp.status}): {text}")

            result = await resp.json()
            logger.info("✅ Webcam mode started")
            return result

    @with_http_retry(max_retries=3)
    async def webcam_stop(self) -> dict[str, Any]:
        """Stop Webcam mode.

        Returns:
            Webcam response

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"⏹️ Stopping Webcam mode (camera {self.http.target})...")

        endpoint = "gopro/webcam/stop"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to stop Webcam (HTTP {resp.status}): {text}")

            result = await resp.json()
            logger.info("✅ Webcam mode stopped")
            return result

    @with_http_retry(max_retries=2)
    async def webcam_status(self) -> dict[str, Any]:
        """Get Webcam status.

        Returns:
            Webcam status dictionary

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"📊 Getting Webcam status (camera {self.http.target})...")

        endpoint = "gopro/webcam/status"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get Webcam status (HTTP {resp.status}): {text}")

            return await resp.json()

    @with_http_retry(max_retries=3)
    async def webcam_preview(self) -> dict[str, Any]:
        """Start Webcam preview.

        Returns:
            Webcam response

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"🎥 Starting Webcam preview (camera {self.http.target})...")

        endpoint = "gopro/webcam/preview"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to start preview (HTTP {resp.status}): {text}")

            result = await resp.json()
            logger.info("✅ Webcam preview started")
            return result

    @with_http_retry(max_retries=3)
    async def webcam_exit(self) -> dict[str, Any]:
        """Exit Webcam mode.

        Returns:
            Webcam response

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"🚪 Exiting Webcam mode (camera {self.http.target})...")

        endpoint = "gopro/webcam/exit"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to exit Webcam (HTTP {resp.status}): {text}")

            result = await resp.json()
            logger.info("✅ Exited Webcam mode")
            return result

    @with_http_retry(max_retries=2)
    async def get_webcam_version(self) -> str:
        """Get Webcam implementation version.

        Returns:
            Version string

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"Getting Webcam version (camera {self.http.target})...")

        endpoint = "gopro/webcam/version"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get version (HTTP {resp.status}): {text}")

            data = await resp.json()
            return data.get("version", "unknown")
