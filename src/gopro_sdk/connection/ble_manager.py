"""BLE connection manager.

Responsible for establishing, disconnecting, and managing BLE connections.

Implementation based on official Tutorial, directly using bleak's BleakClient.
"""

from __future__ import annotations

__all__ = ["BleConnectionManager"]

import asyncio
import contextlib
import logging
import re
import traceback
from typing import Any

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice as BleakDevice

from ..ble_uuid import GoProBleUUID
from ..config import TimeoutConfig
from ..exceptions import BleConnectionError

logger = logging.getLogger(__name__)

# GoPro BLE protocol constants (reference: Open GoPro SDK)
CONT_MASK = 0x80  # 0b10000000 - bit 7: continuation flag
HDR_MASK = 0x60  # 0b01100000 - bit 6-5: header type
GEN_LEN_MASK = 0x1F  # 0b00011111 - bit 4-0: length for general header
EXT_13_BYTE0_MASK = 0x1F  # 0b00011111 - bit 4-0: high bits for 13-bit length

# BLE header type constants (official Open GoPro protocol)
HEADER_TYPE_GENERAL = 0  # 0b00: General header (5-bit length, max 31 bytes)
HEADER_TYPE_EXT_13 = 1  # 0b01: Extended 13-bit header (max 8191 bytes)
HEADER_TYPE_EXT_16 = 2  # 0b10: Extended 16-bit header (max 65535 bytes)

# BLE header encoding constants (used for constructing packet headers)
HEADER_EXT_13_PREFIX = 0x20  # 0b00100000: Extended 13-bit header prefix
HEADER_EXT_16_PREFIX = 0x40  # 0b01000000: Extended 16-bit header prefix
CONTINUATION_HEADER = 0x80  # 0b10000000: Continuation packet header


class BleConnectionManager:
    """BLE connection manager.

    Responsibilities:
    - Establish and disconnect BLE connections
    - Accumulate BLE response fragments
    - Handle BLE notification callbacks
    """

    def __init__(self, target: str, timeout_config: TimeoutConfig) -> None:
        """Initialize BLE connection manager.

        Args:
            target: Last four digits of camera serial number
            timeout_config: Timeout configuration
        """
        self.target = target
        self._timeout = timeout_config

        # Capture current event loop reference (for cross-thread calls)
        # Note: This object must be created after event loop is set up (after asyncio.set_event_loop)
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            # If no running loop, fall back to get_event_loop()
            # This is normal during app.py initialization (event loop is set but not running)
            self._loop = asyncio.get_event_loop()

        # BLE client (directly using bleak's BleakClient)
        self._ble_client: BleakClient | None = None
        self._ble_device: BleakDevice | None = None
        self._ble_lock = asyncio.Lock()

        # BLE response handling
        self._response_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._accumulating_response: bytearray = bytearray()
        self._bytes_remaining: int = 0

        # Fragment header buffer (for handling truncated header cases)
        self._header_buffer: bytearray = bytearray()

        # State
        self._is_connected = False
        self._disconnect_count = 0

    @property
    def is_connected(self) -> bool:
        """Whether BLE is connected."""
        return self._is_connected

    async def connect(self) -> None:
        """Establish BLE connection.

        Implementation based on official Tutorial, directly using bleak's BleakScanner and BleakClient.

        Raises:
            BleConnectionError: BLE connection failed
        """
        async with self._ble_lock:
            if self._is_connected:
                logger.debug(f"Camera {self.target} BLE already connected, skip")
                return

            retries = 3
            for retry in range(retries):
                try:
                    logger.info(f"Starting BLE connection to camera {self.target} (attempt {retry + 1}/{retries})...")

                    # Cleanup before retry: ensure no leftover client
                    if retry > 0 and self._ble_client is not None:
                        with contextlib.suppress(Exception):
                            logger.debug("Cleaning up failed connection...")
                            if self._ble_client.is_connected:
                                await self._ble_client.disconnect()
                            self._ble_client = None
                            # Give Windows more time to clean up
                            await asyncio.sleep(2.0)

                    # 1. Scan devices (based on Tutorial)
                    devices: dict[str, BleakDevice] = {}
                    device_pattern = re.compile(f"GoPro {self.target}")

                    def _scan_callback(device: BleakDevice, _: Any) -> None:
                        """Scan callback to collect devices"""
                        if device.name and device.name != "Unknown":
                            devices[device.name] = device  # noqa: B023

                    logger.info("Scanning for GoPro devices...")
                    matched_devices: list[BleakDevice] = []

                    # Keep scanning until matching devices are found
                    while len(matched_devices) == 0:
                        # Scan devices (with service UUID filter)
                        discovered = await BleakScanner.discover(
                            timeout=self._timeout.ble_discovery_timeout,
                            detection_callback=_scan_callback,
                            service_uuids=[GoProBleUUID.S_CONTROL_QUERY],  # GoPro service UUID
                        )

                        # Add scanned devices
                        for device in discovered:
                            if device.name and device.name != "Unknown":
                                devices[device.name] = device

                        # Log discovered devices
                        for name in devices:
                            logger.debug(f"  Found device: {name}")

                        # Find matching devices
                        matched_devices = [device for name, device in devices.items() if device_pattern.match(name)]

                        if matched_devices:
                            logger.info(f"✅ Found {len(matched_devices)} matching device(s)")
                            break
                        else:
                            logger.warning("No matching devices found, continuing scan...")

                    # 2. Connect to first matching device
                    self._ble_device = matched_devices[0]
                    logger.info(f"Connecting to device: {self._ble_device.name} ({self._ble_device.address})")

                    # Windows-specific: destroy previous client instance if exists
                    if self._ble_client is not None:
                        with contextlib.suppress(Exception):
                            if self._ble_client.is_connected:
                                logger.debug("Destroying old BLE client...")
                                await self._ble_client.disconnect()
                            self._ble_client = None
                            await asyncio.sleep(1.0)

                    # Create new BLE client (with longer timeout)
                    # Pass disconnection callback directly in constructor
                    self._ble_client = BleakClient(
                        self._ble_device,
                        disconnected_callback=lambda c: self._on_disconnected(c),
                        timeout=20.0,  # Increase service discovery timeout to 20 seconds
                    )

                    logger.debug("Starting BLE connection...")

                    # Critical fix: increase connection timeout, give Windows BLE more time to process
                    connect_timeout = max(self._timeout.ble_connect_timeout, 20.0)  # At least 20 seconds

                    try:
                        await self._ble_client.connect(timeout=connect_timeout)
                    except Exception:
                        # On connection failure, log more debug information
                        logger.debug(f"BLE connection failed, device address: {self._ble_device.address}")
                        logger.debug(f"is_connected status: {self._ble_client.is_connected}")
                        raise
                    logger.info("✅ BLE connected")

                    # Slight delay after connection to ensure connection is fully established
                    await asyncio.sleep(1.0)

                    # 3. Pair (required on all systems, as enabling notifications requires authentication)
                    logger.info("Attempting to pair...")
                    try:
                        await self._ble_client.pair()
                        logger.info("✅ Pairing completed")
                        await asyncio.sleep(0.5)
                    except NotImplementedError:
                        logger.debug("Pairing not supported (expected behavior, e.g., on Mac)")
                    except Exception as e:
                        # Pairing failure is not necessarily fatal, continue trying
                        logger.warning(f"Pairing failed (attempting to continue): {e}")

                    # 4. Enable notifications for all notifiable characteristics
                    logger.info("Enabling notifications...")

                    def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
                        """Notification callback adapter"""
                        self._on_notification(characteristic.handle, bytes(data))

                    # 4.1 Before enabling notifications, confirm connection is still valid
                    if not self._ble_client.is_connected:
                        raise BleConnectionError(
                            "BLE connection disconnected after pairing, unable to enable notifications"
                        )

                    for service in self._ble_client.services:
                        for char in service.characteristics:
                            if "notify" in char.properties:
                                logger.debug(f"  Enabling notifications: {char.uuid}")
                                await self._ble_client.start_notify(
                                    char,
                                    notification_handler,
                                )

                    logger.info("✅ Notifications enabled")
                    logger.info(f"✅ Camera {self.target} BLE connection ready")

                    self._is_connected = True
                    return  # Success, exit retry loop

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Connection failed (attempt {retry + 1}/{retries}): {error_msg}")
                    logger.debug(f"Detailed error information:\n{traceback.format_exc()}")

                    # Clean up failed connection
                    with contextlib.suppress(Exception):
                        if self._ble_client and self._ble_client.is_connected:
                            await self._ble_client.disconnect()
                        self._ble_client = None

                    # Provide brief hints for common errors
                    if "Unreachable" in error_msg:
                        logger.warning(f"💡 Hint: Unable to reach camera {self.target}, try restarting the camera")
                    elif "authentication" in error_msg or "authentication" in error_msg.lower():
                        logger.warning(
                            "💡 Hint: Pairing failed, may need to remove the device from system Bluetooth settings"
                        )

                    if retry < retries - 1:
                        # Increase retry wait time, give Windows BLE more time to clean cache
                        wait_time = 3 + retry  # 3 seconds, 4 seconds, 5 seconds incremental
                        logger.info(f"Waiting {wait_time} seconds before retry...")
                        await asyncio.sleep(wait_time)
                    else:
                        msg = f"Camera {self.target} BLE connection failed (retried {retries} times)"
                        logger.error(msg)
                        raise BleConnectionError(msg) from e

    async def disconnect(self) -> None:
        """Disconnect BLE connection."""
        async with self._ble_lock:
            if not self._is_connected:
                logger.debug(f"Camera {self.target} BLE not connected, skip")
                return

            try:
                if self._ble_client:
                    await self._ble_client.disconnect()
                    self._ble_client = None

                self._is_connected = False
                logger.info(f"Camera {self.target} BLE disconnected")

            except Exception as e:
                logger.warning(f"Error disconnecting camera {self.target} BLE: {e}")

    def _on_disconnected(self, client: BleakClient) -> None:
        """BLE disconnection callback.

        Args:
            client: BleakClient instance
        """
        self._disconnect_count += 1
        logger.warning(
            f"Camera {self.target} BLE connection unexpectedly disconnected ({self._disconnect_count} time(s))"
        )
        self._is_connected = False

    def _on_notification(self, handle: int, data: bytes) -> None:
        """BLE notification callback.

        Handles GoPro BLE response fragment accumulation.

        GoPro BLE packet format (reference: Open GoPro SDK):
        - Bit 7: Continuation flag (0=new packet, 1=continuation packet)
        - Bit 6-5: Header type (00=General, 01=Extended 13-bit, 10=Extended 16-bit)
        - Bit 4-0: Data length (depends on header type)

        Important: Use 0x60 (0b01100000) instead of 0xE0 to extract header type,
                  because bit 7 is the continuation flag, not part of the header type.

        Improvement: Added header buffer mechanism to handle edge cases where the BLE stack
                    sends incomplete headers. This situation is not handled in the official SDK,
                    but may occur with Windows BLE drivers or under high camera load.
        """
        buf = bytearray(data)
        logger.debug(f"📦 Received BLE notification (handle={handle}): {len(data)} bytes")

        # Packet length validation
        if len(buf) == 0:
            logger.warning("⚠️ Received empty packet, ignoring")
            return

        # If there's a pending header buffer, try to complete it first
        if self._header_buffer:
            logger.debug(f"  🔄 Detected header buffer: {len(self._header_buffer)} bytes, attempting to complete...")
            self._header_buffer.extend(buf)
            buf = self._header_buffer
            self._header_buffer = bytearray()  # Clear buffer

        # Check if this is a continuation packet (bit 7 = 1)
        if buf[0] & CONT_MASK:  # Continuation packet
            buf = buf[1:]
            self._accumulating_response.extend(buf)
            self._bytes_remaining -= len(buf)
            logger.debug(f"  ↪️ Continuation packet: +{len(buf)} bytes, {self._bytes_remaining} bytes remaining")
        else:
            # New packet: parse header (only use bit 6-5, not including bit 7)
            self._accumulating_response = bytearray()
            header_type = (buf[0] & HDR_MASK) >> 5

            if header_type == HEADER_TYPE_GENERAL:
                self._bytes_remaining = buf[0] & GEN_LEN_MASK
                buf = buf[1:]
                logger.debug(f"  🆕 New packet (General): length {self._bytes_remaining} bytes")
            elif header_type == HEADER_TYPE_EXT_13:
                if len(buf) < 2:
                    # Header incomplete, buffer it and wait for next notification
                    logger.debug(f"  ⏸️ Extended 13-bit header incomplete ({len(buf)}/2 bytes), buffering: {buf.hex()}")
                    self._header_buffer = buf
                    return
                self._bytes_remaining = ((buf[0] & EXT_13_BYTE0_MASK) << 8) | buf[1]
                buf = buf[2:]
                # Large packets (>1KB) are usually status notifications, reduce log level
                if self._bytes_remaining > 1024:
                    logger.debug(
                        f"  🆕 New packet (Extended 13-bit): length {self._bytes_remaining} bytes (status notification)"
                    )
                else:
                    logger.debug(f"  🆕 New packet (Extended 13-bit): length {self._bytes_remaining} bytes")
            elif header_type == HEADER_TYPE_EXT_16:
                if len(buf) < 3:
                    # Header incomplete, buffer it and wait for next notification
                    logger.debug(f"  ⏸️ Extended 16-bit header incomplete ({len(buf)}/3 bytes), buffering: {buf.hex()}")
                    self._header_buffer = buf
                    return
                self._bytes_remaining = (buf[1] << 8) | buf[2]
                buf = buf[3:]
                logger.debug(f"  🆕 New packet (Extended 16-bit): length {self._bytes_remaining} bytes")
            else:
                logger.warning(
                    f"⚠️ Unknown header type: {header_type} (bit 6-5 = 0b{header_type:02b}, data: {buf.hex()})"
                )
                return

            self._accumulating_response.extend(buf)
            self._bytes_remaining -= len(buf)

        # Check if reception is complete
        if self._bytes_remaining < 0:
            logger.error(
                f"❌ Received too much data! Remaining bytes: {self._bytes_remaining} (parsing state abnormal)"
            )
            # Reset state
            self._accumulating_response = bytearray()
            self._bytes_remaining = 0
        elif self._bytes_remaining == 0:
            complete_data = bytes(self._accumulating_response)
            logger.debug(f"  ✅ Response complete: {len(complete_data)} bytes")

            # Use thread-safe method to put data into queue
            # In GUI environment (qasync), BLE callbacks may run in different threads
            # Use event loop reference saved during initialization to avoid calling get_event_loop() in callback thread
            try:
                logger.debug(f"  📤 Using event loop {self._loop} to put data into queue (thread-safe)")
                # call_soon_threadsafe ensures execution in the correct event loop
                self._loop.call_soon_threadsafe(self._put_response_safe, complete_data)
            except Exception as e:
                logger.error(f"  ❌ Failed to put into queue: {e}, falling back to direct put_nowait", exc_info=True)
                try:
                    self._response_queue.put_nowait(complete_data)
                    logger.debug("  ✅ Response put into queue (direct)")
                except asyncio.QueueFull:
                    logger.warning("  ⚠️ Response queue full, discarding response")

            self._accumulating_response = bytearray()
            self._bytes_remaining = 0

    def _put_response_safe(self, data: bytes) -> None:
        """Thread-safely put response into queue (called by call_soon_threadsafe)"""
        try:
            self._response_queue.put_nowait(data)
            logger.debug(f"  ✅ Response put into queue (thread-safe): {len(data)} bytes")
        except asyncio.QueueFull:
            logger.warning(f"  ⚠️ Response queue full, discarding response: {len(data)} bytes")

    async def wait_for_response(self, timeout: float | None = None) -> bytes:
        """Wait for BLE response.

        Args:
            timeout: Timeout in seconds, None means use default timeout

        Returns:
            Response data

        Raises:
            BleConnectionError: Wait timeout
        """
        timeout = timeout or self._timeout.ble_read_timeout
        try:
            return await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
        except TimeoutError as e:
            raise BleConnectionError("BLE response wait timeout") from e

    def _fragment(self, data: bytes) -> list[bytes]:
        """Fragment data into BLE packets (max 20 bytes).

        Reference: open_gopro.domain.communicator_interface.GoProBle._fragment()

        Note: For consistency with the official SDK, always use the Extended 13-bit header,
        not the General 5-bit header. This follows the official SDK implementation.

        GoPro BLE packet format:
        - First packet: Extended 13-bit header (2 bytes) + payload (up to 18 bytes)
        - Subsequent packets: Continuation header (0x80, 1 byte) + payload (up to 19 bytes)

        Args:
            data: Data to fragment

        Returns:
            List of fragmented packets

        Raises:
            ValueError: Data too long
        """
        max_ble_pkt_len = 20  # BLE MTU limit
        data_len = len(data)

        # Select header type (consistent with official SDK)
        if data_len < 8192:  # 13 bits: 2^13 = 8192
            # Extended 13-bit header: 2 bytes
            # Byte 0: bit 7=0, bit 6-5=01, bit 4-0=length[12:8]
            # Byte 1: length[7:0]
            header = bytes([HEADER_EXT_13_PREFIX | ((data_len >> 8) & 0x1F), data_len & 0xFF])
        elif data_len < 65536:  # 16 bits: 2^16 = 65536
            # Extended 16-bit header: 3 bytes
            # Byte 0: bit 7=0, bit 6-5=10, bit 4-0=padding
            # Byte 1: length[15:8]
            # Byte 2: length[7:0]
            header = bytes([HEADER_EXT_16_PREFIX, (data_len >> 8) & 0xFF, data_len & 0xFF])
        else:
            raise ValueError(f"Data length {data_len} too long (max 65535 bytes)")

        packets = []
        remaining_data = data

        # First packet: header + payload
        first_packet_payload_size = max_ble_pkt_len - len(header)
        first_packet = bytearray(header)
        first_packet.extend(remaining_data[:first_packet_payload_size])
        packets.append(bytes(first_packet))
        remaining_data = remaining_data[first_packet_payload_size:]

        # Subsequent packets: continuation header + payload
        while remaining_data:
            packet = bytearray([CONTINUATION_HEADER])
            packet.extend(remaining_data[: max_ble_pkt_len - 1])
            packets.append(bytes(packet))
            remaining_data = remaining_data[max_ble_pkt_len - 1 :]

        logger.debug(f"Data fragmented: {data_len} bytes → {len(packets)} packet(s)")
        return packets

    async def write(self, uuid: str, data: bytes) -> None:
        """Write BLE data (automatic fragmentation).

        Args:
            uuid: Characteristic UUID string (standard format: 8-4-4-4-12)
            data: Data to write

        Raises:
            BleConnectionError: Write failed
        """
        if not self._ble_client:
            raise BleConnectionError("BLE not connected")

        logger.debug(f"📤 Writing BLE data to {uuid}: {len(data)} bytes")

        # Fragment and send one by one
        packets = self._fragment(data)
        for i, packet in enumerate(packets, 1):
            logger.debug(f"  Sending packet {i}/{len(packets)}: {len(packet)} bytes")
            # Use bleak's write_gatt_char (based on Tutorial)
            await self._ble_client.write_gatt_char(uuid, packet, response=True)

    def clear_response_queue(self) -> None:
        """Clear response queue."""
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
