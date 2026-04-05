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
