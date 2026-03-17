# MultiCameraManager

::: gopro_sdk.multi_camera.MultiCameraManager
    options:
      show_root_heading: true
      show_source: true

## Usage Examples

### Basic Multi-Camera Control

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def main():
    async with MultiCameraManager(
        camera_ids=["1234", "5678", "9012"],
    ) as manager:
        # Connect all cameras (BLE only by default)
        results = await manager.connect_all()
        print(f"Connection results: {results}")
        # {"1234": True, "5678": True, "9012": False}

        # Start recording on all cameras
        await manager.execute_all(lambda c: c.start_recording())

        await asyncio.sleep(10)

        # Stop recording on all cameras
        await manager.execute_all(lambda c: c.stop_recording())

asyncio.run(main())
```

### Synchronized Recording with WiFi

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def synchronized_recording(duration: int = 10):
    """Record on multiple cameras simultaneously."""
    async with MultiCameraManager(
        camera_ids=["1234", "5678"],
        wifi_ssid="your-wifi",
        wifi_password="password",
        offline_mode=False,
    ) as manager:
        await manager.connect_all()

        # All cameras start at the same time
        await manager.execute_all(lambda c: c.start_recording())
        await asyncio.sleep(duration)
        await manager.execute_all(lambda c: c.stop_recording())

        print("Recording completed on all cameras")

asyncio.run(synchronized_recording())
```

### Error Handling and Status Tracking

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def robust_multi_camera():
    """Handle errors in multi-camera scenarios."""
    async with MultiCameraManager(
        camera_ids=["1234", "5678", "9012"],
    ) as manager:
        # connect_all returns per-camera success/failure
        results = await manager.connect_all()

        # Check which cameras connected
        connected = manager.get_connected_cameras()
        failed = manager.get_failed_cameras()
        print(f"Connected: {connected}, Failed: {failed}")

        # Execute commands on connected cameras only
        results = await manager.execute_all(
            lambda c: c.start_recording(),
            camera_ids=connected,
        )
        for cam_id, (success, result) in results.items():
            if success:
                print(f"{cam_id}: Recording started")
            else:
                print(f"{cam_id}: Failed - {result}")

        # Get overall manager status
        status = manager.get_manager_status()
        print(f"Total: {status['total_cameras']}, "
              f"Connected: {status['connected_cameras']}")

asyncio.run(robust_multi_camera())
```

### Dynamic Camera Management

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def dynamic_cameras():
    """Add and remove cameras dynamically."""
    async with MultiCameraManager(
        camera_ids=["1234"],
    ) as manager:
        await manager.connect_all()

        # Add another camera (with auto-connect)
        await manager.add_camera("5678", auto_connect=True)

        # Execute on all connected cameras
        await manager.execute_all(lambda c: c.start_recording())
        await asyncio.sleep(5)
        await manager.execute_all(lambda c: c.stop_recording())

        # Remove a camera
        await manager.remove_camera("5678")

asyncio.run(dynamic_cameras())
```

## See Also

- [GoProClient](client.md) - Single camera control
- [CohnConfigManager](config.md) - Configuration management
