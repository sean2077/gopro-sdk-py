"""BLE scanner

Used to discover nearby GoPro camera devices.
"""

from __future__ import annotations

__all__ = ["BleScanner"]

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from bleak import BleakScanner

from ..ble_uuid import GoProBleUUID

logger = logging.getLogger(__name__)


class BleScanner:
    """BLE scanner

    Used to discover nearby GoPro camera devices.
    """

    @staticmethod
    async def scan_devices_stream(
        duration: float = 8.0,
        idle_timeout: float = 2.0,
        target_count: int | None = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Stream scan for GoPro devices

        Args:
            duration: Maximum scan time (seconds)
            idle_timeout: Idle timeout (seconds), ends early if no new devices after this time
            target_count: Target device count, ends early when reached

        Yields:
            Device list, each device is a {"name": str, "address": str} dictionary

        Usage example:
        ```python
        async for devices in BleScanner.scan_devices_stream(duration=8.0):
            for dev in devices:
                print(f"Discovered: {dev['name']}")
        ```
        """
        end_time = time.monotonic() + duration
        discovered: dict[str, dict[str, Any]] = {}  # address -> device_info
        last_discovery_time = time.monotonic()

        logger.info(f"Starting BLE scan (max {duration}s, idle timeout {idle_timeout}s)")

        try:
            async with BleakScanner(
                service_uuids=[GoProBleUUID.S_CONTROL_QUERY]  # GoPro service UUID
            ) as scanner:
                while time.monotonic() < end_time:
                    # Check idle timeout
                    if (time.monotonic() - last_discovery_time) > idle_timeout:
                        logger.debug(f"Idle for more than {idle_timeout}s, ending scan early")
                        break

                    # Check target count
                    if target_count and len(discovered) >= target_count:
                        logger.debug(f"Discovered {target_count} devices, ending scan early")
                        break

                    # Read advertisement data
                    try:
                        async for (
                            device,
                            advertisement_data,
                        ) in scanner.advertisement_data():
                            if device.address not in discovered:
                                # Extract device name (format: GoPro XXXX)
                                device_name = advertisement_data.local_name or device.name or ""

                                if device_name.startswith("GoPro"):
                                    device_info = {
                                        "name": device_name,
                                        "address": device.address,
                                    }
                                    discovered[device.address] = device_info
                                    last_discovery_time = time.monotonic()

                                    logger.debug(f"Discovered GoPro: {device_name} ({device.address})")

                                    # Immediately yield newly discovered device
                                    yield [device_info]

                                    # Check if target count reached
                                    if target_count and len(discovered) >= target_count:
                                        logger.debug(f"Discovered {target_count} devices, ending scan early")
                                        return

                            # Quick check timeout
                            if time.monotonic() >= end_time:
                                break

                            # Yield to event loop
                            await asyncio.sleep(0)

                    except Exception as e:
                        logger.debug(f"Exception reading advertisement data: {e}")
                        await asyncio.sleep(0.1)
                        continue

                    await asyncio.sleep(0.1)  # Avoid too frequent loops

        except Exception as e:
            logger.error(f"BLE scan exception: {e}")

        logger.info(f"BLE scan complete, discovered {len(discovered)} devices")

    @staticmethod
    async def scan_devices(duration: float = 8.0) -> list[dict[str, Any]]:
        """One-time scan for GoPro devices

        Args:
            duration: Scan time (seconds)

        Returns:
            Device list, each device is a {"name": str, "address": str} dictionary

        Usage example:
        ```python
        devices = await BleScanner.scan_devices(duration=5.0)
        for dev in devices:
            print(f"Discovered: {dev['name']}")
        ```
        """
        devices = []
        async for batch in BleScanner.scan_devices_stream(
            duration=duration,
            idle_timeout=duration,  # Don't end early
            target_count=None,
        ):
            devices.extend(batch)
        return devices

    @staticmethod
    async def scan_serials_stream(
        duration: float = 8.0,
        idle_timeout: float = 2.0,
        target_count: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream scan for GoPro serial numbers

        Args:
            duration: Maximum scan time (seconds)
            idle_timeout: Idle timeout (seconds)
            target_count: Target count

        Yields:
            Camera serial number (extracted from device name)

        Usage example:
        ```python
        async for serial in BleScanner.scan_serials_stream(duration=8.0):
            print(f"Discovered serial number: {serial}")
        ```
        """
        seen_serials: set[str] = set()

        async for devices in BleScanner.scan_devices_stream(
            duration=duration,
            idle_timeout=idle_timeout,
            target_count=target_count,
        ):
            for dev in devices:
                # Extract serial number from device name (format: GoPro XXXX)
                name = dev.get("name", "")
                if " " in name:
                    serial = name.split()[-1]
                    if serial and serial not in seen_serials:
                        seen_serials.add(serial)
                        yield serial

    @staticmethod
    async def scan_serials(duration: float = 8.0) -> list[str]:
        """One-time scan for GoPro serial numbers

        Args:
            duration: Scan time (seconds)

        Returns:
            Serial number list

        Usage example:
        ```python
        serials = await BleScanner.scan_serials(duration=5.0)
        print(f"Discovered {len(serials)} cameras")
        ```
        """
        serials = []
        async for serial in BleScanner.scan_serials_stream(
            duration=duration,
            idle_timeout=duration,
            target_count=None,
        ):
            serials.append(serial)
        return serials
