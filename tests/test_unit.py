"""Unit tests - no hardware required.

Tests package imports, class instantiation, and basic functionality that doesn't require real hardware.
"""

import pytest


def test_package_imports():
    """Test that the main package can be imported."""
    import gopro_sdk

    assert gopro_sdk.__version__ is not None
    assert isinstance(gopro_sdk.__version__, str)
    assert len(gopro_sdk.__version__) > 0


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
