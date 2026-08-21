"""tests/test_config.py — config module unit tests."""

import json
import platform
from pathlib import Path
from unittest.mock import patch

from cg_studio.config import (
    codegen_version,
    config_dir,
    default_workspace,
    load_config,
    resolve_codegen,
    save_config,
)


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
        assert cfg["host"] == "127.0.0.1"
        assert cfg["port"] == 8765
        assert "workspace_dir" in cfg
        assert "codegen_path" not in cfg

    def test_reads_existing_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "workspace_dir": "/tmp/ws",
            "host": "0.0.0.0",
            "port": 9000,
        }))
        cfg = load_config(config_path=config_file)
        assert cfg["host"] == "0.0.0.0"
        assert cfg["port"] == 9000

    def test_drops_the_retired_codegen_path(self, tmp_path):
        """An install predating the bundled executables must upgrade cleanly.

        The stale key decides nothing once CODEGEN ships in the wheel, and a
        setting still sitting in config.json reads as though it does.
        """
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "codegen_path": "/usr/local/bin/codegen",
            "workspace_dir": "/tmp/ws",
            "host": "0.0.0.0",
            "port": 9000,
        }))
        cfg = load_config(config_path=config_file)
        assert "codegen_path" not in cfg
        assert cfg["port"] == 9000
        # Rewritten, not merely filtered on the way past.
        assert "codegen_path" not in json.loads(config_file.read_text())


class TestSaveConfig:

    def test_writes_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        save_config({"host": "127.0.0.1",
                      "port": 8765, "workspace_dir": str(tmp_path)},
                     config_path=config_file)
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["port"] == 8765


class TestResolveCodegen:
    """The bundled executable is the only CODEGEN there is.

    resolve_codegen() takes no argument on purpose: the "Codegen binary path"
    setting is gone, so there is nothing for a caller to pass and no way for a
    stale config to point the editor at something else.
    """

    def test_takes_no_argument(self):
        import inspect
        assert list(inspect.signature(resolve_codegen).parameters) == []

    def test_finds_the_bundled_binary_for_this_platform(self):
        result = resolve_codegen()
        assert result is not None, (
            "no bundled CODEGEN for %s; run tools/update_codegen.sh"
            % platform.system()
        )
        assert result.is_file()

    def test_the_bundled_binary_is_executable(self):
        """The one payload in the wheel that gets exec'd.

        A wheel carries the mode bit and pip restores it, but nothing else in
        the package would notice its loss: the failure surfaces only when a
        user presses Run Codegen.
        """
        import os
        assert os.access(resolve_codegen(), os.X_OK)

    @patch("platform.system", return_value="SunOS")
    def test_unsupported_platform_returns_none(self, _mock):
        assert resolve_codegen() is None

    def test_every_platform_has_a_binary_bundled(self):
        """All three, not just the one this test happens to run on.

        A wheel is built once and installed everywhere, so a missing Windows
        executable is invisible to a Linux CI run and reaches users instead.
        """
        from cg_studio.config import _BIN_DIR, _PLATFORM_BINARIES
        for subdir, name in _PLATFORM_BINARIES.values():
            assert (_BIN_DIR / subdir / name).is_file(), \
                "missing bundled CODEGEN: bin/%s/%s" % (subdir, name)


class TestCodegenVersion:

    def test_reports_the_bundled_tag(self):
        version = codegen_version()
        assert version.startswith("v")

    def test_the_package_version_names_the_bundled_codegen(self):
        """The rule tools/bump_version.sh exists to keep.

        __version__ is <codegen X.Y>.<counter>, so the leading pair always
        names the generator in bin/. If these drift, a user reading the wheel
        version is told the wrong thing about what it runs.
        """
        import cg_studio
        base = ".".join(codegen_version().lstrip("v").split(".")[:2])
        assert cg_studio.__version__.startswith(base + "."), (
            "__version__ %s does not name the bundled CODEGEN %s"
            % (cg_studio.__version__, codegen_version())
        )
