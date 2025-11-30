"""Multi-camera manager implementation.

Supports managing multiple GoPro cameras simultaneously, providing batch operations and concurrency control.
"""

from __future__ import annotations

__all__ = ["CameraStatus", "MultiCameraManager"]

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from .client import GoProClient
from .config import CohnConfigManager, TimeoutConfig

logger = logging.getLogger(__name__)


class CameraStatus:
    """Camera status information."""

    def __init__(self, camera_id: str):
        """Initialize camera status.

        Args:
            camera_id: Camera serial number last four digits
        """
        self.camera_id = camera_id
        self.is_connected = False
        self.is_healthy = False
        self.last_error: Exception | None = None
        self.command_count = 0
        self.error_count = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "camera_id": self.camera_id,
            "is_connected": self.is_connected,
            "is_healthy": self.is_healthy,
            "last_error": str(self.last_error) if self.last_error else None,
            "command_count": self.command_count,
            "error_count": self.error_count,
        }


class MultiCameraManager:
    """Multi-camera manager.

    Supports managing multiple GoPro cameras simultaneously, providing:
    1. Batch connection/disconnection
    2. Concurrent command execution
    3. Status synchronization
    4. Error isolation
    5. Health monitoring

    Example usage:
    ```python
    async with MultiCameraManager(["9811", "9812", "9813"]) as manager:
        # Batch connect
        await manager.connect_all()

        # Execute commands concurrently
        results = await manager.execute_all(lambda client: client.start_recording())

        # Get all statuses
        statuses = await manager.get_all_status()
    ```
    """

    def __init__(
        self,
        camera_ids: list[str] | None = None,
        timeout_config: TimeoutConfig | None = None,
        config_manager: CohnConfigManager | None = None,
        max_concurrent: int = 5,
        wifi_ssid: str | None = None,
        wifi_password: str | None = None,
        offline_mode: bool = True,
    ):
        """Initialize multi-camera manager.

        Args:
            camera_ids: List of camera serial numbers (last four digits), default empty
            timeout_config: Timeout configuration, default uses default values
            config_manager: COHN configuration manager, default creates new instance
            max_concurrent: Maximum concurrency limit (prevents overload)
            wifi_ssid: WiFi SSID (used for camera HTTP connection)
            wifi_password: WiFi password (used with wifi_ssid)
            offline_mode: Offline mode (default True), BLE connection only, no preview/download support
        """
        self.camera_ids: list[str] = camera_ids if camera_ids is not None else []
        self._timeout_config = timeout_config or TimeoutConfig()
        self._config_manager = config_manager or CohnConfigManager()
        self._max_concurrent = max_concurrent
        self._wifi_ssid = wifi_ssid
        self._wifi_password = wifi_password
        self._offline_mode = offline_mode

        # Camera client dictionary
        self._clients: dict[str, GoProClient] = {}

        # Camera status dictionary
        self._statuses: dict[str, CameraStatus] = {camera_id: CameraStatus(camera_id) for camera_id in self.camera_ids}

        # Concurrency control semaphore (lazy init to avoid creating before event loop is set)
        self._semaphore: asyncio.Semaphore | None = None
        self._max_concurrent_count = max_concurrent

        # Global lock (lazy init to avoid creating before event loop is set)
        self._global_lock: asyncio.Lock | None = None

        logger.info(
            f"Initialized MultiCameraManager, managing {len(self.camera_ids)} cameras, max concurrency: {max_concurrent}"
        )

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """Lazy create semaphore (ensures creation in correct event loop)."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent_count)
        return self._semaphore

    @property
    def global_lock(self) -> asyncio.Lock:
        """Lazy create global lock (ensures creation in correct event loop)."""
        if self._global_lock is None:
            self._global_lock = asyncio.Lock()
        return self._global_lock

    async def __aenter__(self) -> MultiCameraManager:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect_all()

    # ==================== Connection Management ====================

    async def connect_all(self) -> dict[str, bool]:
        """Batch connect all cameras.

        Default uses BLE+HTTP hybrid mode (automatically manages COHN).

        Returns:
            Connection result for each camera {camera_id: success}

        \b
        Usage example:
        ```python
        results = await manager.connect_all()
        # {"9811": True, "9812": True, "9813": False}
        ```
        """
        logger.info(f"Starting batch connection of {len(self.camera_ids)} cameras (BLE + HTTP)")

        async def connect_one(camera_id: str) -> tuple[str, bool]:
            """Connect single camera."""
            try:
                async with self.semaphore:  # Concurrency control
                    client = GoProClient(
                        camera_id,
                        timeout_config=self._timeout_config,
                        config_manager=self._config_manager,
                        wifi_ssid=self._wifi_ssid,
                        wifi_password=self._wifi_password,
                        offline_mode=self._offline_mode,
                    )
                    self._clients[camera_id] = client

                    # Unified connection (BLE or BLE + HTTP, depends on mode)
                    await client.open(wifi_ssid=self._wifi_ssid, wifi_password=self._wifi_password)

                    # Update status
                    self._statuses[camera_id].is_connected = True
                    self._statuses[camera_id].last_error = None

                    logger.info(f"✅ Camera {camera_id} connected successfully")
                    return camera_id, True

            except Exception as e:
                logger.error(f"❌ Camera {camera_id} connection failed: {e}")
                self._statuses[camera_id].is_connected = False
                self._statuses[camera_id].last_error = e
                self._statuses[camera_id].error_count += 1
                return camera_id, False

        # Concurrently connect all cameras
        tasks = [connect_one(camera_id) for camera_id in self.camera_ids]
        results = await asyncio.gather(*tasks)

        # Convert to dictionary
        result_dict = dict(results)

        success_count = sum(1 for success in result_dict.values() if success)
        logger.info(f"Batch connection complete: {success_count}/{len(self.camera_ids)} successful")

        return result_dict

    async def disconnect_all(self) -> None:
        """Batch disconnect all cameras."""
        logger.info(f"Starting batch disconnection of {len(self._clients)} cameras")

        async def disconnect_one(camera_id: str, client: GoProClient) -> None:
            """Disconnect single camera."""
            try:
                await client.close()
                self._statuses[camera_id].is_connected = False
                logger.info(f"Camera {camera_id} disconnected")
            except Exception as e:
                logger.warning(f"Error disconnecting camera {camera_id}: {e}")

        # Concurrently disconnect all cameras
        tasks = [disconnect_one(camera_id, client) for camera_id, client in self._clients.items()]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Clear client dictionary
        self._clients.clear()

        logger.info("Batch disconnection complete")

    async def reconnect_all(self) -> dict[str, bool]:
        """Batch reconnect all cameras.

        Default uses BLE+HTTP hybrid mode.

        Returns:
            Reconnection result for each camera {camera_id: success}
        """
        logger.info(f"Starting batch reconnection of {len(self._clients)} cameras")

        async def reconnect_one(camera_id: str) -> tuple[str, bool]:
            """Reconnect single camera."""
            try:
                async with self.semaphore:
                    client = self._clients.get(camera_id)
                    if not client:
                        logger.warning(f"Camera {camera_id} client does not exist, skipping reconnection")
                        return camera_id, False

                    success = await client.reconnect()

                    if success:
                        self._statuses[camera_id].is_connected = True
                        self._statuses[camera_id].last_error = None
                        logger.info(f"✅ Camera {camera_id} reconnected successfully")
                    else:
                        logger.error(f"❌ Camera {camera_id} reconnection failed")

                    return camera_id, success

            except Exception as e:
                logger.error(f"❌ Camera {camera_id} reconnection exception: {e}")
                self._statuses[camera_id].error_count += 1
                self._statuses[camera_id].last_error = e
                return camera_id, False

        # Concurrently reconnect all cameras
        tasks = [reconnect_one(camera_id) for camera_id in self._clients]
        results = await asyncio.gather(*tasks)

        result_dict = dict(results)
        success_count = sum(1 for success in result_dict.values() if success)
        logger.info(f"Batch reconnection complete: {success_count}/{len(self._clients)} successful")

        return result_dict

    # ==================== Command Execution ====================

    async def execute_all(
        self,
        command: Callable[[GoProClient], Any],
        camera_ids: list[str] | None = None,
    ) -> dict[str, tuple[bool, Any]]:
        """Execute command concurrently on all (or specified) cameras.

        Args:
            command: Command to execute (lambda or function)
            camera_ids: Target camera list, None means all cameras

        Returns:
            Execution result for each camera {camera_id: (success, result_or_error)}

        \b
        Usage example:
        ```python
        # Start recording on all cameras
        results = await manager.execute_all(lambda client: client.start_recording())

        # Get status from specific cameras
        results = await manager.execute_all(lambda client: client.get_status(), camera_ids=["9811", "9812"])
        ```
        """
        target_ids = camera_ids if camera_ids is not None else list(self._clients.keys())

        if not target_ids:
            logger.warning("No target cameras, skipping command execution")
            return {}

        logger.info(f"Starting concurrent command execution on {len(target_ids)} cameras")

        async def execute_one(camera_id: str) -> tuple[str, tuple[bool, Any]]:
            """Execute command on single camera."""
            try:
                async with self.semaphore:
                    client = self._clients.get(camera_id)
                    if not client:
                        raise ValueError(f"Camera {camera_id} client does not exist")

                    # Execute command
                    result = await command(client)

                    # Update statistics
                    self._statuses[camera_id].command_count += 1

                    logger.debug(f"Camera {camera_id} command executed successfully")
                    return camera_id, (True, result)

            except Exception as e:
                logger.error(f"Camera {camera_id} command execution failed: {e}")
                self._statuses[camera_id].error_count += 1
                self._statuses[camera_id].last_error = e
                return camera_id, (False, e)

        # Execute concurrently
        tasks = [execute_one(camera_id) for camera_id in target_ids]
        results = await asyncio.gather(*tasks)

        result_dict = dict(results)
        success_count = sum(1 for success, _ in result_dict.values() if success)
        logger.info(f"Command execution complete: {success_count}/{len(target_ids)} successful")

        return result_dict

    async def execute_sequentially(
        self,
        command: Callable[[GoProClient], Any],
        camera_ids: list[str] | None = None,
        delay: float = 0.0,
    ) -> dict[str, tuple[bool, Any]]:
        """Execute command sequentially on all (or specified) cameras.

        Suitable for scenarios requiring strict ordering or avoiding conflicts.

        Args:
            command: Command to execute
            camera_ids: Target camera list, None means all cameras
            delay: Delay between each command (seconds)

        Returns:
            Execution result for each camera {camera_id: (success, result_or_error)}
        """
        target_ids = camera_ids if camera_ids is not None else list(self._clients.keys())

        if not target_ids:
            logger.warning("No target cameras, skipping command execution")
            return {}

        logger.info(f"Starting sequential command execution on {len(target_ids)} cameras")

        results = {}

        for camera_id in target_ids:
            try:
                client = self._clients.get(camera_id)
                if not client:
                    raise ValueError(f"Camera {camera_id} client does not exist")

                # Execute command
                result = await command(client)

                # Update statistics
                self._statuses[camera_id].command_count += 1

                logger.debug(f"Camera {camera_id} command executed successfully")
                results[camera_id] = (True, result)

            except Exception as e:
                logger.error(f"Camera {camera_id} command execution failed: {e}")
                self._statuses[camera_id].error_count += 1
                self._statuses[camera_id].last_error = e
                results[camera_id] = (False, e)

            # Delay
            if delay > 0 and camera_id != target_ids[-1]:
                await asyncio.sleep(delay)

        success_count = sum(1 for success, _ in results.values() if success)
        logger.info(f"Command execution complete: {success_count}/{len(target_ids)} successful")

        return results

    # ==================== Status Management ====================

    async def check_all_health(self) -> dict[str, bool]:
        """Check health status of all cameras.

        Returns:
            Health status for each camera {camera_id: is_healthy}
        """
        logger.debug(f"Checking health status of {len(self._clients)} cameras")

        async def check_one(camera_id: str) -> tuple[str, bool]:
            """Check single camera."""
            try:
                async with self.semaphore:
                    client = self._clients.get(camera_id)
                    if not client:
                        return camera_id, False

                    is_healthy = await client.is_healthy()
                    self._statuses[camera_id].is_healthy = is_healthy

                    return camera_id, is_healthy

            except Exception as e:
                logger.error(f"Checking camera {camera_id} health status failed: {e}")
                self._statuses[camera_id].is_healthy = False
                return camera_id, False

        # Check concurrently
        tasks = [check_one(camera_id) for camera_id in self._clients]
        results = await asyncio.gather(*tasks)

        result_dict = dict(results)
        healthy_count = sum(1 for is_healthy in result_dict.values() if is_healthy)
        logger.debug(f"Health check complete: {healthy_count}/{len(self._clients)} healthy")

        return result_dict

    async def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status information for all cameras.

        Returns:
            Status dictionary for each camera {camera_id: status_dict}
        """
        results = await self.execute_all(lambda client: client.get_status())

        status_dict = {}
        for camera_id, (success, result) in results.items():
            if success:
                status_dict[camera_id] = result
            else:
                status_dict[camera_id] = {"error": str(result)}

        return status_dict

    def get_manager_status(self) -> dict[str, Any]:
        """Get overall manager status.

        Returns:
            Manager status dictionary
        """
        total = len(self.camera_ids)
        connected = sum(1 for s in self._statuses.values() if s.is_connected)
        healthy = sum(1 for s in self._statuses.values() if s.is_healthy)

        return {
            "total_cameras": total,
            "connected_cameras": connected,
            "healthy_cameras": healthy,
            "max_concurrent": self._max_concurrent,
            "camera_statuses": {camera_id: status.to_dict() for camera_id, status in self._statuses.items()},
        }

    # ==================== Camera Selection ====================

    def get_client(self, camera_id: str) -> GoProClient | None:
        """Get client for specified camera.

        Args:
            camera_id: Camera serial number

        Returns:
            Client instance, None if not found
        """
        return self._clients.get(camera_id)

    def get_connected_cameras(self) -> list[str]:
        """Get list of connected cameras."""
        return [camera_id for camera_id, status in self._statuses.items() if status.is_connected]

    def get_healthy_cameras(self) -> list[str]:
        """Get list of healthy cameras."""
        return [camera_id for camera_id, status in self._statuses.items() if status.is_healthy]

    def get_failed_cameras(self) -> list[str]:
        """Get list of failed cameras."""
        return [
            camera_id
            for camera_id, status in self._statuses.items()
            if not status.is_connected or status.error_count > 0
        ]

    # ==================== Camera Management (CRUD) ====================

    async def add_camera(self, camera_id: str, auto_connect: bool = False) -> bool:
        """Add camera to manager.

        Args:
            camera_id: Camera serial number
            auto_connect: Whether to automatically connect

        Returns:
            Whether addition was successful

        \b
        Usage example:
        ```python
        # Add without connecting
        await manager.add_camera("9814")

        # Add and automatically connect
        await manager.add_camera("9815", auto_connect=True)
        ```
        """
        if camera_id in self.camera_ids:
            logger.warning(f"Camera {camera_id} already exists, skipping addition")
            return False

        # Add to list
        self.camera_ids.append(camera_id)

        # Initialize status
        self._statuses[camera_id] = CameraStatus(camera_id)

        logger.info(f"Added camera {camera_id} to manager")

        # Auto connect
        if auto_connect:
            try:
                client = GoProClient(
                    camera_id,
                    timeout_config=self._timeout_config,
                    config_manager=self._config_manager,
                    wifi_ssid=self._wifi_ssid,
                    wifi_password=self._wifi_password,
                    offline_mode=self._offline_mode,
                )
                self._clients[camera_id] = client

                await client.open(wifi_ssid=self._wifi_ssid, wifi_password=self._wifi_password)

                self._statuses[camera_id].is_connected = True
                self._statuses[camera_id].last_error = None

                logger.info(f"✅ Camera {camera_id} automatically connected")
                return True

            except Exception as e:
                logger.error(f"❌ Camera {camera_id} automatic connection failed: {e}")
                self._statuses[camera_id].last_error = e
                self._statuses[camera_id].error_count += 1
                return False

        return True

    async def remove_camera(self, camera_id: str, disconnect: bool = True) -> bool:
        """Remove camera from manager.

        Args:
            camera_id: Camera serial number
            disconnect: Whether to disconnect first

        Returns:
            Whether removal was successful

        \b
        Usage example:
        ```python
        # Remove and disconnect
        await manager.remove_camera("9814")

        # Remove only, don't disconnect
        await manager.remove_camera("9814", disconnect=False)
        ```
        """
        if camera_id not in self.camera_ids:
            logger.warning(f"Camera {camera_id} does not exist, skipping removal")
            return False

        # Disconnect connection
        if disconnect and camera_id in self._clients:
            try:
                client = self._clients[camera_id]
                await client.close()
                logger.info(f"Camera {camera_id} connection disconnected")
            except Exception as e:
                logger.warning(f"Error disconnecting camera {camera_id}: {e}")

        # Clean up resources
        self.camera_ids.remove(camera_id)
        self._clients.pop(camera_id, None)
        self._statuses.pop(camera_id, None)

        logger.info(f"Removed camera {camera_id} from manager")
        return True

    def has_camera(self, camera_id: str) -> bool:
        """Check if camera is in manager.

        Args:
            camera_id: Camera serial number

        Returns:
            Whether it exists
        """
        return camera_id in self.camera_ids

    def is_connected(self, camera_id: str) -> bool:
        """Check if camera is connected.

        Args:
            camera_id: Camera serial number

        Returns:
            Whether it is connected
        """
        status = self._statuses.get(camera_id)
        return status.is_connected if status else False

    def get_camera_status(self, camera_id: str) -> CameraStatus | None:
        """Get camera status.

        Args:
            camera_id: Camera serial number

        Returns:
            Camera status, None if not found
        """
        return self._statuses.get(camera_id)

    def list_all_cameras(self) -> list[str]:
        """List all cameras.

        Returns:
            List of camera IDs
        """
        return self.camera_ids.copy()

    async def clear_all(self) -> None:
        """Clear all cameras (disconnect and remove)."""
        logger.info(f"Starting to clear all {len(self.camera_ids)} cameras")

        # Disconnect all connections
        await self.disconnect_all()

        # Clear lists
        self.camera_ids.clear()
        self._clients.clear()
        self._statuses.clear()

        logger.info("Cleared all cameras")
