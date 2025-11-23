"""HTTP command implementation.

Implements commands executed via HTTP/COHN, including:
- Recording control (shutter, preview)
- Camera settings (settings, presets, datetime)
- Camera status queries
- Basic control commands
"""

from __future__ import annotations

__all__ = ["HttpCommands"]

import logging
from datetime import datetime
from typing import Any

from ..connection.http_manager import HttpConnectionManager
from ..exceptions import HttpConnectionError
from .base import with_http_retry

logger = logging.getLogger(__name__)


class HttpCommands:
    """HTTP command interface.

    Implements commands executed via HTTP (recording, settings, status, etc.).
    """

    def __init__(self, http_manager: HttpConnectionManager) -> None:
        """Initialize HTTP command interface.

        Args:
            http_manager: HTTP connection manager
        """
        self.http = http_manager
        self._http_error_count = 0  # HTTP error count (used by retry decorator)

    # ==================== Recording Control ====================

    @with_http_retry(max_retries=3)
    async def set_shutter(self, enable: bool) -> None:
        """Control recording shutter (start/stop recording).

        Args:
            enable: True to start recording, False to stop recording

        Raises:
            HttpConnectionError: Command failed
        """
        mode = "start" if enable else "stop"
        logger.info(f"{'Starting' if enable else 'Stopping'} recording on camera {self.http.target}...")

        endpoint = f"gopro/camera/shutter/{mode}"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to control shutter (HTTP {resp.status}): {text}")

        logger.info(f"✅ Camera {self.http.target} recording {'started' if enable else 'stopped'}")

    @with_http_retry(max_retries=3)
    async def set_preview_stream(self, enable: bool, port: int | None = None) -> None:
        """Control preview stream (start/stop).

        Args:
            enable: True to start, False to stop
            port: Preview stream port (only required when starting), default 8554

        Raises:
            HttpConnectionError: Command failed
        """
        mode = "start" if enable else "stop"
        logger.info(f"{'Starting' if enable else 'Stopping'} preview stream on camera {self.http.target}...")

        endpoint = f"gopro/camera/stream/{mode}"
        params = {"port": str(port)} if (enable and port) else None

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to control preview stream (HTTP {resp.status}): {text}")

        logger.info(f"✅ Camera {self.http.target} preview stream {'started' if enable else 'stopped'}")

    @with_http_retry(max_retries=2)
    async def tag_hilight(self) -> None:
        """Tag highlight (during recording).

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"Tagging highlight (camera {self.http.target})...")

        endpoint = "gopro/media/hilight/moment"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to tag highlight (HTTP {resp.status}): {text}")

        logger.info(f"✅ Camera {self.http.target} highlight tagged")

    # ==================== Camera Status ====================

    @with_http_retry(max_retries=2)
    async def get_camera_state(self) -> dict[str, Any]:
        """Get complete camera state (including all settings and status).

        Returns:
            Status dictionary

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug("Getting camera state...")

        endpoint = "gopro/camera/state"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get state (HTTP {resp.status}): {text}")

            state = await resp.json()
            logger.debug("Camera state retrieved successfully")
            return state

    @with_http_retry(max_retries=2)
    async def get_camera_info(self) -> dict[str, Any]:
        """Get camera information (firmware version, etc.).

        Returns:
            Camera information dictionary

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"Getting camera {self.http.target} information...")

        endpoint = "gopro/camera/info"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get information (HTTP {resp.status}): {text}")

            info = await resp.json()
            return info

    @with_http_retry(max_retries=2)
    async def set_keep_alive(self) -> None:
        """Send keep-alive signal to maintain connection.

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"Sending keep-alive signal (camera {self.http.target})...")

        endpoint = "gopro/camera/keep_alive"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Keep-alive failed (HTTP {resp.status}): {text}")

    # ==================== Date and Time ====================

    @with_http_retry(max_retries=2)
    async def set_date_time(self, dt: datetime | None = None, tz_offset: int = 0, is_dst: bool = False) -> None:
        """Set camera date and time.

        Args:
            dt: Datetime object, default uses current time
            tz_offset: Timezone offset (hours), default 0
            is_dst: Whether daylight saving time is active, default False

        Raises:
            HttpConnectionError: Command failed
        """
        if dt is None:
            dt = datetime.now()

        logger.info(f"Setting camera {self.http.target} time: {dt}...")

        endpoint = "gopro/camera/set_date_time"
        params = {
            "date": f"{dt.year}_{dt.month}_{dt.day}",
            "time": f"{dt.hour}_{dt.minute}_{dt.second}",
            "tzone": str(tz_offset),
            "dst": "1" if is_dst else "0",
        }

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to set time (HTTP {resp.status}): {text}")

        logger.info(f"✅ Camera {self.http.target} time set")

    @with_http_retry(max_retries=2)
    async def get_date_time(self) -> datetime:
        """Get camera date and time.

        Returns:
            Datetime object

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"Getting camera {self.http.target} time...")

        endpoint = "gopro/camera/get_date_time"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get time (HTTP {resp.status}): {text}")

            # Parse time data (adjust according to actual return format)
            # Simplified handling here, may require more complex parsing in practice
            _ = await resp.json()  # Placeholder: not using return data yet
            return datetime.now()  # Placeholder implementation

    # ==================== Settings Management ====================

    @with_http_retry(max_retries=2)
    async def get_setting(self, setting_id: int) -> Any:
        """Get value of specified setting.

        Args:
            setting_id: Setting ID

        Returns:
            Setting value

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"Getting setting ID {setting_id} (camera {self.http.target})...")

        endpoint = "gopro/camera/setting"
        params = {"setting": str(setting_id)}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get setting (HTTP {resp.status}): {text}")

            data = await resp.json()
            value = data.get("setting", {}).get("value")
            logger.debug(f"Setting {setting_id} = {value}")
            return value

    @with_http_retry(max_retries=2)
    async def set_setting(self, setting_id: int, value: int) -> None:
        """Modify value of specified setting.

        Args:
            setting_id: Setting ID
            value: Setting value

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"Setting ID {setting_id} = {value} (camera {self.http.target})...")

        endpoint = "gopro/camera/setting/set"
        params = {"setting": str(setting_id), "option": str(value)}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to modify setting (HTTP {resp.status}): {text}")

        logger.info(f"✅ Setting modified successfully: {setting_id} = {value}")

    # ==================== Preset Management ====================

    @with_http_retry(max_retries=2)
    async def get_preset_status(self, include_hidden: bool = False) -> dict[str, Any]:
        """Get preset status.

        Args:
            include_hidden: Whether to include hidden presets

        Returns:
            Preset status dictionary

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"Getting preset status (camera {self.http.target})...")

        endpoint = "gopro/camera/presets/get"
        params = {"include-hidden": "1" if include_hidden else "0"}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get presets (HTTP {resp.status}): {text}")

            return await resp.json()

    @with_http_retry(max_retries=2)
    async def load_preset(self, preset_id: int) -> None:
        """Load specified preset.

        Args:
            preset_id: Preset ID

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"Loading preset {preset_id} (camera {self.http.target})...")

        endpoint = "gopro/camera/presets/load"
        params = {"id": str(preset_id)}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to load preset (HTTP {resp.status}): {text}")

        logger.info(f"✅ Preset {preset_id} loaded")

    @with_http_retry(max_retries=2)
    async def load_preset_group(self, group_id: int) -> None:
        """Load preset group.

        Args:
            group_id: Preset group ID

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"Loading preset group {group_id} (camera {self.http.target})...")

        endpoint = "gopro/camera/presets/set_group"
        params = {"id": str(group_id)}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to load preset group (HTTP {resp.status}): {text}")

        logger.info(f"✅ Preset group {group_id} loaded")

    # ==================== Other Controls ====================

    @with_http_retry(max_retries=2)
    async def set_digital_zoom(self, percent: int) -> None:
        """Set digital zoom.

        Args:
            percent: Zoom percentage (0-100)

        Raises:
            HttpConnectionError: Command failed
        """
        if not 0 <= percent <= 100:
            raise ValueError("Zoom percentage must be between 0-100")

        logger.info(f"Setting digital zoom to {percent}% (camera {self.http.target})...")

        endpoint = "gopro/camera/digital_zoom"
        params = {"percent": str(percent)}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to set zoom (HTTP {resp.status}): {text}")

        logger.info(f"✅ Digital zoom set to {percent}%")

    @with_http_retry(max_retries=1)
    async def reboot(self) -> None:
        """Reboot camera.

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"Rebooting camera {self.http.target}...")

        endpoint = "gp/gpControl/command/system/reset"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Reboot failed (HTTP {resp.status}): {text}")

        logger.info(f"✅ Camera {self.http.target} is rebooting")
