# GUI Example: GoPro Control

For a complete GUI application built with this SDK, check out [**GoPro Control**](https://github.com/sean2077/gopro-control) - a desktop application for controlling GoPro cameras.

## Features

- Visual camera connection management
- Real-time preview stream display
- Recording control with status indicators
- Media browser and download manager
- Multi-camera support
- Cross-platform (Windows, macOS, Linux)

## Screenshot

Visit the [project repository](https://github.com/sean2077/gopro-control) for screenshots and demo videos.

## Getting Started

```bash
# Clone the repository
git clone https://github.com/sean2077/gopro-control.git
cd gopro-control

# Install dependencies
uv sync

# Run the application
uv run python -m gopro_control
```

## Architecture

GoPro Control uses this SDK (`gopro-sdk-py`) as its core library for camera communication:

```
┌─────────────────────────────────────┐
│         GoPro Control (GUI)         │
│    - User Interface (Qt/Tk/...)     │
│    - Preview Display                │
│    - Media Browser                  │
├─────────────────────────────────────┤
│           gopro-sdk-py              │
│    - BLE/WiFi Communication         │
│    - Camera Commands                │
│    - Media Management               │
├─────────────────────────────────────┤
│           GoPro Camera              │
└─────────────────────────────────────┘
```

## Contributing

The GUI project welcomes contributions. Visit the [GitHub repository](https://github.com/sean2077/gopro-control) to:

- Report issues
- Submit feature requests
- Contribute code
