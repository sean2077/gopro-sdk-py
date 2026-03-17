# Exceptions

## Base Exceptions

::: gopro_sdk.exceptions.CustomGoProError
    options:
      show_root_heading: true
      show_source: true

## Connection Exceptions

::: gopro_sdk.exceptions.BleConnectionError
    options:
      show_root_heading: true
      show_source: true

::: gopro_sdk.exceptions.BleTimeoutError
    options:
      show_root_heading: true
      show_source: true

::: gopro_sdk.exceptions.HttpConnectionError
    options:
      show_root_heading: true
      show_source: true

## Configuration Exceptions

::: gopro_sdk.exceptions.CohnNotConfiguredError
    options:
      show_root_heading: true
      show_source: true

::: gopro_sdk.exceptions.CohnConfigurationError
    options:
      show_root_heading: true
      show_source: true

## Usage Examples

### Basic Error Handling

```python
import asyncio
from gopro_sdk import GoProClient
from gopro_sdk.exceptions import (
    BleConnectionError,
    HttpConnectionError,
    CohnConfigurationError,
)

async def safe_connection():
    """Handle connection errors gracefully."""
    client = GoProClient("1234", offline_mode=False)

    try:
        await client.open(wifi_ssid="your-wifi", wifi_password="password")
    except BleConnectionError as e:
        print(f"Failed to connect via BLE: {e}")
        return
    except CohnConfigurationError as e:
        print(f"COHN configuration failed: {e}")
        await client.close()
        return
    except HttpConnectionError as e:
        print(f"HTTP connection failed: {e}")
        await client.close()
        return

    # Successfully connected
    print("Camera ready")
    await client.close()
```

### Retry Logic

```python
import asyncio
from gopro_sdk import GoProClient
from gopro_sdk.exceptions import BleConnectionError

async def connect_with_retry(target: str, max_retries: int = 3):
    """Connect with automatic retry on failure."""
    client = GoProClient(target)

    for attempt in range(max_retries):
        try:
            await client.open()
            print(f"Connected on attempt {attempt + 1}")
            return client
        except BleConnectionError as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                print("Max retries reached")
                return None
```

### Multi-Camera Error Handling

```python
import asyncio
from gopro_sdk import MultiCameraManager
from gopro_sdk.exceptions import CustomGoProError

async def robust_multi_camera():
    """Handle errors in multi-camera scenarios."""
    async with MultiCameraManager(
        camera_ids=["1234", "5678", "9012"],
    ) as manager:
        # connect_all returns per-camera results (doesn't raise)
        results = await manager.connect_all()

        # Check which cameras failed
        failed = manager.get_failed_cameras()
        connected = manager.get_connected_cameras()

        if failed:
            print(f"Failed cameras: {', '.join(failed)}")

        # Execute commands only on connected cameras
        if connected:
            results = await manager.execute_all(
                lambda c: c.start_recording(),
                camera_ids=connected,
            )
            for cam_id, (success, result) in results.items():
                if not success:
                    print(f"Camera {cam_id} command failed: {result}")

asyncio.run(robust_multi_camera())
```

### Context Manager Pattern

```python
import asyncio
from gopro_sdk import GoProClient
from gopro_sdk.exceptions import CustomGoProError

async def main():
    """GoProClient supports async context manager for automatic cleanup."""
    try:
        async with GoProClient("1234") as client:
            await client.start_recording()
            await asyncio.sleep(5)
            await client.stop_recording()
    except CustomGoProError as e:
        print(f"SDK error: {e}")

asyncio.run(main())
```

## Exception Hierarchy

```
CustomGoProError (base)
├── BleConnectionError
│   └── BleTimeoutError
├── HttpConnectionError
├── CohnNotConfiguredError
└── CohnConfigurationError
```

All exceptions inherit from `CustomGoProError`, allowing you to catch all SDK errors with a single handler:

```python
from gopro_sdk.exceptions import CustomGoProError

try:
    async with GoProClient("1234", offline_mode=False) as client:
        await client.start_recording()
except CustomGoProError as e:
    print(f"SDK error occurred: {e}")
```
