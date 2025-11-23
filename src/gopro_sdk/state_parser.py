"""GoPro camera state parser.

Based on the Open GoPro SDK parsing logic, converts raw state data into readable enumeration types.
"""

from __future__ import annotations

__all__ = [
    "parse_camera_state",
    "format_camera_state",
    "get_status_value",
    "get_setting_value",
    "is_camera_busy",
    "is_camera_encoding",
    "is_preview_stream_active",
]

import logging
from typing import Any

from construct import FormatFieldError
from open_gopro.domain.communicator_interface import GlobalParsers
from open_gopro.models.constants import SettingId, StatusId
from open_gopro.models.types import CameraState, ResponseType

logger = logging.getLogger(__name__)


def parse_camera_state(raw_state: dict[str, Any]) -> CameraState:
    """Parse camera state data.

    Converts raw state dictionary (with string or integer ID keys) to a dictionary using enumeration types.

    Args:
        raw_state: Raw state data in the format:
            {
                "status": {"10": 0, "32": 1, ...},
                "settings": {"2": 1, "3": 8, ...}
            }

    Returns:
        Parsed state dictionary in the format:
            {
                StatusId.ENCODING: False,
                StatusId.PREVIEW_STREAM: True,
                SettingId.VIDEO_RESOLUTION: VideoResolution.NUM_4K,
                ...
            }

    Examples:
        >>> raw = {"status": {"10": 0, "32": 1}, "settings": {"2": 1}}
        >>> parsed = parse_camera_state(raw)
        >>> parsed[StatusId.ENCODING]
        False
        >>> parsed[StatusId.PREVIEW_STREAM]
        True
    """
    parsed: dict = {}

    # Parse status and settings fields
    for name, id_map in [("status", StatusId), ("settings", SettingId)]:
        if name not in raw_state:
            logger.warning(f"State data missing '{name}' field")
            continue

        for k, v in raw_state[name].items():
            try:
                # Convert string ID to integer
                identifier: ResponseType = id_map(int(k))

                # Try to get the corresponding parser
                parser_builder = GlobalParsers.get_query_container(identifier)
                if not parser_builder:
                    # No specific parser, use raw value directly
                    parsed[identifier] = v
                else:
                    # Use parser to convert value (e.g., integer -> enum)
                    parsed[identifier] = parser_builder(v)

            except (ValueError, FormatFieldError) as e:
                logger.debug(f"⚠️ Unable to parse {name}::{k}, value: {v} ==> {repr(e)}")
                continue

    return parsed


def format_camera_state(state: CameraState, verbose: bool = False) -> str:
    """Format camera state as readable string.

    Args:
        state: Parsed state dictionary
        verbose: Whether to display detailed information (including unknown states)

    Returns:
        Formatted string

    Examples:
        >>> state = {StatusId.ENCODING: False, StatusId.BUSY: False}
        >>> print(format_camera_state(state))
        📊 Camera State:a State:
          ✅ ENCODING: False
          ✅ BUSY: False
    """
    lines = ["📊 Camera State:"]

    for key, value in sorted(state.items(), key=lambda x: str(x[0])):
        key_name = key.name if hasattr(key, "name") else str(key)
        value_str = value.name if hasattr(value, "name") else str(value)

        # Choose emoji based on state type
        if isinstance(key, StatusId):
            emoji = "📡"
        elif isinstance(key, SettingId):
            emoji = "⚙️"
        else:
            emoji = "❓"

        lines.append(f"  {emoji} {key_name}: {value_str}")

    return "\n".join(lines)


def get_status_value(state: CameraState, status_id: StatusId) -> Any | None:
    """Get the value of a specified status from the state dictionary.

    Args:
        state: Parsed state dictionary
        status_id: Status ID

    Returns:
        Status value, or None if it doesn't exist

    Examples:
        >>> state = parse_camera_state(raw_state)
        >>> is_encoding = get_status_value(state, StatusId.ENCODING)
        >>> if is_encoding:
        ...     print("Camera is recording")
    """
    return state.get(status_id)


def get_setting_value(state: CameraState, setting_id: SettingId) -> Any | None:
    """Get the value of a specified setting from the state dictionary.

    Args:
        state: Parsed state dictionary
        setting_id: Setting ID

    Returns:
        Setting value, or None if it doesn't exist

    Examples:
        >>> state = parse_camera_state(raw_state)
        >>> resolution = get_setting_value(state, SettingId.VIDEO_RESOLUTION)
        >>> print(f"Current resolution: {resolution}")
    """
    return state.get(setting_id)


def is_camera_busy(state: CameraState) -> bool:
    """Check if camera is busy.

    Args:
        state: Parsed state dictionary

    Returns:
        True if camera is busy

    Examples:
        >>> if is_camera_busy(state):
        ...     print("Camera is busy, please wait...")
    """
    busy = get_status_value(state, StatusId.BUSY)
    return bool(busy) if busy is not None else False


def is_camera_encoding(state: CameraState) -> bool:
    """Check if camera is currently recording.

    Args:
        state: Parsed state dictionary

    Returns:
        True if recording

    Examples:
        >>> if is_camera_encoding(state):
        ...     print("🔴 Recording...")
    """
    encoding = get_status_value(state, StatusId.ENCODING)
    return bool(encoding) if encoding is not None else False


def is_preview_stream_active(state: CameraState) -> bool:
    """Check if preview stream is active.

    Args:
        state: Parsed state dictionary

    Returns:
        True if preview stream is active

    Examples:
        >>> if is_preview_stream_active(state):
        ...     print("📹 Preview stream is active")
    """
    preview = get_status_value(state, StatusId.PREVIEW_STREAM)
    return bool(preview) if preview is not None else False
