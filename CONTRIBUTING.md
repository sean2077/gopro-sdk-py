# Contributing to GoPro SDK for Python

Thank you for your interest in contributing! For detailed technical information, see the [Development Guide](https://sean2077.github.io/gopro-sdk-py/development/).

## Quick Start

1. Fork and clone the repository
2. Install dependencies: `uv sync --extra dev`
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

This project follows an improved [Conventional Commits](https://www.conventionalcommits.org/) specification for automatic versioning and changelog generation.

### Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

### Core Types

#### `feat` - New Feature

A commit that introduces new feature with strong independence, providing significant new capabilities or behaviors. Usually represents relatively complete and independent functional modules.

**Examples:**
```bash
feat: add persistent COHN configuration
feat(client): support lazy HTTP connection
feat: implement multi-camera synchronization
```

#### `fix` - Improvements and Fixes

A commit that fixes, improves, or supplements existing code, including:
- Traditional error corrections
- Improvements and refinements to released features
- Adding minor but beneficial features or adjustments
- Supplementary fixes and optimizations for released versions
- Detail improvements that don't affect core functionality usage

**Examples:**
```bash
fix: correct BLE connection timeout handling
fix(http): handle SSL certificate errors
fix: improve state tracking accuracy
fix: optimize button display in dark mode
fix: adjust mobile menu interaction experience
```

### Supporting Types

- **docs**: Documentation-only changes that do not affect code functionality
- **style**: Code formatting changes (white-space, formatting, missing semi-colons, etc.)
- **refactor**: Code adjustments and modifications that neither add major features nor fix issues, including:
  - Code structure refactoring and optimization
  - Improving code readability and maintainability
  - Adding logs, comments, and other auxiliary code
  - Code standard compliance adjustments
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **build**: Changes to build system or external dependencies
- **ci**: Changes to CI configuration files and scripts
- **chore**: Maintenance tasks (dependencies updates, config cleanup, etc.)

### Breaking Changes

Add `!` after type or include `BREAKING CHANGE:` in footer to trigger MAJOR version bump:

```
feat!: redesign client API

BREAKING CHANGE: Client initialization parameters have changed
```

### Examples

```bash
# Features (complete, independent capabilities)
feat: add persistent COHN configuration
feat(client): support lazy HTTP connection
feat!: redesign multi-camera API

# Fixes and improvements
fix: correct BLE connection timeout handling
fix(http): improve SSL error handling
fix: enhance state tracking accuracy

# Code adjustments
refactor: simplify connection manager logic
refactor: add detailed logging for debugging
refactor: improve code readability

# Other types
docs: update quick start guide
perf: optimize state parsing performance
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

### Version Mapping

- `feat` → MINOR version bump
- `fix` → PATCH version bump
- `!` or `BREAKING CHANGE` → MAJOR version bump
- Other types → PATCH version bump (based on project policy)

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
