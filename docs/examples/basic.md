# Basic Usage Examples

This page provides basic examples for getting started with the GoPro SDK.

## Simple Connection

!!! example "Basic Camera Connection"

    === "With Context Manager (Recommended)"

        ```python
        import asyncio
        from gopro_sdk import GoProClient

        async def main():
            # Create client with last 4 digits of camera name
            async with GoProClient(target="1234", offline_mode=False) as client:
                print("Connected to camera")

                # Get camera status
                status = await client.get_camera_state()
                print(f"Battery: {status.get('battery_percent')}%")
                print(f"Recording: {status.get('is_recording')}")
                # Connection closed automatically

        if __name__ == "__main__":
            asyncio.run(main())
        ```

    === "Manual Connection"

        ```python
        import asyncio
        from gopro_sdk import GoProClient

        async def main():
            # Create client with last 4 digits of camera name
            client = GoProClient(target="1234", offline_mode=False)

            try:
                # Connect via BLE
                await client.open_ble()
                print("Connected to camera")

                # Get camera status
                status = await client.get_camera_state()
                print(f"Battery: {status.get('battery_percent')}%")
                print(f"Recording: {status.get('is_recording')}")

            finally:
                # Always close the connection
                await client.close()

        if __name__ == "__main__":
            asyncio.run(main())
        ```

    !!! warning "Parameter Names"
        Use `target` (not `identifier`) and `offline_mode` (not `offline`) as parameter names.

## Recording Video

Start and stop video recording:

```python
import asyncio
from gopro_sdk import GoProClient

async def record_video(duration: int = 10):
    """Record video for specified duration in seconds."""
    client = GoProClient(identifier="1234")

    try:
        await client.open_ble()

        # Configure COHN for faster commands
        await client.configure_cohn(
            ssid="your-wifi-ssid",
            password="your-wifi-password"
        )
        await client.wait_cohn_ready(timeout=30)

        # Start recording
        print("Starting recording...")
        await client.set_shutter(on=True)

        # Record for specified duration
        await asyncio.sleep(duration)

        # Stop recording
        print("Stopping recording...")
        await client.set_shutter(on=False)

        print(f"Recorded {duration} seconds of video")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(record_video(duration=10))
```

## Taking Photos

Capture a single photo:

```python
import asyncio
from gopro_sdk import GoProClient

async def take_photo():
    """Take a single photo."""
    client = GoProClient(identifier="1234")

    try:
        await client.open_ble()
        await client.configure_cohn("wifi-ssid", "password")
        await client.wait_cohn_ready()

        # Take photo (shutter on then immediately off)
        print("Taking photo...")
        await client.set_shutter(on=True)
        await asyncio.sleep(0.5)  # Brief delay
        await client.set_shutter(on=False)

        print("Photo captured")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(take_photo())
```

## Custom Settings

Configure camera settings before recording:

```python
import asyncio
from gopro_sdk import GoProClient
from open_gopro.models.constants.settings import VideoResolution, VideoFPS

async def record_with_settings():
    """Record with custom video settings."""
    client = GoProClient(identifier="1234")

    try:
        await client.open_ble()
        await client.configure_cohn("wifi-ssid", "password")
        await client.wait_cohn_ready()

        # Set video resolution
        await client.set_video_resolution(VideoResolution.RES_4K)

        # Set frame rate
        await client.set_video_fps(VideoFPS.FPS_30)

        print("Settings configured")

        # Start recording with new settings
        await client.set_shutter(on=True)
        await asyncio.sleep(5)
        await client.set_shutter(on=False)

        print("Recording complete with 4K@30fps")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(record_with_settings())
```

## Media Management

List and download media files:

```python
import asyncio
from gopro_sdk import GoProClient
from pathlib import Path

async def download_latest():
    """Download the latest media file."""
    client = GoProClient(identifier="1234")

    try:
        await client.open_ble()
        await client.configure_cohn("wifi-ssid", "password")
        await client.wait_cohn_ready()

        # List all media
        media_list = await client.list_media()

        if not media_list:
            print("No media files found")
            return

        # Get latest file
        latest = media_list[0]
        print(f"Latest file: {latest['filename']} ({latest['size']} bytes)")

        # Download to local directory
        download_dir = Path("./downloads")
        download_dir.mkdir(exist_ok=True)

        print("Downloading...")
        await client.download_media(
            filename=latest['filename'],
            local_path=str(download_dir)
        )

        print(f"Downloaded to {download_dir / latest['filename']}")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(download_latest())
```

## Error Handling

Robust error handling for production use:

```python
import asyncio
from gopro_sdk import GoProClient
from gopro_sdk.exceptions import (
    BleConnectionError,
    HttpConnectionError,
    CohnConfigError,
)

async def safe_operation():
    """Safely handle potential errors."""
    client = GoProClient(identifier="1234")

    try:
        # Attempt BLE connection
        try:
            await client.open_ble()
            print("BLE connected")
        except BleConnectionError as e:
            print(f"BLE connection failed: {e}")
            return

        # Attempt COHN configuration
        try:
            await client.configure_cohn("wifi-ssid", "password")
            await client.wait_cohn_ready(timeout=30)
            print("COHN ready")
        except CohnConfigError as e:
            print(f"COHN configuration failed: {e}")
            await client.close()
            return
        except HttpConnectionError as e:
            print(f"HTTP connection failed: {e}")
            await client.close()
            return

        # Perform operations
        await client.set_shutter(on=True)
        await asyncio.sleep(5)
        await client.set_shutter(on=False)

        print("Operation completed successfully")

    finally:
        # Always cleanup
        await client.close()

if __name__ == "__main__":
    asyncio.run(safe_operation())
```

## Custom Timeouts

Adjust timeouts for different scenarios:

```python
import asyncio
from gopro_sdk import GoProClient, TimeoutConfig

async def with_custom_timeouts():
    """Use custom timeout configuration."""

    # Create custom timeout config
    timeouts = TimeoutConfig(
        ble_connect=20.0,      # 20 seconds for BLE
        http_request=15.0,     # 15 seconds for HTTP
        cohn_ready=60.0,       # 60 seconds for COHN
        command_response=10.0  # 10 seconds for commands
    )

    client = GoProClient(
        identifier="1234",
        timeout_config=timeouts
    )

    try:
        # Longer timeout will be used for connection
        await client.open_ble()
        await client.configure_cohn("wifi-ssid", "password")
        await client.wait_cohn_ready()

        # Operations with custom command timeout
        await client.set_shutter(on=True)
        await asyncio.sleep(5)
        await client.set_shutter(on=False)

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(with_custom_timeouts())
```

## Next Steps

- Check the [API Reference](../api/client.md) for all available methods
