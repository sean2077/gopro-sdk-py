# Basic Usage Examples

This page provides basic examples for getting started with the GoPro SDK.

## Connection Examples

### Offline Mode (Default)

Offline mode uses BLE only, suitable for scenarios without WiFi or when WiFi is unreliable.

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    # Default is offline mode (BLE only)
    async with GoProClient("1234") as client:
        print("Connected via BLE!")

        # These operations work in offline mode
        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

        await client.set_date_time()  # Sync time
        await client.tag_hilight()    # Tag highlight
        await client.load_preset(0)   # Load preset
        await client.sleep()          # Put camera to sleep

if __name__ == "__main__":
    asyncio.run(main())
```

### Online Mode

Online mode enables all features including preview stream and media download.

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    # Online mode with WiFi credentials
    async with GoProClient(
        "1234",
        offline_mode=False,
        wifi_ssid="YourWiFi",
        wifi_password="YourPassword"
    ) as client:
        print("Connected via BLE + WiFi!")

        # All operations available
        status = await client.get_camera_state()
        print(f"Camera state: {status}")

        # Preview stream
        stream_url = await client.start_preview()
        print(f"Preview: {stream_url}")

        # Recording
        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

        # Media management
        media_list = await client.get_media_list()
        print(f"Found {len(media_list)} files")

if __name__ == "__main__":
    asyncio.run(main())
```

### Manual Connection (Without Context Manager)

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    client = GoProClient("1234", offline_mode=False)

    try:
        # Manual connection
        await client.open(wifi_ssid="YourWiFi", wifi_password="YourPassword")
        print("Connected!")

        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

    finally:
        # Always close the connection
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Recording Examples

### Basic Recording

```python
import asyncio
from gopro_sdk import GoProClient

async def record_video(duration: int = 10):
    """Record video for specified duration."""
    async with GoProClient("1234") as client:
        print(f"Recording for {duration} seconds...")

        await client.start_recording()
        await asyncio.sleep(duration)
        await client.stop_recording()

        print("Recording complete!")

if __name__ == "__main__":
    asyncio.run(record_video(10))
```

### Recording with Highlights

```python
import asyncio
from gopro_sdk import GoProClient

async def record_with_highlights():
    """Record video and tag highlights at specific moments."""
    async with GoProClient("1234") as client:
        await client.start_recording()

        # Tag highlight at 5 seconds
        await asyncio.sleep(5)
        await client.tag_hilight()
        print("Highlight tagged at 5s")

        # Tag another highlight at 10 seconds
        await asyncio.sleep(5)
        await client.tag_hilight()
        print("Highlight tagged at 10s")

        await asyncio.sleep(5)
        await client.stop_recording()

if __name__ == "__main__":
    asyncio.run(record_with_highlights())
```

## Preset Management

### Load Preset

```python
import asyncio
from gopro_sdk import GoProClient

async def switch_presets():
    """Switch between different presets."""
    async with GoProClient("1234") as client:
        # Load preset by ID
        await client.load_preset(preset_id=0)
        print("Loaded preset 0")

        await asyncio.sleep(2)

        # Load preset group (e.g., Video, Photo, Timelapse)
        await client.load_preset_group(group_id=1000)
        print("Loaded preset group 1000")

if __name__ == "__main__":
    asyncio.run(switch_presets())
```

## Media Management (Online Mode)

### List Media Files

```python
import asyncio
from gopro_sdk import GoProClient

async def list_all_media():
    """List all media files on the camera."""
    async with GoProClient("1234", offline_mode=False) as client:
        media_list = await client.get_media_list()

        print(f"Found {len(media_list)} files:")
        for media in media_list:
            print(f"  - {media.filename} (created: {media.created_datetime})")

if __name__ == "__main__":
    asyncio.run(list_all_media())
```

### Download Media

```python
import asyncio
from pathlib import Path
from gopro_sdk import GoProClient

async def download_latest():
    """Download the most recent media file."""
    async with GoProClient(
        "1234",
        offline_mode=False,
        wifi_ssid="YourWiFi",
        wifi_password="YourPassword"
    ) as client:
        media_list = await client.get_media_list()

        if not media_list:
            print("No media files found")
            return

        # Get the latest file
        latest = media_list[-1]
        print(f"Downloading: {latest.filename}")

        # Create download directory
        download_dir = Path("./downloads")
        download_dir.mkdir(exist_ok=True)

        # Download with progress callback
        def progress(downloaded: int, total: int):
            percent = (downloaded / total) * 100 if total > 0 else 0
            print(f"Progress: {percent:.1f}%", end="\r")

        save_path = download_dir / Path(latest.filename).name
        bytes_downloaded = await client.download_file(
            latest,
            save_path,
            progress_callback=progress
        )

        print(f"\nDownloaded {bytes_downloaded} bytes to {save_path}")

if __name__ == "__main__":
    asyncio.run(download_latest())
```

### Delete Media

```python
import asyncio
from gopro_sdk import GoProClient

async def delete_oldest():
    """Delete the oldest media file."""
    async with GoProClient("1234", offline_mode=False) as client:
        media_list = await client.get_media_list()

        if not media_list:
            print("No media files to delete")
            return

        oldest = media_list[0]
        print(f"Deleting: {oldest.filename}")

        await client.delete_file(oldest.filename)
        print("Deleted successfully"))

if __name__ == "__main__":
    asyncio.run(delete_oldest())
```

## Preview Stream (Online Mode)

```python
import asyncio
from gopro_sdk import GoProClient

async def preview_stream():
    """Start preview stream for viewing."""
    async with GoProClient(
        "1234",
        offline_mode=False,
        wifi_ssid="YourWiFi",
        wifi_password="YourPassword"
    ) as client:
        # Start preview
        stream_url = await client.start_preview(port=8554)
        print(f"Preview stream available at: {stream_url}")
        print("Use VLC or ffplay to view the stream")
        print("Press Ctrl+C to stop...")

        try:
            # Keep the stream running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await client.stop_preview()
            print("Preview stopped")

if __name__ == "__main__":
    asyncio.run(preview_stream())
```

## Multi-Camera Control

### Basic Multi-Camera

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def multi_camera_recording():
    """Control multiple cameras simultaneously."""
    async with MultiCameraManager(
        camera_ids=["1234", "5678", "9012"],
        offline_mode=True,  # BLE only
    ) as manager:
        # Connect all cameras
        results = await manager.connect_all()
        print(f"Connection results: {results}")

        # Start recording on all cameras
        await manager.execute_all(lambda c: c.start_recording())
        print("All cameras recording...")

        await asyncio.sleep(10)

        # Stop recording on all cameras
        await manager.execute_all(lambda c: c.stop_recording())
        print("All cameras stopped")

if __name__ == "__main__":
    asyncio.run(multi_camera_recording())
```

### Multi-Camera with Status Tracking

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def multi_camera_with_status():
    """Multi-camera control with status monitoring."""
    async with MultiCameraManager(
        camera_ids=["1234", "5678"],
        wifi_ssid="YourWiFi",
        wifi_password="YourPassword",
        offline_mode=False,
    ) as manager:
        await manager.connect_all()

        # Get status for all cameras
        statuses = manager.get_camera_status()
        for camera_id, status in statuses.items():
            print(f"Camera {camera_id}: connected={status.is_connected}")

        # Execute with error handling
        results = await manager.execute_all(
            lambda c: c.start_recording(),
            ignore_errors=True
        )

        for camera_id, (success, result) in results.items():
            if success:
                print(f"Camera {camera_id}: Recording started")
            else:
                print(f"Camera {camera_id}: Failed - {result}")

if __name__ == "__main__":
    asyncio.run(multi_camera_with_status())
```

## Error Handling

```python
import asyncio
from gopro_sdk import GoProClient
from gopro_sdk.exceptions import (
    BleConnectionError,
    HttpConnectionError,
    CohnConfigurationError,
)

async def with_error_handling():
    """Example with proper error handling."""
    try:
        async with GoProClient("1234", offline_mode=False) as client:
            await client.start_recording()

    except BleConnectionError as e:
        print(f"BLE connection failed: {e}")
        print("Make sure camera is in pairing mode and nearby")

    except HttpConnectionError as e:
        print(f"HTTP connection failed: {e}")
        print("Check WiFi connection and COHN configuration")

    except CohnConfigurationError as e:
        print(f"COHN configuration failed: {e}")
        print("Try resetting camera network settings")

    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(with_error_handling())
```

## Custom Timeout Configuration

```python
import asyncio
from gopro_sdk import GoProClient
from gopro_sdk.config import TimeoutConfig

async def with_custom_timeouts():
    """Use custom timeout configuration."""
    # Create custom timeout config
    timeout_config = TimeoutConfig(
        ble_connect_timeout=30.0,      # Longer BLE timeout
        http_request_timeout=60.0,     # Longer HTTP timeout
        wifi_provision_timeout=120.0,  # Longer WiFi setup
    )

    async with GoProClient(
        "1234",
        timeout_config=timeout_config,
        offline_mode=False,
    ) as client:
        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

if __name__ == "__main__":
    asyncio.run(with_custom_timeouts())
```

## BLE Device Scanning

```python
import asyncio
from gopro_sdk import BleScanner

async def scan_for_cameras():
    """Scan for nearby GoPro cameras."""
    print("Scanning for GoPro cameras...")

    async for devices in BleScanner.scan_devices_stream(
        duration=10.0,
        idle_timeout=3.0
    ):
        for device in devices:
            print(f"Found: {device['name']} (serial: {device['serial']})")

    print("Scan complete")

if __name__ == "__main__":
    asyncio.run(scan_for_cameras())
```
