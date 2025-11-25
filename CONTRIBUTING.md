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

**Description rules:**
- Use imperative mood: "add feature" not "added feature"
- Start with lowercase letter
- No period at the end
- Keep it under 72 characters

### Core Types

#### `feat` - New Feature

A commit that introduces a new capability or behavior. Use `feat` when adding something that users can do that they couldn't do before.

**Examples:**
```bash
feat: add persistent COHN configuration
feat(client): support lazy HTTP connection
feat: implement multi-camera synchronization
```

#### `fix` - Fixes and Improvements

A commit that fixes, improves, or supplements existing code. This is broader than traditional "bug fix" - it covers any incremental improvement, including:
- Bug fixes and error corrections
- Improvements and refinements to existing features
- Minor enhancements that don't warrant a new feature
- Adjustments to default values, configurations, or behaviors

Use `fix` when the change is **user-facing** or affects runtime behavior. Use `refactor` for internal code restructuring that doesn't change observable behavior.

**Examples:**
```bash
fix: correct BLE connection timeout handling
fix(http): handle SSL certificate errors
fix: improve state tracking accuracy
fix: add missing error message for invalid input
fix: update default timeout value
```

#### `perf` - Performance Improvements

A commit that improves performance metrics (speed, memory, battery, etc.) without changing the external API or expected behavior.

**When to use `perf` vs `fix`:**
- `perf`: The primary goal is performance optimization (e.g., caching, algorithm improvement)
- `fix`: Performance issue was a bug causing unacceptable behavior (e.g., memory leak, timeout)

**Examples:**
```bash
perf: cache parsed state to reduce CPU usage
perf(ble): reduce connection handshake time
perf: lazy load modules to improve startup time
```

### Supporting Types

These types do not trigger a release or appear in the changelog:

- **docs**: Documentation-only changes (README, docstrings, inline comments explaining "why")
- **style**: Code formatting only (whitespace, semicolons, quotes, line breaks)
- **refactor**: Internal code restructuring with no external behavior change (rename variables, extract functions, simplify logic)
- **test**: Adding or updating tests (no production code changes)
- **build**: Changes to build system or tooling (hatch, setuptools, webpack)
- **ci**: Changes to CI configuration (GitHub Actions, Jenkins)
- **chore**: Maintenance tasks (dependency updates, config cleanup, gitignore)

> **`fix` vs `refactor`**: If the change affects user-facing behavior or fixes an issue, use `fix`. If it's purely internal restructuring with identical external behavior, use `refactor`.

### Breaking Changes

Add `!` after type or include `BREAKING CHANGE:` in footer to trigger MAJOR version bump. This can be used with any type:

```bash
feat!: redesign client API
fix!: rename `connect()` parameter from `timeout` to `timeout_seconds`
perf!: require Python 3.12+ for performance features
```

Example with footer:
```
feat: redesign client API

BREAKING CHANGE: Client initialization parameters have changed.
The `timeout` parameter is now required.
```

### Best Practices

- **One logical change per commit**: Don't mix unrelated changes
- **Atomic commits**: Each commit should build and pass tests independently
- **Prefer specificity**: Choose the most specific type that applies (`perf` over `fix` for optimizations)

### Examples

```bash
# Features (complete, independent capabilities)
feat: add persistent COHN configuration
feat(client): support lazy HTTP connection
feat!: redesign multi-camera API

# Fixes and improvements (user-facing changes)
fix: correct BLE connection timeout handling
fix(http): handle SSL certificate errors
fix: add validation for camera serial format

# Performance (measurable improvements)
perf: cache state parsing results
perf(ble): batch BLE write operations

# Internal changes (no release)
refactor: extract connection logic to separate module
docs: update quick start guide
test: add multi-camera integration tests
chore(deps): update aiohttp to 3.9.0
```

### Scope (Optional)

Scope provides additional context. Common patterns:
- Module/component name: `client`, `ble`, `http`, `api`
- Feature area: `auth`, `config`, `logging`
- Special scopes: `deps` (dependencies), `release`

### Version Mapping

| Type                              | Version Bump      | Changelog |
| --------------------------------- | ----------------- | --------- |
| `feat`                            | MINOR (x.**Y**.0) | Yes       |
| `fix`                             | PATCH (x.y.**Z**) | Yes       |
| `perf`                            | PATCH (x.y.**Z**) | Yes       |
| `!` or `BREAKING CHANGE`          | MAJOR (**X**.0.0) | Yes       |
| Others (`docs`, `refactor`, etc.) | No release        | No        |

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
