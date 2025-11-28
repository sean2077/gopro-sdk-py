# Architecture Overview

## Design Philosophy

This SDK is built on several core principles:

1. **Separation of Concerns** - Each component has a single, well-defined responsibility
2. **Composition over Inheritance** - Flexibility through component assembly rather than class hierarchies
3. **BLE-First Strategy** - Prioritize BLE commands for reliability; HTTP only when necessary
4. **Dual-Mode Support** - Offline mode (BLE only) by default, with optional online mode (BLE+WiFi)

This SDK implements the [OpenGoPro](https://github.com/gopro/OpenGoPro) protocol specifications and reuses OpenGoPro's protobuf definitions and constants. For detailed protocol documentation, refer to the [official OpenGoPro documentation](https://gopro.github.io/OpenGoPro/).

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
├─────────────────────────────────────────────────────────────┤
│  MultiCameraManager (multi_camera.py)                        │
│  - Batch operations across multiple cameras                  │
│  - Concurrent execution with configurable parallelism        │
│  - Per-camera error isolation                                │
└─────────────────────────────────────────────────────────────┘
                          ↓ manages
┌─────────────────────────────────────────────────────────────┐
│                      Client Layer                            │
├─────────────────────────────────────────────────────────────┤
│  GoProClient (client.py)                                     │
│  - Unified API for camera control                            │
│  - Offline/Online mode management                            │
│  - COHN credential persistence                               │
│  - Assembles command and connection components               │
└─────────────────────────────────────────────────────────────┘
                          ↓ delegates to
┌─────────────────────────────────────────────────────────────┐
│                     Command Layer                            │
├─────────────────────────────────────────────────────────────┤
│  BleCommands        │  HttpCommands     │  MediaCommands     │
│  - Shutter control  │  - Preview stream │  - File listing    │
│  - Date/time sync   │  - Camera state   │  - Download        │
│  - Tag highlight    │  - Settings       │  - Delete          │
│  - Load preset      │  - Digital zoom   │  - Metadata        │
│  - Sleep            │  - Reboot         │  - Turbo mode      │
│  - WiFi management  │  - Keep alive     │                    │
│  - COHN config      │                   │  WebcamCommands    │
│                     │                   │  - USB webcam mode │
└─────────────────────────────────────────────────────────────┘
                          ↓ uses
┌─────────────────────────────────────────────────────────────┐
│                   Connection Layer                           │
├─────────────────────────────────────────────────────────────┤
│  BleConnectionManager     │  HttpConnectionManager           │
│  - BLE connect/disconnect │  - HTTPS session management      │
│  - Response fragmentation │  - SSL context (COHN certs)      │
│  - Notification handling  │  - Basic auth credentials        │
│  - Async response queue   │  - Connection pooling            │
├───────────────────────────┴──────────────────────────────────┤
│  BleScanner               │  HealthCheckMixin                │
│  - Device discovery       │  - Connection health monitoring  │
│  - Streaming scan API     │  - Auto-reconnect logic          │
└─────────────────────────────────────────────────────────────┘
                          ↓ uses
┌─────────────────────────────────────────────────────────────┐
│                 Configuration & Utilities                    │
├─────────────────────────────────────────────────────────────┤
│  CohnConfigManager  │  TimeoutConfig    │  StateParser       │
│  - TinyDB storage   │  - BLE timeouts   │  - Raw → enum      │
│  - CRUD operations  │  - HTTP timeouts  │  - Status helpers  │
│  - Per-camera creds │  - WiFi timeouts  │                    │
│                     │  - COHN timeouts  │  Exceptions        │
│                     │                   │  - Custom hierarchy│
└─────────────────────────────────────────────────────────────┘
                          ↓ built on
┌─────────────────────────────────────────────────────────────┐
│                   External Dependencies                      │
├─────────────────────────────────────────────────────────────┤
│  bleak              │  aiohttp          │  open-gopro        │
│  - BLE operations   │  - HTTP client    │  - Protobuf defs   │
│  - Cross-platform   │  - Async I/O      │  - Constants       │
│                     │  - SSL support    │  - Parsers         │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### GoProClient

The main entry point providing a unified interface for camera control.

**Key Design Decisions:**

- **Offline mode by default** - BLE-only operation for scenarios without WiFi
- **Composition pattern** - Holds instances of command interfaces and connection managers
- **Delegation pattern** - High-level methods delegate to specialized command classes
- **BLE-first strategy** - Control commands prefer BLE for reliability

```python
class GoProClient(HealthCheckMixin):
    def __init__(self, target: str, offline_mode: bool = True, ...):
        # Connection managers
        self.ble = BleConnectionManager(target, timeout_config)
        self.http = HttpConnectionManager(target, timeout_config)

        # Command interfaces (composition)
        self.ble_commands = BleCommands(self.ble)
        self.http_commands = HttpCommands(self.http)
        self.media_commands = MediaCommands(self.http)
        self.webcam_commands = WebcamCommands(self.http)
```

**Command Routing Strategy:**

| Command Type | Protocol | Reason |
|-------------|----------|--------|
| Shutter control | BLE | More reliable, works offline |
| Date/time sync | BLE | More reliable, works offline |
| Tag highlight | BLE | More reliable, works offline |
| Load preset | BLE | More reliable, works offline |
| Sleep | BLE | More reliable, works offline |
| Preview stream | HTTP | Requires network for UDP stream |
| Media operations | HTTP | Large data transfer |
| Camera state query | HTTP | Comprehensive status data |
| Webcam mode | HTTP | USB mode control |

### Connection Layer

#### BleConnectionManager

Handles low-level BLE communication with response fragmentation.

**Key Features:**

- Direct use of \`bleak\` library for cross-platform BLE
- Response queue for async command handling
- BLE packet fragmentation/reassembly (Open GoPro protocol)
- Notification callback handling

**BLE Protocol Details:**

```python
# GoPro BLE packet header types
HEADER_TYPE_GENERAL = 0  # 5-bit length, max 31 bytes
HEADER_TYPE_EXT_13 = 1   # 13-bit length, max 8191 bytes
HEADER_TYPE_EXT_16 = 2   # 16-bit length, max 65535 bytes
```

#### HttpConnectionManager

Manages HTTPS connections for COHN (Camera on Home Network) mode.

**Key Features:**

- SSL context with camera's self-signed certificate
- HTTP Basic authentication
- Connection pooling via \`aiohttp.ClientSession\`
- Lazy connection (connects on first request)

```python
# COHN connection setup
ssl_context = ssl.create_default_context()
ssl_context.load_verify_locations(cadata=credentials.certificate)
auth = aiohttp.BasicAuth(credentials.username, credentials.password)
```

#### BleScanner

Discovers nearby GoPro cameras via BLE advertising.

**Key Features:**

- Streaming scan API with \`AsyncIterator\`
- Idle timeout for early termination
- Target count for batch discovery
- Serial number extraction from device names

```python
async for devices in BleScanner.scan_devices_stream(duration=8.0):
    for dev in devices:
        print(f"Found: {dev['name']} ({dev['serial']})")
```

### Command Layer

#### BleCommands

Implements commands executed via BLE, using simple byte commands and protobuf messages.

**Simple Commands** (CmdId-based):
```python
# Format: [cmd_id, param_len, ...params]
command_data = bytes([CmdId.SET_SHUTTER, 0x01, shutter_value])
await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)
```

**Protobuf Commands** (FeatureId + ActionId):
```python
# COHN configuration, WiFi management, etc.
command_data = bytes([feature_id, action_id]) + proto_message.SerializeToString()
await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)
```

#### HttpCommands

Implements commands executed via HTTP REST API.

**Key Features:**

- Automatic retry decorator for transient failures
- JSON response parsing
- Error handling with custom exceptions

```python
@with_http_retry(max_retries=3)
async def get_camera_state(self) -> dict[str, Any]:
    async with self.http.get("gopro/camera/state") as resp:
        return await resp.json()
```

#### MediaCommands

Handles media file operations.

**Key Features:**

- File listing with \`MediaFile\` dataclass
- Streaming download with progress callback
- Turbo transfer mode support

#### WebcamCommands

Controls USB webcam mode.

**Key Features:**

- Resolution and FOV configuration
- Protocol selection (TS/RTSP)
- Status monitoring

### Configuration Layer

#### CohnConfigManager

Persists COHN credentials using TinyDB.

**Storage Format:**
```json
{
  "camera_id": "1332",
  "ip_address": "192.168.1.100",
  "username": "gopro",
  "password": "xxx",
  "certificate": "-----BEGIN CERTIFICATE-----..."
}
```

#### TimeoutConfig

Centralized timeout configuration with sensible defaults.

```python
@dataclass
class TimeoutConfig:
    # BLE timeouts
    ble_connect_timeout: float = 20.0
    ble_response_timeout: float = 5.0

    # HTTP timeouts
    http_request_timeout: float = 30.0
    http_download_timeout: float = 300.0

    # WiFi timeouts
    wifi_connect_configured_timeout: float = 15.0
    wifi_provision_timeout: float = 60.0

    # COHN timeouts
    cohn_provision_timeout: float = 60.0
```

### Exception Hierarchy

```
CustomGoProError (base)
├── BleConnectionError
│   └── BleTimeoutError
├── HttpConnectionError
├── CohnNotConfiguredError
└── CohnConfigurationError
```

## Operating Modes

### Offline Mode (Default)

BLE-only operation for scenarios without WiFi or when WiFi is unreliable.

**Supported Features:**

- Recording control (start/stop)
- Date/time synchronization
- Tag highlight
- Load preset / preset group
- Sleep

**Not Supported:**

- Preview stream (requires UDP)
- Media download (requires HTTP)
- Camera state queries (HTTP only)
- Webcam mode (USB)

### Online Mode

BLE + WiFi/COHN for full functionality.

**Connection Flow:**
```
1. BLE connect
2. WiFi configuration (if credentials provided)
3. COHN credential retrieval/refresh
4. HTTP session initialization (lazy)
```

**Dynamic Mode Switching:**
```python
async with GoProClient("1332") as client:  # Starts in offline mode
    await client.start_recording()  # Works via BLE

    # Switch to online when needed
    await client.switch_to_online_mode(wifi_ssid="MyWiFi", wifi_password="pass")
    await client.start_preview()  # Now available
```

## Multi-Camera Management

\`MultiCameraManager\` provides coordinated control of multiple cameras.

**Key Features:**

- Configurable concurrency (\`max_concurrent\`)
- Per-camera error isolation
- Batch operations with aggregated results
- Camera status tracking

```python
async with MultiCameraManager(["1332", "1333", "1334"]) as manager:
    await manager.connect_all()

    # Execute on all cameras
    results = await manager.execute_all(lambda c: c.start_recording())

    # Get all statuses
    statuses = manager.get_camera_status()
```

## Data Flow Examples

### BLE Command Execution

```
GoProClient.start_recording()
    └─> BleCommands.set_shutter(True)
        └─> Build command: [0x01, 0x01, 0x01]
        └─> BleConnectionManager.write(CQ_COMMAND, data)
            └─> BleakClient.write_gatt_char()
        └─> BleConnectionManager.wait_for_response()
            └─> Response queue.get()
        └─> Parse response: [cmd_id, status_code]
```

### HTTP Command Execution

```
GoProClient.get_camera_state()
    └─> HttpCommands.get_camera_state()
        └─> HttpConnectionManager.get("gopro/camera/state")
            └─> aiohttp session request
            └─> SSL verification with COHN cert
            └─> Basic auth header
        └─> Parse JSON response
        └─> Return state dict
```

### COHN Configuration Flow

```
GoProClient.open() [online mode]
    └─> BleConnectionManager.connect()
    └─> [Optional] BleCommands.connect_to_wifi(ssid, password)
    └─> Check CohnConfigManager for existing credentials
    └─> If not exists:
        └─> BleCommands.configure_cohn()
            └─> REQUEST_CREATE_COHN_CERT via BLE
            └─> Wait for COHN_PROVISIONED state
            └─> REQUEST_GET_COHN_CERT via BLE
            └─> REQUEST_GET_COHN_STATUS via BLE
        └─> CohnConfigManager.save(credentials)
    └─> Else:
        └─> Refresh IP address from camera
    └─> HttpConnectionManager.set_credentials()
```

## Extension Points

### Adding New BLE Commands

1. Add command method to \`BleCommands\`
2. Use \`CmdId\` constants or define protobuf messages
3. Handle response parsing
4. Add convenience method to \`GoProClient\`

```python
# In ble_commands.py
async def new_command(self, param: int) -> None:
    command_data = bytes([CmdId.NEW_CMD, 0x01, param])
    await self.ble.write(GoProBleUUID.CQ_COMMAND, command_data)
    response = await self.ble.wait_for_response()
    # Parse response...
```

### Adding New HTTP Commands

1. Add command method to \`HttpCommands\`
2. Use \`@with_http_retry\` decorator
3. Add to \`GoProClient\` with offline mode check

```python
# In http_commands.py
@with_http_retry(max_retries=3)
async def new_command(self) -> dict[str, Any]:
    async with self.http.get("gopro/new/endpoint") as resp:
        return await resp.json()

# In client.py
async def new_command(self) -> dict[str, Any]:
    self._require_online_mode("New command")
    return await self.http_commands.new_command()
```

### Custom Configuration Storage

Extend \`CohnConfigManager\` for alternative storage:

```python
class RedisConfigManager(CohnConfigManager):
    def save(self, camera_id: str, credentials: CohnCredentials) -> None:
        # Save to Redis
        pass

    def load(self, camera_id: str) -> CohnCredentials | None:
        # Load from Redis
        pass
```

## Performance Considerations

### Connection Management

- **BLE connection reuse** - Single connection per camera session
- **HTTP session pooling** - \`aiohttp.ClientSession\` manages connection pool
- **Lazy HTTP connection** - Only connects when first HTTP request is made

### Concurrency

- **All I/O is async** - Non-blocking operations throughout
- **Multi-camera parallelism** - \`asyncio.gather()\` with semaphore control
- **Response queue** - Efficient BLE notification dispatching

### Timeout Tuning

\`TimeoutConfig\` allows fine-tuning based on network conditions:

```python
config = TimeoutConfig(
    ble_connect_timeout=30.0,      # Slow BLE environment
    http_request_timeout=60.0,     # High-latency network
    wifi_provision_timeout=120.0,  # Slow WiFi setup
)
client = GoProClient("1332", timeout_config=config)
```
