"""GoPro BLE UUID constants.

Based on the OpenGoPro specification, using standard UUID strings directly without complex SDK encapsulation.

References:
- OpenGoPro BLE specification: https://gopro.github.io/OpenGoPro/ble/
- Open GoPro SDK: open_gopro.models.constants.uuids
"""

from __future__ import annotations

__all__ = ["GoProBleUUID", "get_uuid_name"]

from typing import Final

# GoPro UUID base template
GOPRO_BASE_UUID: Final = "b5f9{}-aa8d-11e3-9046-0002a5d5c51b"


class GoProBleUUID:
    """GoPro BLE UUID constants (standard UUID string format).

    All UUIDs are in standard format (8-4-4-4-12), can be used directly with bleak.
    """

    # === GoPro WiFi Access Point Service ===
    S_WIFI_ACCESS_POINT: Final = GOPRO_BASE_UUID.format("0001")
    WAP_SSID: Final = GOPRO_BASE_UUID.format("0002")
    WAP_PASSWORD: Final = GOPRO_BASE_UUID.format("0003")
    WAP_POWER: Final = GOPRO_BASE_UUID.format("0004")
    WAP_STATE: Final = GOPRO_BASE_UUID.format("0005")
    WAP_CSI_PASSWORD: Final = GOPRO_BASE_UUID.format("0006")

    # === GoPro Control & Query Service ===
    S_CONTROL_QUERY: Final = "0000fea6-0000-1000-8000-00805f9b34fb"  # GoPro service UUID
    CQ_COMMAND: Final = GOPRO_BASE_UUID.format("0072")  # Command write
    CQ_COMMAND_RESP: Final = GOPRO_BASE_UUID.format("0073")  # Command response
    CQ_SETTINGS: Final = GOPRO_BASE_UUID.format("0074")  # Settings write
    CQ_SETTINGS_RESP: Final = GOPRO_BASE_UUID.format("0075")  # Settings response
    CQ_QUERY: Final = GOPRO_BASE_UUID.format("0076")  # Query write
    CQ_QUERY_RESP: Final = GOPRO_BASE_UUID.format("0077")  # Query response
    CQ_SENSOR: Final = GOPRO_BASE_UUID.format("0078")  # Sensor
    CQ_SENSOR_RESP: Final = GOPRO_BASE_UUID.format("0079")  # Sensor response

    # === GoPro Camera Management Service ===
    S_CAMERA_MANAGEMENT: Final = GOPRO_BASE_UUID.format("0090")
    CM_NET_MGMT_COMM: Final = GOPRO_BASE_UUID.format("0091")  # Network management command
    CN_NET_MGMT_RESP: Final = GOPRO_BASE_UUID.format("0092")  # Network management response

    # === Internal/Unknown ===
    S_INTERNAL: Final = GOPRO_BASE_UUID.format("0080")
    INTERNAL_81: Final = GOPRO_BASE_UUID.format("0081")
    INTERNAL_82: Final = GOPRO_BASE_UUID.format("0082")
    INTERNAL_83: Final = GOPRO_BASE_UUID.format("0083")
    INTERNAL_84: Final = GOPRO_BASE_UUID.format("0084")

    # === Standard BLE characteristics (not GoPro-specific) ===
    BATT_LEVEL: Final = "00002a19-0000-1000-8000-00805f9b34fb"  # Battery level


# Name mapping (for logging)
UUID_NAME_MAP: Final[dict[str, str]] = {
    GoProBleUUID.S_WIFI_ACCESS_POINT: "WiFi Access Point Service",
    GoProBleUUID.WAP_SSID: "WiFi AP SSID",
    GoProBleUUID.WAP_PASSWORD: "WiFi AP Password",
    GoProBleUUID.WAP_POWER: "WiFi Power",
    GoProBleUUID.WAP_STATE: "WiFi State",
    GoProBleUUID.WAP_CSI_PASSWORD: "CSI Password",
    GoProBleUUID.S_CONTROL_QUERY: "Control and Query Service",
    GoProBleUUID.CQ_COMMAND: "Command",
    GoProBleUUID.CQ_COMMAND_RESP: "Command Response",
    GoProBleUUID.CQ_SETTINGS: "Settings",
    GoProBleUUID.CQ_SETTINGS_RESP: "Settings Response",
    GoProBleUUID.CQ_QUERY: "Query",
    GoProBleUUID.CQ_QUERY_RESP: "Query Response",
    GoProBleUUID.CQ_SENSOR: "Sensor",
    GoProBleUUID.CQ_SENSOR_RESP: "Sensor Response",
    GoProBleUUID.S_CAMERA_MANAGEMENT: "Camera Management Service",
    GoProBleUUID.CM_NET_MGMT_COMM: "Network Management Command",
    GoProBleUUID.CN_NET_MGMT_RESP: "Network Management Response",
    GoProBleUUID.BATT_LEVEL: "Battery Level",
}


def get_uuid_name(uuid: str) -> str:
    """Get human-readable name for UUID.

    Args:
        uuid: UUID string

    Returns:
        Human-readable name for the UUID, or the UUID itself if not found
    """
    return UUID_NAME_MAP.get(uuid, uuid)
