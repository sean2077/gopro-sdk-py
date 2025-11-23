"""Basic functionality tests - pytest version.

Tests core GoProClient functionality including BLE connection, HTTP connection, status queries, etc.
"""

import asyncio
import logging
from datetime import datetime

import pytest
from open_gopro.models.constants import StatusId
from open_gopro.models.constants.settings import Led, SettingId

from gopro_sdk import (
    BleScanner,
    GoProClient,
    format_camera_state,
    get_status_value,
    is_camera_encoding,
)
from gopro_sdk.commands.media_commands import MediaFile

logger = logging.getLogger(__name__)


def test_package_imports():
    """Test that the main package can be imported."""
    import gopro_sdk

    assert gopro_sdk.__version__ == "0.1.0"


def test_client_import():
    """Test that GoProClient can be imported."""
    from gopro_sdk import GoProClient

    assert GoProClient is not None


def test_multi_camera_import():
    """Test that MultiCameraManager can be imported."""
    from gopro_sdk import MultiCameraManager

    assert MultiCameraManager is not None


def test_config_import():
    """Test that configuration classes can be imported."""
    from gopro_sdk import CohnConfigManager, CohnCredentials

    assert CohnConfigManager is not None
    assert CohnCredentials is not None


def test_exceptions_import():
    """Test that exceptions can be imported."""
    from gopro_sdk.exceptions import BleConnectionError, HttpConnectionError

    assert BleConnectionError is not None
    assert HttpConnectionError is not None


@pytest.mark.asyncio
async def test_client_creation():
    """Test that a GoProClient can be created."""
    from gopro_sdk import GoProClient

    client = GoProClient("1332")
    assert client is not None
    assert client.target == "1332"


@pytest.mark.hardware
async def test_ble_scan():
    """Test BLE scanning for GoPro cameras.

    Validates:
    1. Can scan for nearby GoPro devices
    2. Returns list of serial numbers
    """
    logger.info("🔍 Starting GoPro camera scan...")

    # Scan for 5 seconds
    serials = []
    async for serial in BleScanner.scan_serials_stream(duration=5.0):
        if serial not in serials:
            serials.append(serial)
            logger.info(f"📱 Found camera: {serial}")
    logger.info("🔍 Scan complete")
    if not serials:
        logger.info("ℹ️ No GoPro cameras found")

    # Validate return type
    assert isinstance(serials, list), "Should return a list"


@pytest.mark.hardware
async def test_ble_connection(gopro_client_no_connect: GoProClient):
    """Test BLE connection.

    Validates:
    1. BLE can successfully connect
    2. Connection state is correct
    3. Connection can be maintained
    """
    client = gopro_client_no_connect

    # Connect BLE
    await client.ble.connect()
    assert client.ble.is_connected, "BLE should be connected"

    # Maintain connection
    await asyncio.sleep(2)
    assert client.ble.is_connected, "BLE should remain connected"


@pytest.mark.hardware
async def test_hybrid_connection(gopro_client: GoProClient):
    """Test hybrid mode connection (BLE + HTTP).

    Validates:
    1. Automatically connects BLE
    2. Automatically configures/loads COHN
    3. HTTP lazy connection (automatically established on first request)
    """
    client = gopro_client

    # Verify BLE connection status
    assert client.ble.is_connected, "BLE should be connected"

    # HTTP uses lazy connection, only connects on first request
    # At this point is_connected might still be False
    logger.info("HTTP uses lazy connection strategy, automatically established on first request")

    # Send first HTTP request, this triggers auto-connection
    info = await client.get_camera_info()
    assert info, "Camera info should not be empty"
    assert isinstance(info, dict), "Camera info should be a dictionary"
    logger.info("Camera info:")
    for key, value in info.items():
        logger.info(f"  {key}: {value}")

    # Now HTTP should be connected
    assert client.ble.is_connected, "BLE should remain connected"
    assert client.http.is_connected, "HTTP should be connected after first request"


@pytest.mark.hardware
async def test_get_status(gopro_client: GoProClient):
    """Test getting camera status.

    Validates:
    1. Can successfully get status
    2. Status contains necessary fields
    """
    client = gopro_client

    # Get status
    state = await client.get_status()

    # Validate
    assert state, "Status should not be empty"
    assert isinstance(state, dict), "Status should be a dictionary"
    assert "status" in state or "settings" in state, "Status should contain necessary fields"


@pytest.mark.hardware
async def test_get_camera_info(gopro_client: GoProClient):
    """Test getting camera info.

    Validates:
    1. Can successfully get camera info
    2. Info format is correct
    """
    client = gopro_client

    # Get info
    info = await client.get_camera_info()

    # Validate
    assert info, "Camera info should not be empty"
    assert isinstance(info, dict), "Camera info should be a dictionary"

    # Use logger for output (automatically displayed in pytest logs)
    logger.info("Camera info:")
    for key, value in info.items():
        logger.info(f"  {key}: {value}")


@pytest.mark.hardware
async def test_keep_alive(gopro_client: GoProClient):
    """Test keep-alive signal.

    Validates:
    1. Can successfully send keep-alive signal
    2. Connection remains normal
    """
    client = gopro_client

    # Send keep-alive
    await client.set_keep_alive()

    # Verify connection is still normal
    assert client.http.is_connected, "HTTP should still be connected"


@pytest.mark.hardware
async def test_recording_control(gopro_client: GoProClient):
    """Test recording control (convenience methods).

    Validates:
    1. Can start recording
    2. Can stop recording
    """
    client = gopro_client

    # Start recording
    await client.start_recording()
    await asyncio.sleep(2)

    # Stop recording
    await client.stop_recording()
    await asyncio.sleep(1)


@pytest.mark.slow
@pytest.mark.hardware
async def test_preview_stream(gopro_client: GoProClient):
    """Test preview stream control (convenience methods).

    Validates:
    1. Can enable preview stream
    2. Can disable preview stream

    How to view preview stream:

    Method 1 - VLC Player (recommended):
        vlc udp://@:8554

    Method 2 - ffplay (FFmpeg tool):
        ffplay -fflags nobuffer -flags low_delay udp://127.0.0.1:8554

    Method 3 - GStreamer:
        gst-launch-1.0 udpsrc port=8554 ! decodebin ! autovideosink

    Method 4 - Python OpenCV:
        import cv2
        cap = cv2.VideoCapture("udp://127.0.0.1:8554")
        while True:
            ret, frame = cap.read()
            if ret:
                cv2.imshow('GoPro Preview', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    """
    client = gopro_client

    # Enable preview
    await client.start_preview(port=8554)

    # Inform user how to view preview stream
    logger.info("📹 Preview stream started, can be viewed using:")
    logger.info("   VLC: vlc udp://@:8554")
    logger.info("   FFplay: ffplay -fflags nobuffer udp://127.0.0.1:8554")

    await asyncio.sleep(10)

    # Disable preview
    await client.stop_preview()
    await asyncio.sleep(1)


@pytest.mark.hardware
async def test_date_time_sync(gopro_client: GoProClient):
    """Test date time synchronization.

    Validates:
    1. Can set camera date time
    2. Time sync is successful
    """
    client = gopro_client

    # Get current time
    now = datetime.now()

    # Sync time (use current system time)
    await client.set_date_time(now)

    # Validate: get timestamp from camera status (indirect validation)
    await asyncio.sleep(1)
    state = await client.get_status()
    assert state, "Status should not be empty"

    # Get and display parsed state
    parsed_state = await client.get_parsed_state()

    # Print parsed state
    logger.info(format_camera_state(parsed_state))

    # Demonstrate how to use parsed state
    battery = get_status_value(parsed_state, StatusId.INTERNAL_BATTERY_PERCENTAGE)
    if battery:
        logger.info(f"🔋 Current battery: {battery}%")

    if is_camera_encoding(parsed_state):
        logger.info("🔴 Camera is recording")


@pytest.mark.hardware
async def test_media_list(gopro_client: GoProClient):
    """Test media file list retrieval.

    Validates:
    1. Can get media file list
    2. List format is correct
    """
    client = gopro_client

    # Get media list
    media_list = await client.get_media_list()

    # Validate
    assert isinstance(media_list, list), "Media list should be a list"
    logger.info(f"Found {len(media_list)} media files")

    if media_list:
        # Validate structure of first file
        first_file = media_list[0]
        logger.info(f"First file: {first_file}")

        # Validate it's a MediaFile object
        assert isinstance(first_file, MediaFile), "Media file info should be a MediaFile object"

        # Validate required fields
        assert hasattr(first_file, "filename"), "Should have filename field"
        assert hasattr(first_file, "size"), "Should have size field"
        assert hasattr(first_file, "created_time"), "Should have created_time field"

        # Validate field types
        assert isinstance(first_file.filename, str), "filename should be a string"
        assert isinstance(first_file.size, int), "size should be an integer"
        assert isinstance(first_file.created_time, int), "created_time should be an integer"


@pytest.mark.hardware
@pytest.mark.slow
async def test_settings_management(gopro_client: GoProClient):
    """Test settings management (get and modify).

    Validates:
    1. Can get camera status (including settings)
    2. Can modify settings
    3. Status updates after modification

    Note: This test temporarily modifies camera settings
    """
    client = gopro_client

    # 1. Get current status (including all settings)
    state = await client.get_status()
    assert "settings" in state, "Status should contain settings field"

    settings = state["settings"]
    logger.info(f"Currently has {len(settings)} settings")
    logger.info(f"Available setting IDs: {sorted(settings.keys())}")

    # 2. Test modifying a safe setting (LED)
    led_id = SettingId.LED
    if str(led_id.value) in settings:
        original_value = settings[str(led_id.value)]
        logger.info(f"Original LED setting: {original_value} ({Led(original_value).name})")

        # Toggle LED (OFF <-> ON, use simple two-value toggle to avoid compatibility issues)
        # Note: original_value is an integer, needs to compare with enum's .value
        new_value = Led.ON.value if original_value == Led.OFF.value else Led.OFF.value
        await client.set_setting(led_id.value, new_value)
        logger.info(f"Modified LED to: {new_value} ({Led(new_value).name})")

        # Wait for setting to take effect
        await asyncio.sleep(1)

        # Verify setting updated
        updated_state = await client.get_status()
        updated_value = updated_state["settings"].get(str(led_id.value))
        logger.info(f"Updated LED: {updated_value} ({Led(updated_value).name})")

        # Restore original setting
        await client.set_setting(led_id.value, original_value)
        logger.info(f"Restored LED to: {original_value} ({Led(original_value).name})")
    else:
        logger.warning(f"Setting {led_id.value} ({led_id.name}) does not exist, skipping modification test")
