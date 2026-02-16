# Publishing to PyPI

## Prerequisites

```bash
pip install build twine
```

## Build the Package

```bash
# Clean previous builds (Windows)
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist ghostscraper.egg-info rmdir /s /q ghostscraper.egg-info

# Build
python -m build
```

## Test on TestPyPI (Optional but Recommended)

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test install
pip install --index-url https://test.pypi.org/simple/ ghostscraper
```

## Publish to PyPI

```bash
# Upload to PyPI
twine upload dist/*
```

## Post-Publication

```bash
# Install from PyPI
pip install ghostscraper

# Or upgrade
pip install --upgrade ghostscraper
```

## Version Bumping

Update version in both:
1. `pyproject.toml` - version field
2. `ghostscraper/__init__.py` - __version__ variable

Version scheme:
- Patch: 0.2.0 → 0.2.1 (bug fixes)
- Minor: 0.2.0 → 0.3.0 (new features)
- Major: 0.2.0 → 1.0.0 (breaking changes)

Update `CHANGELOG.md` with changes.
