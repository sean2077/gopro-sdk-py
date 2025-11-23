"""Pytest configuration and common fixtures."""

import asyncio
from collections.abc import AsyncGenerator

import pytest

from gopro_sdk import GoProClient

# Test camera list (modify according to actual situation)
TEST_CAMERAS = ["1332"]  # Add your camera serial numbers here
# Note: Computer and camera must be on the same WiFi network for HTTP communication
TEST_WIFI_SSID = "your-wifi-ssid"  # Use the same network as your computer
TEST_WIFI_PASSWORD = "your-wifi-password"  # Modify according to actual situation


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop (session level)."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(params=TEST_CAMERAS)
def camera_id(request) -> str:
    """Camera ID fixture (runs tests for each camera).

    Returns:
        Last four digits of camera serial number
    """
    return request.param


@pytest.fixture
def single_camera_id() -> str:
    """Single camera ID (not parameterized, only uses first camera).

    Returns:
        Last four digits of camera serial number
    """
    return TEST_CAMERAS[0]


@pytest.fixture
async def gopro_client(camera_id: str) -> AsyncGenerator[GoProClient, None]:
    """Create and connect GoPro client fixture (independent for each test).

    Suitable for tests that change camera state (recording control, setting modifications, etc.).

    Args:
        camera_id: Camera serial number

    Yields:
        Connected GoProClient instance
    """
    client = GoProClient(
        camera_id,
        offline_mode=False,
        wifi_ssid=TEST_WIFI_SSID,
        wifi_password=TEST_WIFI_PASSWORD,
    )
    try:
        await client.open()
        yield client
    finally:
        await client.close()


@pytest.fixture
async def gopro_client_no_connect(camera_id: str) -> AsyncGenerator[GoProClient, None]:
    """Create unconnected GoPro client fixture.

    Args:
        camera_id: Camera serial number

    Yields:
        Unconnected GoProClient instance
    """
    client = GoProClient(camera_id)
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
async def gopro_clients_multi() -> AsyncGenerator[dict[str, GoProClient], None]:
    """Create multiple GoPro client fixtures.

    Yields:
        Dictionary {camera_id: GoProClient}
    """
    clients = {
        camera_id: GoProClient(
            camera_id,
            offline_mode=False,
            wifi_ssid=TEST_WIFI_SSID,
            wifi_password=TEST_WIFI_PASSWORD,
        )
        for camera_id in TEST_CAMERAS
    }
    try:
        # Concurrently connect all cameras
        await asyncio.gather(
            *[client.open() for client in clients.values()],
            return_exceptions=True,
        )
        yield clients
    finally:
        # Concurrently close all cameras
        await asyncio.gather(
            *[client.close() for client in clients.values()],
            return_exceptions=True,
        )
