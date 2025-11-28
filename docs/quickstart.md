# Quick Start Guide

This guide will help you get started with the GoPro SDK for Python in just a few minutes.

## Prerequisites

- Python 3.12 or higher
- GoPro camera (HERO 9 or later recommended)
- Bluetooth adapter on your computer
- WiFi network for online mode (optional)

## Installation

=== "Using uv (Recommended)"

    ```bash
    uv add gopro-sdk-py
    ```

=== "Using pip"

    ```bash
    pip install gopro-sdk-py
    ```

=== "From Source"

    ```bash
    git clone https://github.com/sean2077/gopro-sdk-py.git
    cd gopro-sdk-py
    uv sync
    ```

## Your First Connection

### 1. Prepare Your Camera

!!! warning "Install GoPro Labs Firmware"
    Open GoPro API requires **GoPro Labs firmware** to be installed on your camera. This is a special developer-focused firmware that enables API access.

    **Installation Guide**: [GoPro Labs](https://community.gopro.com/s/article/GoPro-Labs)

    Supported cameras: HERO9 Black, HERO10 Black, HERO11 Black, HERO11 Black Mini, HERO12 Black, HERO13 Black, MAX 2

!!! note "First-time Pairing"
    For first-time pairing, you need to enable pairing mode on your GoPro camera. The exact steps vary by camera model. Please refer to the [GoPro Pairing Guide](https://community.gopro.com/s/article/GoPro-Quik-How-To-Pair-Your-Camera?language=en_US).

Note the last 4 digits of your camera's name (e.g., "GoPro 1234" → use "1234")

### 2. Offline Mode (Default, BLE Only)

Create a file `test_connection.py`:

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    # Replace "1234" with your camera's identifier
    # Default is offline mode (BLE only)
    async with GoProClient("1234") as client:
        print("Connected to camera via BLE!")

        # Control recording (works in offline mode)
        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

        # Sync time
        await client.set_date_time()

        print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
python test_connection.py
```

### 3. Online Mode (BLE + WiFi)

For features like preview stream and media download, use online mode:

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    # Online mode with WiFi credentials
    async with GoProClient(
        "1234",
        offline_mode=False,
        wifi_ssid="YourWiFiName",
        wifi_password="YourWiFiPassword"
    ) as client:
        print("Connected via BLE + WiFi!")

        # Get camera status (requires online mode)
        status = await client.get_camera_state()
        print(f"Camera state: {status}")

        # Start preview stream
        stream_url = await client.start_preview()
        print(f"Preview URL: {stream_url}")

        # Start recording
        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

if __name__ == "__main__":
    asyncio.run(main())
```

### 4. Dynamic Mode Switching

Start in offline mode and switch to online when needed:

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    # Start in offline mode
    async with GoProClient("1234") as client:
        # Works in offline mode
        await client.start_recording()
        await asyncio.sleep(5)
        await client.stop_recording()

        # Switch to online mode when needed
        await client.switch_to_online_mode(
            wifi_ssid="YourWiFiName",
            wifi_password="YourWiFiPassword"
        )

        # Now online features are available
        media_list = await client.get_media_list()
        print(f"Found {len(media_list)} media files")

if __name__ == "__main__":
    asyncio.run(main())
```

## Common Operations

### Recording Control

```python
# Start recording
await client.start_recording()

# Stop recording
await client.stop_recording()

# Or use set_shutter directly
await client.set_shutter(True)   # Start
await client.set_shutter(False)  # Stop
```

### Tag Highlight

```python
# Tag highlight during recording (works offline)
await client.tag_hilight()
```

### Load Preset

```python
# Load preset by ID (works offline)
await client.load_preset(preset_id=0)

# Load preset group
await client.load_preset_group(group_id=1000)
```

### Camera Control

```python
# Put camera to sleep (works offline)
await client.sleep()

# Sync date/time (works offline)
await client.set_date_time()
```

### Check Camera Status (Online Mode)

```python
# Get full camera state
status = await client.get_camera_state()

# Get parsed state with enum keys
parsed = await client.get_parsed_state()
```

### Download Media (Online Mode)

```python
# List all media files
media_list = await client.get_media_list()

# Download a file
if media_list:
    latest = media_list[-1]
    await client.download_file(latest, "./downloads/video.mp4")
```

## Multiple Cameras

For controlling multiple cameras simultaneously:

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def main():
    # Create manager with camera IDs
    async with MultiCameraManager(
        camera_ids=["1234", "5678"],
        wifi_ssid="YourWiFi",
        wifi_password="YourPassword",
        offline_mode=False,
    ) as manager:
        # Connect all cameras
        results = await manager.connect_all()
        print(f"Connection results: {results}")

        # Execute on all cameras
        await manager.execute_all(lambda c: c.start_recording())

        await asyncio.sleep(10)

        await manager.execute_all(lambda c: c.stop_recording())

if __name__ == "__main__":
    asyncio.run(main())
```

## Operating Mode Summary

| Feature            | Offline Mode | Online Mode |
| ------------------ | ------------ | ----------- |
| Recording control  | Yes          | Yes         |
| Date/time sync     | Yes          | Yes         |
| Tag highlight      | Yes          | Yes         |
| Load preset        | Yes          | Yes         |
| Sleep              | Yes          | Yes         |
| Preview stream     | No           | Yes         |
| Media download     | No           | Yes         |
| Camera state query | No           | Yes         |
| Webcam mode        | No           | Yes         |

## Troubleshooting

!!! warning "Camera Not Found"
    - **Check firmware**: Ensure [GoPro Labs firmware](https://community.gopro.com/s/article/GoPro-Labs) is installed
    - Make sure Bluetooth is enabled on your computer
    - Ensure the camera is in pairing mode
    - Try moving closer to the camera
    - Check that no other app is connected to the camera

!!! bug "Connection Timeout"
    - Increase timeout values in TimeoutConfig
    - Check WiFi signal strength for online mode
    - Restart the camera
    - Try reconnecting

!!! failure "Import Errors"
    - Make sure you've installed the package: `pip install gopro-sdk-py`
    - Check that you're using Python 3.12 or higher
    - Try reinstalling: `pip install --force-reinstall gopro-sdk-py`

## Next Steps

- Check out the [Examples](examples/basic.md) for more complex use cases
- Read the [API Reference](api/overview.md) for detailed API documentation
- See [Architecture](architecture.md) for design overview
