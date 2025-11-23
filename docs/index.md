# Welcome to GoPro SDK for Python

A production-ready Python SDK for controlling GoPro cameras, specifically designed and optimized for multi-camera COHN (Camera on Home Network) scenarios.

## Overview

This SDK addresses critical limitations in the official OpenGoPro SDK, providing:

- **Multi-Camera Support**: Efficient concurrent control of multiple GoPro cameras
- **Persistent COHN Configuration**: Save and restore COHN settings without reconfiguration
- **Optimized Connection Management**: Eliminate unnecessary connection cycles and resource waste
- **Robust State Tracking**: Accurate connection state management for COHN mode
- **Production-Ready Error Handling**: Comprehensive exception handling and recovery mechanisms

## Quick Example

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    client = GoProClient(identifier="1234")

    await client.open_ble()
    await client.configure_cohn(ssid="your-wifi", password="password")
    await client.wait_cohn_ready(timeout=30)

    # Start recording
    await client.set_shutter(on=True)
    await asyncio.sleep(5)
    await client.set_shutter(on=False)

    await client.close()

asyncio.run(main())
```

## Installation

```bash
pip install gopro-sdk-py
```

For development setup and alternative installation methods, see the [Quick Start Guide](quickstart.md#installation).

## Key Features

- **Multi-Camera Control** - Concurrent management of multiple cameras with `MultiCameraManager`
- **Persistent Configuration** - Save and reuse COHN settings with `CohnConfigManager`
- **Type-Safe API** - Full type hints for better IDE support
- **Production-Ready** - Comprehensive error handling and retry mechanisms

## Documentation

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } **Quick Start**

    ---

    Get up and running in minutes with installation and basic usage examples.

    [:octicons-arrow-right-24: Quick Start](quickstart.md)

-   :material-help-circle:{ .lg .middle } **Why This SDK?**

    ---

    Understand the rationale and advantages over the official OpenGoPro SDK.

    [:octicons-arrow-right-24: Learn More](why-this-sdk.md)

-   :material-code-braces:{ .lg .middle } **API Reference**

    ---

    Complete API documentation auto-generated from source code.

    [:octicons-arrow-right-24: API Docs](api/overview.md)

-   :material-github:{ .lg .middle } **Development**

    ---

    Contributing guidelines and development setup instructions.

    [:octicons-arrow-right-24: Contribute](development.md)

</div>

## Requirements

- Python 3.12 or higher
- Windows, macOS, or Linux
- Bluetooth adapter (for BLE connection)
- Network connectivity (for COHN mode)

## Support

- [GitHub Issues](https://github.com/sean2077/gopro-sdk-py/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/sean2077/gopro-sdk-py/discussions) - Questions and community discussion

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/sean2077/gopro-sdk-py/blob/main/LICENSE) file for details.
