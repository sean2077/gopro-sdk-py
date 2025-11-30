"""Custom exception classes."""

__all__ = [
    "BleConnectionError",
    "BleTimeoutError",
    "CohnConfigurationError",
    "CohnNotConfiguredError",
    "CustomGoProError",
    "HttpConnectionError",
]


class CustomGoProError(Exception):
    """Base class for all custom GoPro client exceptions."""


class BleConnectionError(CustomGoProError):
    """BLE connection related error."""


class BleTimeoutError(BleConnectionError):
    """BLE response timeout error."""


class HttpConnectionError(CustomGoProError):
    """HTTP connection related error."""


class CohnNotConfiguredError(CustomGoProError):
    """COHN not configured error."""


class CohnConfigurationError(CustomGoProError):
    """COHN configuration process error."""
