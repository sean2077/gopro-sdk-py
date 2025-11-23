"""Health check and auto-reconnect functionality.

Known Limitation:
    GoPro API does not provide network cache reset functionality. When COHN times out
    due to cached network connections from previous WiFi networks, manual camera menu
    operation is required: Preferences → Connections → Reset Connections

    Future enhancement: Detect COHN_STATE_Idle timeout and provide clear user guidance
    to manually reset camera network settings.

    Reference: docs/development.md#cohn-configuration-timeout for troubleshooting guide
"""

from __future__ import annotations

__all__ = ["HealthCheckMixin"]

import asyncio
import logging
import time

from .ble_manager import BleConnectionManager
from .http_manager import HttpConnectionManager

logger = logging.getLogger(__name__)


class HealthCheckMixin:
    """Health check and auto-reconnect Mixin.

    Provides connection health check and auto-reconnect functionality.
    Requires subclasses to have ble and http attributes.
    """

    # These attributes should be provided by subclass
    ble: BleConnectionManager
    http: HttpConnectionManager
    target: str
    _enable_auto_reconnect: bool
    _max_reconnect_attempts: int
    _last_health_check: float | None

    async def is_healthy(self) -> bool:
        """Check connection health status.

        Returns:
            True if connection is healthy, False otherwise
        """
        logger.debug(f"Checking connection health for camera {self.target}...")
        self._last_health_check = time.time()

        try:
            # Check BLE status
            if hasattr(self, "ble") and not self.ble.is_connected:
                logger.warning(f"Camera {self.target} BLE not connected")
                return False

            # Check HTTP status
            if hasattr(self, "http") and self.http.is_connected:
                # Try quick query to verify communication
                try:
                    async with self.http.get("gopro/version") as resp:
                        if resp.status != 200:
                            logger.warning(f"Camera {self.target} HTTP health check failed")
                            return False
                except Exception as e:
                    logger.warning(f"Camera {self.target} HTTP health check exception: {e}")
                    return False

            logger.debug(f"Camera {self.target} connection healthy ✅")
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def reconnect(self) -> bool:
        """Smart reconnect.

        Returns:
            True if reconnect successful, False otherwise
        """
        logger.info(f"Starting reconnection to camera {self.target}...")

        attempt = 0

        while attempt < self._max_reconnect_attempts:
            attempt += 1
            logger.info(f"Attempting reconnect {attempt}/{self._max_reconnect_attempts}...")

            try:
                # Reconnect BLE
                if hasattr(self, "ble") and not self.ble.is_connected:
                    logger.info("Reconnecting BLE...")
                    await self.ble.connect()
                    logger.info("✅ BLE reconnected successfully")

                # Reconnect HTTP
                if hasattr(self, "http") and not self.http.is_connected:
                    logger.info("Reconnecting HTTP...")
                    await self.http.connect()
                    logger.info("✅ HTTP reconnected successfully")

                # Verify connection
                if await self.is_healthy():
                    logger.info(f"✅ Camera {self.target} reconnected successfully")
                    return True

            except Exception as e:
                logger.warning(f"Reconnect attempt {attempt} failed: {e}")
                if attempt < self._max_reconnect_attempts:
                    wait_time = min(2**attempt, 10)  # Exponential backoff, max 10 seconds
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)

        logger.error(f"Camera {self.target} reconnection failed (attempted {self._max_reconnect_attempts} times)")
        return False

    def set_auto_reconnect(self, enabled: bool) -> None:
        """Set whether to enable auto-reconnect.

        Args:
            enabled: True to enable, False to disable
        """
        self._enable_auto_reconnect = enabled
        logger.info(f"Auto-reconnect {'enabled' if enabled else 'disabled'} (camera {self.target})")

    def set_max_reconnect_attempts(self, attempts: int) -> None:
        """Set maximum reconnect attempt count.

        Args:
            attempts: Maximum attempt count (>= 1)
        """
        if attempts < 1:
            raise ValueError("Maximum reconnect attempts must be >= 1")

        self._max_reconnect_attempts = attempts
        logger.info(f"Maximum reconnect attempts set to {attempts} (camera {self.target})")

    def get_health_stats(self) -> dict[str, any]:
        """Get health statistics.

        Returns:
            Health statistics dictionary
        """
        stats = {
            "last_health_check": self._last_health_check,
            "auto_reconnect_enabled": self._enable_auto_reconnect,
            "max_reconnect_attempts": self._max_reconnect_attempts,
        }

        if hasattr(self, "ble"):
            stats.update(
                {
                    "ble_connected": self.ble.is_connected,
                    "ble_disconnect_count": self.ble._disconnect_count,
                }
            )

        if hasattr(self, "http"):
            stats.update(
                {
                    "http_connected": self.http.is_connected,
                    "http_error_count": self.http._error_count,
                }
            )

        return stats
