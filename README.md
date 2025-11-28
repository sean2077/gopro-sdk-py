# GoPro SDK for Python

A production-ready Python SDK for controlling GoPro cameras, specifically designed and optimized for multi-camera COHN (Camera on Home Network) scenarios.

## Features

- **Multi-Camera Support**: Efficient concurrent control of multiple GoPro cameras
- **Persistent COHN Configuration**: Save and restore COHN settings without reconfiguration
- **Optimized Connection Management**: Eliminate unnecessary connection cycles and resource waste
- **Robust State Tracking**: Accurate connection state management for COHN mode
- **Production-Ready Error Handling**: Comprehensive exception handling and recovery mechanisms

See [Why This SDK?](https://sean2077.github.io/gopro-sdk-py/why-this-sdk/) for detailed rationale and comparison with OpenGoPro.

## Quick Start

```bash
uv add gopro-sdk-py
# Or use pip
pip install gopro-sdk-py
```

```python
import asyncio
from gopro_sdk import GoProClient

async def main():
    client = GoProClient(identifier="GoPro 1234")
    await client.open_ble()
    await client.configure_cohn(ssid="your-wifi", password="password")
    await client.set_shutter(on=True)
    await client.close()

asyncio.run(main())
```

## Documentation

📖 **[Full Documentation](https://sean2077.github.io/gopro-sdk-py/)**

- [Quick Start Guide](https://sean2077.github.io/gopro-sdk-py/quickstart/) - Installation and basic usage
- [API Reference](https://sean2077.github.io/gopro-sdk-py/api/overview/) - Complete API documentation
- [Development Guide](https://sean2077.github.io/gopro-sdk-py/development/) - Setup, testing, and contribution guidelines

## Contributing

Contributions are welcome! Please check out our [documentation](https://sean2077.github.io/gopro-sdk-py/development/) for development setup and guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- [GitHub Issues](https://github.com/sean2077/gopro-sdk-py/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/sean2077/gopro-sdk-py/discussions) - Questions and community discussion

## Related Projects

- [OpenGoPro](https://github.com/gopro/OpenGoPro) - Official GoPro Open SDK and protocol specifications
- [OpenGoPro Python SDK](https://gopro.github.io/OpenGoPro/python_sdk/) - Official Python implementation

**Note**: This SDK builds upon OpenGoPro's protocol specifications and reuses its protobuf definitions, BLE UUIDs, and command constants. We acknowledge and appreciate GoPro's excellent work in documenting and open-sourcing the camera control protocol.
