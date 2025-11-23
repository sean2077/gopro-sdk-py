"""Multi-camera example: Control multiple GoPro cameras simultaneously.

This example demonstrates:
- Connecting to multiple cameras
- Synchronizing recording across all cameras
- Getting status from all cameras
- Handling cameras gracefully
"""

import asyncio
import logging

from gopro_sdk import MultiCameraManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main example function for multi-camera control."""
    # Define your cameras with identifiers
    camera_ids = {
        "cam1": "1234",  # GoPro 1234
        "cam2": "5678",  # GoPro 5678
        "cam3": "9012",  # GoPro 9012
    }

    # Your WiFi credentials (same for all cameras)
    wifi_ssid = "your-wifi-ssid"
    wifi_password = "your-wifi-password"

    # Create manager
    manager = MultiCameraManager()

    try:
        logger.info("Connecting to all cameras...")
        await manager.connect_all(camera_ids, wifi_ssid, wifi_password)
        logger.info("All cameras connected!")

        # Get status from all cameras
        logger.info("Getting status from all cameras...")
        statuses = await manager.get_all_status()
        for cam_id, status in statuses.items():
            battery = status.get("battery_percent", "unknown")
            logger.info(f"{cam_id}: Battery {battery}%")

        # Start recording on all cameras
        logger.info("Starting recording on all cameras...")
        await manager.execute_all("set_shutter", on=True)
        logger.info("Recording started!")

        # Record for 10 seconds
        logger.info("Recording for 10 seconds...")
        await asyncio.sleep(10)

        # Stop recording on all cameras
        logger.info("Stopping recording on all cameras...")
        await manager.execute_all("set_shutter", on=False)
        logger.info("Recording stopped!")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        logger.info("Disconnecting all cameras...")
        await manager.disconnect_all()
        logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
