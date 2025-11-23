# Configuration

## TimeoutConfig

::: gopro_sdk.config.TimeoutConfig
    options:
      show_root_heading: true
      show_source: true

## CohnConfigManager

::: gopro_sdk.config.CohnConfigManager
    options:
      show_root_heading: true
      show_source: true

## CohnCredentials

::: gopro_sdk.config.CohnCredentials
    options:
      show_root_heading: true
      show_source: true

## Usage Examples

### Custom Timeouts

```python
from gopro_sdk import GoProClient, TimeoutConfig

# Create custom timeout configuration
timeouts = TimeoutConfig(
    ble_connect=20.0,      # 20 seconds for BLE connection
    ble_disconnect=10.0,   # 10 seconds for disconnection
    http_request=15.0,     # 15 seconds for HTTP requests
    command_response=10.0, # 10 seconds for command responses
    cohn_ready=60.0        # 60 seconds to wait for COHN
)

client = GoProClient(identifier="1234", timeout_config=timeouts)
```

### Persistent COHN Configuration

```python
from gopro_sdk import GoProClient, CohnConfigManager

async def use_saved_config():
    """Use saved COHN configuration."""
    client = GoProClient(identifier="1234")
    config_mgr = CohnConfigManager()
    
    # Try to load saved config
    saved_config = config_mgr.load_config("1234")
    
    await client.open_ble()
    
    if saved_config:
        # Use saved configuration
        print("Using saved COHN configuration")
        await client.apply_cohn_config(saved_config)
    else:
        # First time setup
        print("Configuring COHN for the first time")
        config = await client.configure_cohn(
            ssid="your-wifi",
            password="password"
        )
        # Save for future use
        config_mgr.save_config("1234", config)
    
    await client.wait_cohn_ready()
```

### Managing Multiple Camera Configs

```python
from gopro_sdk import CohnConfigManager

def manage_camera_configs():
    """Manage configurations for multiple cameras."""
    config_mgr = CohnConfigManager()
    
    # List all saved configurations
    configs = config_mgr.list_configs()
    print(f"Found {len(configs)} saved configurations")
    
    for identifier in configs:
        config = config_mgr.load_config(identifier)
        print(f"Camera {identifier}: {config.ssid}")
    
    # Delete old configuration
    config_mgr.delete_config("old_camera_id")
```

### Custom Cache Directory

```python
from gopro_sdk import CohnConfigManager
from pathlib import Path

# Use custom directory for config storage
custom_dir = Path.home() / ".gopro_configs"
config_mgr = CohnConfigManager(cache_dir=custom_dir)
```
