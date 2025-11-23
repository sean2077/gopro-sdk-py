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
    manager = MultiCameraManager()
    
    cameras = {
        "cam1": "1234",
        "cam2": "5678",
        "cam3": "9012",
    }
    
    try:
        # Connect all cameras
        await manager.connect_all(
            cameras,
            ssid="your-wifi",
            password="password"
        )
        
        # Start recording on all cameras
        await manager.execute_all("set_shutter", on=True)
        
        # Wait for recording
        await asyncio.sleep(10)
        
        # Stop recording on all cameras
        await manager.execute_all("set_shutter", on=False)
        
        # Get status from all cameras
        statuses = await manager.get_all_status()
        for cam_id, status in statuses.items():
            battery = status.get('battery_percent', 'N/A')
            print(f"{cam_id}: Battery {battery}%")
    finally:
        await manager.disconnect_all()

asyncio.run(main())
```

### Synchronized Recording

```python
async def synchronized_recording(
    camera_ids: dict,
    duration: int,
    wifi_ssid: str,
    wifi_password: str
):
    """Record on multiple cameras simultaneously."""
    manager = MultiCameraManager()
    
    try:
        await manager.connect_all(camera_ids, wifi_ssid, wifi_password)
        
        # All cameras start at the same time
        await manager.execute_all("set_shutter", on=True)
        await asyncio.sleep(duration)
        await manager.execute_all("set_shutter", on=False)
        
        print("Recording completed on all cameras")
    finally:
        await manager.disconnect_all()
```

### Error Handling

```python
async def robust_multi_camera():
    """Handle errors in multi-camera scenarios."""
    manager = MultiCameraManager()
    cameras = {"cam1": "1234", "cam2": "5678"}
    
    try:
        await manager.connect_all(cameras, "wifi", "password")
    except Exception as e:
        print(f"Failed to connect all cameras: {e}")
        # Check which cameras connected
        for cam_id, client in manager.clients.items():
            if client:
                print(f"{cam_id}: Connected")
            else:
                print(f"{cam_id}: Failed")
    
    # Continue with connected cameras only
    await manager.execute_all("set_shutter", on=True)
```

## See Also

- [GoProClient](client.md) - Single camera control
- [CohnConfigManager](config.md) - Configuration management
