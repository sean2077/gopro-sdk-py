"""COHN configuration example with persistent storage.

This example demonstrates:
- Saving COHN configuration to disk
- Loading saved configuration
- Avoiding reconfiguration on subsequent runs
"""

import asyncio
import logging
from pathlib import Path

from gopro_sdk import CohnConfigManager, GoProClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main example function for COHN configuration."""
    camera_identifier = "1234"
    wifi_ssid = "your-wifi-ssid"
    wifi_password = "your-wifi-password"

    # Create config manager with custom cache directory
    cache_dir = Path.home() / ".gopro_sdk_cache"
    config_manager = CohnConfigManager(cache_dir=cache_dir)

    # Create client
    client = GoProClient(identifier=camera_identifier)

    try:
        # Try to load saved configuration
        saved_config = config_manager.load_config(camera_identifier)

        logger.info("Connecting to camera via BLE...")
        await client.open_ble()

        if saved_config:
            logger.info("Found saved COHN configuration, applying...")
            await client.apply_cohn_config(saved_config)
        else:
            logger.info("No saved configuration found, configuring COHN...")
            cohn_config = await client.configure_cohn(ssid=wifi_ssid, password=wifi_password)
            # Save for next time
            config_manager.save_config(camera_identifier, cohn_config)
            logger.info(f"COHN configuration saved to: {config_manager.get_config_path(camera_identifier)}")

        logger.info("Waiting for COHN to be ready...")
        await client.wait_cohn_ready(timeout=30)
        logger.info("COHN is ready!")

        # Now you can use the camera
        status = await client.get_camera_state()
        logger.info(f"Camera status: Battery {status.get('battery_percent')}%")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
