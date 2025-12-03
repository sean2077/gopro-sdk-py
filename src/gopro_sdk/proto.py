"""Re-exported protobuf models from open_gopro for convenient access.

This module provides direct access to all GoPro protobuf definitions without
requiring users to depend on open_gopro directly.

Usage:
    from gopro_sdk import proto

    # Access protobuf modules
    from gopro_sdk.proto import cohn_pb2, network_management_pb2

    # Access protobuf enums and messages
    from gopro_sdk.proto import EnumCOHNStatus, RequestGetCOHNStatus
"""

# Also make individual pb2 modules accessible
# Re-export the entire proto module
from open_gopro.models.proto import *  # noqa: F403
from open_gopro.models.proto import (  # noqa: F401
    camera_control_pb2,
    cohn_pb2,
    live_streaming_pb2,
    media_pb2,
    network_management_pb2,
    preset_status_pb2,
    request_get_preset_status_pb2,
    response_generic_pb2,
    set_camera_control_status_pb2,
    turbo_transfer_pb2,
)
