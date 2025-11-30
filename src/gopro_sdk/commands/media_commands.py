"""Command: Media management

Provides functionality for listing, downloading, and deleting media files.
"""

from __future__ import annotations

__all__ = ["MediaCommands", "MediaFile"]

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from open_gopro.models.media_list import MediaList

from ..connection.http_manager import HttpConnectionManager
from ..exceptions import HttpConnectionError
from .base import with_http_retry

logger = logging.getLogger(__name__)


@dataclass
class MediaFile:
    """Media file information.

    GoPro's media list API does not return file sizes, so we define this custom class.
    Inherits fields from MediaItem: filename, creation_timestamp, modified_time, etc.
    """

    filename: str  # Filename (includes directory, e.g., "100GOPRO/GX010001.MP4")
    creation_timestamp: str  # Creation time (Unix timestamp string, UTC)
    modified_time: str  # Modified time (Unix timestamp string, UTC)
    size: int = 0  # File size (bytes), default 0 (requires additional query or obtained from download response)

    @property
    def created_time(self) -> int:
        """Compatibility property: returns creation time as int (UTC timestamp)."""
        return int(self.creation_timestamp)

    @property
    def created_datetime(self) -> datetime:
        """Returns creation time in local timezone.

        ⚠️ GoPro firmware timestamp issue:
        Testing revealed that after setting GoPro camera to local timezone (UTC+8),
        the creation_timestamp value still behaves as a UTC timestamp, but when
        parsed using Python's fromtimestamp() in local timezone, it results in
        time being 8 hours fast.

        Suspected GoPro firmware bug: camera timezone is set but timestamp does not
        correctly apply timezone offset.

        Temporary solution: Manually subtract 8 hours (28800 seconds) for compensation.
        Recommendation: Use "sync all camera times" feature to ensure camera clock is correct.

        Returns:
            datetime object in local timezone
        """
        # Temporary workaround: subtract 8-hour offset (28800 seconds = 8 * 3600) to compensate for firmware issue
        adjusted_timestamp = self.created_time - 28800
        return datetime.fromtimestamp(adjusted_timestamp)


class MediaCommands:
    """Media management command interface."""

    def __init__(self, http_manager: HttpConnectionManager) -> None:
        """Initialize media command interface.

        Args:
            http_manager: HTTP connection manager
        """
        self.http = http_manager
        self._http_error_count = 0  # HTTP error count (used by retry decorator)

    @with_http_retry(max_retries=3)
    async def get_media_list(self) -> list[MediaFile]:
        """List all media files.

        Uses the Open GoPro SDK's MediaList to parse the response, then converts to custom MediaFile.

        Returns:
            Media file list (MediaFile objects)

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"📂 Listing media files on camera {self.http.target}...")

        endpoint = "gopro/media/list"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to list media (HTTP {resp.status}): {text}")

            data = await resp.json()

            # Parse media list using the Open GoPro SDK
            media_list = MediaList(**data)

            # Convert to MediaFile objects
            media_files = [
                MediaFile(
                    filename=item.filename,
                    creation_timestamp=item.creation_timestamp,
                    modified_time=item.modified_time,
                    size=0,  # GoPro API does not return file size
                )
                for item in media_list.files
            ]

            # Sort by creation time descending (newest files first)
            media_files.sort(key=lambda f: int(f.creation_timestamp), reverse=True)

            logger.info(f"✅ Found {len(media_files)} media files")
            return media_files

    @with_http_retry(max_retries=3)
    async def download_file(
        self,
        media_file: MediaFile | str,
        save_path: str | Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Download media file.

        Args:
            media_file: MediaFile object or file path (e.g., "100GOPRO/GX010001.MP4")
            save_path: Save path
            progress_callback: Progress callback function (downloaded: int, total: int) -> None

        Returns:
            Number of bytes downloaded

        Raises:
            HttpConnectionError: Download failed
        """
        # Extract file path
        file_path = media_file.filename if isinstance(media_file, MediaFile) else media_file

        logger.info(f"⬇️ Downloading file {file_path} to {save_path}...")

        # GoPro download endpoint format: videos/DCIM/<directory>/<filename>
        endpoint = f"videos/DCIM/{file_path}"
        downloaded = await self.http.download(endpoint, str(save_path), progress_callback=progress_callback)

        logger.info(f"✅ File download complete: {save_path} ({downloaded} bytes)")
        return downloaded

    @with_http_retry(max_retries=3)
    async def delete_file(self, path: str) -> None:
        """Delete single media file.

        Args:
            path: File path (e.g., "100GOPRO/GX010001.MP4")

        Raises:
            HttpConnectionError: Deletion failed
        """
        logger.info(f"🗑️ Deleting file {path} (camera {self.http.target})...")

        endpoint = "gopro/media/delete/file"
        params = {"path": path}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to delete file (HTTP {resp.status}): {text}")

        logger.info(f"✅ File deleted successfully: {path}")

    @with_http_retry(max_retries=3)
    async def delete_all_media(self) -> None:
        """Delete all media files.

        Raises:
            HttpConnectionError: Deletion failed
        """
        logger.warning(f"⚠️ Deleting all media files on camera {self.http.target}...")

        endpoint = "gp/gpControl/command/storage/delete/all"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to delete all media (HTTP {resp.status}): {text}")

        logger.info("✅ All media files deleted")

    @with_http_retry(max_retries=3)
    async def get_media_metadata(self, path: str) -> dict[str, Any]:
        """Get media file metadata.

        Args:
            path: File path

        Returns:
            Metadata dictionary

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"📄 Getting file metadata: {path}...")

        endpoint = "gopro/media/info"
        params = {"path": path}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get metadata (HTTP {resp.status}): {text}")

            return await resp.json()

    @with_http_retry(max_retries=3)
    async def get_last_captured_media(self) -> dict[str, Any]:
        """Get information about last captured media file.

        Returns:
            Media information dictionary

        Raises:
            HttpConnectionError: Command failed
        """
        logger.debug(f"Getting last captured media (camera {self.http.target})...")

        endpoint = "gopro/media/last_captured"
        async with self.http.get(endpoint) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to get last media (HTTP {resp.status}): {text}")

            return await resp.json()

    @with_http_retry(max_retries=3)
    async def set_turbo_mode(self, enable: bool) -> None:
        """Enable/disable Turbo transfer mode (accelerates downloads).

        Args:
            enable: True to enable, False to disable

        Raises:
            HttpConnectionError: Command failed
        """
        logger.info(f"{'Enabling' if enable else 'Disabling'} Turbo mode (camera {self.http.target})...")

        endpoint = "gopro/media/turbo_transfer"
        params = {"p": "1" if enable else "0"}

        async with self.http.get(endpoint, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HttpConnectionError(f"Failed to set Turbo mode (HTTP {resp.status}): {text}")

        logger.info(f"✅ Turbo mode {'enabled' if enable else 'disabled'}")
