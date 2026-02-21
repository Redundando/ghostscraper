---
Package: readmerator
Version: 0.1.2
Source: https://pypi.org/project/readmerator/
Fetched: 2026-02-21 16:58:45
---

# readmerator

> Supercharge your AI coding assistant with instant access to all your dependency documentation.

Fetch and cache README files for Python dependencies, making them instantly available to AI assistants like Amazon Q, GitHub Copilot, and Cursor.

## Why?

AI coding assistants are powerful, but they don't automatically know about the packages you're using. You end up:
- Manually looking up documentation
- Copy-pasting docs into context
- Getting generic answers instead of package-specific help

**readmerator** solves this by automatically fetching all your dependency READMEs into a local folder that your AI can reference.

## Installation

```bash
pip install readmerator
```

## Quick Start

```bash
# In your project directory
readmerator

# Then in your AI assistant
@folder .ai-docs
```

That's it! Your AI now has full context on all your dependencies.

## How It Works

1. **Finds** all your dependency files (`requirements.txt`, `pyproject.toml`, `setup.py`, `setup.cfg`, `Pipfile`, `environment.yml`)
2. **Fetches** README files from PyPI and GitHub for each package
3. **Saves** them to `.ai-docs/` with metadata headers
4. **You reference** the folder in your AI assistant

## Usage

### Basic

```bash
readmerator
```

### With Options

```bash
# Custom output directory
readmerator --output-dir docs/packages

# Specify a specific requirements file
readmerator --source requirements.txt

# Verbose output (shows source: PyPI vs GitHub)
readmerator --verbose
```

By default, readmerator automatically detects and parses all dependency files in your project:
- `requirements.txt`
- `pyproject.toml` (PEP 621 and Poetry)
- `setup.py`
- `setup.cfg`
- `Pipfile` (Pipenv)
- `environment.yml` (Conda)

### Example Output

```bash
$ readmerator --verbose
Found 16 packages
Fetching READMEs to .ai-docs/

Fetching flask...
  ✓ flask: Saved (12453 bytes) from PyPI
Fetching fastapi...
  ✓ fastapi: Saved (23891 bytes) from GitHub
...

✓ Successfully fetched: 15
✗ Failed: 1
  Failed packages: private-internal-package

READMEs saved to .ai-docs/
Use '@folder .ai-docs' in your AI assistant to include documentation
```

## Output Format

Each package gets a markdown file with metadata:

```markdown
---
Package: requests
Version: 2.32.5
Source: https://github.com/psf/requests
Fetched: 2024-01-15 10:30:00
---

# Requests

**Requests** is a simple, yet elegant, HTTP library.
...
```

## Features

- **Multi-Format Support**: Automatically detects and parses all common Python dependency formats
- **Smart Fetching**: Tries PyPI first, falls back to GitHub
- **Fast**: Async/concurrent fetching
- **Reliable**: Graceful error handling for missing packages
- **Informative**: Progress indicators and detailed verbose mode
- **Lightweight**: Minimal dependencies (just aiohttp)

## AI Assistant Integration

### Amazon Q
```
@folder .ai-docs
```

### GitHub Copilot
```
#file:.ai-docs/*
```

### Cursor
```
@Docs .ai-docs
```

## Requirements

- Python 3.8+
- aiohttp
- tomli (for Python < 3.11)

## Contributing

Contributions welcome! Feel free to open issues or PRs on [GitHub](https://github.com/Redundando/readmerator).

## License

MIT © Arved Klöhn
