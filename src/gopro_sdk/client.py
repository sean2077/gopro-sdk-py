"""Simplified GoPro client implementation.

Uses composition and delegation patterns to split complex functionality into independent modules:
- connection/: BLE and HTTP connection management
- commands/: BLE, HTTP, media, and webcam command implementations

The client acts as an "assembler", providing a unified and concise API.
"""

from __future__ import annotations

__all__ = ["GoProClient", "OfflineModeError"]

import asyncio
import contextlib
import functools
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import open_gopro.models.proto.cohn_pb2 as cohn_proto
import open_gopro.models.proto.response_generic_pb2 as response_proto
from open_gopro.models.constants import ActionId, FeatureId

from .ble_uuid import GoProBleUUID
from .commands import BleCommands, HttpCommands, MediaCommands, MediaFile, WebcamCommands
from .config import CohnConfigManager, CohnCredentials, TimeoutConfig
from .connection import BleConnectionManager, HealthCheckMixin, HttpConnectionManager
from .exceptions import BleConnectionError
from .state_parser import parse_camera_state

logger = logging.getLogger(__name__)


class OfflineModeError(Exception):
    """Offline mode error: attempted to call a function that requires online mode."""

    pass


def _require_online(feature_name: str):
    """Decorator that ensures the method is called in online mode.

    Args:
        feature_name: Feature name for error message

    Raises:
        OfflineModeError: If client is in offline mode
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self: GoProClient, *args, **kwargs):
            if self._offline_mode:
                raise OfflineModeError(
                    f"❌ {feature_name} requires online mode (BLE+WiFi) to use\n"
                    f"Solutions:\n"
                    f"  1. Set offline_mode=False when creating client\n"
                    f"     >>> client = GoProClient('{self.target}', offline_mode=False)\n"
                    f"  2. Or switch to online mode at runtime\n"
                    f"     >>> await client.switch_to_online_mode(wifi_ssid='...', wifi_password='...')\n"
                    f"\n"
                    f"Offline mode supports basic features via BLE:\n"
                    f"  ✅ start_recording() / stop_recording()\n"
                    f"  ✅ set_date_time()\n"
                    f"  ✅ tag_hilight()\n"
                    f"  ✅ load_preset() / load_preset_group()\n"
                    f"  ✅ sleep()\n"
                    f"  ❌ Preview (start_preview)\n"
                    f"  ❌ Download media (download_media)\n"
                    f"  ❌ Manage files (list_media, delete_media)"
                )
            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


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
        ...     await client.set_date_time()  # ✅ Sync time via BLE
        ...     # await client.start_preview()  # ❌ Not supported in offline mode

        Method 2 - Online mode (BLE+WiFi, supports preview, download, etc.):
        >>> async with GoProClient("1332", offline_mode=False, wifi_ssid="MyWiFi", wifi_password="pass") as client:
        ...     await client.start_recording()  # ✅ Control via BLE
        ...     await client.start_preview()  # ✅ Preview via HTTP
        ...     await client.download_media(...)  # ✅ Download via HTTP

        Method 3 - Dynamic mode switching:
        >>> async with GoProClient("1332") as client:  # Start in offline mode
        ...     await client.start_recording()  # Via BLE
        ...     # Switch to online mode when preview needed
        ...     await client.switch_to_online_mode(wifi_ssid="MyWiFi", wifi_password="pass")
        ...     await client.start_preview()  # Preview now available

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
            >>> async with GoProClient("1332", offline_mode=False, wifi_ssid="MyWiFi", wifi_password="pass") as client:
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

        # Step 2-4: Setup COHN credentials (WiFi connection + credential management)
        await self._setup_cohn_credentials(final_wifi_ssid, final_wifi_password)

        logger.info(f"✅ Camera {self.target} connected successfully (BLE + COHN configured)")

    async def close(self) -> None:
        """Close all connections."""
        # Only disconnect connections that are actually connected
        # In offline mode, http was never connected, so we shouldn't call disconnect
        if self.http.is_connected:
            await self.http.disconnect()

        if self.ble.is_connected:
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

    async def _setup_cohn_credentials(
        self,
        wifi_ssid: str | None = None,
        wifi_password: str | None = None,
    ) -> None:
        """Setup COHN credentials for online mode.

        This is the shared logic used by both open() and switch_to_online_mode().
        Handles WiFi connection (if credentials provided) and COHN credential management.

        Workflow:
        1. If WiFi credentials provided, connect camera to WiFi
        2. Load existing COHN credentials from config
        3. If no valid credentials, fetch from camera
        4. If valid credentials exist, refresh IP address
        5. Configure HTTP client with credentials

        Args:
            wifi_ssid: WiFi SSID (optional)
            wifi_password: WiFi password (optional)

        Raises:
            BleConnectionError: WiFi connection or COHN setup failed
        """
        # Step 1: If WiFi credentials provided, connect to WiFi
        if wifi_ssid is not None:
            credentials = self._config_manager.load(self.target)
            has_cohn_credentials = (
                credentials is not None and credentials.certificate and credentials.username and credentials.password
            )
            logger.debug(f"[camera {self.target}] COHN credentials check: has_credentials={has_cohn_credentials}")
            await self.setup_wifi(
                wifi_ssid,
                wifi_password,
                has_cohn_credentials=has_cohn_credentials,
            )

        # Step 2: Get or refresh COHN credentials
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
            # New camera or credentials incomplete -> Get credentials
            logger.info("COHN credentials do not exist or are incomplete, fetching from camera...")

            try:
                credentials = await self._get_cohn_credentials_from_camera()
                self._config_manager.save(self.target, credentials)
                logger.info(f"✅ COHN credentials fetched successfully, IP: {credentials.ip_address}")

            except Exception as e:
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
            # Already have credentials (certificate), refresh IP address
            # WiFi network may have changed, IP will change, but certificate remains valid
            logger.info("COHN already configured, refreshing network info...")
            credentials = await self._refresh_cohn_ip_address(credentials)

        # Step 3: Initialize HTTP credentials (lazy connection, auto-connect on first request)
        self.http.set_credentials(credentials)
        logger.info(f"✅ COHN credentials configured: https://{credentials.ip_address}")

    async def _refresh_cohn_ip_address(self, credentials: CohnCredentials) -> CohnCredentials:
        """Refresh COHN IP address from camera status.

        Args:
            credentials: Existing COHN credentials (with certificate)

        Returns:
            Updated credentials (possibly with new IP address)
        """
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
                # Poll for IP address using configured timeout values
                max_attempts = self._timeout.ip_wait_max_attempts
                interval = self._timeout.ip_wait_interval
                for attempt in range(max_attempts):
                    await asyncio.sleep(interval)
                    status = await self.ble_commands.get_cohn_status()
                    has_ip = bool(status.ipaddress) and bool(status.ipaddress.strip())
                    if has_ip:
                        logger.info(f"✅ Camera got IP: {status.ipaddress}")
                        break
                    logger.debug(
                        f"Still waiting for IP (attempt {attempt + 1}/{max_attempts}), "
                        f"state: {cohn_proto.EnumCOHNNetworkState.Name(status.state)}"
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
                logger.warning(
                    f"Will attempt to use saved IP address: {credentials.ip_address}\n"
                    f"If connection fails, consider reconfiguring COHN (delete old credentials)."
                )
                return credentials  # Return unchanged credentials

            # Successfully got IP, refresh credentials
            updated_credentials = CohnCredentials(
                username=status.username,
                password=status.password,
                ip_address=status.ipaddress,
                certificate=credentials.certificate,  # Keep old certificate
            )
            self._config_manager.save(self.target, updated_credentials)
            logger.info(f"✅ COHN credentials refreshed, IP: {status.ipaddress}")
            return updated_credentials

        except Exception as e:
            logger.warning(
                f"⚠️ Unable to get status via BLE: {e}\n"
                f"Will attempt HTTP connection using saved credentials (IP: {credentials.ip_address}).\n"
                f"Note: Ensure computer and camera are on the same WiFi network, otherwise HTTP connection will fail."
            )
            return credentials  # Return unchanged credentials on error

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

        # Setup COHN credentials (reuse the same logic as open())
        await self._setup_cohn_credentials(final_wifi_ssid, final_wifi_password)

        # Switch mode flag
        self._offline_mode = False
        logger.info("✅ Switched to online mode (BLE+WiFi)")

    # ==================== Recording Control (BLE preferred) ====================

    async def set_shutter(self, enable: bool) -> None:
        """Control recording shutter.

        Always uses BLE for more reliable recording control.

        Args:
            enable: True to start recording, False to stop recording
        """
        # Always use BLE for recording control (more reliable)
        await self.ble_commands.set_shutter(enable)

    async def start_recording(self) -> None:
        """Start recording. Convenience wrapper for set_shutter(True)."""
        await self.set_shutter(True)

    async def stop_recording(self) -> None:
        """Stop recording. Convenience wrapper for set_shutter(False)."""
        await self.set_shutter(False)

    @_require_online("Preview stream control")
    async def set_preview_stream(self, enable: bool, port: int | None = None) -> None:
        """Control preview stream.

        Args:
            enable: True to enable, False to disable
            port: Preview stream port (only needed when enabling)

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        await self.http_commands.set_preview_stream(enable, port)

    async def start_preview(self, port: int = 8554) -> str:
        """Start preview stream.

        Args:
            port: Preview stream port, default 8554

        Returns:
            Preview stream URL (udp://ip:port)

        Raises:
            HttpConnectionError: HTTP connection failed or unavailable
            GoproError: Camera rejected preview request

        Design philosophy:
            Direct attempt without polling - let operations fail fast with clear errors.
            Camera will return appropriate HTTP status codes if not ready (e.g., 409 if busy).
        """
        # Attempt to stop any existing preview/recording directly
        # Failures are expected and ignored - camera handles state internally
        with contextlib.suppress(Exception):
            await self.set_preview_stream(False)

        with contextlib.suppress(Exception):
            await self.set_shutter(False)

        # Brief pause to let camera update state
        await asyncio.sleep(self._timeout.preview_state_settle_delay)

        # Direct attempt to start preview - camera will reject if not ready
        await self.set_preview_stream(True, port)

        # Return preview stream URL
        stream_url = f"udp://127.0.0.1:{port}"
        logger.info(f"📹 [{self.target}] Preview stream started on port {port}")

        return stream_url

    async def stop_preview(self) -> None:
        """Stop preview stream. Convenience wrapper for set_preview_stream(False)."""
        await self.set_preview_stream(False)

    async def tag_hilight(self) -> None:
        """Tag highlight (during recording).

        Note:
            Always uses BLE command for more reliable operation.
        """
        await self.ble_commands.tag_hilight()

    # ==================== Camera Status (delegated to http_commands) ====================

    @_require_online("Get camera status")
    async def get_camera_state(self) -> dict[str, Any]:
        """Get camera status (raw format).

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
        return await self.http_commands.get_camera_state()

    async def get_parsed_state(self) -> dict[Any, Any]:
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

    @_require_online("Get camera info")
    async def get_camera_info(self) -> dict[str, Any]:
        """Get camera information.

        Returns:
            Camera information dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.http_commands.get_camera_info()

    @_require_online("Keep-alive signal")
    async def set_keep_alive(self) -> None:
        """Send keep-alive signal.

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        await self.http_commands.set_keep_alive()

    # ==================== Date Time (delegated to http_commands) ====================

    async def set_date_time(self, dt: datetime | None = None, tz_offset: int = 0, is_dst: bool = False) -> None:
        """Set camera date and time.

        Args:
            dt: Datetime object, defaults to current time
            tz_offset: Timezone offset (hours)
            is_dst: Whether daylight saving time

        Note:
            Always uses BLE command for time sync (more reliable than HTTP)
        """
        # Always use BLE for time sync (more reliable)
        await self.ble_commands.set_date_time(dt, tz_offset, is_dst)

    @_require_online("Get camera time")
    async def get_date_time(self) -> datetime:
        """Get camera date and time.

        Returns:
            Datetime object

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.http_commands.get_date_time()

    # ==================== Settings Management (delegated to http_commands) ====================

    @_require_online("Get setting")
    async def get_setting(self, setting_id: int) -> Any:
        """Get the value of specified setting.

        Args:
            setting_id: Setting ID

        Returns:
            Setting value

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.http_commands.get_setting(setting_id)

    @_require_online("Set setting")
    async def set_setting(self, setting_id: int, value: int) -> None:
        """Modify the value of specified setting.

        Args:
            setting_id: Setting ID
            value: Setting value

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        await self.http_commands.set_setting(setting_id, value)

    # ==================== Preset Management (delegated to http_commands) ====================

    @_require_online("Get preset status")
    async def get_preset_status(self, include_hidden: bool = False) -> dict[str, Any]:
        """Get preset status.

        Args:
            include_hidden: Whether to include hidden presets

        Returns:
            Preset status dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.http_commands.get_preset_status(include_hidden)

    async def load_preset(self, preset_id: int) -> None:
        """Load specified preset.

        Args:
            preset_id: Preset ID

        Note:
            Always uses BLE command for more reliable operation.
        """
        await self.ble_commands.load_preset(preset_id)

    async def load_preset_group(self, group_id: int) -> None:
        """Load preset group.

        Args:
            group_id: Preset group ID

        Note:
            Always uses BLE command for more reliable operation.
        """
        await self.ble_commands.load_preset_group(group_id)

    # ==================== Other Controls ====================

    @_require_online("Digital zoom")
    async def set_digital_zoom(self, percent: int) -> None:
        """Set digital zoom.

        Args:
            percent: Zoom percentage (0-100)

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        await self.http_commands.set_digital_zoom(percent)

    async def sleep(self) -> None:
        """Put camera to sleep.

        Note:
            Uses BLE command which works in both online and offline modes.
        """
        await self.ble_commands.sleep()

    async def reboot(self) -> None:
        """Reboot camera.

        Note:
            Uses BLE command which works in both online and offline modes.
        """
        await self.ble_commands.reboot()

    # ==================== Media Management (delegated to media_commands) ====================

    @_require_online("Media file list")
    async def get_media_list(self) -> list[MediaFile]:
        """Get list of all media files.

        Returns:
            List of media files (MediaFile objects)

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.media_commands.get_media_list()

    @_require_online("Media download")
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
        return await self.media_commands.download_file(media_file, save_path, progress_callback)

    @_require_online("Delete media file")
    async def delete_file(self, path: str) -> None:
        """Delete single media file.

        Args:
            path: File path

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        await self.media_commands.delete_file(path)

    @_require_online("Delete all media")
    async def delete_all_media(self) -> None:
        """Delete all media files.

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        await self.media_commands.delete_all_media()

    @_require_online("Get media metadata")
    async def get_media_metadata(self, path: str) -> dict[str, Any]:
        """Get media file metadata.

        Args:
            path: File path

        Returns:
            Metadata dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.media_commands.get_media_metadata(path)

    @_require_online("Get last captured media")
    async def get_last_captured_media(self) -> dict[str, Any]:
        """Get last captured media file information.

        Returns:
            Media information dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.media_commands.get_last_captured_media()

    @_require_online("Turbo transfer mode")
    async def set_turbo_mode(self, enable: bool) -> None:
        """Enable/disable Turbo transfer mode.

        Args:
            enable: True to enable, False to disable

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        await self.media_commands.set_turbo_mode(enable)

    # ==================== Webcam Mode (delegated to webcam_commands) ====================

    @_require_online("Webcam mode")
    async def start_webcam(
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
        return await self.webcam_commands.webcam_start(resolution, fov, port, protocol)

    @_require_online("Webcam mode")
    async def stop_webcam(self) -> dict[str, Any]:
        """Stop Webcam mode.

        Returns:
            Webcam response

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.webcam_commands.webcam_stop()

    @_require_online("Webcam status")
    async def get_webcam_status(self) -> dict[str, Any]:
        """Get Webcam status.

        Returns:
            Webcam status dictionary

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.webcam_commands.webcam_status()

    @_require_online("Webcam preview")
    async def start_webcam_preview(self) -> dict[str, Any]:
        """Start Webcam preview.

        Returns:
            Webcam response

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.webcam_commands.webcam_preview()

    @_require_online("Webcam mode")
    async def webcam_exit(self) -> dict[str, Any]:
        """Exit Webcam mode.

        Returns:
            Webcam response

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
        return await self.webcam_commands.webcam_exit()

    @_require_online("Webcam version")
    async def get_webcam_version(self) -> str:
        """Get Webcam implementation version.

        Returns:
            Version string

        Raises:
            OfflineModeError: This feature is not supported in offline mode
        """
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
        if not all([
            credentials.ip_address,
            credentials.username,
            credentials.password,
            credentials.certificate,
        ]):
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
                f"5. 📌 Camera may have connected but BLE disconnected (COHN mode)\n"
                f"\n"
                f"Suggestions:\n"
                f"- Check WiFi configuration is correct\n"
                f"- Ensure camera is within router signal range\n"
                f"- If repeatedly fails, try manually resetting network settings on camera"
            )
            logger.error(error_msg)
            raise BleConnectionError(error_msg) from e

    async def scan_wifi_networks(self, timeout: float | None = None) -> list[Any]:
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
