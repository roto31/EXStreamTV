# Contributing to EXStreamTV

Thank you for your interest in contributing to EXStreamTV! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Release Process](#release-process)

---

## Code of Conduct

This project follows a simple code of conduct:

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Accept constructive criticism gracefully
- Focus on what's best for the community
- Show empathy towards others

---

## Getting Started

### Finding Issues to Work On

- Check the [GitHub Issues](https://github.com/roto31/EXStreamTV/issues) for open tasks
- Look for issues labeled `good first issue` if you're new
- `help wanted` labels indicate issues where contributions are especially welcome
- Comment on an issue before starting work to avoid duplicate efforts

### Types of Contributions

We welcome:

- **Bug fixes** - Fix issues and improve stability
- **Features** - Implement new functionality
- **Documentation** - Improve guides and API docs
- **Tests** - Add or improve test coverage
- **Performance** - Optimize code and reduce resource usage
- **UI/UX** - Enhance the web interface

---

## Development Setup

### Prerequisites

- Python 3.10 or higher
- FFmpeg 5.0+
- Git
- Node.js (for frontend development, optional)

### Clone the Repository

```bash
git clone https://github.com/roto31/EXStreamTV.git
cd EXStreamTV
```

### Create Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1 on Windows

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e ".[dev]"
```

### Verify Setup

```bash
# Run tests
pytest

# Start development server
python -m exstreamtv --debug
```

### IDE Setup

**VS Code (Recommended):**

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true
}
```

**PyCharm:**
1. Open the project folder
2. Configure interpreter: Settings → Project → Python Interpreter → Select `venv`
3. Enable Black formatter: Settings → Tools → Black

---

## Making Changes

### Branching Strategy

```bash
# Create a feature branch from main
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# For bug fixes
git checkout -b fix/issue-description

# For documentation
git checkout -b docs/topic-name
```

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style (formatting, missing semicolons)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```bash
git commit -m "feat(channels): add bulk import from M3U"
git commit -m "fix(streaming): resolve buffer overflow on long streams"
git commit -m "docs(api): add examples for library endpoints"
```

### Keeping Up to Date

```bash
# Regularly sync with main
git fetch origin
git rebase origin/main
```

---

## Pull Request Process

### Before Submitting

1. **Run all tests**
   ```bash
   pytest
   ```

2. **Check code formatting**
   ```bash
   black --check .
   flake8
   ```

3. **Update documentation** if you've changed APIs or behavior

4. **Add tests** for new functionality

### Creating the Pull Request

1. Push your branch:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Open a Pull Request on GitHub

3. Fill out the PR template:
   - Description of changes
   - Related issue(s)
   - Type of change
   - Testing performed
   - Screenshots (for UI changes)

### PR Review Process

- At least one maintainer must approve
- All CI checks must pass
- Discussions should be resolved
- Branch must be up to date with main

### After Merge

Your changes will be included in the next release. Thank you for contributing!

---

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 100 characters maximum
- **Imports**: Sorted with `isort`
- **Formatting**: Handled by `black`
- **Type hints**: Required for public APIs

```python
# Good
from typing import Optional, List

async def get_channels(
    group: Optional[str] = None,
    limit: int = 100,
) -> List[Channel]:
    """
    Retrieve channels with optional filtering.
    
    Args:
        group: Filter by channel group name
        limit: Maximum number of results
        
    Returns:
        List of Channel objects
    """
    ...
```

### Code Organization

```
exstreamtv/
├── api/           # FastAPI routes
├── database/      # SQLAlchemy models and repositories
├── media/         # Media handling (libraries, scanning)
├── streaming/     # Stream management
├── transcoding/   # FFmpeg integration
├── templates/     # Jinja2 HTML templates
├── static/        # CSS, JS assets
└── utils/         # Shared utilities
```

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

### Error Handling

```python
# Use specific exceptions
from exstreamtv.exceptions import ChannelNotFoundError, StreamingError

async def get_channel(channel_id: int) -> Channel:
    channel = await repository.get(channel_id)
    if not channel:
        raise ChannelNotFoundError(f"Channel {channel_id} not found")
    return channel
```

### Async Best Practices

- Use `async`/`await` for I/O operations
- Avoid blocking calls in async functions
- Use `asyncio.gather()` for concurrent operations

```python
# Good - concurrent execution
results = await asyncio.gather(
    fetch_channel_info(channel_id),
    fetch_channel_schedule(channel_id),
    fetch_channel_stats(channel_id),
)

# Avoid - sequential when concurrent is possible
info = await fetch_channel_info(channel_id)
schedule = await fetch_channel_schedule(channel_id)
stats = await fetch_channel_stats(channel_id)
```

---

## Testing

### Test Structure

```
tests/
├── unit/              # Fast, isolated tests
├── integration/       # API and database tests
├── e2e/              # End-to-end workflow tests
└── fixtures/         # Shared test data
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_channels.py

# Run with coverage
pytest --cov=exstreamtv --cov-report=html

# Run only fast unit tests
pytest tests/unit/ -x

# Run integration tests
pytest tests/integration/
```

### Writing Tests

```python
import pytest
from exstreamtv.api.channels import create_channel

class TestChannels:
    """Tests for channel operations."""
    
    @pytest.fixture
    def sample_channel(self):
        return {
            "number": 1,
            "name": "Test Channel",
            "group": "Test"
        }
    
    async def test_create_channel_success(self, client, sample_channel):
        """Creating a channel should return 201 with channel data."""
        response = await client.post("/api/channels", json=sample_channel)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_channel["name"]
        assert "id" in data
    
    async def test_create_channel_duplicate_number(self, client, sample_channel):
        """Creating a channel with duplicate number should fail."""
        await client.post("/api/channels", json=sample_channel)
        response = await client.post("/api/channels", json=sample_channel)
        
        assert response.status_code == 409
```

### Test Coverage

We aim for 80%+ test coverage. Check coverage locally:

```bash
pytest --cov=exstreamtv --cov-report=term-missing
```

---

## Documentation

### Documentation Structure

```
docs/
├── api/              # API reference
├── architecture/     # System design docs
└── guides/          # User guides
```

### Writing Documentation

- Use clear, concise language
- Include code examples
- Add screenshots for UI features
- Keep docs up to date with code changes

### Building Docs

```bash
# Install mkdocs
pip install mkdocs mkdocs-material

# Serve locally
mkdocs serve

# Build static site
mkdocs build
```

### Docstrings

Use Google-style docstrings:

```python
def scan_library(
    library_id: int,
    full_scan: bool = False,
) -> ScanResult:
    """
    Scan a media library for new and updated content.
    
    Args:
        library_id: The ID of the library to scan.
        full_scan: If True, rescan all files. If False, only scan
            new or modified files.
            
    Returns:
        ScanResult containing counts and any errors.
        
    Raises:
        LibraryNotFoundError: If the library doesn't exist.
        ScanInProgressError: If a scan is already running.
        
    Example:
        >>> result = await scan_library(1, full_scan=True)
        >>> print(f"Found {result.new_items} new items")
    """
```

---

## Release Process

Releases are managed by maintainers using semantic versioning.

### Version Numbers

- **MAJOR.MINOR.PATCH** (e.g., 1.6.0)
- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes

### Changelog

All notable changes are documented in `CHANGELOG.md`:

```markdown
## [1.6.0] - 2024-01-20

### Added
- Local media library support (#123)
- Hardware transcoding profiles (#145)

### Fixed
- Stream buffer overflow on long playback (#156)
- EPG timezone handling (#160)

### Changed
- Improved scanning performance by 40%
```

---

## Getting Help

- **Questions**: Open a [Discussion](https://github.com/roto31/EXStreamTV/discussions)
- **Bugs**: Open an [Issue](https://github.com/roto31/EXStreamTV/issues)
- **Chat**: Join our [Discord](https://discord.gg/exstreamtv)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to EXStreamTV! 🎬
