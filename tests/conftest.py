"""
conftest.py — shared fixtures for E2E tests.

Starts a uvicorn server in a background thread on port 8799.
"""
import sys
import os
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


@pytest.fixture(scope="session")
def server_url():
    """Start the FastAPI app in a background thread, return the base URL."""
    import uvicorn
    from app import app

    PORT = 8799
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()

    # Wait for server readiness
    import httpx

    for _ in range(80):
        try:
            r = httpx.get(f"http://127.0.0.1:{PORT}/blocks", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    else:
        pytest.fail("Server did not start in time")

    yield f"http://127.0.0.1:{PORT}"
    srv.should_exit = True


@pytest.fixture()
def app_page(server_url, page):
    """Navigate to the app and wait for JS initialisation to complete."""
    page.goto(server_url)
    # Wait for palette items — they're rendered by JS after async init
    page.wait_for_selector("#palette-tree [draggable='true']", timeout=10000)
    # Wait for the main() IIFE to fully complete by checking a late-set attribute
    page.wait_for_function(
        "typeof window.Modal === 'object' && typeof window.Modal.show === 'function'",
        timeout=5000,
    )
    # Small extra settle time for all event listeners to attach
    page.wait_for_timeout(200)
    return page
