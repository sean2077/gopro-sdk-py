# API Reference

The GoPro SDK provides a comprehensive API for controlling GoPro cameras. This reference documentation is automatically generated from the source code docstrings.

## Main Components

### Client API
The [`GoProClient`](client.md) class provides the main interface for controlling a single camera.

### Multi-Camera Management
The [`MultiCameraManager`](multi-camera.md) class enables efficient concurrent control of multiple cameras.

### Commands
Various command classes for different protocols and operations:

- [BLE Commands](commands.md#ble-commands)
- [HTTP Commands](commands.md#http-commands)
- [Media Commands](commands.md#media-commands)
- [Webcam Commands](commands.md#webcam-commands)

### Connection Management
Connection lifecycle and health monitoring:

- [BLE Connection Manager](connection.md#ble-connection-manager)
- [HTTP Connection Manager](connection.md#http-connection-manager)
- [Health Check Mixin](connection.md#health-check-mixin)

### Configuration
Configuration and credential management:

- [TimeoutConfig](config.md#timeoutconfig)
- [CohnConfigManager](config.md#cohnconfigmanager)
- [CohnCredentials](config.md#cohncredentials)

### Exceptions
Comprehensive exception hierarchy for error handling:

- [Base Exceptions](exceptions.md#base-exceptions)
- [Connection Exceptions](exceptions.md#connection-exceptions)
- [Configuration Exceptions](exceptions.md#configuration-exceptions)

## Quick Navigation

- **Getting Started**: See [Quick Start](../quickstart.md) for basic usage
- **Architecture**: See [Architecture](../architecture.md) for design overview
- **Examples**: Check the [Examples](../examples/basic.md) section for code samples

## Type Annotations

All public APIs are fully typed. Use the following imports for type checking:

```python
from gopro_sdk import (
    GoProClient,
    MultiCameraManager,
    CohnConfigManager,
    CohnCredentials,
    TimeoutConfig,
)
```
