"""
test_e2e.py — End-to-end browser tests using Playwright for Python.

Run with:  pytest tests/test_e2e.py -v
Requires:  pip install playwright pytest-playwright && playwright install chromium

Tests are skipped automatically if Playwright browsers are not installed.
"""
import pytest

try:
    from playwright.sync_api import expect  # noqa: F401

    _pw_available = True
except ImportError:
    _pw_available = False

pytestmark = pytest.mark.skipif(not _pw_available, reason="playwright not installed")


# ---------------------------------------------------------------------------
# Basic app loading
# ---------------------------------------------------------------------------


def test_app_loads(app_page):
    """Page loads with topbar, palette, and canvas visible."""
    page = app_page
    expect(page.locator("#topbar")).to_be_visible()
    expect(page.locator("#palette-panel")).to_be_visible()
    expect(page.locator("#drawflow")).to_be_visible()
    expect(page.locator("#dsl-preview-wrap")).to_be_visible()


def test_palette_has_blocks(app_page):
    """Palette renders at least one block item."""
    page = app_page
    items = page.locator("#palette-tree [draggable='true']")
    expect(items.first).to_be_visible()
    assert items.count() > 10  # we have 52 blocks


# ---------------------------------------------------------------------------
# Model type theming
# ---------------------------------------------------------------------------


def test_model_type_default_is_exc(app_page):
    """Default model type is 'exc'."""
    page = app_page
    val = page.locator("#sel-model-type").input_value()
    assert val == "exc"


def test_model_type_change_updates_theme(app_page):
    """Switching model type changes the --accent CSS variable."""
    page = app_page

    themes = {
        "exc": "#3b82f6",
        "tor": "#22c55e",
        "inj": "#f59e0b",
        "twop": "#a855f7",
    }
    for mtype, expected_color in themes.items():
        page.select_option("#sel-model-type", mtype)
        # Ensure the change event fires
        page.evaluate(
            "document.getElementById('sel-model-type').dispatchEvent(new Event('change'))"
        )
        accent = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"
        )
        assert accent == expected_color, f"{mtype}: expected {expected_color}, got {accent}"


# ---------------------------------------------------------------------------
# Palette search
# ---------------------------------------------------------------------------


def test_palette_search_filters(app_page):
    """Typing in the palette search box filters visible blocks."""
    page = app_page
    all_items = page.locator("#palette-tree [draggable='true']")
    total = all_items.count()

    page.fill("#palette-search", "tf1p")
    page.wait_for_timeout(300)  # allow filter to apply
    filtered = page.locator("#palette-tree [draggable='true']:visible")
    filtered_count = filtered.count()
    assert 0 < filtered_count < total

    # Clear search restores all
    page.fill("#palette-search", "")
    page.wait_for_timeout(300)
    restored = page.locator("#palette-tree [draggable='true']")
    assert restored.count() == total


# ---------------------------------------------------------------------------
# Validation overlay
# ---------------------------------------------------------------------------


def test_validation_modal_on_empty_model(app_page):
    """Export DSL on an empty exc model shows the mandatory-outputs warning."""
    page = app_page
    page.select_option("#sel-model-type", "exc")
    page.evaluate(
        "document.getElementById('sel-model-type').dispatchEvent(new Event('change'))"
    )
    page.click("#btn-export-dsl")
    expect(page.locator("#modal-overlay")).not_to_have_class("hidden", timeout=5000)
    expect(page.locator("#modal-title")).to_contain_text("Missing Mandatory Outputs")
    expect(page.locator("#modal-body")).to_contain_text("vf")
    # Dismiss
    page.click("#modal-cancel")
    expect(page.locator("#modal-overlay")).to_have_class("hidden")


def test_validation_export_anyway(app_page):
    """User can click 'Export Anyway' to bypass the validation warning."""
    page = app_page
    page.select_option("#sel-model-type", "tor")
    page.evaluate(
        "document.getElementById('sel-model-type').dispatchEvent(new Event('change'))"
    )

    page.click("#btn-export-dsl")
    expect(page.locator("#modal-overlay")).not_to_have_class("hidden", timeout=5000)
    expect(page.locator("#modal-title")).to_contain_text("Missing Mandatory Outputs")
    # Verify the OK button says "Export Anyway"
    expect(page.locator("#modal-ok")).to_contain_text("Export Anyway")
    # Click through — modal should close (export continues, may or may not download)
    page.click("#modal-ok")
    expect(page.locator("#modal-overlay")).to_have_class("hidden")


# ---------------------------------------------------------------------------
# Canvas status bar
# ---------------------------------------------------------------------------


def test_status_shows_block_count(app_page):
    """Status bar shows block/wire counts on empty model."""
    page = app_page
    status = page.locator("#canvas-status")
    # Status is set by _status() at end of main(); may contain "0 blocks" or be empty
    # if the IIFE hasn't fully finished. Wait for it.
    expect(status).to_contain_text("blocks", timeout=5000)


# ---------------------------------------------------------------------------
# Keyboard shortcuts
# ---------------------------------------------------------------------------


def test_escape_closes_modal(app_page):
    """Pressing Escape dismisses the generic modal."""
    page = app_page
    # Trigger the validation modal
    page.click("#btn-export-dsl")
    expect(page.locator("#modal-overlay")).not_to_have_class("hidden", timeout=5000)
    page.keyboard.press("Escape")
    expect(page.locator("#modal-overlay")).to_have_class("hidden")


# ---------------------------------------------------------------------------
# Settings modal
# ---------------------------------------------------------------------------


def test_settings_modal_opens(app_page):
    """Clicking the settings gear opens the settings overlay."""
    page = app_page
    page.click("#btn-settings")
    expect(page.locator("#settings-overlay")).to_be_visible()
    expect(page.locator("#cfg-codegen-path")).to_be_visible()
    # Close it
    page.click("#settings-cancel")
    expect(page.locator("#settings-overlay")).to_be_hidden()
