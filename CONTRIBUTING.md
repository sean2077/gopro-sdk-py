# Contributing to GoPro SDK for Python

Thank you for your interest in contributing! For detailed technical information, see the [Development Guide](https://sean2077.github.io/gopro-sdk-py/development/).

## Quick Start

1. Fork and clone the repository
2. Install dependencies: `uv sync --extra dev` (or `pip install -e ".[dev]"`)
3. Make your changes
4. Run checks: `poe format && poe lint && poe test`
5. Submit a pull request

## Pull Request Process

1. **Create your branch** from `main`
2. **Make your changes** following the code style guidelines
3. **Add tests** for new functionality
4. **Update documentation** as needed
5. **Commit** using conventional commit format (see below)
6. **Push** and create a pull request

## Commit Message Convention

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification for automatic versioning and changelog generation.

### Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

### Types

- **feat**: New feature (triggers MINOR version bump)
- **fix**: Bug fix (triggers PATCH version bump)
- **docs**: Documentation changes only
- **style**: Code style changes (formatting, whitespace)
- **refactor**: Code restructuring without feature changes
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Maintenance tasks (dependencies, config)

### Breaking Changes

Add `!` after type or include `BREAKING CHANGE:` in footer to trigger MAJOR version bump:

```
feat!: redesign client API

BREAKING CHANGE: Client initialization parameters have changed
```

### Examples

```bash
# Features
feat: add persistent COHN configuration
feat(client): support lazy HTTP connection
feat!: redesign multi-camera API

# Fixes
fix: correct BLE connection timeout handling
fix(http): handle SSL certificate errors
fix: improve state tracking accuracy

# Documentation
docs: update quick start guide
docs(api): add client usage examples

# Other types
refactor: simplify connection manager
perf: optimize state parsing
test: add multi-camera integration tests
chore: update dependencies
```

### Scope (Optional)

Common scopes in this project:
- `client`: GoProClient related
- `ble`: BLE connection
- `http`: HTTP/COHN connection
- `commands`: Command implementations
- `config`: Configuration management
- `docs`: Documentation
- `tests`: Test suite

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for formatting and linting:

- **Line length**: 120 characters
- **Formatter**: ruff format
- **Linter**: ruff check
- **Type hints**: Required for public APIs
- **Docstrings**: Google style for public functions/classes

## Testing

- Write tests for new features
- Mark hardware tests: `@pytest.mark.hardware`
- Mark slow tests: `@pytest.mark.slow`
- Ensure all tests pass before submitting

## Need Help?

- Read the [Development Guide](https://sean2077.github.io/gopro-sdk-py/development/)
- Check [existing issues](https://github.com/sean2077/gopro-sdk-py/issues)
- Open a [discussion](https://github.com/sean2077/gopro-sdk-py/discussions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
