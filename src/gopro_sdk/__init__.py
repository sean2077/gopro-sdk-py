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

from importlib.metadata import version

__version__ = version("gopro-sdk-py")

from .client import GoProClient
from .config import CohnConfigManager, CohnCredentials
from .connection.ble_scanner import BleScanner
from .logging_config import get_logger, setup_logging
from .multi_camera import MultiCameraManager
from .rich_utils import Console, Progress, Table, console, create_progress, create_table
from .state_parser import format_camera_state, get_status_value, is_camera_encoding

__all__ = [
    "BleScanner",
    "CohnConfigManager",
    "CohnCredentials",
    "Console",
    "GoProClient",
    "MultiCameraManager",
    "Progress",
    "Table",
    "console",
    "create_progress",
    "create_table",
    "format_camera_state",
    "get_logger",
    "get_status_value",
    "is_camera_encoding",
    "setup_logging",
]
