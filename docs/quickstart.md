# Quick Start Guide

This guide will help you get started with the GoPro SDK for Python in just a few minutes.

## Prerequisites

- Python 3.12 or higher
- GoPro camera (HERO 9 or later recommended)
- Bluetooth adapter on your computer
- WiFi network for COHN mode

## Installation

### From PyPI

```bash
pip install gopro-sdk-py
```

### From Source

```bash
git clone https://github.com/sean2077/gopro-sdk-py.git
cd gopro-sdk-py
pip install -e .
```

## Your First Connection

### 1. Find Your Camera

First, make sure your camera is turned on and in pairing mode. Note the last 4 digits of your camera's name (e.g., "GoPro 1234" → use "1234").

### 2. Simple Connection Test

Create a file `test_connection.py`:

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    # Replace "1234" with your camera's identifier
    client = GoProClient(identifier="1234")

    try:
        print("Connecting to camera...")
        await client.open_ble()
        print("Connected successfully!")

        # Get camera status
        status = await client.get_camera_state()
        print(f"Battery: {status.get('battery_percent')}%")

    finally:
        await client.close()

asyncio.run(main())
```

Run it:

```bash
python test_connection.py
```

### 3. Set Up COHN (Recommended)

COHN (Camera on Home Network) allows you to control the camera over WiFi, which is faster and more reliable than BLE for many operations.

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    client = GoProClient(identifier="1234")

    try:
        # Connect via BLE first
        await client.open_ble()

        # Configure COHN
        await client.configure_cohn(
            ssid="YourWiFiName",
            password="YourWiFiPassword"
        )

        # Wait for COHN to be ready
        await client.wait_cohn_ready(timeout=30)
        print("COHN is ready!")

        # Now you can use faster HTTP commands
        await client.set_shutter(on=True)  # Start recording
        await asyncio.sleep(5)
        await client.set_shutter(on=False)  # Stop recording

    finally:
        await client.close()

asyncio.run(main())
```

### 4. Save COHN Configuration

To avoid reconfiguring COHN every time:

```python
import asyncio
from gopro_sdk import GoProClient, CohnConfigManager

async def main():
    client = GoProClient(identifier="1234")
    config_manager = CohnConfigManager()

    # Try to load saved config
    saved_config = config_manager.load_config("1234")

    try:
        await client.open_ble()

        if saved_config:
            print("Using saved configuration...")
            await client.apply_cohn_config(saved_config)
        else:
            print("Configuring COHN for the first time...")
            config = await client.configure_cohn(
                ssid="YourWiFiName",
                password="YourWiFiPassword"
            )
            config_manager.save_config("1234", config)

        await client.wait_cohn_ready()
        print("Ready to go!")

    finally:
        await client.close()

asyncio.run(main())
```

## Common Operations

### Take a Photo

```python
await client.set_shutter(on=True)
```

### Start/Stop Video Recording

```python
# Start recording
await client.set_shutter(on=True)

# Record for 10 seconds
await asyncio.sleep(10)

# Stop recording
await client.set_shutter(on=False)
```

### Check Camera Status

```python
status = await client.get_camera_state()
print(f"Battery: {status.get('battery_percent')}%")
print(f"Recording: {status.get('is_recording')}")
print(f"SD Space: {status.get('space_remaining')} MB")
```

### Set Video Resolution

```python
from open_gopro.models.constants.settings import VideoResolution

await client.set_video_resolution(VideoResolution.RES_1080)
```

### Download Latest Media

```python
# List media files
media_list = await client.list_media()

# Download the latest file
if media_list:
    latest = media_list[0]
    await client.download_media(
        filename=latest['filename'],
        local_path="./downloads/"
    )
```

## Multiple Cameras

For controlling multiple cameras simultaneously:

```python
import asyncio
from gopro_sdk import MultiCameraManager

async def main():
    cameras = {
        "cam1": "1234",
        "cam2": "5678",
    }

    manager = MultiCameraManager()

    try:
        # Connect all cameras
        await manager.connect_all(cameras)

        # Start recording on all cameras
        await manager.execute_all("set_shutter", on=True)

        # Wait a bit
        await asyncio.sleep(10)

        # Stop all cameras
        await manager.execute_all("set_shutter", on=False)

    finally:
        await manager.disconnect_all()

asyncio.run(main())
```

## Troubleshooting

### Camera Not Found

- Make sure Bluetooth is enabled on your computer
- Ensure the camera is in pairing mode
- Try moving closer to the camera
- Check that no other app is connected to the camera

### Connection Timeout

- Increase timeout values in TimeoutConfig
- Check WiFi signal strength for COHN
- Restart the camera
- Try reconnecting

### Import Errors

- Make sure you've installed the package: `pip install -e .`
- Check that you're using Python 3.9 or higher
- Try reinstalling dependencies: `pip install -r requirements.txt`

## Next Steps

- Check out the [Examples](examples/basic.md) for more complex use cases
- Read the [API Reference](api/overview.md) for detailed API documentation
- See [Contributing](contributing.md) if you want to contribute

## Getting Help

- Open an issue on GitHub
- Start a discussion
- Check the documentation
