"""Basic example: Connect to a single GoPro camera and take a photo.

This example demonstrates:
- Connecting to a GoPro via BLE
- Configuring COHN (Camera on Home Network)
- Taking a photo
- Getting camera status
"""

import asyncio
import logging

from gopro_sdk import GoProClient

# Enable logging to see what's happening
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


async def main():
    """Main example function."""
    # Replace with your camera's identifier (last 4 digits of the name)
    # e.g., if your camera is named "GoPro 1234", use "1234"
    camera_identifier = "1234"

    # Your WiFi credentials
    wifi_ssid = "your-wifi-ssid"
    wifi_password = "your-wifi-password"

    # Create client
    client = GoProClient(identifier=camera_identifier)

    try:
        logger.info("Connecting to camera via BLE...")
        await client.open_ble()
        logger.info("Connected!")

        logger.info("Configuring COHN...")
        await client.configure_cohn(ssid=wifi_ssid, password=wifi_password)

        logger.info("Waiting for COHN to be ready...")
        await client.wait_cohn_ready(timeout=30)
        logger.info("COHN is ready!")

        # Get camera status
        logger.info("Getting camera status...")
        status = await client.get_camera_state()
        logger.info(f"Battery: {status.get('battery_percent')}%")
        logger.info(f"SD card space: {status.get('space_remaining')} MB")

        # Take a photo
        logger.info("Taking a photo...")
        await client.set_shutter(on=True)
        await asyncio.sleep(2)  # Wait for photo to be captured
        logger.info("Photo taken!")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        logger.info("Closing connection...")
        await client.close()
        logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
