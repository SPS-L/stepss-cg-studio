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
