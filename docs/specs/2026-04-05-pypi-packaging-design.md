# PyPI Packaging Design — `stepss-cg-studio`

**Date:** 2026-04-05
**Status:** Draft
**Goal:** Package CG Studio as a `pip install`-able PyPI package with a bundled CODEGEN binary, so electrical engineers can install and run it with two commands and zero configuration.

---

## 1. User Experience

### Install

```bash
pip install stepss-cg-studio
```

Platform-specific wheels include the CODEGEN binary for Windows and Linux. No separate download or PATH configuration needed.

### Run

```bash
cg-studio
```

Starts the local server and auto-opens the default browser to the editor. The user never touches a terminal again after this command.

### Upgrade

```bash
pip install --upgrade stepss-cg-studio
```

User config and workspace are preserved across upgrades (stored outside the package).

---

## 2. Package Identity

| Field | Value |
|-------|-------|
| PyPI name | `stepss-cg-studio` |
| Import name | `cg_studio` |
| CLI command | `cg-studio` |
| Python support | `>=3.10` |
| License | MIT |
| Build system | setuptools via `pyproject.toml` |

---

## 3. Package Layout

```
stepss-cg-studio/
├── pyproject.toml
├── LICENSE
├── README.md
├── src/
│   └── cg_studio/
│       ├── __init__.py          # __version__, package metadata
│       ├── __main__.py          # python -m cg_studio support
│       ├── cli.py               # entry point: parse args, start server, open browser
│       ├── app.py               # FastAPI app (moved from server/app.py)
│       ├── dsl_parser.py        # moved from server/dsl_parser.py
│       ├── dsl_emitter.py       # moved from server/dsl_emitter.py
│       ├── config.py            # platform-aware config/workspace dir resolution
│       ├── bin/                  # bundled CODEGEN binaries
│       │   ├── codegen.exe      # Windows (included only in win_amd64 wheel)
│       │   ├── codegen          # Linux (included only in manylinux wheel)
│       │   └── .gitkeep         # macOS: no binary yet, dir exists for future use
│       └── frontend/            # all static assets (moved from frontend/)
│           ├── index.html
│           ├── css/
│           │   └── style.css
│           ├── js/
│           │   ├── main.js
│           │   ├── canvas.js
│           │   ├── store.js
│           │   ├── forms.js
│           │   ├── palette.js
│           │   ├── dsl_preview.js
│           │   └── api.js
│           ├── blocks.json
│           └── favicon.svg
├── tests/                       # stays at repo root, not packaged
├── examples/                    # stays at repo root, not packaged
└── docs/                        # stays at repo root, not packaged
```

Uses `src/` layout (current setuptools best practice) to prevent accidental imports from the working directory.

---

## 4. `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "stepss-cg-studio"
dynamic = ["version"]
description = "Visual block diagram editor for STEPSS CODEGEN power system models"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "Petros Aristidou", email = "apetros@pm.me"},
]
keywords = ["CODEGEN", "Power Systems", "STEPSS", "RAMSES", "Block Diagram"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering",
]
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
    "aiofiles>=23.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "httpx>=0.27.0",
    "playwright>=1.40",
]

[project.urls]
Homepage = "https://stepss.sps-lab.org/"
Documentation = "https://stepss.sps-lab.org/developer/cg-studio/"
Repository = "https://github.com/SPS-L/stepss-cg-studio"
Issues = "https://github.com/SPS-L/stepss-cg-studio/issues"

[project.scripts]
cg-studio = "cg_studio.cli:main"

[tool.setuptools.dynamic]
version = {attr = "cg_studio.__version__"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
cg_studio = ["frontend/**/*", "bin/*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## 5. Platform-Aware Configuration (`config.py`)

### Config directory

| Platform | Path |
|----------|------|
| Windows | `%LOCALAPPDATA%\cg-studio\` (e.g., `C:\Users\<name>\AppData\Local\cg-studio\`) |
| Linux | `~/.config/cg-studio/` |
| macOS | `~/.config/cg-studio/` |

### Workspace directory

| Platform | Path |
|----------|------|
| Windows | `Documents\cg-studio-workspace` |
| Linux/macOS | `~/cg-studio-workspace` |

### Implementation

```python
import os
import platform
from pathlib import Path

def config_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        return Path(base) / "cg-studio"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cg-studio"

def default_workspace() -> Path:
    if platform.system() == "Windows":
        return Path.home() / "Documents" / "cg-studio-workspace"
    return Path.home() / "cg-studio-workspace"
```

### Config file (`config.json`)

Created automatically on first run inside `config_dir()`:

```json
{
    "codegen_path": "bundled",
    "workspace_dir": "<platform-specific default, absolute>",
    "host": "127.0.0.1",
    "port": 8765
}
```

All paths are stored and displayed as absolute paths — never raw `~/` strings.

### Config loading priority

1. `config_dir() / "config.json"` if it exists (installed mode)
2. `server/config.json` relative to repo root (dev mode, for editable installs)
3. Built-in defaults (if neither file exists)

---

## 6. CODEGEN Binary Resolution

When the app needs to invoke CODEGEN, resolve the binary path in this order:

1. **User override** — if `config.json` has `codegen_path` set to anything other than `"bundled"`, use that value as-is
2. **Bundled binary** — locate `cg_studio/bin/codegen(.exe)` via `importlib.resources`
3. **System PATH** — fall back to `shutil.which("codegen")`
4. **Not found** — return a platform-aware warning:
   - **macOS:** "CODEGEN binary is not yet available for macOS. Please provide your own binary via Settings (gear icon) > Codegen binary path."
   - **Windows/Linux:** "CODEGEN binary not found. Reinstall stepss-cg-studio with pip or set the path in Settings."
   
   In both cases, the rest of the app works normally (editing, saving, exporting DSL). Only the "Run Codegen" button is disabled, with a tooltip explaining why.

```python
import importlib.resources
import platform
import shutil
from pathlib import Path

def resolve_codegen(configured_path: str) -> Path | None:
    # 1. User override
    if configured_path and configured_path != "bundled":
        p = Path(configured_path)
        if p.is_file():
            return p
        return None

    # 2. Bundled binary
    suffix = ".exe" if platform.system() == "Windows" else ""
    ref = importlib.resources.files("cg_studio") / "bin" / f"codegen{suffix}"
    with importlib.resources.as_file(ref) as bundled:
        if bundled.is_file():
            return bundled

    # 3. System PATH
    found = shutil.which("codegen")
    return Path(found) if found else None
```

On Linux, the bundled binary must have its execute permission set. The CI build step handles this (see Section 9).

---

## 7. CLI Entry Point (`cli.py`)

```python
import argparse
import sys
import webbrowser
import threading
import uvicorn

def main():
    parser = argparse.ArgumentParser(description="CODEGEN Studio")
    parser.add_argument("--host", default=None, help="Override host")
    parser.add_argument("--port", type=int, default=None, help="Override port")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    from cg_studio.config import load_config
    cfg = load_config()

    host = args.host or cfg["host"]
    port = args.port or cfg["port"]

    if not args.no_browser:
        # Open browser after short delay to let server start
        threading.Timer(1.5, webbrowser.open, args=[f"http://{host}:{port}"]).start()

    uvicorn.run(
        "cg_studio.app:app",
        host=host,
        port=port,
        log_level="info",
    )
```

Key differences from current dev `app.py`:
- **No `--reload`** in installed mode (not a dev server)
- **Auto-opens browser** (can be suppressed with `--no-browser`)
- **CLI flags** for host/port override without editing config

### `__main__.py`

```python
from cg_studio.cli import main
main()
```

Enables `python -m cg_studio` as an alternative to the `cg-studio` command.

---

## 8. Migration from Current Structure

### Files that move

| Current location | New location |
|-----------------|-------------|
| `server/app.py` | `src/cg_studio/app.py` |
| `server/dsl_parser.py` | `src/cg_studio/dsl_parser.py` |
| `server/dsl_emitter.py` | `src/cg_studio/dsl_emitter.py` |
| `server/config.json` | Becomes default template in `config.py` |
| `frontend/` (all contents) | `src/cg_studio/frontend/` |
| `requirements.txt` | Replaced by `pyproject.toml [project.dependencies]` |

### Files that stay

| File | Reason |
|------|--------|
| `tests/` | Stays at repo root, standard pytest location |
| `examples/` | Not packaged, stays at repo root |
| `docs/` | Not packaged, stays at repo root |
| `run.bat`, `run.sh` | Keep for dev convenience, update to call `python -m cg_studio` |
| `.github/workflows/ci.yml` | Updated (see Section 9) |

### Import adjustments

All internal imports change from relative file references to package imports:

```python
# Before (server/app.py)
from dsl_parser import parse_dsl
from dsl_emitter import emit_dsl

# After (src/cg_studio/app.py)
from cg_studio.dsl_parser import parse_dsl
from cg_studio.dsl_emitter import emit_dsl
```

### Static file serving

`app.py` currently resolves the frontend path relative to `__file__`. After the move:

```python
# Before
FRONTEND = Path(__file__).parent.parent / "frontend"

# After
FRONTEND = importlib.resources.files("cg_studio") / "frontend"
```

### Test adjustments

Tests currently import from `server.dsl_parser` etc. After migration:

```python
# Before
sys.path.insert(0, "server")
from dsl_parser import parse_dsl

# After
from cg_studio.dsl_parser import parse_dsl
```

Existing test logic and assertions remain unchanged.

---

## 9. CI/CD — Build and Publish

### Updated CI workflow (`.github/workflows/ci.yml`)

The existing test job stays. Add a publish job triggered on version tags:

```yaml
on:
  push:
    branches: ["**"]
    tags: ["v*"]
  pull_request:
    branches: ["main"]

jobs:
  test:
    # ... existing pytest matrix (unchanged)

  build:
    needs: test
    if: startsWith(github.ref, 'refs/tags/v')
    strategy:
      matrix:
        include:
          - os: windows-latest
            wheel_plat: win_amd64
          - os: ubuntu-latest
            wheel_plat: manylinux_2_17_x86_64
          - os: macos-latest
            wheel_plat: macosx_11_0_arm64
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Copy CODEGEN binary
        run: |
          # Download or copy the platform-specific codegen binary
          # into src/cg_studio/bin/
      - name: Set execute permission (Linux)
        if: runner.os == 'Linux'
        run: chmod +x src/cg_studio/bin/codegen
      - name: Build wheel
        run: pip install build && python -m build --wheel
      - uses: actions/upload-artifact@v4
        with:
          name: wheel-${{ matrix.wheel_plat }}
          path: dist/*.whl

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write    # trusted publishing
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: dist/
          merge-multiple: true
      - uses: pypa/gh-action-pypi-publish@release/v1
```

### Release process

1. Update `__version__` in `src/cg_studio/__init__.py`
2. Commit: `git commit -m "release: vX.Y.Z"`
3. Tag: `git tag vX.Y.Z && git push --tags`
4. CI builds platform wheels, runs tests, publishes to PyPI

### CODEGEN binary source

The CODEGEN binaries are built from [SPS-L/stepss-Codegen](https://github.com/SPS-L/stepss-Codegen). The CI workflow must either:
- **(a)** Download a tagged release from the Codegen repo, or
- **(b)** Pull pre-built binaries from a known location (e.g., a GitHub release asset)

The exact mechanism depends on how the Codegen repo publishes its binaries. This is the one external dependency the CI must resolve.

---

## 10. Dev Workflow

Developers working on cg-studio itself use an editable install:

```bash
git clone https://github.com/SPS-L/stepss-cg-studio.git
cd stepss-cg-studio
pip install -e ".[dev]"
cg-studio                    # runs from source
pytest tests/ -v
```

Editable mode means changes to `src/cg_studio/` are reflected immediately without reinstalling.

The `run.bat` and `run.sh` scripts are updated to:

```bash
# run.sh
python -m cg_studio
```

```bat
:: run.bat
python -m cg_studio
pause
```

---

## 11. Backwards Compatibility

- **Existing `.cgproj` files** — fully compatible. The file format is unchanged; only the server code location moved.
- **Existing DSL `.txt` files** — fully compatible. Parser/emitter logic is unchanged.
- **`/config` API endpoint** — still works. Reads/writes to the new platform-specific config location.
- **`server/config.json`** — no longer used in installed mode. Old files are ignored (not migrated). Users who had custom settings will need to reconfigure via the Settings modal on first run.

---

## 12. Scope Exclusions

The following are explicitly **not** part of this work:

- **macOS CODEGEN binary** — no CODEGEN binary for macOS exists yet. The macOS wheel is distributed without a bundled binary. The app runs normally but disables "Run Codegen" with a warning prompting users to provide their own binary via Settings. When the macOS binary becomes available, it will be added to the macOS wheel with no app changes needed.
- **Auto-update mechanism** — users upgrade via `pip install --upgrade`.
- **Standalone executables** (PyInstaller/Nuitka) — potential future enhancement, not in scope.
- **Docker packaging** — not in scope.
- **Changes to the frontend or DSL logic** — this is a packaging-only change. All application behaviour is preserved.
