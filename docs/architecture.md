# Architecture Overview

## Design Philosophy

!!! abstract "Core Principles"
    The gopro-sdk-py is built on three core principles:

    1. :material-puzzle-outline: **Separation of Concerns** - Each component has a single, well-defined responsibility
    2. :material-puzzle: **Composition over Inheritance** - Flexibility through component assembly rather than class hierarchies
    3. :material-eye-check: **Explicit over Implicit** - Clear, predictable behavior with no hidden magic

!!! info "Protocol Foundation"
    This SDK implements the [OpenGoPro](https://github.com/gopro/OpenGoPro) protocol specifications and reuses OpenGoPro's protobuf definitions and constants. For detailed protocol documentation, refer to the [official OpenGoPro documentation](https://gopro.github.io/OpenGoPro/).

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Multi-Camera Management (multi_camera.py)                   │
│  - MultiCameraManager: Batch control and state sync          │
│  - Concurrent camera operations                              │
└─────────────────────────────────────────────────────────────┘
                          ↓ uses
┌─────────────────────────────────────────────────────────────┐
│  Client Layer (client.py)                                    │
│  - GoProClient: Main client interface                        │
│  - Connection state management                               │
│  - COHN persistence support                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓ uses
┌─────────────────────────────────────────────────────────────┐
│  Command Layer (commands/)                                   │
│  ├── BleCommands: COHN config, WiFi management               │
│  ├── HttpCommands: Recording, settings, status               │
│  ├── MediaCommands: Media list, download, delete             │
│  └── WebcamCommands: USB mode control                        │
└─────────────────────────────────────────────────────────────┘
                          ↓ uses
┌─────────────────────────────────────────────────────────────┐
│  Connection Layer (connection/)                              │
│  ├── BleConnectionManager: BLE connection + response queue   │
│  ├── HttpConnectionManager: HTTP/COHN connection             │
│  └── HealthCheckMixin: Connection health monitoring          │
└─────────────────────────────────────────────────────────────┘
                          ↓ uses
┌─────────────────────────────────────────────────────────────┐
│  Configuration & Utilities                                   │
│  ├── CohnConfigManager: Persistent COHN storage              │
│  ├── TimeoutConfig: Timeout settings                         │
│  ├── StateParser: Camera state parsing                       │
│  └── Exceptions: Custom exception hierarchy                  │
└─────────────────────────────────────────────────────────────┘
                          ↓ uses
┌─────────────────────────────────────────────────────────────┐
│  OpenGoPro Foundation                                        │
│  - BleClient (based on bleak)                                │
│  - Protocol Parsers (protobuf)                               │
│  - Constants and Models                                      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### Client Layer

**GoProClient** is the main entry point, providing a unified interface for camera control.

Key features:
- Delegates to specialized command and connection managers
- Manages overall connection lifecycle
- Coordinates between BLE and HTTP operations
- Provides high-level convenience methods

Example structure:
```python
class GoProClient:
    def __init__(self, identifier: str):
        self.ble_manager = BleConnectionManager()
        self.http_manager = HttpConnectionManager()
        self.ble_commands = BleCommands(self.ble_manager)
        self.http_commands = HttpCommands(self.http_manager)
        # ...
```

### Command Layer

Commands are organized by protocol and functionality:

**BleCommands**: Low-level BLE operations
- COHN configuration
- WiFi network management
- Camera pairing

**HttpCommands**: HTTP API operations
- Recording control
- Camera settings
- Status queries

**MediaCommands**: Media management
- File listing
- Download with progress tracking
- Deletion

**WebcamCommands**: Webcam mode
- USB mode activation
- Stream control

### Connection Layer

**BleConnectionManager**:
- Manages BLE connection lifecycle
- Response queue for async command handling
- Automatic retry on connection failures

**HttpConnectionManager**:
- HTTP session management for COHN
- Connection pooling
- Timeout handling

**HealthCheckMixin**:
- Periodic connection health checks
- Automatic reconnection on failures
- Configurable check intervals

### Configuration Layer

**CohnConfigManager**:
- Persists COHN configuration to disk
- Automatic loading on startup
- Secure credential storage

**TimeoutConfig**:
- Centralized timeout management
- Per-operation timeout customization
- Default values for common operations

## Data Flow

### Connection Establishment

```
1. Client.open_ble()
   └─> BleConnectionManager.connect()
       └─> Scan for camera
       └─> Establish BLE connection
       └─> Start response queue

2. Client.configure_cohn()
   └─> BleCommands.configure_cohn()
       └─> Send COHN config via BLE
       └─> Wait for acknowledgment
       └─> CohnConfigManager.save_config()

3. Client.wait_cohn_ready()
   └─> Poll camera status via HTTP
   └─> Wait for COHN state = ready
```

### Command Execution

```
BLE Command:
  Client.method()
    └─> BleCommands.command()
        └─> BleConnectionManager.send()
            └─> Wait for response in queue
            └─> Return result

HTTP Command:
  Client.method()
    └─> HttpCommands.command()
        └─> HttpConnectionManager.request()
            └─> Send HTTP request
            └─> Parse response
            └─> Return result
```

## State Management

### Connection States

```
BLE Connection:
  disconnected → connecting → connected → ready
                      ↓
                  connection_failed

COHN Connection:
  unconfigured → configuring → configured → ready
                      ↓
                 config_failed
```

### Error Handling

Custom exception hierarchy:
```
GoproSdkError (base)
├── ConnectionError
│   ├── BleConnectionError
│   └── HttpConnectionError
├── ConfigurationError
│   └── CohnConfigError
├── CommandError
│   ├── BleCommandError
│   └── HttpCommandError
└── StateError
    └── InvalidStateError
```

## Concurrency Model

### Async/Await Pattern

All I/O operations are async:
- BLE communication
- HTTP requests
- File operations

Benefits:
- Efficient resource usage
- Natural concurrent multi-camera control
- Non-blocking operations

### Multi-Camera Coordination

**MultiCameraManager** provides:
- Parallel connection establishment
- Synchronized command execution
- Aggregated status queries
- Graceful error handling per camera

Example:
```python
manager = MultiCameraManager()
await manager.connect_all(camera_ids)
await manager.execute_all("set_shutter", on=True)
statuses = await manager.get_all_status()
```

## Extension Points

### Adding New Commands

1. Create command method in appropriate command class
2. Use existing connection manager
3. Handle errors appropriately
4. Add convenience method to GoProClient if needed

### Custom Connection Handling

Implement `HealthCheckMixin` for custom health check logic:
```python
class CustomClient(GoProClient, HealthCheckMixin):
    async def check_health(self) -> bool:
        # Custom health check logic
        pass
```

### Custom Configuration Storage

Extend `CohnConfigManager`:
```python
class DatabaseConfigManager(CohnConfigManager):
    def save_config(self, identifier: str, config: CohnCredentials):
        # Save to database instead of file
        pass
```

## Performance Considerations

### Connection Pooling

HTTP connections are reused via `HttpConnectionManager` session pooling.

### Response Queue

BLE responses are efficiently queued and dispatched to waiting commands without blocking.

### Batch Operations

`MultiCameraManager` executes commands in parallel rather than sequentially.

### Timeout Tuning

`TimeoutConfig` allows fine-tuning timeouts based on network conditions and operation types.

## Testing Strategy

### Unit Tests

Test individual components in isolation:
- Command classes with mocked connections
- Connection managers with mocked BLE/HTTP
- Configuration managers with temporary storage

### Integration Tests

Test component interactions:
- Client with real command/connection flow
- Multi-camera manager with multiple clients

### Hardware Tests

Optional tests requiring real cameras:
- Mark with `@pytest.mark.hardware`
- Skip in CI, run manually

## Future Enhancements

Potential areas for extension:
- WebSocket support for real-time status
- Advanced media management (thumbnails, metadata)
- Recording templates and presets
- Cloud storage integration
- Enhanced error recovery strategies
