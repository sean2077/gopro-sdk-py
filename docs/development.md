# Development Guide

## Toolchain

This project uses modern Python tooling:

- **Package Manager**: [uv](https://docs.astral.sh/uv/) - Fast Python package installer and resolver
- **Formatter & Linter**: [ruff](https://docs.astral.sh/ruff/) - Fast Python linter and formatter
- **Task Runner**: [poethepoet](https://github.com/nat-n/poethepoet) - Task runner for Python projects

## Getting Started

### Prerequisites

- Python 3.12 or higher
- Git
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Clone and Setup

=== "Using uv (Recommended)"

    ```bash
    # Clone the repository
    git clone https://github.com/sean2077/gopro-sdk-py.git
    cd gopro-sdk-py

    # Install dependencies
    uv sync --extra dev

    # Install pre-commit hooks (optional)
    pre-commit install
    ```

    !!! tip
        uv is significantly faster than pip for dependency resolution and installation.

=== "Using pip"

    ```bash
    # Clone the repository
    git clone https://github.com/sean2077/gopro-sdk-py.git
    cd gopro-sdk-py

    # Create virtual environment
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

    # Install dependencies
    pip install -e ".[dev]"

    # Install pre-commit hooks (optional)
    pre-commit install
    ```

## Development Workflow

### Common Tasks

=== "Using poe (Task Runner)"

    ```bash
    poe format  # Format code and organize imports
    poe lint    # Check code style
    poe test    # Run tests
    poe docs    # Start documentation server (http://localhost:8000)
    ```

=== "Using Tools Directly"

    ```bash
    ruff format .              # Format code
    ruff check .               # Lint code
    pytest                     # Run tests
    uv run mkdocs serve        # Serve documentation
    ```

!!! tip "Quick Commands"
    - ++ctrl+shift+p++ in VS Code → "Run Task" → Select task
    - Use `poe --help` to see all available tasks

### Code Style

- **Line length**: 120 characters
- **Formatter**: ruff
- **Linter**: ruff
- **Type hints**: Required for public APIs

For commit message conventions, see the [Contributing Guide](contributing.md#commit-message-convention).

## Project Structure

```
gopro-sdk-py/
├── src/
│   └── gopro_sdk/          # Main package
│       ├── __init__.py     # Package exports
│       ├── client.py       # GoProClient
│       ├── config.py       # Configuration
│       ├── exceptions.py   # Custom exceptions
│       ├── state_parser.py # State parsing
│       ├── commands/       # Command implementations
│       │   ├── ble_commands.py
│       │   ├── http_commands.py
│       │   ├── media_commands.py
│       │   └── webcam_commands.py
│       └── connection/     # Connection managers
│           ├── ble_manager.py
│           ├── http_manager.py
│           └── health_check.py
├── tests/                  # Test suite
│   └── test_*.py
├── examples/               # Usage examples
├── docs/                   # Documentation
├── pyproject.toml          # Project configuration
└── .github/workflows/      # CI/CD workflows
```

## Testing

### Running Tests

```bash
# Run all tests
poe test
# or: pytest

# Run with coverage
pytest --cov=src/gopro_sdk --cov-report=html

# Run specific test file
pytest tests/test_basic.py

# Run specific test
pytest tests/test_basic.py::test_client_creation

# Run with markers
pytest -m "not slow"      # Skip slow tests
pytest -m "not hardware"  # Skip hardware tests
```

### Writing Tests

```python
import pytest
from gopro_sdk import GoProClient

def test_client_creation():
    """Test that a client can be created."""
    client = GoProClient(identifier="test")
    assert client.identifier == "test"

@pytest.mark.asyncio
async def test_async_operation():
    """Test async operations."""
    client = GoProClient(identifier="test")
    # Test async code...

@pytest.mark.slow
def test_slow_operation():
    """Test marked as slow."""
    # Long-running test...

@pytest.mark.hardware
async def test_real_camera():
    """Test requiring real hardware."""
    # Test with actual camera...
```

### Test Markers

- `@pytest.mark.slow`: Long-running tests
- `@pytest.mark.hardware`: Requires real GoPro camera
- `@pytest.mark.asyncio`: Async test functions

## Adding New Features

### 1. Add Command Method

If adding a new camera command:

```python
# src/gopro_sdk/commands/http_commands.py

class HttpCommands:
    async def new_command(self, param: str) -> dict:
        """Execute new command.

        Args:
            param: Command parameter

        Returns:
            Command result

        Raises:
            HttpCommandError: If command fails
        """
        response = await self.http_manager.get(f"/gopro/camera/new/{param}")
        return response.json()
```

### 2. Add Client Method

Add convenience method to `GoProClient`:

```python
# src/gopro_sdk/client.py

class GoProClient:
    async def new_feature(self, param: str) -> dict:
        """New feature description.

        Args:
            param: Parameter description

        Returns:
            Result description
        """
        return await self.http_commands.new_command(param)
```

### 3. Export in __init__.py

If adding a new public class:

```python
# src/gopro_sdk/__init__.py

from .new_module import NewClass

__all__ = [
    # ... existing exports
    "NewClass",
]
```

### 4. Add Tests

```python
# tests/test_new_feature.py

import pytest
from gopro_sdk import GoProClient

@pytest.mark.asyncio
async def test_new_feature():
    """Test new feature."""
    client = GoProClient(identifier="test")
    # Test implementation...
```

### 5. Update Documentation

- Add to `docs/api-reference.md`
- Update examples if needed
- Add to README if user-facing

## Debugging

### Enable Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("gopro_sdk")
logger.setLevel(logging.DEBUG)
```

### Using Debugger

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use built-in breakpoint()
breakpoint()
```

### Async Debugging

```python
import asyncio

# Enable debug mode
asyncio.run(main(), debug=True)
```

## Performance Profiling

### Using cProfile

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
async def my_function():
    # Function to profile
    pass
```

## Release Process

Releases are automated via semantic-release. Just follow these steps:

1. **Make changes** following conventional commits
2. **Push to main branch**
3. **Automatic release**:
   - Version determined from commits
   - CHANGELOG generated
   - Git tag created
   - GitHub release published
   - PyPI package uploaded (main branch only)

### Manual Version Check

To see what version would be released:

```bash
npx semantic-release --dry-run
```

## CI/CD

### GitHub Actions Workflows

**CI Workflow** (`.github/workflows/ci.yml`):
- Runs on push and PR
- Tests on multiple Python versions (3.12-3.13)
- Tests on multiple OS (Ubuntu, Windows, macOS)
- Linting and type checking
- Coverage reporting

**Release Workflow** (`.github/workflows/release.yml`):
- Runs on push to main/dev branches
- Automatic versioning
- CHANGELOG generation
- GitHub release creation
- PyPI publication (main only)

### Running CI Locally

```bash
# Format, lint, and test before pushing
poe format && poe lint && poe test
```

## Documentation

### Building Documentation

Documentation is in Markdown format in `docs/` directory.

### Adding Documentation

1. Create new `.md` file in `docs/`
2. Update `README.md` to link to it
3. Use clear headings and examples
4. Keep language professional and technical

## Troubleshooting

### Import Errors

```bash
# Reinstall dependencies
uv sync --reinstall
```

### Pre-commit Hooks Failing

```bash
# Run manually to see issues
pre-commit run --all-files

# Update hooks
pre-commit autoupdate
```

### Type Errors

Type checking is handled by Pyright (via VS Code Python extension) or ruff's type checker.

```bash
# Run ruff with type checking
ruff check src/gopro_sdk
```

## Getting Help

- Open an issue on GitHub
- Check existing issues and discussions
- Review the documentation in `docs/`
- Look at `examples/` directory

## Contributing

See [Contributing](contributing.md) for detailed contribution guidelines.
