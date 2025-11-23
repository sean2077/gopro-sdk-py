"""GoPro SDK - A Python SDK for controlling GoPro cameras.

Optimized for multi-camera COHN (Camera on Home Network) scenarios with modular design.

Main components:
- connection/: BLE and HTTP connection management
- commands/: BLE, HTTP, media, and webcam command implementations
- client.py: Main client interface (composition + delegation pattern)
- config.py: Configuration management for COHN and timeouts
- multi_camera.py: Multi-camera coordination utilities

Key features:
- Persistent COHN configuration
- Efficient multi-camera management
- Robust connection handling
- Comprehensive state parsing
"""

__version__ = "0.1.0"

from .client import GoProClient
from .config import CohnConfigManager, CohnCredentials
from .multi_camera import MultiCameraManager

__all__ = [
    "GoProClient",
    "MultiCameraManager",
    "CohnConfigManager",
    "CohnCredentials",
]
