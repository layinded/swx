# SwX v2.0.0 PyPI Packaging Guide

Complete guide for packaging and publishing SwX to PyPI.

---

## Package Structure

```
swx-v2/
├── pyproject.toml          # Main package configuration
├── README.md               # Package description
├── LICENSE                 # MIT License
├── swx_core/               # Main package
│   ├── __init__.py
│   ├── version.py
│   └── ...
├── tests/                  # Test suite
├── docs/                   # Documentation
└── examples/               # Example applications
```

---

## pyproject.toml Configuration

```toml
[project]
name = "swx-core"
version = "2.0.0"
description = "Production-ready FastAPI framework with RBAC, JWT, and modular architecture"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10,<4.0"
authors = [
    {name = "SwX Team", email = "team@swx.dev"}
]
maintainers = [
    {name = "SwX Team", email = "team@swx.dev"}
]
keywords = [
    "fastapi",
    "framework",
    "jwt",
    "oauth",
    "rbac",
    "authentication",
    "authorization",
    "api",
    "rest",
    "async",
]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Framework :: FastAPI",
    "Topic :: Internet :: WWW/HTTP",
    "Topic :: Security",
    "Typing :: Typed",
]
dependencies = [
    "fastapi[standard]>=0.114.2,<1.0.0",
    "uvicorn[standard]>=0.23.0,<1.0.0",
    "gunicorn>=20.1.0,<22.0.0",
    "sqlalchemy>=2.0,<3.0",
    "sqlmodel>=0.0.21,<1.0.0",
    # ... other dependencies
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.3,<8.0.0",
    "pytest-asyncio>=0.23.0,<1.0.0",
    "pytest-cov>=4.1.0,<6.0.0",
    "mypy>=1.8.0,<2.0.0",
    "ruff>=0.2.2,<1.0.0",
    "black>=23.12.0,<24.0.0",
    "pre-commit>=3.6.2,<4.0.0",
]
redis = [
    "redis[hiredis]>=5.0.0",
]
celery = [
    "celery>=5.3.0",
]
prometheus = [
    "prometheus_client>=0.19.0",
]
all = [
    "swx-core[dev,redis,celery,prometheus]",
]

[project.urls]
Homepage = "https://github.com/swx/swx-api"
Documentation = "https://docs.swx.dev"
Repository = "https://github.com/swx/swx-api.git"
Issues = "https://github.com/swx/swx-api/issues"
Changelog = "https://github.com/swx/swx-api/blob/main/CHANGELOG.md"

[project.scripts]
swx = "swx_core.cli.main:main"

[build-system]
requires = ["hatchling>=1.18.0", "uv>=0.1.0"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["swx_core"]

[tool.hatch.build.targets.sdist]
include = [
    "/swx_core",
    "/tests",
    "/docs",
    "/README.md",
    "/LICENSE",
    "/pyproject.toml",
]
exclude = [
    "/.git",
    "/.github",
    "/.venv",
    "/__pycache__",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
]
```

---

## Building the Package

### Install Build Tools

```bash
pip install build twine
```

### Build Source Distribution and Wheel

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build
python -m build

# Output:
# dist/
# ├── swx_core-2.0.0-py3-none-any.whl
# └── swx_core-2.0.0.tar.gz
```

### Verify the Build

```bash
# Check package metadata
tar -tzf dist/swx_core-2.0.0.tar.gz | head -20

# Check wheel contents
unzip -l dist/swx_core-2.0.0-py3-none-any.whl | head -30

# Validate with twine
twine check dist/*
```

---

## Publishing to TestPyPI

First, test with TestPyPI before publishing to production.

### Configure TestPyPI Credentials

```bash
# Create ~/.pypirc
[distutils]
index-servers =
    pypi
    testpypi

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = <testpypi-token>

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = <pypi-token>
```

### Upload to TestPyPI

```bash
twine upload --repository testpypi dist/*
```

### Verify TestPyPI Installation

```bash
# Create clean venv
python -m venv test-env
source test-env/bin/activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ swx-core

# Test import
python -c "from swx_core import __version__; print(__version__)"
```

---

## Publishing to PyPI

### Pre-Publication Checklist

- [ ] Version updated in `swx_core/version.py`
- [ ] Version updated in `pyproject.toml`
- [ ] CHANGELOG.md updated
- [ ] All tests passing
- [ ] Documentation up to date
- [ ] No secrets in codebase
- [ ] README.md accurate
- [ ] License file present

### Upload to PyPI

```bash
# Final verification
twine check dist/*

# Upload
twine upload dist/*
```

### Verify PyPI Installation

```bash
# Wait 5-10 minutes for PyPI to index

# Create clean venv
python -m venv verify-env
source verify-env/bin/activate

# Install from PyPI
pip install swx-core

# Verify
python -c "
from swx_core import __version__, get_version_info
print(f'Version: {__version__}')
print(f'Info: {get_version_info()}')
"
```

---

## Version Management

### version.py Template

```python
# swx_core/version.py

VERSION_MAJOR = 2
VERSION_MINOR = 0
VERSION_PATCH = 0
VERSION_RELEASE = "final"  # alpha, beta, candidate, final
VERSION_SERIAL = 0

__version__ = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"

def get_version_info():
    return {
        "major": VERSION_MAJOR,
        "minor": VERSION_MINOR,
        "patch": VERSION_PATCH,
        "release": VERSION_RELEASE,
        "full": __version__,
    }
```

### Semantic Versioning Rules

| Bump Type | When to Use | Example |
|-----------|-------------|---------|
| MAJOR | Breaking changes | 1.0.0 → 2.0.0 |
| MINOR | New features, backward compatible | 2.0.0 → 2.1.0 |
| PATCH | Bug fixes | 2.0.0 → 2.0.1 |
| Pre-release | Alpha/beta/RC | 2.1.0a1, 2.1.0b2, 2.1.0rc1 |

---

## Automated Release Process

### GitHub Actions Workflow

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install build tools
        run: |
          pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Check package
        run: twine check dist/*
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: twine upload dist/*
```

---

## Post-Release Verification

### Automated Checks

```bash
#!/bin/bash
# scripts/verify-release.sh

VERSION=$1

echo "Verifying swx-core $VERSION..."

# Check PyPI API
curl -s https://pypi.org/pypi/swx-core/$VERSION/json | jq '.info.version'

# Install and test
pip install swx-core==$VERSION

# Import check
python -c "from swx_core import __version__; assert __version__ == '$VERSION'"

# CLI check
swx --version

echo "✅ Release $VERSION verified!"
```

### Rollback Procedure

If critical issues are discovered:

1. **Yank the release on PyPI**:
   - Go to https://pypi.org/manage/project/swx-core/releases/
   - Click "Yank" on the problematic version
   - This prevents new installs but keeps existing downloads working

2. **Publish hotfix**:
   ```bash
   # Bump patch version
   # Fix the issue
   # Build and release
   python -m build
   twine upload dist/*
   ```

3. **Document the issue**:
   - Update CHANGELOG.md
   - Create GitHub issue
   - Notify users via appropriate channels

---

## Dependency Management

### Pinning Strategy

```toml
# Production dependencies: Pin minor version
dependencies = [
    "fastapi>=0.114.2,<0.115.0",  # Allow patches, not minor
    "uvicorn>=0.23.0,<0.24.0",
]

# Development dependencies: Pin exact version
[project.optional-dependencies]
dev = [
    "pytest==7.4.3",
    "mypy==1.8.0",
]
```

### Dependency Security

```bash
# Check for vulnerabilities
pip install pip-audit
pip-audit -r requirements.txt

# Check for outdated packages
pip list --outdated
```

---

## Package Statistics

After release, monitor:

- Download stats: https://pypistats.org/packages/swx-core
- GitHub stars/issues
- PyPI classifiers and metadata

---

## Checklist

### Pre-Release

- [ ] All tests pass (`pytest --cov`)
- [ ] Linting passes (`ruff check .`)
- [ ] Type checking passes (`mypy swx_core/`)
- [ ] Version bumped
- [ ] CHANGELOG.md updated
- [ ] Documentation updated
- [ ] No secrets in codebase
- [ ] Build succeeds (`python -m build`)
- [ ] Package validates (`twine check dist/*`)

### Post-Release

- [ ] PyPI page looks correct
- [ ] Installation works (`pip install swx-core`)
- [ ] Imports work (`from swx_core import ...`)
- [ ] CLI works (`swx --version`)
- [ ] GitHub release created
- [ ] Announcement posted