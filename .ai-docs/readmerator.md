---
Package: readmerator
Version: 0.1.5
Source: https://pypi.org/project/readmerator/
Fetched: 2026-03-13 09:44:29
---

# readmerator

> Supercharge your AI coding assistant with instant access to all your dependency documentation.

Fetch and cache README files for Python and npm dependencies, making them instantly available to AI assistants like Amazon Q, GitHub Copilot, and Cursor.

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

1. **Finds** all your dependency files recursively (Python: `requirements.txt`, `pyproject.toml`, etc. | npm: `package.json`)
2. **Fetches** README files from PyPI, npm registry, and GitHub for each package
3. **Saves** them to `.ai-docs/python/` and `.ai-docs/npm/` with metadata headers
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

# Verbose output (shows source: PyPI vs GitHub vs npm)
readmerator --verbose

# Only scan root directory (no subdirectories)
readmerator --no-recursive

# Limit recursion depth
readmerator --max-depth 2

# Fetch README from a custom URL
readmerator --url https://github.com/pallets/flask --name flask-docs

# Fetch from PyPI
readmerator --url https://pypi.org/project/requests

# Fetch from npm
readmerator --url https://www.npmjs.com/package/react
```

### Supported Formats

**Python:**
- `requirements.txt`
- `pyproject.toml` (PEP 621 and Poetry)
- `setup.py`
- `setup.cfg`
- `Pipfile` (Pipenv)
- `environment.yml` (Conda)

**npm:**
- `package.json` (dependencies + devDependencies)

### Example Output

```bash
$ readmerator --verbose
Found 25 packages
  Python: 15 packages
  npm: 10 packages
Fetching READMEs to .ai-docs/

Fetching flask...
  ✓ flask: Saved (12453 bytes) from PyPI
Fetching react...
  ✓ react: Saved (8234 bytes) from npm
Fetching fastapi...
  ✓ fastapi: Saved (23891 bytes) from GitHub
...

Python:
  ✓ Successfully fetched: 14
  ✗ Failed: 1
    Failed packages: private-internal-package
npm:
  ✓ Successfully fetched: 10

READMEs saved to .ai-docs/
Use '@folder .ai-docs' in your AI assistant to include documentation
```

## Output Format

Packages are organized by ecosystem:

```
.ai-docs/
├── python/
│   ├── flask.md
│   ├── requests.md
│   └── ...
└── npm/
    ├── react.md
    ├── lodash.md
    └── ...
```

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

- **Multi-Language Support**: Python (PyPI) and npm packages
- **Recursive Scanning**: Finds dependencies in subdirectories (monorepos, nested projects)
- **Multi-Format Support**: Automatically detects all common Python and npm dependency formats
- **Custom URLs**: Fetch READMEs from PyPI, npm, GitHub, or any URL
- **Smart Fetching**: Tries PyPI/npm first, falls back to GitHub
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
