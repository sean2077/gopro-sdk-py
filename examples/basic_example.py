"""Basic example: Connect to a single GoPro camera via BLE and control recording.

This example demonstrates:
- Connecting to a GoPro via BLE (offline mode)
- Syncing camera date/time
- Starting/stopping recording

Prerequisites:
    For first-time pairing, enable pairing mode on your GoPro:
    See: https://community.gopro.com/s/article/GoPro-Quik-How-To-Pair-Your-Camera?language=en_US

Usage:
    python basic_example.py 1234
"""

import argparse
import asyncio
import logging

from gopro_sdk import GoProClient, setup_logging

# Enable logging with rich formatting
setup_logging(level=logging.INFO)

logger = logging.getLogger(__name__)


async def async_main(camera_identifier: str):
    """Connect to camera and control recording via BLE."""
    async with GoProClient(target=camera_identifier, offline_mode=True) as client:
        logger.info("Connected to camera via BLE (offline mode)!")

        # Sync camera date/time
        logger.info("Syncing camera date/time...")
        await client.set_date_time()
        logger.info("Date/time synced!")

        # Start recording
        logger.info("Starting recording...")
        await client.start_recording()
        logger.info("Recording started!")

        # Record for a few seconds
        logger.info("Recording for 5 seconds...")
        await asyncio.sleep(5)

        # Stop recording
        logger.info("Stopping recording...")
        await client.stop_recording()
        logger.info("Recording stopped!")


def main():
    """Connect to a GoPro camera via BLE and control recording."""
    parser = argparse.ArgumentParser(description="Connect to a GoPro camera via BLE and control recording")
    parser.add_argument(
        "identifier",
        help="Camera identifier (last 4 digits of camera name, e.g., '1234' for 'GoPro 1234')",
    )
    args = parser.parse_args()

    asyncio.run(async_main(args.identifier))


if __name__ == "__main__":
    main()
