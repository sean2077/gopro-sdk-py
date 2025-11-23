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
    CohnConfigError,
)

async def safe_connection():
    """Handle connection errors gracefully."""
    client = GoProClient(identifier="1234")
    
    try:
        await client.open_ble()
    except BleConnectionError as e:
        print(f"Failed to connect via BLE: {e}")
        return
    
    try:
        await client.configure_cohn("wifi", "password")
        await client.wait_cohn_ready()
    except CohnConfigError as e:
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
async def connect_with_retry(
    client: GoProClient,
    max_retries: int = 3
):
    """Connect with automatic retry on failure."""
    from gopro_sdk.exceptions import BleConnectionError
    
    for attempt in range(max_retries):
        try:
            await client.open_ble()
            print(f"Connected on attempt {attempt + 1}")
            return True
        except BleConnectionError as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                print("Max retries reached")
                return False
```

### Multi-Camera Error Handling

```python
from gopro_sdk import MultiCameraManager
from gopro_sdk.exceptions import GoproSdkError

async def robust_multi_camera():
    """Handle errors in multi-camera scenarios."""
    manager = MultiCameraManager()
    cameras = {
        "cam1": "1234",
        "cam2": "5678",
        "cam3": "9012",
    }
    
    # Track failed cameras
    failed = []
    
    try:
        await manager.connect_all(cameras, "wifi", "password")
    except GoproSdkError as e:
        print(f"Some cameras failed to connect: {e}")
        
        # Check individual camera status
        for cam_id, client in manager.clients.items():
            if client is None:
                failed.append(cam_id)
    
    if failed:
        print(f"Failed cameras: {', '.join(failed)}")
        # Continue with successfully connected cameras
    
    # Execute commands only on connected cameras
    try:
        await manager.execute_all("set_shutter", on=True)
    except GoproSdkError as e:
        print(f"Command execution error: {e}")
```

### Context Manager Pattern

```python
from contextlib import asynccontextmanager
from gopro_sdk import GoProClient
from gopro_sdk.exceptions import GoproSdkError

@asynccontextmanager
async def gopro_session(identifier: str):
    """Safe camera session with automatic cleanup."""
    client = GoProClient(identifier=identifier)
    
    try:
        await client.open_ble()
        yield client
    except GoproSdkError as e:
        print(f"Session error: {e}")
        raise
    finally:
        await client.close()

# Usage
async def main():
    async with gopro_session("1234") as camera:
        await camera.set_shutter(on=True)
        await asyncio.sleep(5)
        await camera.set_shutter(on=False)
```

## Exception Hierarchy

```
GoproSdkError (base)
├── BleConnectionError
├── HttpConnectionError
├── BleCommandError
├── HttpCommandError
└── CohnConfigError
```

All exceptions inherit from `GoproSdkError`, allowing you to catch all SDK errors with a single handler:

```python
try:
    await client.open_ble()
    await client.configure_cohn("wifi", "password")
except GoproSdkError as e:
    print(f"SDK error occurred: {e}")
```
