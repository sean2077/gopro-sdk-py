# GoProClient

::: gopro_sdk.client.GoProClient
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - open
        - close
        - offline_mode
        - is_online
        - switch_to_online_mode
        - set_shutter
        - start_recording
        - stop_recording
        - set_preview_stream
        - start_preview
        - stop_preview
        - tag_hilight
        - get_camera_state
        - get_parsed_state
        - get_camera_info
        - set_keep_alive
        - set_date_time
        - get_date_time
        - get_setting
        - set_setting
        - get_preset_status
        - load_preset
        - load_preset_group
        - set_digital_zoom
        - sleep
        - reboot
        - get_media_list
        - download_file
        - delete_file
        - delete_all_media
        - get_media_metadata
        - get_last_captured_media
        - set_turbo_mode
        - start_webcam
        - stop_webcam
        - get_webcam_status
        - start_webcam_preview
        - webcam_exit
        - get_webcam_version
        - reset_cohn
        - configure_cohn
        - setup_wifi
        - scan_wifi_networks
        - connect_to_wifi

## Usage Examples

### Basic Connection (Offline Mode)

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    # Default offline mode (BLE only)
    async with GoProClient("1234") as client:
        # Recording control
        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

        # Time sync
        await client.set_date_time()

asyncio.run(main())
```

### Online Mode (BLE + WiFi)

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    async with GoProClient(
        "1234",
        offline_mode=False,
        wifi_ssid="YourWiFi",
        wifi_password="YourPassword"
    ) as client:
        # Get camera status
        status = await client.get_camera_state()
        print(f"Camera state: {status}")

        # Start preview stream
        stream_url = await client.start_preview()
        print(f"Preview: {stream_url}")

asyncio.run(main())
```

### Dynamic Mode Switching

```python
async def main():
    # Start in offline mode
    async with GoProClient("1234") as client:
        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

        # Switch to online mode when needed
        await client.switch_to_online_mode(
            wifi_ssid="YourWiFi",
            wifi_password="YourPassword"
        )

        # Now online features work
        media = await client.get_media_list()
        print(f"Found {len(media)} files")
```

### With Custom Timeouts

```python
from gopro_sdk import GoProClient
from gopro_sdk.config import TimeoutConfig

timeout_config = TimeoutConfig(
    ble_connect_timeout=30.0,
    http_request_timeout=60.0,
    wifi_provision_timeout=120.0,
)

async with GoProClient(
    "1234",
    timeout_config=timeout_config,
    offline_mode=False,
) as client:
    await client.start_recording()
```

## See Also

- [MultiCameraManager](multi-camera.md) - For controlling multiple cameras
- [Commands](commands.md) - Available camera commands
- [Connection](connection.md) - Connection management details
