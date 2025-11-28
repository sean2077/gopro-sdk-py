# GoProClient

::: gopro_sdk.client.GoProClient
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - open_ble
        - close
        - configure_cohn
        - apply_cohn_config
        - wait_cohn_ready
        - set_shutter
        - get_camera_state
        - set_video_resolution
        - set_video_fps
        - list_media
        - download_media
        - delete_media
        - start_webcam
        - stop_webcam
        - get_webcam_url
        - check_health
        - reconnect

## Usage Examples

### Basic Connection

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    client = GoProClient(identifier="1234")

    try:
        await client.open_ble()
        await client.configure_cohn(
            ssid="your-wifi",
            password="password"
        )
        await client.wait_cohn_ready()

        # Camera is ready to use
        status = await client.get_camera_state()
        print(f"Battery: {status.get('battery_percent')}%")
    finally:
        await client.close()

asyncio.run(main())
```

### Recording Control

```python
async def record_video(client: GoProClient, duration: int):
    """Record video for specified duration."""
    await client.set_shutter(on=True)
    await asyncio.sleep(duration)
    await client.set_shutter(on=False)
```

### With Custom Timeouts

```python
from gopro_sdk import TimeoutConfig

custom_timeouts = TimeoutConfig(
    ble_connect=20.0,
    http_request=15.0,
    cohn_ready=60.0
)

client = GoProClient(
    identifier="1234",
    timeout_config=custom_timeouts
)
```

## See Also

- [MultiCameraManager](multi-camera.md) - For controlling multiple cameras
- [Commands](commands.md) - Available camera commands
- [Connection](connection.md) - Connection management details
