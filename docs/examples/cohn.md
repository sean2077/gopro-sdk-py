# COHN Configuration Examples

Examples for managing COHN (Camera on Home Network) configuration.

## Basic COHN Setup

Configure a camera for COHN mode:

```python
import asyncio
from gopro_sdk import GoProClient

async def setup_cohn():
    """Configure COHN for the first time."""
    client = GoProClient(identifier="1234")

    try:
        # Connect via BLE
        await client.open_ble()
        print("BLE connected")

        # Configure COHN
        print("Configuring COHN...")
        config = await client.configure_cohn(
            ssid="your-wifi-ssid",
            password="your-wifi-password"
        )

        # Wait for COHN to be ready
        print("Waiting for COHN connection...")
        await client.wait_cohn_ready(timeout=30)

        print("COHN ready!")
        print(f"Camera IP: {config.ip_address}")

        # Now you can use HTTP commands efficiently
        status = await client.get_camera_state()
        print(f"Battery: {status.get('battery_percent')}%")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(setup_cohn())
```

## Persistent Configuration

Save and reuse COHN configuration:

```python
import asyncio
from gopro_sdk import GoProClient, CohnConfigManager

async def with_persistent_config():
    """Use saved COHN configuration."""
    client = GoProClient(identifier="1234")
    config_mgr = CohnConfigManager()

    try:
        await client.open_ble()

        # Try to load saved configuration
        saved_config = config_mgr.load_config("1234")

        if saved_config:
            # Use saved configuration
            print("Using saved COHN configuration")
            print(f"  SSID: {saved_config.ssid}")
            print(f"  IP: {saved_config.ip_address}")

            await client.apply_cohn_config(saved_config)
        else:
            # First time setup
            print("No saved config found, configuring COHN...")
            config = await client.configure_cohn(
                ssid="your-wifi-ssid",
                password="your-wifi-password"
            )

            # Save for future use
            config_mgr.save_config("1234", config)
            print("Configuration saved")

        # Wait for COHN to be ready
        await client.wait_cohn_ready(timeout=30)
        print("COHN ready")

        # Use camera...
        await client.set_shutter(on=True)
        await asyncio.sleep(5)
        await client.set_shutter(on=False)

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(with_persistent_config())
```

## Managing Multiple Camera Configs

Manage configurations for multiple cameras:

```python
from gopro_sdk import CohnConfigManager
from pathlib import Path

def manage_configs():
    """Manage COHN configurations for multiple cameras."""
    config_mgr = CohnConfigManager()

    # List all saved configurations
    configs = config_mgr.list_configs()
    print(f"Found {len(configs)} saved configuration(s)\n")

    for identifier in configs:
        config = config_mgr.load_config(identifier)
        if config:
            print(f"Camera {identifier}:")
            print(f"  SSID: {config.ssid}")
            print(f"  IP: {config.ip_address}")
            print(f"  Username: {config.username}")
            print()

    # Delete old configuration (example)
    # config_mgr.delete_config("old_camera_id")

if __name__ == "__main__":
    manage_configs()
```

## Custom Cache Directory

Use a custom directory for configuration storage:

```python
import asyncio
from gopro_sdk import GoProClient, CohnConfigManager
from pathlib import Path

async def custom_cache_dir():
    """Use custom directory for COHN config storage."""
    # Define custom cache directory
    cache_dir = Path.home() / ".my_app" / "gopro_configs"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create config manager with custom directory
    config_mgr = CohnConfigManager(cache_dir=cache_dir)

    client = GoProClient(identifier="1234")

    try:
        await client.open_ble()

        saved_config = config_mgr.load_config("1234")

        if saved_config:
            await client.apply_cohn_config(saved_config)
        else:
            config = await client.configure_cohn("wifi-ssid", "password")
            config_mgr.save_config("1234", config)
            print(f"Config saved to {cache_dir}")

        await client.wait_cohn_ready()

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(custom_cache_dir())
```

## Reconfigure COHN

Update COHN configuration (e.g., new WiFi network):

```python
import asyncio
from gopro_sdk import GoProClient, CohnConfigManager

async def reconfigure_cohn(new_ssid: str, new_password: str):
    """Reconfigure COHN with new WiFi credentials."""
    client = GoProClient(identifier="1234")
    config_mgr = CohnConfigManager()

    try:
        await client.open_ble()

        # Configure with new credentials
        print(f"Configuring COHN for new network: {new_ssid}")
        config = await client.configure_cohn(
            ssid=new_ssid,
            password=new_password
        )

        # Save new configuration (overwrites old one)
        config_mgr.save_config("1234", config)
        print("New configuration saved")

        await client.wait_cohn_ready(timeout=30)
        print("COHN ready with new network")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(reconfigure_cohn(
        new_ssid="new-wifi-network",
        new_password="new-password"
    ))
```

## Multi-Camera with Persistent Config

Use persistent configuration for multiple cameras:

```python
import asyncio
from gopro_sdk import MultiCameraManager, CohnConfigManager, GoProClient

async def multi_camera_persistent():
    """Connect multiple cameras using saved configurations."""
    config_mgr = CohnConfigManager()

    cameras = {
        "cam1": "1234",
        "cam2": "5678",
    }

    # Check which cameras have saved configs
    for cam_id, identifier in cameras.items():
        config = config_mgr.load_config(identifier)
        if config:
            print(f"{cam_id} has saved config for {config.ssid}")
        else:
            print(f"{cam_id} needs configuration")

    # Option 1: Use MultiCameraManager with new config
    manager = MultiCameraManager()

    try:
        # This will configure all cameras
        await manager.connect_all(
            cameras,
            ssid="wifi-ssid",
            password="password"
        )

        # Save configs for next time
        for cam_id, client in manager.clients.items():
            if client and hasattr(client, 'cohn_config'):
                identifier = cameras[cam_id]
                config_mgr.save_config(identifier, client.cohn_config)
                print(f"Saved config for {cam_id}")

        # Use cameras...
        await manager.execute_all("set_shutter", on=True)
        await asyncio.sleep(5)
        await manager.execute_all("set_shutter", on=False)

    finally:
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(multi_camera_persistent())
```

## COHN Status Checking

Check COHN connection status:

```python
import asyncio
from gopro_sdk import GoProClient

async def check_cohn_status():
    """Check if COHN is properly configured and connected."""
    client = GoProClient(identifier="1234")

    try:
        await client.open_ble()

        # Get camera state
        status = await client.get_camera_state()

        # Check COHN status (example - actual fields may vary)
        if status.get('cohn_connected'):
            print("COHN is connected")
            print(f"  Network: {status.get('cohn_ssid')}")
            print(f"  IP: {status.get('cohn_ip')}")
        else:
            print("COHN is not connected")
            print("  Needs configuration")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check_cohn_status())
```

## Automatic Reconnection

Automatically reconnect if COHN connection drops:

```python
import asyncio
from gopro_sdk import GoProClient, CohnConfigManager
from gopro_sdk.exceptions import HttpConnectionError

async def auto_reconnect():
    """Automatically reconnect if COHN fails."""
    client = GoProClient(identifier="1234")
    config_mgr = CohnConfigManager()

    try:
        await client.open_ble()

        # Load and apply config
        config = config_mgr.load_config("1234")
        if config:
            await client.apply_cohn_config(config)
            await client.wait_cohn_ready()

        # Try to use camera
        max_retries = 3
        for attempt in range(max_retries):
            try:
                status = await client.get_camera_state()
                print(f"Battery: {status.get('battery_percent')}%")
                break
            except HttpConnectionError as e:
                print(f"Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    print("Attempting to reconnect...")
                    # Reapply COHN config
                    await client.apply_cohn_config(config)
                    await client.wait_cohn_ready(timeout=30)
                else:
                    print("Max retries reached")
                    raise

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(auto_reconnect())
```

## Next Steps

- See [Basic Examples](basic.md) for general camera operations
- See [Multi-Camera Examples](multi-camera.md) for multiple cameras
- Check [API Reference](../api/config.md) for configuration details
