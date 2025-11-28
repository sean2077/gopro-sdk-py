"""BLE command implementation.

Implements BLE-only commands, mainly including:
- Basic control commands (shutter, etc.)
- COHN configuration and management
- Network management (WiFi scanning, connection, etc.)
- Other BLE-specific features
"""

from __future__ import annotations

__all__ = ["BleCommands"]

import asyncio
import logging
import struct
from datetime import datetime
from typing import Any

import open_gopro.models.proto.cohn_pb2 as cohn_proto
import open_gopro.models.proto.network_management_pb2 as network_proto
import open_gopro.models.proto.response_generic_pb2 as response_proto
from open_gopro.models.constants import ActionId, CmdId, FeatureId
from open_gopro.models.proto.network_management_pb2 import (
    EnumProvisioning,
    EnumScanEntryFlags,
    EnumScanning,
)
from open_gopro.models.proto.response_generic_pb2 import RESULT_SUCCESS

from ..ble_uuid import GoProBleUUID
from ..config import CohnCredentials
from ..connection.ble_manager import BleConnectionManager
from ..exceptions import BleConnectionError, CohnConfigurationError

logger = logging.getLogger(__name__)


class BleCommands:
    """BLE command interface.

    Implements commands that need to be executed via BLE, mainly:
    - COHN configuration workflow
    - Network management commands
    - Other BLE-specific commands
    """

    def __init__(self, ble_manager: BleConnectionManager) -> None:
        """Initialize BLE command interface.

        Args:
            ble_manager: BLE connection manager
        """
        self.ble = ble_manager
        self._timeout = ble_manager._timeout  # Get timeout configuration from BLE manager

    def _build_protobuf_command(self, feature_id: int, action_id: int, protobuf_message: Any) -> bytes:
        """Build protobuf command data (excluding length byte).

        Note: Length byte for BLE packets is automatically added during fragmentation,
              here we only need to return feature_id + action_id + protobuf_data.

        Reference: open_gopro.api.builders.BleProtoCommand._build_data()

        Args:
            feature_id: Feature ID (0xF1=Command, 0xF5=Query)
            action_id: Action ID
            protobuf_message: protobuf message object

        Returns:
            Command data (feature_id + action_id + protobuf_data)
        """
        proto_data = protobuf_message.SerializeToString()
        # Only includes feature_id + action_id + protobuf_data
        # Length byte is automatically added by the Open GoPro SDK's fragmentation logic
        return bytes([feature_id, action_id]) + proto_data

    async def _send_protobuf_command(
        self,
        feature_id: int,
        action_id: int,
        request_proto: Any,
        response_proto_class: Any,
        uuid: str,
    ) -> Any:
        """Send protobuf command and wait for response.

        Args:
            feature_id: Feature ID
            action_id: Action ID
            request_proto: Request protobuf
            response_proto_class: Response protobuf class
            uuid: BLE UUID

        Returns:
            Parsed response
        """
        # Clear response queue
        self.ble.clear_response_queue()

        # Build and send command
        command_data = self._build_protobuf_command(feature_id, action_id, request_proto)
        logger.debug(f"📤 Sending protobuf command: feature={hex(feature_id)}, action={hex(action_id)}")
        await self.ble.write(uuid, command_data)

        # Wait for response
        response_data = await self.ble.wait_for_response()

        # Parse response
        logger.debug(f"📥 Received complete response: {len(response_data)} bytes")

        if len(response_data) < 2:
            raise BleConnectionError(f"Response data too short: {len(response_data)} bytes")

        # Skip feature_id and action_id, parse protobuf data
        proto_data = response_data[2:]
        response = response_proto_class()

        try:
            response.ParseFromString(proto_data)
            logger.debug("✅ Successfully parsed response")
            return response
        except Exception as e:
            logger.error(f"❌ Protobuf parse failed: {e}")
            raise BleConnectionError(f"Failed to parse response: {e}") from e

    # ==================== Basic Control Commands ====================

    async def set_shutter(self, enable: bool) -> None:
        """Control recording shutter via BLE.

        Args:
            enable: True to start recording, False to stop recording

        Raises:
            BleConnectionError: Command send failed or response error
        """
        shutter_value = 0x01 if enable else 0x00
        action = "Starting" if enable else "Stopping"
        logger.info(f"🎬 {action} recording (BLE command)...")

        # Clear response queue (avoid interference from old status notifications)
        self.ble.clear_response_queue()

        # Build command: [cmd_id, param_len, param_value]
        # Reference: BleWriteCommand._build_data() implementation
        command_data = bytes([CmdId.SET_SHUTTER, 0x01, shutter_value])
        logger.debug(f"📤 Sending shutter command: {command_data.hex()}")

        try:
            # Send command to CQ_COMMAND UUID
            await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)

            # Wait for response: [cmd_id, status_code]
            # Command response should arrive within 100ms, 2 second timeout is sufficient
            response_data = await self.ble.wait_for_response(timeout=2.0)

            # Parse response
            if len(response_data) < 2:
                raise BleConnectionError(f"Response data too short: {len(response_data)} bytes")

            cmd_id = response_data[0]
            status_code = response_data[1]

            if cmd_id != CmdId.SET_SHUTTER:
                raise BleConnectionError(
                    f"Response command ID mismatch: expected {CmdId.SET_SHUTTER:#x}, got {cmd_id:#x}"
                )

            if status_code != 0x00:  # 0x00 = SUCCESS
                raise BleConnectionError(f"Shutter command failed: status code {status_code:#x}")

            logger.info(f"✅ {action} recording successful")

        except TimeoutError as e:
            logger.error(f"❌ {action} recording timeout")
            raise BleConnectionError(f"{action} recording timeout") from e
        except Exception as e:
            logger.error(f"❌ {action} recording failed: {e}")
            raise BleConnectionError(f"{action} recording failed: {e}") from e

    async def set_date_time(self, dt: datetime | None = None, tz_offset: int = 0, is_dst: bool = False) -> None:
        """Set camera date and time via BLE.

        Args:
            dt: Datetime to set, None uses current system time
            tz_offset: Timezone offset (UTC hours), e.g., UTC+8 is 8
            is_dst: Whether daylight saving time

        Raises:
            BleConnectionError: Command send failed or response error
        """
        if dt is None:
            dt = datetime.now()

        logger.info(f"🕐 Setting camera time: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

        # Clear response queue
        self.ble.clear_response_queue()

        # Build time parameters (reference: DateTimeByteParserBuilder.build)
        # Format: year(2-byte big-endian) + month + day + hour + minute + second
        #         [+ tz_offset(2-byte signed big-endian) + is_dst(1-byte)] (optional)
        time_bytes = bytearray()
        time_bytes.extend(struct.pack(">H", dt.year))  # Year (big-endian uint16)
        time_bytes.extend([dt.month, dt.day, dt.hour, dt.minute, dt.second])

        # Choose command based on timezone/DST info
        if tz_offset != 0 or is_dst:
            # Use SET_DATE_TIME_DST (0x0F), includes timezone and DST
            cmd_id = CmdId.SET_DATE_TIME_DST
            time_bytes.extend(struct.pack(">h", tz_offset))  # Timezone offset (signed)
            time_bytes.append(0x01 if is_dst else 0x00)  # DST flag
        else:
            # Use SET_DATE_TIME (0x0D), no timezone info
            cmd_id = CmdId.SET_DATE_TIME

        # Build command: [cmd_id, param_len, ...param_bytes]
        param_len = len(time_bytes)
        command_data = bytes([cmd_id, param_len]) + bytes(time_bytes)
        logger.debug(f"📤 Sending time sync command: {command_data.hex()}")

        try:
            # Send command to CQ_COMMAND UUID
            await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)

            # Wait for response: [cmd_id, status_code]
            response_data = await self.ble.wait_for_response(timeout=2.0)

            # Parse response
            if len(response_data) < 2:
                raise BleConnectionError(f"Response data too short: {len(response_data)} bytes")

            resp_cmd_id = response_data[0]
            status_code = response_data[1]

            if resp_cmd_id != cmd_id:
                raise BleConnectionError(f"Response command ID mismatch: expected {cmd_id:#x}, got {resp_cmd_id:#x}")

            if status_code != 0x00:  # 0x00 = SUCCESS
                raise BleConnectionError(f"Time sync failed: status code {status_code:#x}")

            logger.info("✅ Time sync successful")

        except TimeoutError as e:
            logger.error("❌ Time sync timeout")
            raise BleConnectionError("Time sync timeout") from e
        except Exception as e:
            logger.error(f"❌ Time sync failed: {e}")
            raise BleConnectionError(f"Time sync failed: {e}") from e

    async def tag_hilight(self) -> None:
        """Tag highlight during recording via BLE.

        Raises:
            BleConnectionError: Command send failed or response error
        """
        logger.info("🏷️ Tagging highlight (BLE command)...")

        # Clear response queue
        self.ble.clear_response_queue()

        # Build command: [cmd_id] (no parameters)
        command_data = bytes([CmdId.TAG_HILIGHT])
        logger.debug(f"📤 Sending tag hilight command: {command_data.hex()}")

        try:
            await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)

            response_data = await self.ble.wait_for_response(timeout=2.0)

            if len(response_data) < 2:
                raise BleConnectionError(f"Response data too short: {len(response_data)} bytes")

            cmd_id = response_data[0]
            status_code = response_data[1]

            if cmd_id != CmdId.TAG_HILIGHT:
                raise BleConnectionError(
                    f"Response command ID mismatch: expected {CmdId.TAG_HILIGHT:#x}, got {cmd_id:#x}"
                )

            if status_code != 0x00:
                raise BleConnectionError(f"Tag hilight failed: status code {status_code:#x}")

            logger.info("✅ Highlight tagged successfully")

        except TimeoutError as e:
            logger.error("❌ Tag hilight timeout")
            raise BleConnectionError("Tag hilight timeout") from e
        except Exception as e:
            logger.error(f"❌ Tag hilight failed: {e}")
            raise BleConnectionError(f"Tag hilight failed: {e}") from e

    async def load_preset(self, preset_id: int) -> None:
        """Load specified preset via BLE.

        Args:
            preset_id: Preset ID

        Raises:
            BleConnectionError: Command send failed or response error
        """
        logger.info(f"📋 Loading preset {preset_id} (BLE command)...")

        # Clear response queue
        self.ble.clear_response_queue()

        # Build command: [cmd_id, param_len, preset_id (2 bytes big-endian)]
        command_data = bytes([CmdId.LOAD_PRESET, 0x02]) + struct.pack(">H", preset_id)
        logger.debug(f"📤 Sending load preset command: {command_data.hex()}")

        try:
            await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)

            response_data = await self.ble.wait_for_response(timeout=2.0)

            if len(response_data) < 2:
                raise BleConnectionError(f"Response data too short: {len(response_data)} bytes")

            cmd_id = response_data[0]
            status_code = response_data[1]

            if cmd_id != CmdId.LOAD_PRESET:
                raise BleConnectionError(
                    f"Response command ID mismatch: expected {CmdId.LOAD_PRESET:#x}, got {cmd_id:#x}"
                )

            if status_code != 0x00:
                raise BleConnectionError(f"Load preset failed: status code {status_code:#x}")

            logger.info(f"✅ Preset {preset_id} loaded successfully")

        except TimeoutError as e:
            logger.error(f"❌ Load preset {preset_id} timeout")
            raise BleConnectionError(f"Load preset {preset_id} timeout") from e
        except Exception as e:
            logger.error(f"❌ Load preset {preset_id} failed: {e}")
            raise BleConnectionError(f"Load preset {preset_id} failed: {e}") from e

    async def load_preset_group(self, group_id: int) -> None:
        """Load preset group via BLE.

        Args:
            group_id: Preset group ID

        Raises:
            BleConnectionError: Command send failed or response error
        """
        logger.info(f"📋 Loading preset group {group_id} (BLE command)...")

        # Clear response queue
        self.ble.clear_response_queue()

        # Build command: [cmd_id, param_len, group_id (2 bytes big-endian)]
        command_data = bytes([CmdId.LOAD_PRESET_GROUP, 0x02]) + struct.pack(">H", group_id)
        logger.debug(f"📤 Sending load preset group command: {command_data.hex()}")

        try:
            await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)

            response_data = await self.ble.wait_for_response(timeout=2.0)

            if len(response_data) < 2:
                raise BleConnectionError(f"Response data too short: {len(response_data)} bytes")

            cmd_id = response_data[0]
            status_code = response_data[1]

            if cmd_id != CmdId.LOAD_PRESET_GROUP:
                raise BleConnectionError(
                    f"Response command ID mismatch: expected {CmdId.LOAD_PRESET_GROUP:#x}, got {cmd_id:#x}"
                )

            if status_code != 0x00:
                raise BleConnectionError(f"Load preset group failed: status code {status_code:#x}")

            logger.info(f"✅ Preset group {group_id} loaded successfully")

        except TimeoutError as e:
            logger.error(f"❌ Load preset group {group_id} timeout")
            raise BleConnectionError(f"Load preset group {group_id} timeout") from e
        except Exception as e:
            logger.error(f"❌ Load preset group {group_id} failed: {e}")
            raise BleConnectionError(f"Load preset group {group_id} failed: {e}") from e

    async def sleep(self) -> None:
        """Put camera to sleep via BLE.

        Raises:
            BleConnectionError: Command send failed or response error
        """
        logger.info("😴 Putting camera to sleep (BLE command)...")

        # Clear response queue
        self.ble.clear_response_queue()

        # Build command: [cmd_id] (no parameters)
        command_data = bytes([CmdId.SLEEP])
        logger.debug(f"📤 Sending sleep command: {command_data.hex()}")

        try:
            await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)

            response_data = await self.ble.wait_for_response(timeout=2.0)

            if len(response_data) < 2:
                raise BleConnectionError(f"Response data too short: {len(response_data)} bytes")

            cmd_id = response_data[0]
            status_code = response_data[1]

            if cmd_id != CmdId.SLEEP:
                raise BleConnectionError(f"Response command ID mismatch: expected {CmdId.SLEEP:#x}, got {cmd_id:#x}")

            if status_code != 0x00:
                raise BleConnectionError(f"Sleep command failed: status code {status_code:#x}")

            logger.info("✅ Camera is going to sleep")

        except TimeoutError as e:
            logger.error("❌ Sleep command timeout")
            raise BleConnectionError("Sleep command timeout") from e
        except Exception as e:
            logger.error(f"❌ Sleep command failed: {e}")
            raise BleConnectionError(f"Sleep command failed: {e}") from e

    async def reboot(self) -> None:
        """Reboot camera via BLE.

        Raises:
            BleConnectionError: Command send failed or response error
        """
        logger.info("🔄 Rebooting camera (BLE command)...")

        # Clear response queue
        self.ble.clear_response_queue()

        # Build command: [cmd_id] (no parameters)
        command_data = bytes([CmdId.REBOOT])
        logger.debug(f"📤 Sending reboot command: {command_data.hex()}")

        try:
            await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)

            response_data = await self.ble.wait_for_response(timeout=2.0)

            if len(response_data) < 2:
                raise BleConnectionError(f"Response data too short: {len(response_data)} bytes")

            cmd_id = response_data[0]
            status_code = response_data[1]

            if cmd_id != CmdId.REBOOT:
                raise BleConnectionError(f"Response command ID mismatch: expected {CmdId.REBOOT:#x}, got {cmd_id:#x}")

            if status_code != 0x00:
                raise BleConnectionError(f"Reboot command failed: status code {status_code:#x}")

            logger.info("✅ Camera is rebooting")

        except TimeoutError as e:
            logger.error("❌ Reboot command timeout")
            raise BleConnectionError("Reboot command timeout") from e
        except Exception as e:
            logger.error(f"❌ Reboot command failed: {e}")
            raise BleConnectionError(f"Reboot command failed: {e}") from e

    # ==================== Network Management Commands ====================

    async def release_network(self) -> None:
        """Disconnect camera's WiFi connection (return from STA mode to AP mode).

        Purpose:
        - When camera is connected to router (STA mode), WiFi chip is occupied and cannot scan
        - Call this method to disconnect, return camera to AP mode for WiFi reconfiguration

        Raises:
            BleConnectionError: Disconnect failed
        """
        logger.info("📡 Disconnecting camera WiFi connection...")

        request = network_proto.RequestReleaseNetwork()

        try:
            await self._send_protobuf_command(
                feature_id=FeatureId.NETWORK_MANAGEMENT.value,
                action_id=ActionId.RELEASE_NETWORK,
                request_proto=request,
                response_proto_class=response_proto.ResponseGeneric,
                uuid=GoProBleUUID.CQ_COMMAND,
            )

            logger.info("✅ Camera WiFi disconnected")

        except Exception as e:
            logger.error(f"❌ WiFi disconnect failed: {e}")
            raise BleConnectionError(f"WiFi disconnect failed: {e}") from e

    async def get_cohn_status(self) -> cohn_proto.NotifyCOHNStatus:
        """Get current COHN status.

        Returns:
            COHN status information, including network connection state, configuration state, IP address, etc.

        Raises:
            BleConnectionError: BLE communication failed
        """
        logger.debug("🔍 Querying COHN status")

        request = cohn_proto.RequestGetCOHNStatus()
        request.register_cohn_status = False  # Don't register continuous monitoring, query once only

        try:
            # Send request, action_id is REQUEST_GET_COHN_STATUS (0x6F)
            # Response action_id will be RESPONSE_GET_COHN_STATUS (0xEF)
            response = await self._send_protobuf_command(
                feature_id=FeatureId.QUERY.value,
                action_id=ActionId.REQUEST_GET_COHN_STATUS,
                request_proto=request,
                response_proto_class=cohn_proto.NotifyCOHNStatus,
                uuid=GoProBleUUID.CQ_QUERY,
            )

            logger.info(
                f"✅ COHN status: "
                f"status={cohn_proto.EnumCOHNStatus.Name(response.status)}, "
                f"state={cohn_proto.EnumCOHNNetworkState.Name(response.state)}, "
                f"ssid={response.ssid or 'N/A'}, "
                f"ip={response.ipaddress or 'N/A'}"
            )

            return response

        except Exception as e:
            logger.error(f"❌ Failed to get COHN status: {e}")
            raise BleConnectionError(f"Failed to get COHN status: {e}") from e

    async def configure_cohn(self) -> CohnCredentials:
        """Configure COHN (Camera on Home Network).

        Workflow:
        1. Clear existing certificate
        2. Create new certificate
        3. Get certificate and credentials
        4. Wait for network connection

        Returns:
            COHN credentials

        Raises:
            CohnConfigurationError: Configuration failed
        """
        try:
            logger.info(f"Starting COHN configuration for camera {self.ble.target}...")

            # Step 1: Clear old certificate
            logger.debug("Clearing old COHN certificate...")
            clear_request = cohn_proto.RequestClearCOHNCert()
            await self._send_protobuf_command(
                feature_id=FeatureId.COMMAND,
                action_id=ActionId.REQUEST_CLEAR_COHN_CERT,
                request_proto=clear_request,
                response_proto_class=response_proto.ResponseGeneric,
                uuid=GoProBleUUID.CQ_COMMAND,
            )

            # Step 2: Create new certificate
            logger.debug("Creating new COHN certificate...")
            create_request = cohn_proto.RequestCreateCOHNCert()
            create_request.override = True
            await self._send_protobuf_command(
                feature_id=FeatureId.COMMAND,
                action_id=ActionId.REQUEST_CREATE_COHN_CERT,
                request_proto=create_request,
                response_proto_class=response_proto.ResponseGeneric,
                uuid=GoProBleUUID.CQ_COMMAND,
            )

            # Step 3: Poll status until PROVISIONED
            logger.info("⏳ Waiting for COHN certificate generation and camera to connect to WiFi...")
            await self._wait_for_cohn_provisioned(timeout=self._timeout.cohn_wait_provisioned_timeout)

            # Step 4: Get credentials
            logger.debug("Retrieving COHN credentials...")

            # Get certificate
            cert_request = cohn_proto.RequestCOHNCert()
            cert_response = await self._send_protobuf_command(
                feature_id=FeatureId.QUERY,
                action_id=ActionId.REQUEST_GET_COHN_CERT,
                request_proto=cert_request,
                response_proto_class=cohn_proto.ResponseCOHNCert,
                uuid=GoProBleUUID.CQ_QUERY,
            )

            # Get status
            status_request = cohn_proto.RequestGetCOHNStatus()
            status_request.register_cohn_status = False
            status_response = await self._send_protobuf_command(
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

            # Validate credential completeness
            if not all(
                [
                    credentials.ip_address,
                    credentials.username,
                    credentials.password,
                    credentials.certificate,
                ]
            ):
                raise CohnConfigurationError("Credentials incomplete")

            logger.info(f"✅ Camera {self.ble.target} COHN configuration successful: {credentials.ip_address}")
            return credentials

        except Exception as e:
            msg = f"Camera {self.ble.target} COHN configuration failed: {e}"
            logger.error(msg)
            raise CohnConfigurationError(msg) from e

    async def _wait_for_cohn_provisioned(self, timeout: float | None = None) -> None:
        """Poll and wait for COHN status to become PROVISIONED.

        Args:
            timeout: Timeout duration (seconds), defaults to configured value

        Raises:
            TimeoutError: Timeout occurred
        """
        if timeout is None:
            timeout = self._timeout.cohn_provision_timeout

        loop = asyncio.get_running_loop()
        start_time = loop.time()
        interval = self._timeout.cohn_status_poll_interval

        while True:
            elapsed = loop.time() - start_time
            if elapsed > timeout:
                error_msg = (
                    f"COHN configuration timeout ({timeout} seconds)\n"
                    f"Possible causes:\n"
                    f"1. Router WiFi password incorrect\n"
                    f"2. WiFi signal too weak\n"
                    f"3. Router DHCP service abnormal\n"
                    f"Suggestion: Check network status on camera screen"
                )
                logger.error(error_msg)
                raise TimeoutError(error_msg)

            # Query status
            is_first_query = loop.time() - start_time < 1
            status_request = cohn_proto.RequestGetCOHNStatus()
            status_request.register_cohn_status = is_first_query

            status_response = await self._send_protobuf_command(
                feature_id=FeatureId.QUERY,
                action_id=ActionId.REQUEST_GET_COHN_STATUS,
                request_proto=status_request,
                response_proto_class=cohn_proto.NotifyCOHNStatus,
                uuid=GoProBleUUID.CQ_QUERY,
            )

            # Display status name
            status_name = cohn_proto.EnumCOHNStatus.Name(status_response.status)
            state_name = cohn_proto.EnumCOHNNetworkState.Name(status_response.state)
            elapsed = loop.time() - start_time
            has_ip = bool(status_response.ipaddress) and bool(status_response.ipaddress.strip())

            logger.info(
                f"⏳ COHN configuration progress ({elapsed:.0f}s): "
                f"status={status_name}, network={state_name}, "
                f"IP={'✅ ' + status_response.ipaddress if has_ip else '⏳ Waiting...'}"
            )

            # Check if completed (relaxed condition: allow connecting state if has IP)
            # In some cases camera state may be COHN_STATE_ConnectingToNetwork, but actually available
            is_provisioned = status_response.status == cohn_proto.EnumCOHNStatus.COHN_PROVISIONED
            is_connected = status_response.state == cohn_proto.EnumCOHNNetworkState.COHN_STATE_NetworkConnected
            is_connecting = status_response.state == cohn_proto.EnumCOHNNetworkState.COHN_STATE_ConnectingToNetwork

            # Completion condition: provisioned + (connected OR (connecting and has IP))
            if is_provisioned and (is_connected or (is_connecting and has_ip)):
                if is_connecting:
                    logger.info(
                        f"ℹ️ Camera state is {state_name}, but has IP ({status_response.ipaddress}), considered configured"
                    )
                logger.info(f"✅ COHN configuration complete! IP: {status_response.ipaddress}")
                return

            await asyncio.sleep(interval)

    async def scan_wifi_networks(self, timeout: float | None = None) -> list[dict[str, Any]]:
        """Scan WiFi networks.

        Args:
            timeout: Scan timeout (seconds), defaults to configured value
                    - Normal scan usually completes within 3-5 seconds
                    - If camera is in STA mode (connected to WiFi), scan will fail
                    - Using shorter timeout can quickly detect failure and fall back to direct connect mode

        Returns:
            List of WiFi networks, each containing ssid, signal_strength, flags, etc.

        Raises:
            BleConnectionError: Scan failed
            TimeoutError: Scan timeout (possibly because camera is in STA mode)
        """
        if timeout is None:
            timeout = self._timeout.wifi_scan_timeout

        logger.info(f"📡 Starting WiFi network scan (camera {self.ble.target})...")

        # Build and send scan request
        request = network_proto.RequestStartScan()
        command = self._build_protobuf_command(FeatureId.NETWORK_MANAGEMENT, ActionId.SCAN_WIFI_NETWORKS, request)

        # Clear response queue, prepare to receive notifications
        self.ble.clear_response_queue()

        # Send scan command
        logger.debug(f"Sending scan command: {command.hex(':')}")
        await self.ble.write(GoProBleUUID.CM_NET_MGMT_COMM, command)

        # Wait for initial response (ResponseStartScanning)
        initial_response_data = await self.ble.wait_for_response(timeout=self._timeout.ble_response_timeout)
        if len(initial_response_data) < 2:
            raise BleConnectionError("Invalid initial scan response")

        # Parse initial response
        initial_proto_data = initial_response_data[2:]
        initial_response = network_proto.ResponseStartScanning()
        initial_response.ParseFromString(initial_proto_data)

        if initial_response.result != RESULT_SUCCESS:
            error_msg = (
                f"Failed to start scan: result={initial_response.result}. "
                f"Possible cause: Camera is in STA mode (connected to router), WiFi chip is occupied. "
                f"Solution: Manually disconnect WiFi on camera, or reset network settings."
            )
            raise BleConnectionError(error_msg)

        logger.debug("Scan started, waiting for scan complete notification...")

        # Wait for scan complete notification (NotifStartScanning)
        scan_id = await self._wait_for_scan_complete(timeout=timeout)

        # Get scan results
        logger.debug(f"Scan complete, getting results (scan_id={scan_id})...")
        get_entries_request = network_proto.RequestGetApEntries()
        get_entries_request.scan_id = scan_id
        get_entries_request.start_index = 0
        get_entries_request.max_entries = 100

        response = await self._send_protobuf_command(
            FeatureId.NETWORK_MANAGEMENT,
            ActionId.GET_AP_ENTRIES,
            get_entries_request,
            network_proto.ResponseGetApEntries,
            GoProBleUUID.CM_NET_MGMT_COMM,
        )

        # Parse results
        networks = []
        for entry in response.entries:
            networks.append(
                {
                    "ssid": entry.ssid,
                    "signal_strength": entry.signal_strength_bars,
                    "signal_frequency": entry.signal_frequency_mhz,
                    "configured": bool(entry.scan_entry_flags & EnumScanEntryFlags.SCAN_FLAG_CONFIGURED),
                }
            )

        logger.info(f"✅ Scan complete, found {len(networks)} networks")
        return networks

    async def _wait_for_scan_complete(self, timeout: float) -> int:
        """Wait for WiFi scan complete notification.

        Args:
            timeout: Timeout duration (seconds)

        Returns:
            Scan ID

        Raises:
            BleConnectionError: Scan failed or timeout
        """
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        while True:
            if loop.time() - start_time > timeout:
                raise TimeoutError("WiFi scan complete timeout")

            try:
                # Wait for notification (NotifStartScanning)
                notification_data = await self.ble.wait_for_response(timeout=self._timeout.ble_response_timeout)

                if len(notification_data) < 2:
                    logger.debug("Received invalid notification, continue waiting...")
                    continue

                # Check if it's NotifStartScanning (NETWORK_MANAGEMENT + NOTIF_START_SCAN)
                feature_id = notification_data[0]
                action_id = notification_data[1]

                if feature_id != FeatureId.NETWORK_MANAGEMENT or action_id != ActionId.NOTIF_START_SCAN:
                    logger.debug(
                        f"Received other notification (feature={hex(feature_id)}, action={hex(action_id)}), continue waiting..."
                    )
                    continue

                # Parse notification
                proto_data = notification_data[2:]
                notification = network_proto.NotifStartScanning()
                notification.ParseFromString(proto_data)

                logger.debug(
                    f"Received scan notification: state={notification.scanning_state}, "
                    f"scan_id={notification.scan_id}, "
                    f"total_entries={notification.total_entries}"
                )

                # Check scan status
                if notification.scanning_state == EnumScanning.SCANNING_SUCCESS:
                    logger.info(f"✅ Scan completed successfully! Found {notification.total_entries} networks")
                    return notification.scan_id
                elif notification.scanning_state == EnumScanning.SCANNING_STARTED:
                    logger.debug("⏳ Scan in progress...")
                    continue
                elif notification.scanning_state in (
                    EnumScanning.SCANNING_ABORTED_BY_SYSTEM,
                    EnumScanning.SCANNING_CANCELLED_BY_USER,
                ):
                    raise BleConnectionError(f"Scan aborted: state={notification.scanning_state}")
                else:  # Other states
                    logger.debug(f"Received scan status update: {notification.scanning_state}")
                    continue

            except BleConnectionError:
                # wait_for_response timeout, check overall timeout
                if loop.time() - start_time > timeout:
                    raise TimeoutError("WiFi scan complete timeout") from None
                logger.debug("Waiting for scan notification timeout (5 seconds), continue waiting...")
                continue

    async def _wait_for_provisioning_complete(self, ssid: str, timeout: float) -> None:
        """Wait for WiFi configuration complete notification.

        Note: When switching WiFi in COHN mode, camera will disconnect BLE,
        making it impossible to receive SUCCESS notification. In this case,
        will timeout and return, caller should verify WiFi connection via HTTP.

        Args:
            ssid: WiFi SSID (for logging)
            timeout: Timeout duration (seconds)

        Raises:
            BleConnectionError: Connection failed (wrong password, etc.)
            TimeoutError: Timeout (possibly due to BLE disconnect)
        """
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        last_log_time = start_time

        while True:
            elapsed = loop.time() - start_time

            if elapsed > timeout:
                logger.warning(f"⚠️ WiFi '{ssid}' connection complete timeout ({timeout:.0f} seconds)")
                raise TimeoutError(f"WiFi '{ssid}' connection complete timeout")

            # Log waiting progress every 5 seconds
            if elapsed - (last_log_time - start_time) >= 5:
                logger.info(f"⏳ Waiting for WiFi connection... ({elapsed:.0f}s/{timeout:.0f}s)")
                last_log_time = loop.time()

            try:
                # Wait for notification (NotifProvisioningState)
                logger.debug("Waiting for NotifProvisioningState notification...")
                notification_data = await self.ble.wait_for_response(timeout=self._timeout.ble_response_timeout)

                if len(notification_data) < 2:
                    logger.debug("Received invalid notification, continue waiting...")
                    continue

                # Check if it's NotifProvisioningState (Feature=0x02, Action=0x0C)
                feature_id = notification_data[0]
                action_id = notification_data[1]

                logger.debug(
                    f"Received notification: feature={hex(feature_id)}, "
                    f"action={hex(action_id)}, "
                    f"data length={len(notification_data)} bytes"
                )

                # Ignore WiFi scan notification (NOTIF_START_SCAN), this is camera's auto-scan before WiFi connection
                if feature_id == FeatureId.NETWORK_MANAGEMENT and action_id == ActionId.NOTIF_START_SCAN:
                    logger.debug(
                        "⏭️ Received WiFi scan notification (NOTIF_START_SCAN), ignoring and continue waiting for config notification"
                    )
                    continue

                # Only handle WiFi configuration notification (NOTIF_PROVIS_STATE)
                if feature_id != FeatureId.NETWORK_MANAGEMENT or action_id != ActionId.NOTIF_PROVIS_STATE:
                    logger.debug(
                        f"⏭️ Received other notification (feature={hex(feature_id)}, action={hex(action_id)}), ignoring and continue waiting for config notification"
                    )
                    continue

                # Parse notification
                proto_data = notification_data[2:]
                notification = network_proto.NotifProvisioningState()
                notification.ParseFromString(proto_data)

                logger.debug(f"Received config notification: state={notification.provisioning_state}")

                state = notification.provisioning_state

                # Success state: return immediately
                if state in (
                    EnumProvisioning.PROVISIONING_SUCCESS_NEW_AP,
                    EnumProvisioning.PROVISIONING_SUCCESS_OLD_AP,
                ):
                    logger.info(
                        f"✅ WiFi connection successful! Status: {state} "
                        f"({'new network' if state == EnumProvisioning.PROVISIONING_SUCCESS_NEW_AP else 'configured network'})"
                    )
                    return

                # In-progress state: continue waiting
                if state == EnumProvisioning.PROVISIONING_STARTED:
                    logger.debug("⏳ WiFi configuration in progress...")
                    continue

                # Error state: throw exception immediately (cannot be caught by except below)
                if state in (
                    EnumProvisioning.PROVISIONING_ABORTED_BY_SYSTEM,
                    EnumProvisioning.PROVISIONING_CANCELLED_BY_USER,
                    EnumProvisioning.PROVISIONING_ERROR_FAILED_TO_ASSOCIATE,
                    EnumProvisioning.PROVISIONING_ERROR_PASSWORD_AUTH,
                    EnumProvisioning.PROVISIONING_ERROR_EULA_BLOCKING,
                    EnumProvisioning.PROVISIONING_ERROR_NO_INTERNET,
                    EnumProvisioning.PROVISIONING_ERROR_UNSUPPORTED_TYPE,
                ):
                    error_messages = {
                        EnumProvisioning.PROVISIONING_ABORTED_BY_SYSTEM: "Connection aborted by system",
                        EnumProvisioning.PROVISIONING_CANCELLED_BY_USER: "Connection cancelled by user",
                        EnumProvisioning.PROVISIONING_ERROR_FAILED_TO_ASSOCIATE: "Failed to associate to AP (signal too weak or AP unreachable)",
                        EnumProvisioning.PROVISIONING_ERROR_PASSWORD_AUTH: "Password authentication failed (incorrect password)",
                        EnumProvisioning.PROVISIONING_ERROR_EULA_BLOCKING: "EULA blocking (need to agree to user agreement)",
                        EnumProvisioning.PROVISIONING_ERROR_NO_INTERNET: "No internet connection",
                        EnumProvisioning.PROVISIONING_ERROR_UNSUPPORTED_TYPE: "Unsupported network type",
                    }
                    error_msg = error_messages.get(state, f"Unknown error (state={state})")
                    logger.error(f"❌ WiFi connection failed: {error_msg}")

                    # Create exception and mark as WiFi state error
                    exc = BleConnectionError(
                        f"WiFi '{ssid}' connection failed: {error_msg} (provisioning_state={state})"
                    )
                    exc._is_wifi_state_error = True  # type: ignore
                    raise exc

                # Other unknown states: log and continue waiting
                logger.debug(f"⚠️ Received unknown provisioning state: {state}, continue waiting...")
                continue

            except BleConnectionError as e:
                # Distinguish two types of BleConnectionError:
                # 1. WiFi state error (actively thrown) -> fail immediately
                # 2. wait_for_response timeout -> continue waiting

                if hasattr(e, "_is_wifi_state_error") and e._is_wifi_state_error:
                    # WiFi configuration failed, propagate immediately
                    raise

                # wait_for_response timeout, check overall timeout
                if loop.time() - start_time > timeout:
                    logger.warning(
                        f"⚠️ WiFi '{ssid}' configuration notification timeout. In COHN mode camera may have disconnected BLE, this is normal"
                    )
                    raise TimeoutError(f"WiFi '{ssid}' connection complete timeout") from None

                logger.debug("Waiting for config notification timeout (5 seconds), continue waiting...")
                continue

    async def connect_to_wifi(
        self,
        ssid: str,
        password: str,
        timeout: float | None = None,
        has_cohn_credentials: bool = False,
    ) -> None:
        """Connect to WiFi network (compliant with OpenGoPro official specification).

        **Correct workflow (official requirement)**:
        1. Scan WiFi networks
        2. Check target SSID's SCAN_FLAG_CONFIGURED flag
        3. Choose command based on flag:
           - Has CONFIGURED flag → RequestConnect (no password)
           - No CONFIGURED flag → RequestConnectNew (with password)

        Args:
            ssid: WiFi SSID
            password: WiFi password
            timeout: Connection timeout (seconds), defaults to configured value
            has_cohn_credentials: Whether has COHN credentials (for optimization: can skip scan when has credentials)

        Raises:
            BleConnectionError: Connection failed

        Reference: https://gopro.github.io/OpenGoPro/ble/features/access_points.html
        """
        if timeout is None:
            timeout = self._timeout.wifi_provision_timeout

        logger.info(
            f"📶 [camera {self.ble.target}] Starting WiFi connection workflow: ssid='{ssid}', "
            f"has_cohn_credentials={has_cohn_credentials}"
        )

        # Optimization: if has COHN credentials, try direct connection first (skip scan)
        if has_cohn_credentials:
            logger.info(
                f"✅ [camera {self.ble.target}] Detected COHN credentials, trying RequestConnect first (skip scan, quick detection)"
            )
            try:
                await self._connect_to_configured_wifi(ssid, timeout=self._timeout.wifi_connect_configured_timeout)
                logger.info(
                    f"✅ [camera {self.ble.target}] RequestConnect successful! Network configured, camera connected to '{ssid}'"
                )
                return
            except (BleConnectionError, TimeoutError) as e:
                logger.warning(
                    f"⚠️ [camera {self.ble.target}] RequestConnect failed: {e}\n"
                    f"Possible cause: Camera reset network config, fallback to full workflow"
                )
                # Continue with scan workflow below

        # Standard workflow: scan WiFi → check CONFIGURED flag → choose command
        logger.info(f"📡 [camera {self.ble.target}] Scanning WiFi networks...")
        try:
            networks = await self.scan_wifi_networks(timeout=self._timeout.wifi_scan_internal_timeout)
        except TimeoutError:
            logger.warning(
                f"⚠️ [camera {self.ble.target}] WiFi scan timeout, camera may be in STA mode, trying RequestConnectNew directly"
            )
            # Scan failed, use RequestConnectNew directly
            await self._connect_to_new_wifi(ssid, password, timeout)
            logger.info(f"✅ [camera {self.ble.target}] RequestConnectNew successful! Camera connected to '{ssid}'")
            return

        # Check if target SSID is configured
        target_network = next((n for n in networks if n["ssid"] == ssid), None)
        if not target_network:
            raise BleConnectionError(
                f"WiFi '{ssid}' not found in scan results, please check:\n"
                f"1. SSID name is correct\n"
                f"2. Router is powered on\n"
                f"3. Camera is not too far from router"
            )

        is_configured = target_network.get("configured", False)
        logger.info(
            f"🔍 [camera {self.ble.target}] WiFi '{ssid}' "
            f"{'configured (SCAN_FLAG_CONFIGURED)' if is_configured else 'not configured'}"
        )

        # Smart strategy:
        # 1. If configured → try RequestConnect first (fast, no password)
        # 2. If failed (state=7, wrong password) → fallback to RequestConnectNew (with password, update saved password)
        # 3. If not configured → use RequestConnectNew directly
        if is_configured:
            logger.info(f"📤 [camera {self.ble.target}] WiFi configured, trying RequestConnect (fast mode)")
            try:
                await self._connect_to_configured_wifi(ssid, timeout)
                logger.info(f"✅ [camera {self.ble.target}] RequestConnect successful! Camera connected to '{ssid}'")
                return
            except BleConnectionError as e:
                # Check if password error (state=7)
                if "provisioning_state=7" in str(e):
                    logger.warning(
                        f"⚠️ [camera {self.ble.target}] RequestConnect failed (wrong password), "
                        f"fallback to RequestConnectNew to update password"
                    )
                    # Continue with RequestConnectNew below
                else:
                    # Other errors, throw directly
                    raise

        # Use RequestConnectNew (with password)
        logger.info(f"📤 [camera {self.ble.target}] Using RequestConnectNew (with password)")
        await self._connect_to_new_wifi(ssid, password, timeout)
        logger.info(f"✅ [camera {self.ble.target}] RequestConnectNew successful! Camera connected to '{ssid}'")

    async def _connect_to_configured_wifi(self, ssid: str, timeout: int) -> None:
        """Connect to configured WiFi network (using RequestConnect).

        Args:
            ssid: WiFi SSID
            timeout: Connection timeout (seconds)

        Raises:
            BleConnectionError: Connection failed
        """
        request = network_proto.RequestConnect()
        request.ssid = ssid

        command = self._build_protobuf_command(FeatureId.NETWORK_MANAGEMENT, ActionId.REQUEST_WIFI_CONNECT, request)

        # Clear response queue
        self.ble.clear_response_queue()

        # Send connection command
        logger.info(f"📤 [camera {self.ble.target}] Sending RequestConnect command: ssid='{ssid}' (no password)")
        await self.ble.write(GoProBleUUID.CM_NET_MGMT_COMM, command)

        # Wait for initial response
        logger.debug(f"[camera {self.ble.target}] Waiting for RequestConnect initial response...")
        initial_response_data = await self.ble.wait_for_response(timeout=self._timeout.ble_response_timeout)
        if len(initial_response_data) < 2:
            raise BleConnectionError("RequestConnect initial response invalid (data too short)")

        # Parse initial response
        initial_proto_data = initial_response_data[2:]
        initial_response = network_proto.ResponseConnect()
        initial_response.ParseFromString(initial_proto_data)

        # Check result
        result_name = response_proto.EnumResultGeneric.Name(initial_response.result)
        provisioning_state_name = network_proto.EnumProvisioning.Name(initial_response.provisioning_state)

        logger.info(
            f"📥 [camera {self.ble.target}] RequestConnect initial response: "
            f"result={result_name} ({initial_response.result}), "
            f"state={provisioning_state_name} ({initial_response.provisioning_state}), "
            f"timeout={initial_response.timeout_seconds}s"
        )

        if initial_response.result != RESULT_SUCCESS:
            error_msg = (
                f"RequestConnect start failed: "
                f"result={result_name} ({initial_response.result}), "
                f"state={provisioning_state_name} ({initial_response.provisioning_state})"
            )
            logger.error(f"❌ [camera {self.ble.target}] {error_msg}")
            raise BleConnectionError(error_msg)

        logger.info(
            f"✅ [camera {self.ble.target}] RequestConnect command accepted by camera, "
            f"initial state={provisioning_state_name}, expected timeout={initial_response.timeout_seconds}s"
        )

        # Wait for connection complete notification
        logger.info(f"⏳ [camera {self.ble.target}] Waiting for WiFi connection complete (max {timeout}s)...")
        try:
            await self._wait_for_provisioning_complete(ssid, timeout=timeout)
            logger.info(
                f"✅ [camera {self.ble.target}] RequestConnect successful! WiFi connection confirmed via BLE notification: '{ssid}'"
            )
        except TimeoutError:
            logger.warning(
                f"⏱️ [camera {self.ble.target}] BLE notification timeout (camera may have disconnected BLE). "
                f"Note: In COHN mode camera will disconnect BLE, this is normal behavior"
            )

    async def _connect_to_new_wifi(self, ssid: str, password: str, timeout: int) -> None:
        """Connect to new WiFi network (using RequestConnectNew).

        Args:
            ssid: WiFi SSID
            password: WiFi password
            timeout: Connection timeout (seconds)

        Raises:
            BleConnectionError: Connection failed
        """
        request = network_proto.RequestConnectNew()
        request.ssid = ssid
        request.password = password
        request.bypass_eula_check = True  # Bypass EULA check

        command = self._build_protobuf_command(FeatureId.NETWORK_MANAGEMENT, ActionId.REQUEST_WIFI_CONNECT_NEW, request)

        # Clear response queue
        self.ble.clear_response_queue()

        # Send connection command (note: don't log password)
        logger.info(
            f"📤 [camera {self.ble.target}] Sending RequestConnectNew command: "
            f"ssid='{ssid}', password={'***' if password else '(empty)'}, "
            f"bypass_eula={request.bypass_eula_check}"
        )
        await self.ble.write(GoProBleUUID.CM_NET_MGMT_COMM, command)

        # Wait for initial response
        logger.debug(f"[camera {self.ble.target}] Waiting for RequestConnectNew initial response...")
        initial_response_data = await self.ble.wait_for_response(timeout=self._timeout.ble_response_timeout)
        if len(initial_response_data) < 2:
            raise BleConnectionError("RequestConnectNew initial response invalid (data too short)")

        # Parse initial response
        initial_proto_data = initial_response_data[2:]
        initial_response = network_proto.ResponseConnectNew()
        initial_response.ParseFromString(initial_proto_data)

        # Check result
        result_name = response_proto.EnumResultGeneric.Name(initial_response.result)
        provisioning_state_name = network_proto.EnumProvisioning.Name(initial_response.provisioning_state)

        logger.info(
            f"📥 [camera {self.ble.target}] RequestConnectNew initial response: "
            f"result={result_name} ({initial_response.result}), "
            f"state={provisioning_state_name} ({initial_response.provisioning_state}), "
            f"timeout={initial_response.timeout_seconds}s"
        )

        if initial_response.result != RESULT_SUCCESS:
            error_msg = (
                f"RequestConnectNew start failed: "
                f"result={result_name} ({initial_response.result}), "
                f"state={provisioning_state_name} ({initial_response.provisioning_state})"
            )
            logger.error(f"❌ [camera {self.ble.target}] {error_msg}")
            raise BleConnectionError(error_msg)

        logger.info(
            f"✅ [camera {self.ble.target}] RequestConnectNew command accepted by camera, "
            f"initial state={provisioning_state_name}, expected timeout={initial_response.timeout_seconds}s"
        )

        # Wait for connection complete notification
        logger.info(f"⏳ [camera {self.ble.target}] Waiting for WiFi connection complete (max {timeout}s)...")
        try:
            await self._wait_for_provisioning_complete(ssid, timeout=timeout)
            logger.info(
                f"✅ [camera {self.ble.target}] RequestConnectNew successful! WiFi connection confirmed via BLE notification: '{ssid}'"
            )
        except TimeoutError:
            logger.info(
                f"⏱️ BLE notification timeout (camera may have disconnected BLE), will verify WiFi connection status via HTTP: {ssid}"
            )

    async def enable_wifi_ap(self, enable: bool) -> None:
        """Enable/disable WiFi access point.

        Args:
            enable: True to enable, False to disable

        Raises:
            BleConnectionError: Command failed
        """
        # BLE write command, implementation requires SDK reference
        # Will be implemented when needed
        raise NotImplementedError("enable_wifi_ap command not yet implemented")

    async def get_hardware_info(self) -> dict[str, Any]:
        """Get hardware information.

        Returns:
            Hardware information dictionary

        Raises:
            BleConnectionError: Command failed
        """
        # BLE write command, implementation requires SDK reference
        # Will be implemented when needed
        raise NotImplementedError("get_hardware_info command not yet implemented")
