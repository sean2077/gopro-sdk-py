"""Re-exported protobuf models from open_gopro for convenient access.

This package provides direct access to all GoPro protobuf definitions without
requiring users to depend on open_gopro directly.

Usage:
    from gopro_sdk import proto

    # Access protobuf modules
    from gopro_sdk.proto import cohn_pb2, network_management_pb2

    # Access protobuf enums and messages
    from gopro_sdk.proto import EnumCOHNStatus, RequestGetCOHNStatus

    # Access specific items from pb2 modules
    from gopro_sdk.proto.preset_status_pb2 import PRESET_GROUP_ID_VIDEO
"""

# Make individual pb2 modules accessible as submodules
# Re-export the entire proto module contents
from open_gopro.models.proto import *  # noqa: F403
from open_gopro.models.proto import camera_control_pb2 as camera_control_pb2
from open_gopro.models.proto import cohn_pb2 as cohn_pb2
from open_gopro.models.proto import live_streaming_pb2 as live_streaming_pb2
from open_gopro.models.proto import media_pb2 as media_pb2
from open_gopro.models.proto import network_management_pb2 as network_management_pb2
from open_gopro.models.proto import preset_status_pb2 as preset_status_pb2
from open_gopro.models.proto import request_get_preset_status_pb2 as request_get_preset_status_pb2
from open_gopro.models.proto import response_generic_pb2 as response_generic_pb2
from open_gopro.models.proto import set_camera_control_status_pb2 as set_camera_control_status_pb2
from open_gopro.models.proto import turbo_transfer_pb2 as turbo_transfer_pb2
