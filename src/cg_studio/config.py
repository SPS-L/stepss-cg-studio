"""
config.py
=========
Platform-aware configuration, workspace directory resolution,
and bundled CODEGEN executable lookup.
"""

from __future__ import annotations

import json
import os
import platform
import stat
from pathlib import Path

from cg_studio._bundled import CODEGEN_VERSION

#: ``platform.system()`` -> (directory under ``bin/``, executable name).
#:
#: Keyed on the operating system alone, deliberately not on
#: ``platform.machine()`` as well. Both Windows on ARM and macOS under Rosetta
#: report an architecture that does not match the binary yet run it perfectly
#: well, so an architecture check here would refuse to launch a CODEGEN that
#: works. The genuinely unsupported cases -- aarch64 Linux, an Intel Mac --
#: surface instead as an ``OSError`` from the exec itself, which ``app.py``
#: turns into a message naming the architecture.
_PLATFORM_BINARIES = {
    "Linux": ("lin", "CODEGEN"),
    "Windows": ("win", "CODEGEN.exe"),
    "Darwin": ("mac", "CODEGEN"),
}

_BIN_DIR = Path(__file__).resolve().parent / "bin"


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
    "host": "127.0.0.1",
    "port": 8765,
}

#: Keys dropped from an existing config.json on load. ``codegen_path`` was the
#: setting that let a user point at their own CODEGEN, which existed only
#: because no CODEGEN was shipped: the wheel now carries all three platforms
#: and there is exactly one executable to run. Removed rather than ignored in
#: place, so an upgraded installation does not keep displaying a path that no
#: longer decides anything.
_RETIRED_KEYS = ("codegen_path",)


def load_config(config_path: Path | None = None) -> dict:
    """Load config from *config_path* (default: platform config dir).

    Creates the file with defaults if it does not exist, and drops any retired
    key an older version wrote.
    """
    if config_path is None:
        config_path = config_dir() / "config.json"

    if config_path.exists():
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        if any(key in cfg for key in _RETIRED_KEYS):
            for key in _RETIRED_KEYS:
                cfg.pop(key, None)
            save_config(cfg, config_path)
        return cfg

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


def codegen_version() -> str:
    """Return the CODEGEN release tag bundled in this package, e.g. ``v5.3``."""
    return CODEGEN_VERSION


def resolve_codegen() -> Path | None:
    """Return the bundled CODEGEN executable for this platform, or ``None``.

    ``None`` means this operating system has no bundled build at all, which is
    a different thing from a bundled build that will not run here: see
    :data:`_PLATFORM_BINARIES`.
    """
    entry = _PLATFORM_BINARIES.get(platform.system())
    if entry is None:
        return None

    subdir, name = entry
    binary = _BIN_DIR / subdir / name
    if not binary.is_file():
        return None

    # A backstop, not the mechanism: tools/update_codegen.sh installs the
    # executables 755 and pip restores the mode bit from the wheel. It costs a
    # stat and covers the ways a file can reach an installation without it --
    # an unzip by hand, a copy across a filesystem that drops modes, an
    # installer that normalises permissions.
    mode = binary.stat().st_mode
    if not mode & stat.S_IXUSR:
        try:
            binary.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            # A read-only site-packages is not a reason to claim there is no
            # CODEGEN; the exec below may still succeed, and if it does not the
            # caller reports the real error.
            pass

    return binary
