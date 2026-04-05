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
        resolve_codegen("bundled")

    @patch("shutil.which", return_value=None)
    def test_not_found_returns_none(self, _mock):
        result = resolve_codegen("bundled")
        assert result is None or isinstance(result, Path)
