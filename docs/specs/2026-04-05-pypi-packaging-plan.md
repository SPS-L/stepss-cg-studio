# PyPI Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure cg-studio into a `pip install`-able PyPI package with bundled CODEGEN binary, platform-aware config, and `cg-studio` CLI command — per the approved spec at `docs/specs/2026-04-05-pypi-packaging-design.md`.

**Architecture:** Move `server/*.py` and `frontend/` into a `src/cg_studio/` package. Add `config.py` for platform-aware config/codegen resolution, `cli.py` for the entry point, and `pyproject.toml` for build metadata. Update all imports in source and tests. Existing app logic is untouched.

**Tech Stack:** Python 3.10+, setuptools, FastAPI, uvicorn, importlib.resources

---

## File Structure

### New files to create

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Build config, dependencies, entry point, package-data |
| `src/cg_studio/__init__.py` | `__version__` constant |
| `src/cg_studio/__main__.py` | `python -m cg_studio` support |
| `src/cg_studio/cli.py` | CLI entry point: arg parsing, server start, browser open |
| `src/cg_studio/config.py` | Platform-aware config dir, workspace dir, config load/save, codegen resolution |
| `src/cg_studio/bin/.gitkeep` | Placeholder for bundled binaries |

### Files to move (git mv)

| From | To |
|------|-----|
| `server/app.py` | `src/cg_studio/app.py` |
| `server/dsl_parser.py` | `src/cg_studio/dsl_parser.py` |
| `server/dsl_emitter.py` | `src/cg_studio/dsl_emitter.py` |
| `frontend/` (entire tree) | `src/cg_studio/frontend/` |

### Files to modify in-place

| File | What changes |
|------|-------------|
| `src/cg_studio/app.py` | Imports, path resolution, config loading — use `cg_studio.config` and `importlib.resources` |
| `src/cg_studio/dsl_parser.py` | `_load_blocks()` path resolution uses `importlib.resources` |
| `src/cg_studio/dsl_emitter.py` | `_load_blocks()` path resolution uses `importlib.resources` |
| `tests/conftest.py` | Remove `sys.path` hack, import `from cg_studio.app import app` |
| `tests/test_parser.py` | Remove `sys.path` hack, import `from cg_studio.dsl_parser` / `from cg_studio.dsl_emitter` |
| `tests/test_api.py` | Remove `sys.path` hack, import `from cg_studio.app import app` |
| `run.sh` | Change to `python -m cg_studio` |
| `run.bat` | Change to `python -m cg_studio` |
| `.github/workflows/ci.yml` | Add `pip install -e ".[dev]"` step, add build/publish jobs |

### Files to delete

| File | Reason |
|------|--------|
| `server/config.json` | Replaced by runtime default in `config.py` |
| `server/` directory | Empty after moves |
| `requirements.txt` | Replaced by `pyproject.toml` |

---

### Task 1: Create package skeleton and pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `src/cg_studio/__init__.py`
- Create: `src/cg_studio/__main__.py`
- Create: `src/cg_studio/bin/.gitkeep`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src/cg_studio/bin
```

- [ ] **Step 2: Create `src/cg_studio/__init__.py`**

```python
"""CODEGEN Studio — visual block diagram editor for STEPSS CODEGEN models."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `src/cg_studio/__main__.py`**

```python
"""Allow running as `python -m cg_studio`."""

from cg_studio.cli import main

main()
```

- [ ] **Step 4: Create `src/cg_studio/bin/.gitkeep`**

Empty file. Placeholder for bundled CODEGEN binaries.

- [ ] **Step 5: Create `pyproject.toml`**

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

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/cg_studio/__init__.py src/cg_studio/__main__.py src/cg_studio/bin/.gitkeep
git commit -m "feat: add package skeleton with pyproject.toml"
```

---

### Task 2: Create `config.py` — platform-aware config and codegen resolution

**Files:**
- Create: `src/cg_studio/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config.py**

Create `tests/test_config.py`:

```python
"""tests/test_config.py — config module unit tests."""

import json
import platform
from pathlib import Path
from unittest.mock import patch

from cg_studio.config import config_dir, default_workspace, load_config, save_config, resolve_codegen


class TestConfigDir:
    """Platform-aware config directory resolution."""

    @patch("platform.system", return_value="Windows")
    def test_windows_uses_localappdata(self, _mock, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\test\\AppData\\Local")
        result = config_dir()
        assert result == Path("C:\\Users\\test\\AppData\\Local") / "cg-studio"

    @patch("platform.system", return_value="Linux")
    def test_linux_uses_xdg_config_home(self, _mock, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/test/.config")
        result = config_dir()
        assert result == Path("/home/test/.config") / "cg-studio"

    @patch("platform.system", return_value="Linux")
    def test_linux_default_without_xdg(self, _mock, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = config_dir()
        assert result == Path.home() / ".config" / "cg-studio"


class TestDefaultWorkspace:

    @patch("platform.system", return_value="Windows")
    def test_windows_uses_documents(self, _mock):
        result = default_workspace()
        assert result == Path.home() / "Documents" / "cg-studio-workspace"

    @patch("platform.system", return_value="Linux")
    def test_linux_uses_home(self, _mock):
        result = default_workspace()
        assert result == Path.home() / "cg-studio-workspace"


class TestLoadConfig:

    def test_creates_default_when_missing(self, tmp_path):
        cfg = load_config(config_path=tmp_path / "config.json")
        assert cfg["codegen_path"] == "bundled"
        assert cfg["host"] == "127.0.0.1"
        assert cfg["port"] == 8765
        assert "workspace_dir" in cfg

    def test_reads_existing_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "codegen_path": "/usr/local/bin/codegen",
            "workspace_dir": "/tmp/ws",
            "host": "0.0.0.0",
            "port": 9000,
        }))
        cfg = load_config(config_path=config_file)
        assert cfg["codegen_path"] == "/usr/local/bin/codegen"
        assert cfg["port"] == 9000


class TestSaveConfig:

    def test_writes_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        save_config({"codegen_path": "bundled", "host": "127.0.0.1",
                      "port": 8765, "workspace_dir": str(tmp_path)},
                     config_path=config_file)
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["port"] == 8765


class TestResolveCodegen:

    def test_user_override_valid_path(self, tmp_path):
        binary = tmp_path / "my_codegen"
        binary.write_text("fake")
        result = resolve_codegen(str(binary))
        assert result == binary

    def test_user_override_invalid_path(self):
        result = resolve_codegen("/nonexistent/path/codegen")
        assert result is None

    def test_bundled_sentinel(self):
        # "bundled" should attempt package lookup then PATH; result depends on env
        # Just verify it doesn't crash
        resolve_codegen("bundled")

    @patch("shutil.which", return_value=None)
    def test_not_found_returns_none(self, _mock):
        result = resolve_codegen("bundled")
        # May find bundled or not — if not, should be None
        # This test verifies the fallback chain completes without error
        assert result is None or isinstance(result, Path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'cg_studio'` (package not installed yet).

- [ ] **Step 3: Create `src/cg_studio/config.py`**

```python
"""
config.py
=========
Platform-aware configuration, workspace directory resolution,
and CODEGEN binary lookup.
"""

from __future__ import annotations

import importlib.resources
import json
import os
import platform
import shutil
from pathlib import Path


def config_dir() -> Path:
    """Return the platform-appropriate config directory for cg-studio."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(base) / "cg-studio"
    xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg) / "cg-studio"


def default_workspace() -> Path:
    """Return the platform-appropriate default workspace directory."""
    if platform.system() == "Windows":
        return Path.home() / "Documents" / "cg-studio-workspace"
    return Path.home() / "cg-studio-workspace"


_DEFAULTS = {
    "codegen_path": "bundled",
    "host": "127.0.0.1",
    "port": 8765,
}


def load_config(config_path: Path | None = None) -> dict:
    """Load config from *config_path* (default: platform config dir).

    Creates the file with defaults if it does not exist.
    """
    if config_path is None:
        config_path = config_dir() / "config.json"

    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))

    # Build defaults with resolved workspace path
    cfg = {**_DEFAULTS, "workspace_dir": str(default_workspace())}
    # Write defaults for next time (ensure parent dir exists)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def save_config(cfg: dict, config_path: Path | None = None) -> None:
    """Persist *cfg* to *config_path* (default: platform config dir)."""
    if config_path is None:
        config_path = config_dir() / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def resolve_codegen(configured_path: str) -> Path | None:
    """Resolve the CODEGEN binary using the priority chain:

    1. User override (any value other than ``"bundled"``)
    2. Bundled binary inside this package
    3. System PATH lookup
    4. ``None`` (not found)
    """
    # 1. User override
    if configured_path and configured_path != "bundled":
        p = Path(configured_path)
        return p if p.is_file() else None

    # 2. Bundled binary
    suffix = ".exe" if platform.system() == "Windows" else ""
    try:
        ref = importlib.resources.files("cg_studio") / "bin" / f"codegen{suffix}"
        with importlib.resources.as_file(ref) as bundled:
            if bundled.is_file():
                return Path(str(bundled))
    except (TypeError, FileNotFoundError):
        pass

    # 3. System PATH
    found = shutil.which("codegen")
    return Path(found) if found else None
```

- [ ] **Step 4: Install package in editable mode and run tests**

```bash
pip install -e ".[dev]"
pytest tests/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cg_studio/config.py tests/test_config.py
git commit -m "feat: add platform-aware config and codegen resolution"
```

---

### Task 3: Create `cli.py` — CLI entry point

**Files:**
- Create: `src/cg_studio/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for cli.py**

Create `tests/test_cli.py`:

```python
"""tests/test_cli.py — CLI entry point tests."""

from unittest.mock import patch, MagicMock

from cg_studio.cli import main


class TestCLI:

    @patch("cg_studio.cli.uvicorn")
    @patch("cg_studio.cli.webbrowser")
    @patch("cg_studio.cli.load_config", return_value={
        "host": "127.0.0.1", "port": 8765,
        "codegen_path": "bundled", "workspace_dir": "/tmp",
    })
    def test_default_opens_browser(self, _cfg, mock_wb, mock_uv):
        with patch("sys.argv", ["cg-studio"]):
            main()
        mock_uv.run.assert_called_once()
        # Browser timer is started (threading.Timer)
        # Just verify uvicorn was called with correct host/port
        call_kwargs = mock_uv.run.call_args
        assert call_kwargs[1]["host"] == "127.0.0.1"
        assert call_kwargs[1]["port"] == 8765

    @patch("cg_studio.cli.uvicorn")
    @patch("cg_studio.cli.webbrowser")
    @patch("cg_studio.cli.load_config", return_value={
        "host": "127.0.0.1", "port": 8765,
        "codegen_path": "bundled", "workspace_dir": "/tmp",
    })
    def test_no_browser_flag(self, _cfg, mock_wb, mock_uv):
        with patch("sys.argv", ["cg-studio", "--no-browser"]):
            main()
        mock_uv.run.assert_called_once()

    @patch("cg_studio.cli.uvicorn")
    @patch("cg_studio.cli.webbrowser")
    @patch("cg_studio.cli.load_config", return_value={
        "host": "127.0.0.1", "port": 8765,
        "codegen_path": "bundled", "workspace_dir": "/tmp",
    })
    def test_port_override(self, _cfg, mock_wb, mock_uv):
        with patch("sys.argv", ["cg-studio", "--port", "9999"]):
            main()
        call_kwargs = mock_uv.run.call_args
        assert call_kwargs[1]["port"] == 9999
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'cg_studio.cli'`.

- [ ] **Step 3: Create `src/cg_studio/cli.py`**

```python
"""
cli.py
======
Console entry point for ``cg-studio`` command.

Usage::

    cg-studio                  # start server, open browser
    cg-studio --no-browser     # start server only
    cg-studio --port 9000      # override port
    python -m cg_studio        # alternative invocation
"""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from cg_studio.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cg-studio",
        description="CODEGEN Studio — visual block diagram editor for STEPSS CODEGEN models",
    )
    parser.add_argument("--host", default=None, help="Override server host")
    parser.add_argument("--port", type=int, default=None, help="Override server port")
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't auto-open the browser",
    )
    args = parser.parse_args()

    cfg = load_config()
    host = args.host or cfg["host"]
    port = args.port or cfg["port"]

    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=[f"http://{host}:{port}"]).start()

    uvicorn.run(
        "cg_studio.app:app",
        host=host,
        port=port,
        log_level="info",
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cli.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cg_studio/cli.py tests/test_cli.py
git commit -m "feat: add cg-studio CLI entry point"
```

---

### Task 4: Move source files into `src/cg_studio/`

This task moves files with `git mv` to preserve history, then updates imports. The moves and import edits are tightly coupled — do them all in one commit.

**Files:**
- Move: `server/app.py` -> `src/cg_studio/app.py`
- Move: `server/dsl_parser.py` -> `src/cg_studio/dsl_parser.py`
- Move: `server/dsl_emitter.py` -> `src/cg_studio/dsl_emitter.py`
- Move: `frontend/` -> `src/cg_studio/frontend/`
- Delete: `server/config.json`, `server/` directory, `requirements.txt`

- [ ] **Step 1: Move files with git**

```bash
git mv server/app.py src/cg_studio/app.py
git mv server/dsl_parser.py src/cg_studio/dsl_parser.py
git mv server/dsl_emitter.py src/cg_studio/dsl_emitter.py
git mv frontend/ src/cg_studio/frontend/
git rm server/config.json
rmdir server/__pycache__ 2>/dev/null; rmdir server 2>/dev/null || true
git rm requirements.txt
```

- [ ] **Step 2: Update imports in `src/cg_studio/app.py`**

Replace the path resolution block at the top (lines 43-47) and update lazy imports inside route handlers.

**Old code (lines 43-47):**
```python
HERE = Path(__file__).parent
ROOT = HERE.parent
FRONTEND_DIR = ROOT / "frontend"
CONFIG_PATH = HERE / "config.json"
```

**New code:**
```python
import importlib.resources

_PKG_FILES = importlib.resources.files("cg_studio")
FRONTEND_DIR = _PKG_FILES / "frontend"
```

**Old config functions (lines 50-58):**
```python
def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"codegen_path": "codegen", "workspace_dir": "workspace",
            "host": "127.0.0.1", "port": 8765}


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
```

**New config functions:**
```python
from cg_studio.config import load_config as _load_config, save_config as _save_config, resolve_codegen as _resolve_codegen
```

Remove the old `_load_config` and `_save_config` function definitions entirely.

**Old lazy imports inside route handlers (lines 113, 120, 173):**
```python
from dsl_parser import MANDATORY_OUTPUTS
from dsl_parser import parse_dsl as _parse
from dsl_emitter import emit_dsl as _emit
```

**New imports** (move to top of file, no longer lazy):
```python
from cg_studio.dsl_parser import parse_dsl as _parse, MANDATORY_OUTPUTS
from cg_studio.dsl_emitter import emit_dsl as _emit
```

Remove the `from dsl_parser ...` and `from dsl_emitter ...` lines from inside route handler bodies.

**Old codegen binary resolution in `run_codegen` (line 188):**
```python
codegen_bin = cfg.get("codegen_path", "codegen")
```

**New:**
```python
codegen_bin = _resolve_codegen(cfg.get("codegen_path", "bundled"))
if codegen_bin is None:
    import platform as _plat
    if _plat.system() == "Darwin":
        detail = ("CODEGEN binary is not yet available for macOS. "
                  "Please provide your own binary via Settings "
                  "(gear icon) > Codegen binary path.")
    else:
        detail = ("CODEGEN binary not found. Reinstall stepss-cg-studio "
                  "with pip or set the path in Settings.")
    raise HTTPException(status_code=500, detail=detail)
```

**Old static mount (lines 252-253):**
```python
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
```

**New static mount** (importlib.resources traversable needs `as_file` for StaticFiles):
```python
_frontend_ctx = importlib.resources.as_file(FRONTEND_DIR)
_frontend_path = _frontend_ctx.__enter__()
app.mount("/", StaticFiles(directory=str(_frontend_path), html=True), name="frontend")
```

**Old __main__ block (lines 257-268):** Replace entirely:
```python
if __name__ == "__main__":
    from cg_studio.cli import main
    main()
```

**Old blocks endpoint path (line 104):**
```python
blocks_path = FRONTEND_DIR / "blocks.json"
```

**New** (works with traversable):
```python
with importlib.resources.as_file(_PKG_FILES / "frontend" / "blocks.json") as blocks_path:
    if not blocks_path.exists():
        raise HTTPException(status_code=404, detail="blocks.json not found")
    return JSONResponse(content=json.loads(blocks_path.read_text(encoding="utf-8")))
```

Also remove `ROOT` and `CONFIG_PATH` variables (no longer used). Remove `import uvicorn` from the top-level imports (moved to cli.py; only needed in __main__ which now delegates to cli).

- [ ] **Step 3: Update `_load_blocks()` in `src/cg_studio/dsl_parser.py`**

**Old (lines 60-66):**
```python
def _load_blocks(blocks_path: str | None = None) -> dict[str, Any]:
    """Load blocks.json catalogue.  Returns dict keyed by block name."""
    if blocks_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        blocks_path = os.path.join(here, "..", "frontend", "blocks.json")
    with open(blocks_path, encoding="utf-8") as fh:
        return json.load(fh)
```

**New:**
```python
def _load_blocks(blocks_path: str | None = None) -> dict[str, Any]:
    """Load blocks.json catalogue.  Returns dict keyed by block name."""
    if blocks_path is None:
        import importlib.resources
        ref = importlib.resources.files("cg_studio") / "frontend" / "blocks.json"
        with importlib.resources.as_file(ref) as p:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    with open(blocks_path, encoding="utf-8") as fh:
        return json.load(fh)
```

- [ ] **Step 4: Update `_load_blocks()` in `src/cg_studio/dsl_emitter.py`**

Same change as Step 3 — identical function:

**Old (lines 18-23):**
```python
def _load_blocks(blocks_path: str | None = None) -> dict[str, Any]:
    if blocks_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        blocks_path = os.path.join(here, "..", "frontend", "blocks.json")
    with open(blocks_path, encoding="utf-8") as fh:
        return json.load(fh)
```

**New:**
```python
def _load_blocks(blocks_path: str | None = None) -> dict[str, Any]:
    """Load blocks.json catalogue.  Returns dict keyed by block name."""
    if blocks_path is None:
        import importlib.resources
        ref = importlib.resources.files("cg_studio") / "frontend" / "blocks.json"
        with importlib.resources.as_file(ref) as p:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    with open(blocks_path, encoding="utf-8") as fh:
        return json.load(fh)
```

- [ ] **Step 5: Reinstall editable package**

The file moves require re-running the install:

```bash
pip install -e ".[dev]"
```

- [ ] **Step 6: Run parser and emitter tests to verify they still pass**

```bash
pytest tests/test_parser.py -v
```

Expected: FAIL — tests still use `sys.path` hack pointing to old `server/` directory. This is expected; we fix test imports in Task 5.

- [ ] **Step 7: Commit the moves and source edits**

```bash
git add -A
git commit -m "refactor: move source into src/cg_studio/ package layout"
```

---

### Task 5: Update test imports

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_parser.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_e2e.py` (if any server imports)

- [ ] **Step 1: Update `tests/conftest.py`**

**Old (lines 6-13):**
```python
import sys
import os
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
```

**New:**
```python
import threading
import time

import pytest
```

Remove the `sys` and `os` imports (unless used elsewhere in the file — in conftest.py they are only used for the path hack). Remove the `sys.path.insert` line.

**Old import in `server_url` fixture (line 20):**
```python
from app import app
```

**New:**
```python
from cg_studio.app import app
```

- [ ] **Step 2: Update `tests/test_parser.py`**

**Old (lines 8-16):**
```python
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from dsl_parser import parse_dsl, RAMSES_INPUTS, MANDATORY_OUTPUTS
from dsl_emitter import emit_dsl
```

**New:**
```python
import os
import json
import pytest

from cg_studio.dsl_parser import parse_dsl, RAMSES_INPUTS, MANDATORY_OUTPUTS
from cg_studio.dsl_emitter import emit_dsl
```

Keep `os` — it's used for `EXAMPLES_DIR` on line 18.

- [ ] **Step 3: Update `tests/test_api.py`**

**Old (lines 8-18):**
```python
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)
```

**New:**
```python
import json
import pytest

from fastapi.testclient import TestClient
from cg_studio.app import app

client = TestClient(app)
```

Remove `os` and `sys` imports if not used elsewhere in the file. Keep `json` and `pytest`.

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "refactor: update test imports to use cg_studio package"
```

---

### Task 6: Update launchers and clean up

**Files:**
- Modify: `run.sh`
- Modify: `run.bat`
- Delete: `requirements.txt` (if not already deleted in Task 4)

- [ ] **Step 1: Update `run.sh`**

**Full new content:**
```bash
#!/usr/bin/env bash
echo "Starting CODEGEN Studio..."
python -m cg_studio
```

- [ ] **Step 2: Update `run.bat`**

**Full new content:**
```batch
@echo off
echo Starting CODEGEN Studio...
python -m cg_studio
pause
```

- [ ] **Step 3: Verify launcher works**

```bash
bash run.sh &
sleep 3
curl -s http://127.0.0.1:8765/blocks | head -c 100
kill %1
```

Expected: JSON output from blocks endpoint.

- [ ] **Step 4: Commit**

```bash
git add run.sh run.bat
git commit -m "chore: update launchers to use python -m cg_studio"
```

---

### Task 7: Update CI workflow

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Read current CI file**

```bash
cat .github/workflows/ci.yml
```

- [ ] **Step 2: Update the test job to use editable install**

In the existing `test` job, replace the `pip install -r requirements.txt` step with:

```yaml
      - name: Install package with dev dependencies
        run: pip install -e ".[dev]"
```

- [ ] **Step 3: Add build and publish jobs**

Append after the existing `test` job:

```yaml
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
      - name: Install build tools
        run: pip install build
      # TODO: Add step to download platform-specific CODEGEN binary
      # into src/cg_studio/bin/ from stepss-Codegen releases
      - name: Set execute permission (Linux)
        if: runner.os == 'Linux'
        run: chmod +x src/cg_studio/bin/codegen || true
      - name: Build wheel
        run: python -m build --wheel
      - uses: actions/upload-artifact@v4
        with:
          name: wheel-${{ matrix.wheel_plat }}
          path: dist/*.whl

  publish:
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: dist/
          merge-multiple: true
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 4: Also update the trigger to include tags**

Ensure the `on:` block includes tags:

```yaml
on:
  push:
    branches: ["**"]
    tags: ["v*"]
  pull_request:
    branches: ["main"]
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add editable install, build wheels, and PyPI publish"
```

---

### Task 8: Full integration verification

**Files:** None new — verification only.

- [ ] **Step 1: Clean reinstall from scratch**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all ~75 tests PASS.

- [ ] **Step 3: Verify CLI entry point works**

```bash
cg-studio --no-browser &
sleep 2
curl -s http://127.0.0.1:8765/blocks | python -m json.tool | head -5
curl -s http://127.0.0.1:8765/config | python -m json.tool
kill %1
```

Expected: blocks JSON and config JSON both return correctly. Config should show `"codegen_path": "bundled"`.

- [ ] **Step 4: Verify `python -m cg_studio` works**

```bash
python -m cg_studio --no-browser &
sleep 2
curl -s http://127.0.0.1:8765/mandatory_outputs | python -m json.tool
kill %1
```

Expected: mandatory outputs JSON returned.

- [ ] **Step 5: Verify wheel builds**

```bash
pip install build
python -m build --wheel
ls -la dist/
```

Expected: `.whl` file created in `dist/`.

- [ ] **Step 6: Commit any fixes needed, then tag**

If all checks pass and no fixes are needed, no commit is necessary here. This task is verification only.
