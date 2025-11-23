# Testing Guide

This project uses pytest for testing. Tests are divided into unit tests and hardware tests.

## Quick Start

### Run All Tests

```bash
# Run all tests
pytest -v

# Run with detailed logs
pytest -v --log-cli-level=DEBUG

# Quick mode (failures only)
pytest -q
```

### Run by Category

```bash
# Unit tests only (no hardware required)
pytest -v -m "not hardware"

# Hardware tests only (requires real GoPro camera)
pytest -v -m hardware

# Exclude slow tests
pytest -v -m "not slow"
```

### Run Specific Tests

```bash
# Run specific file
pytest tests/test_basic.py -v

# Run specific test function
pytest tests/test_basic.py::test_package_imports -v

# Run tests matching pattern
pytest -v -k connection

# Run multiple tests
pytest -v -k "connection or info"
```

## Test Markers

Available markers defined in `pyproject.toml`:

| Marker                  | Description                      | Usage                    |
| ----------------------- | -------------------------------- | ------------------------ |
| `@pytest.mark.hardware` | Requires real GoPro camera       | Integration tests        |
| `@pytest.mark.slow`     | Long-running tests (>30 seconds) | COHN setup, media upload |

### Example Usage

```python
import pytest

@pytest.mark.hardware
async def test_camera_connection():
    """Test requiring real camera hardware."""
    pass

@pytest.mark.slow
@pytest.mark.hardware
async def test_cohn_provisioning():
    """Long-running COHN configuration test."""
    pass
```

## Test Configuration

Hardware tests require environment variables. Create a `.env` file:

```bash
# Copy from template
cp .env.example .env

# Edit with your camera details
GOPRO_TEST_CAMERAS=1332
GOPRO_TEST_WIFI_SSID=your-wifi-ssid
GOPRO_TEST_WIFI_PASSWORD=your-wifi-password
```

## Common Scenarios

### Development Workflow

```bash
# Fast feedback during development
pytest -v -m "not hardware and not slow"

# Full local validation before push
pytest -v -m "not hardware"
```

### Hardware Testing

```bash
# Run all hardware tests
pytest -v -m hardware

# Run specific hardware test
pytest tests/test_basic.py::test_ble_connection -v

# Hardware tests without slow ones
pytest -v -m "hardware and not slow"
```

## Debugging

```bash
# Stop at first failure
pytest -x -v

# Show local variables on failure
pytest -v -l

# Disable output capture (see prints)
pytest -v -s

# Enter debugger on failure
pytest -v --pdb

# Run only failed tests from last run
pytest --lf -v
```

## Coverage

```bash
# Generate coverage report
pytest --cov=src/gopro_sdk --cov-report=html

# View report
open htmlcov/index.html  # macOS/Linux
start htmlcov/index.html  # Windows

# Terminal coverage report
pytest --cov=src/gopro_sdk --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=src/gopro_sdk --cov-fail-under=80
```

## CI/CD

Tests run automatically on GitHub Actions:

- **CI Workflow**: Runs unit tests on all push/PR
- **Hardware Tests**: Runs on push to main/dev branches only (requires secrets)

To skip CI on a commit:

```bash
git commit -m "docs: update README [skip ci]"
```

## Reference

- **Pytest Documentation**: https://docs.pytest.org/
- **Pytest-asyncio**: https://pytest-asyncio.readthedocs.io/
- **Coverage.py**: https://coverage.readthedocs.io/
