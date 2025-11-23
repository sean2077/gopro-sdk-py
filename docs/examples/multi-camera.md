# Multi-Camera Examples

Examples for controlling multiple GoPro cameras simultaneously.

## Basic Multi-Camera Setup

Connect and control multiple cameras:

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def main():
    # Create manager
    manager = MultiCameraManager()

    # Define cameras
    cameras = {
        "front": "1234",
        "back": "5678",
        "left": "9012",
    }

    try:
        # Connect all cameras
        print("Connecting to cameras...")
        await manager.connect_all(
            cameras,
            ssid="your-wifi-ssid",
            password="your-wifi-password"
        )
        print("All cameras connected")

        # Get status from all
        statuses = await manager.get_all_status()
        for cam_id, status in statuses.items():
            battery = status.get('battery_percent', 'N/A')
            print(f"{cam_id}: Battery {battery}%")

    finally:
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(main())
```

## Synchronized Recording

Start and stop recording on all cameras simultaneously:

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def synchronized_recording(duration: int = 10):
    """Record synchronized video on multiple cameras."""
    manager = MultiCameraManager()

    cameras = {
        "camera1": "1234",
        "camera2": "5678",
        "camera3": "9012",
    }

    try:
        # Connect all
        print("Connecting cameras...")
        await manager.connect_all(cameras, "wifi-ssid", "password")

        # Verify all are ready
        statuses = await manager.get_all_status()
        for cam_id, status in statuses.items():
            if status.get('is_recording'):
                print(f"Warning: {cam_id} is already recording")

        # Start recording on all cameras simultaneously
        print("Starting recording on all cameras...")
        await manager.execute_all("set_shutter", on=True)

        # Record for duration
        print(f"Recording for {duration} seconds...")
        await asyncio.sleep(duration)

        # Stop all cameras simultaneously
        print("Stopping recording...")
        await manager.execute_all("set_shutter", on=False)

        print("Recording completed on all cameras")

    finally:
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(synchronized_recording(duration=10))
```

## Individual Camera Control

Access individual cameras for specific operations:

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def individual_control():
    """Control cameras individually within manager."""
    manager = MultiCameraManager()

    cameras = {
        "main": "1234",
        "secondary": "5678",
    }

    try:
        await manager.connect_all(cameras, "wifi-ssid", "password")

        # Start recording on main camera only
        main_camera = manager.clients["main"]
        if main_camera:
            await main_camera.set_shutter(on=True)
            print("Main camera recording")

        # Wait a bit
        await asyncio.sleep(5)

        # Now start secondary camera
        secondary_camera = manager.clients["secondary"]
        if secondary_camera:
            await secondary_camera.set_shutter(on=True)
            print("Secondary camera recording")

        # Wait more
        await asyncio.sleep(5)

        # Stop both
        await manager.execute_all("set_shutter", on=False)
        print("All cameras stopped")

    finally:
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(individual_control())
```

## Error Handling

Handle failures gracefully in multi-camera scenarios:

```python
import asyncio
from gopro_sdk import MultiCameraManager
from gopro_sdk.exceptions import GoproSdkError

async def robust_multi_camera():
    """Handle connection failures gracefully."""
    manager = MultiCameraManager()

    cameras = {
        "cam1": "1234",
        "cam2": "5678",
        "cam3": "9012",
    }

    try:
        # Attempt to connect all
        await manager.connect_all(cameras, "wifi-ssid", "password")
    except GoproSdkError as e:
        print(f"Some cameras failed to connect: {e}")

    # Check which cameras connected successfully
    connected = []
    failed = []

    for cam_id, client in manager.clients.items():
        if client is not None:
            connected.append(cam_id)
            print(f"✓ {cam_id}: Connected")
        else:
            failed.append(cam_id)
            print(f"✗ {cam_id}: Failed")

    if not connected:
        print("No cameras connected, aborting")
        return

    # Continue with connected cameras only
    print(f"\nProceeding with {len(connected)} camera(s)")

    try:
        # Execute on all connected cameras
        await manager.execute_all("set_shutter", on=True)
        await asyncio.sleep(5)
        await manager.execute_all("set_shutter", on=False)

        print("Recording completed on connected cameras")
    except GoproSdkError as e:
        print(f"Command execution error: {e}")
    finally:
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(robust_multi_camera())
```

## Different Settings Per Camera

Configure each camera with different settings:

```python
import asyncio
from gopro_sdk import MultiCameraManager
from open_gopro.models.constants.settings import VideoResolution, VideoFPS

async def different_settings():
    """Configure different settings for each camera."""
    manager = MultiCameraManager()

    cameras = {
        "high_quality": "1234",  # 4K 30fps
        "high_speed": "5678",    # 1080p 60fps
    }

    try:
        await manager.connect_all(cameras, "wifi-ssid", "password")

        # Configure high quality camera
        hq_camera = manager.clients["high_quality"]
        if hq_camera:
            await hq_camera.set_video_resolution(VideoResolution.RES_4K)
            await hq_camera.set_video_fps(VideoFPS.FPS_30)
            print("High quality camera: 4K@30fps")

        # Configure high speed camera
        hs_camera = manager.clients["high_speed"]
        if hs_camera:
            await hs_camera.set_video_resolution(VideoResolution.RES_1080)
            await hs_camera.set_video_fps(VideoFPS.FPS_60)
            print("High speed camera: 1080p@60fps")

        # Start recording on all
        await manager.execute_all("set_shutter", on=True)
        await asyncio.sleep(10)
        await manager.execute_all("set_shutter", on=False)

        print("Recorded with different settings")

    finally:
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(different_settings())
```

## Monitoring Multiple Cameras

Continuously monitor status of all cameras:

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def monitor_cameras(interval: int = 5, duration: int = 30):
    """Monitor camera status periodically."""
    manager = MultiCameraManager()

    cameras = {
        "cam1": "1234",
        "cam2": "5678",
    }

    try:
        await manager.connect_all(cameras, "wifi-ssid", "password")

        # Start recording
        await manager.execute_all("set_shutter", on=True)

        # Monitor for duration
        elapsed = 0
        while elapsed < duration:
            # Get status from all cameras
            statuses = await manager.get_all_status()

            print(f"\n--- Status at {elapsed}s ---")
            for cam_id, status in statuses.items():
                battery = status.get('battery_percent', 'N/A')
                recording = status.get('is_recording', False)
                print(f"{cam_id}: Battery {battery}%, Recording: {recording}")

            # Wait before next check
            await asyncio.sleep(interval)
            elapsed += interval

        # Stop recording
        await manager.execute_all("set_shutter", on=False)

    finally:
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(monitor_cameras(interval=5, duration=30))
```

## Batch Media Download

Download media from all cameras:

```python
import asyncio
from pathlib import Path
from gopro_sdk import MultiCameraManager

async def download_from_all():
    """Download latest media from all cameras."""
    manager = MultiCameraManager()

    cameras = {
        "cam1": "1234",
        "cam2": "5678",
    }

    try:
        await manager.connect_all(cameras, "wifi-ssid", "password")

        # Create download directory
        download_dir = Path("./downloads")
        download_dir.mkdir(exist_ok=True)

        # Download from each camera
        for cam_id, client in manager.clients.items():
            if client is None:
                continue

            print(f"\nProcessing {cam_id}...")

            # Get media list
            media_list = await client.list_media()

            if not media_list:
                print(f"  No media on {cam_id}")
                continue

            # Download latest file
            latest = media_list[0]
            filename = latest['filename']

            # Create camera-specific subfolder
            cam_dir = download_dir / cam_id
            cam_dir.mkdir(exist_ok=True)

            print(f"  Downloading {filename}...")
            await client.download_media(
                filename=filename,
                local_path=str(cam_dir)
            )

            print(f"  Downloaded to {cam_dir / filename}")

        print("\nAll downloads complete")

    finally:
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(download_from_all())
```

## Next Steps

- See [COHN Configuration](cohn.md) for persistent configuration
- Check [API Reference](../api/multi-camera.md) for more methods
- Review [Basic Examples](basic.md) for single camera operations
