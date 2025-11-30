"""COHN configuration management module."""

from __future__ import annotations

__all__ = ["CohnConfigManager", "CohnCredentials", "TimeoutConfig"]

import contextlib
import logging
from dataclasses import dataclass
from pathlib import Path

from tinydb import Query, TinyDB

logger = logging.getLogger(__name__)


@dataclass
class CohnCredentials:
    """COHN credentials information.

    Attributes:
        ip_address: IP address assigned by camera
        username: HTTP authentication username
        password: HTTP authentication password
        certificate: SSL certificate in PEM format (string)
    """

    ip_address: str
    username: str
    password: str
    certificate: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return {
            "ip_address": self.ip_address,
            "username": self.username,
            "password": self.password,
            "certificate": self.certificate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> CohnCredentials:
        """Create from dictionary."""
        return cls(
            ip_address=data["ip_address"],
            username=data["username"],
            password=data["password"],
            certificate=data["certificate"],
        )


@dataclass
class TimeoutConfig:
    """Timeout configuration.

    Reference design document question 13, all timeout values are configurable.
    """

    # BLE related timeouts
    ble_write_timeout: float = 10.0  # BLE write timeout (Open GoPro SDK: 5s)
    ble_read_timeout: float = 10.0  # BLE read timeout (Open GoPro SDK: 5s)
    ble_discovery_timeout: float = 5.0  # BLE device discovery timeout
    ble_response_timeout: float = 5.0  # BLE wait response timeout (notification data)
    ble_connect_timeout: float = 20.0  # BLE connection establishment timeout
    ble_service_discovery_timeout: float = 30.0  # BLE service discovery timeout

    # HTTP related timeouts
    http_request_timeout: float = 30.0  # HTTP request timeout (Open GoPro SDK: 5s)
    http_download_timeout: float = 300.0  # HTTP download timeout (large files)
    http_keep_alive_timeout: float = 8.0  # HTTP keep-alive check timeout
    http_initial_check_timeout: float = 2.0  # HTTP initial reachability check timeout

    # WiFi network related timeouts
    wifi_scan_timeout: float = 15.0  # WiFi scan total timeout
    wifi_scan_internal_timeout: float = 10.0  # WiFi scan internal call timeout
    wifi_connect_configured_timeout: float = 15.0  # Connect to configured network timeout
    wifi_provision_timeout: float = 60.0  # WiFi provisioning total timeout

    # COHN related timeouts
    cohn_provision_timeout: float = 60.0  # COHN configuration total timeout
    cohn_wait_provisioned_timeout: float = 45.0  # Wait for COHN configuration complete timeout
    cohn_status_poll_interval: float = 1.0  # COHN status polling interval

    # General configuration
    connection_retry_interval: float = 2.0  # Connection retry interval
    max_reconnect_attempts: int = 3  # Maximum reconnect attempt count
    camera_ready_timeout: float = 10.0  # Wait for camera ready timeout
    camera_ready_poll_interval: float = 0.5  # Camera ready status polling interval

    # HTTP connection check configuration
    http_keepalive_max_retries: int = 12  # Keep-alive maximum retry count
    http_keepalive_retry_interval: float = 1.5  # Keep-alive retry interval
    http_keepalive_timeout_threshold: int = 4  # Consecutive timeout threshold (trigger warning)
    http_keepalive_fatal_threshold: int = 6  # Consecutive timeout threshold (trigger disconnection determination)

    # IP address acquisition configuration
    ip_wait_max_attempts: int = 5  # Maximum attempts when waiting for IP address
    ip_wait_interval: float = 3.0  # Interval between IP address checks (seconds)

    # Preview stream configuration
    preview_state_settle_delay: float = 0.2  # Delay for camera state to settle before starting preview


class CohnConfigManager:
    """COHN configuration persistence manager.

    Uses Repository pattern to encapsulate TinyDB operations.
    Database file is stored in user data directory.

    Supports context manager protocol for automatic resource cleanup:
        with CohnConfigManager() as manager:
            manager.save(serial, credentials)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize configuration manager.

        Args:
            db_path: Database file path, defaults to cohn_credentials.json in current directory
        """
        if db_path is None:
            db_path = Path("cohn_credentials.json")

        self._db_path = db_path
        self._db = TinyDB(str(db_path))
        self._table = self._db.table("credentials")
        logger.info(f"COHN configuration database initialized: {db_path}")

    def __enter__(self) -> CohnConfigManager:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and close database."""
        self.close()

    def __del__(self) -> None:
        """Cleanup: ensure database is closed when object is destroyed."""
        with contextlib.suppress(Exception):
            if hasattr(self, "_db") and self._db is not None:
                self._db.close()

    def save(self, serial: str, credentials: CohnCredentials) -> None:
        """Save or update camera COHN credentials.

        Args:
            serial: Camera serial number (last 4 digits)
            credentials: COHN credentials
        """
        query = Query()
        data = {"serial": serial, **credentials.to_dict()}

        # Update or insert
        if self._table.search(query.serial == serial):
            self._table.update(data, query.serial == serial)
            logger.info(f"Updated COHN credentials for camera {serial}")
        else:
            self._table.insert(data)
            logger.info(f"Saved COHN credentials for camera {serial}")

    def load(self, serial: str) -> CohnCredentials | None:
        """Load camera COHN credentials.

        Args:
            serial: Camera serial number (last 4 digits)

        Returns:
            COHN credentials, or None if not found
        """
        query = Query()
        result = self._table.search(query.serial == serial)

        if not result:
            logger.debug(f"COHN credentials not found for camera {serial}")
            return None

        data = result[0]
        credentials = CohnCredentials.from_dict({
            "ip_address": data["ip_address"],
            "username": data["username"],
            "password": data["password"],
            "certificate": data["certificate"],
        })
        logger.debug(f"Loaded COHN credentials for camera {serial}: {credentials.ip_address}")
        return credentials

    def delete(self, serial: str) -> bool:
        """Delete camera COHN credentials.

        Args:
            serial: Camera serial number (last 4 digits)

        Returns:
            Whether deletion was successful
        """
        query = Query()
        removed = self._table.remove(query.serial == serial)
        if removed:
            logger.info(f"Deleted COHN credentials for camera {serial}")
            return True
        else:
            logger.debug(f"COHN credentials for camera {serial} do not exist")
            return False

    def list_all(self) -> dict[str, CohnCredentials]:
        """List all saved COHN credentials.

        Returns:
            Mapping from serial number to credentials
        """
        all_records = self._table.all()
        result = {}

        for record in all_records:
            serial = record["serial"]
            credentials = CohnCredentials.from_dict({
                "ip_address": record["ip_address"],
                "username": record["username"],
                "password": record["password"],
                "certificate": record["certificate"],
            })
            result[serial] = credentials

        logger.debug(f"Listed all COHN credentials, total: {len(result)}")
        return result

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self, "_db") and self._db is not None:
            self._db.close()
            self._db = None
            logger.debug("COHN configuration database closed")
