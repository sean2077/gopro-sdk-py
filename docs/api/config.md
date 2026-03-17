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
from gopro_sdk import GoProClient
from gopro_sdk.config import TimeoutConfig

# Create custom timeout configuration
timeouts = TimeoutConfig(
    ble_connect_timeout=30.0,         # 30 seconds for BLE connection
    ble_response_timeout=10.0,        # 10 seconds for BLE response
    http_request_timeout=60.0,        # 60 seconds for HTTP requests
    wifi_provision_timeout=120.0,     # 120 seconds for WiFi setup
    cohn_provision_timeout=90.0,      # 90 seconds for COHN setup
)

async with GoProClient("1234", timeout_config=timeouts) as client:
    await client.start_recording()
```

### Persistent COHN Configuration

The SDK automatically manages COHN credential persistence via `CohnConfigManager`.
When using online mode, credentials are saved on first connection and reused on subsequent connections.

```python
from gopro_sdk import GoProClient, CohnConfigManager

async def use_persistent_config():
    """COHN credentials are automatically persisted."""
    # First connection: credentials are fetched and saved
    async with GoProClient(
        "1234",
        offline_mode=False,
        wifi_ssid="your-wifi",
        wifi_password="password",
    ) as client:
        status = await client.get_camera_state()
        print(f"Camera state: {status}")

    # Subsequent connections: saved credentials are reused automatically
    async with GoProClient(
        "1234",
        offline_mode=False,
    ) as client:
        print("Connected using saved COHN credentials!")
```

### Managing Multiple Camera Configs

```python
from gopro_sdk import CohnConfigManager, CohnCredentials

def manage_camera_configs():
    """Manage configurations for multiple cameras."""
    with CohnConfigManager() as config_mgr:
        # List all saved configurations
        all_creds = config_mgr.list_all()
        print(f"Found {len(all_creds)} saved configurations")

        for serial, creds in all_creds.items():
            print(f"Camera {serial}: IP {creds.ip_address}")

        # Load specific camera credentials
        creds = config_mgr.load("1234")
        if creds:
            print(f"Camera 1234: {creds.ip_address}")

        # Delete old configuration
        config_mgr.delete("old_camera_id")
```

### Custom Database Path

```python
from gopro_sdk import CohnConfigManager
from pathlib import Path

# Use custom path for credential storage
custom_path = Path.home() / ".gopro" / "cohn_credentials.json"
config_mgr = CohnConfigManager(db_path=custom_path)
```
