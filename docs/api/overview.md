# API Reference

!!! info "Auto-Generated Documentation"
    This reference documentation is automatically generated from source code docstrings using [mkdocstrings](https://mkdocstrings.github.io/).

## Main Components

<div class="grid cards" markdown>

-   :material-camera:{ .lg } **[GoProClient](client.md)**

    ---

    Main interface for controlling a single GoPro camera

    [:octicons-arrow-right-24: Client API](client.md)

-   :material-camera-burst:{ .lg } **[MultiCameraManager](multi-camera.md)**

    ---

    Efficient concurrent control of multiple cameras

    [:octicons-arrow-right-24: Multi-Camera API](multi-camera.md)

-   :material-console:{ .lg } **[Commands](commands.md)**

    ---

    BLE, HTTP, Media, and Webcam command interfaces

    [:octicons-arrow-right-24: Commands API](commands.md)

-   :material-connection:{ .lg } **[Connection](connection.md)**

    ---

    BLE and HTTP connection management with health checks

    [:octicons-arrow-right-24: Connection API](connection.md)

-   :material-cog:{ .lg } **[Configuration](config.md)**

    ---

    Timeout settings and COHN credential management

    [:octicons-arrow-right-24: Config API](config.md)

-   :material-alert-circle:{ .lg } **[Exceptions](exceptions.md)**

    ---

    Comprehensive exception hierarchy for error handling

    [:octicons-arrow-right-24: Exceptions API](exceptions.md)

</div>

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
