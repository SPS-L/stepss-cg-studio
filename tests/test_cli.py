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
