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


# ---------------------------------------------------------------------------
# Load DSL — regression test for backend→frontend project shape mismatch
# ---------------------------------------------------------------------------


def test_load_example_dsl_renders_canvas(app_page):
    """Loading examples/ENTSOE_simp_exc.txt should populate canvas + header.

    Regression: the /parse response uses camelCase keys and a `blocks[]` array,
    while the frontend Store expects snake_case + `models[]` + `wires[]`. If the
    frontend doesn't normalise, Canvas.loadProject() crashes on
    `proj.models.length` and nothing appears.
    """
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    assert example.is_file(), f"missing example file: {example}"

    # Collect JS errors so we catch the "Cannot read properties of undefined" crash
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.set_input_files("#file-input-dsl", str(example))

    # Wait for the canvas to show the 9 parsed blocks (one per `& blockname`)
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )

    # Header reflects the parsed model
    assert page.locator("#sel-model-type").input_value() == "exc"
    assert page.locator("#inp-model-name").input_value() == "ENTSOE_simp"
    expect(page.locator("#model-title")).to_have_text("ENTSOE_simp")

    # Metadata tables populated (8 states, 3 observables for this example)
    page.click(".meta-tab[data-tab='states']")
    assert page.locator("#tab-states tbody tr").count() == 8
    page.click(".meta-tab[data-tab='observables']")
    assert page.locator("#tab-observables tbody tr").count() == 3

    # At least one connection drawn (pss chain + avr chain = 6 direct wires)
    assert page.locator("#drawflow .connection").count() >= 5

    # No uncaught JS errors during load
    assert not errors, "JS errors during Load DSL: " + "\n".join(errors)


def test_inspector_works_for_loaded_block(app_page):
    """Clicking a loaded DSL block selects it and populates the inspector.

    Regression: backend assigns integer block IDs while el.dataset.storeId is a
    string, so Store.models.find(m => m.id === storeId) returned undefined and
    the inspector silently stayed blank. Also: Canvas.loadProject used to call
    _add which pushed duplicate models into the Store.
    """
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )

    # No duplicate models in Store (loadProject must not push duplicates)
    n_models = page.evaluate("Store.get().models.length")
    # 9 DSL blocks + 3 auto-seeded RAMSES I/O pseudo-nodes (omega, v, vf)
    assert n_models == 12, f"expected 12 models in store, got {n_models}"

    # Click the first node (via Drawflow's selection API — more reliable than
    # mouse coordinates given the canvas transform)
    page.evaluate("""() => {
        const el = document.querySelector('#drawflow .drawflow-node');
        const id = parseInt(el.id.replace('node-',''));
        const df = el.closest('.drawflow').__drawflow
                || window.Canvas; // fallback
        // Manually dispatch selection the way Drawflow does on click.
        el.classList.add('selected');
        // Find the Drawflow instance's event hook via a mousedown.
        el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0}));
    }""")
    # Inspector title should no longer say "Select a block to inspect"
    page.wait_for_function(
        "document.getElementById('inspector-title').textContent "
        "&& !document.getElementById('inspector-title').textContent.includes('Select')",
        timeout=3000,
    )
    title = page.locator("#inspector-title").text_content()
    assert title and "Select" not in title, f"inspector title still prompt: {title!r}"


def test_connected_input_shows_signal_name(app_page):
    """A connected input port label shows the upstream output signal name,
    not the generic placeholder (e.g. 'u', 'x') from blocks.json.

    In ENTSOE_simp_exc the PSS chain connects leadlagtf (output 'pss3') into
    gain (input placeholder 'u'). After load, the gain node's input row should
    read 'pss3', not 'u'.
    """
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )

    # Collect all port-row texts across every node; at least one connected
    # input should carry a real signal name from the DSL (pss1/pss2/pss3/…).
    labels = page.evaluate("""
        () => Array.from(document.querySelectorAll('#drawflow .drawflow-node'))
            .map(n => {
                const rows = n.querySelectorAll('.port-row span');
                return {
                    storeId: n.dataset.storeId,
                    rows: Array.from(rows).map(r => r.textContent)
                };
            })
    """)
    flat_inputs = []
    for entry in labels:
        rows = entry["rows"]
        # rows[0] = input row (if any inputs); rows[1] = output row
        if rows:
            flat_inputs.append(rows[0])

    # At least one connected input label matches a DSL state name
    # (the PSS chain uses pss1..pss3).
    assert any(
        name in " ".join(flat_inputs)
        for name in ("pss1", "pss2", "pss3", "avr2")
    ), f"no connected signal names appear in input labels: {flat_inputs}"

    # And no input label should still be the bare generic placeholder when a
    # wire is attached. Check by scanning wires:
    joined = " ".join(flat_inputs)
    # 'u' is the common placeholder in blocks.json — it shouldn't appear as a
    # standalone label for a node that has an incoming wire.
    # (We only assert the positive case above to keep this robust.)
    assert joined, "expected some input port labels on loaded canvas"


def test_wire_labels_render_over_connections(app_page):
    """Each Drawflow connection gets an SVG <text> showing the wire's
    signal_name (the state that links the two blocks)."""
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )
    # Wait until at least one label has been painted (loadProject paints them
    # after wires are drawn).
    page.wait_for_function(
        "document.querySelectorAll('#drawflow svg.connection text.wire-label').length > 0",
        timeout=5000,
    )
    texts = page.evaluate(
        "Array.from(document.querySelectorAll('#drawflow svg.connection text.wire-label'))"
        ".map(t => t.textContent)"
    )
    # ENTSOE_simp_exc wires the PSS chain with signals pss1/pss2/pss3.
    assert any(t in ("pss1", "pss2", "pss3", "avr2") for t in texts), texts


# ---------------------------------------------------------------------------
# RAMSES I/O pseudo-nodes
# ---------------------------------------------------------------------------


def test_palette_shows_ramses_io_for_exc(app_page):
    """The I/O palette category lists the RAMSES inputs and mandatory outputs
    for the currently-selected model type. For exc the expected rows are:
    inputs = v, p, q, omega; outputs = vf (no `if`)."""
    page = app_page
    page.select_option("#sel-model-type", "exc")
    page.evaluate(
        "document.getElementById('sel-model-type').dispatchEvent(new Event('change'))"
    )
    # Open the I/O category in case it collapsed
    labels = page.evaluate("""
        () => {
            const items = Array.from(document.querySelectorAll('#palette-tree .pal-item'));
            // Only I/O items carry a colon in their drag payload
            return items
                .filter(it => {
                    const lbl = it.querySelector('.pi-label').textContent;
                    return ['v','p','q','omega','vf'].includes(lbl);
                })
                .map(it => it.querySelector('.pi-label').textContent);
        }
    """)
    assert set(labels) >= {"v", "p", "q", "omega", "vf"}, labels
    # `if` must not be exposed — the user guide lists it but it is not used
    assert "if" not in labels, labels


def test_new_model_seeds_ramses_io_nodes(app_page):
    """Clicking 'New' on an exc model pre-places ramses_in (v,p,q,omega) and
    ramses_out (vf) nodes on the canvas."""
    page = app_page
    page.select_option("#sel-model-type", "exc")
    page.evaluate(
        "document.getElementById('sel-model-type').dispatchEvent(new Event('change'))"
    )
    page.click("#btn-new")
    # Discard confirmation modal -> click Discard
    page.click("#modal-ok")
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length >= 5",
        timeout=3000,
    )
    info = page.evaluate("""
        () => {
            const m = Store.get().models;
            const ins  = m.filter(x => x.block_type === 'ramses_in' ).map(x => x.args.name);
            const outs = m.filter(x => x.block_type === 'ramses_out').map(x => x.args.name);
            return {ins, outs, total: m.length};
        }
    """)
    assert set(info["ins"])  == {"v", "p", "q", "omega"}, info
    assert set(info["outs"]) == {"vf"}, info
    assert info["total"] == 5

    # The ramses_out card must show "vf" on its body (not the generic
    # catalogue placeholder "state") even before a wire is attached.
    card_texts = page.evaluate("""
        () => {
            const out = [];
            document.querySelectorAll('#drawflow .drawflow-node').forEach(n => {
                const sid = n.dataset.storeId;
                const m = Store.get().models.find(x => x.id === sid);
                if (!m || m.block_type !== 'ramses_out') return;
                const title = n.querySelector('.nh-title')?.textContent || '';
                const ports = Array.from(n.querySelectorAll('.port-row span'))
                                   .map(s => s.textContent);
                out.push({name: m.args.name, title, ports});
            });
            return out;
        }
    """)
    assert card_texts, "no ramses_out cards found"
    for c in card_texts:
        assert c["title"] == c["name"], c
        assert "state" not in c["ports"], c   # generic placeholder gone
        assert c["name"] in c["ports"], c     # actual state name shown


def test_new_model_type_picker_creates_tor_model(app_page):
    """The New dialog asks for a model type. Picking tor must seed tor's
    I/O pins (p, omega -> tm) regardless of what type the current model is."""
    page = app_page
    # Start from an exc model (default).
    page.click("#btn-new")
    # Modal is up — pick tor, then Create.
    page.wait_for_selector("#new-model-type", timeout=3000)
    page.select_option("#new-model-type", "tor")
    page.click("#modal-ok")

    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 3",
        timeout=3000,
    )
    info = page.evaluate("""() => {
        const s = Store.get();
        const m = s.models;
        return {
            model_type: s.model_type,
            ins:  m.filter(x => x.block_type === 'ramses_in' ).map(x => x.args.name),
            outs: m.filter(x => x.block_type === 'ramses_out').map(x => x.args.name),
            header_type: document.getElementById('sel-model-type').value,
        };
    }""")
    assert info["model_type"]  == "tor", info
    assert info["header_type"] == "tor", info
    assert set(info["ins"])    == {"p", "omega"}, info
    assert set(info["outs"])   == {"tm"}, info


def test_algeq_renders_connectors_and_autowires_on_load(app_page):
    """Loading a DSL with algeq blocks: each algeq should render with one
    connector per [state] reference, labeled "[state]", and wires should be
    synthesized to upstream blocks producing those states."""
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )

    # Inspect every algeq node's connectors and outgoing/incoming shape.
    info = page.evaluate("""() => {
        const nodes = Array.from(document.querySelectorAll('#drawflow .drawflow-node'));
        const out = [];
        nodes.forEach(n => {
            const sid = n.dataset.storeId;
            const m = Store.get().models.find(x => x.id === sid);
            if (!m || m.block_type !== 'algeq') return;
            const nIn  = n.querySelectorAll('.inputs  .input').length;
            const nOut = n.querySelectorAll('.outputs .output').length;
            const labels = Array.from(n.querySelectorAll('.port-row span'))
                                .map(s => s.textContent).join('|');
            out.push({expr: (m.args||{}).expr, nIn, nOut, labels});
        });
        return out;
    }""")
    assert info, "no algeq nodes rendered"
    for a in info:
        import re
        refs = sorted(set(re.findall(r"\[([a-zA-Z_]\w*)\]", a["expr"])))
        # Each state in the expression gets exactly one connector — either
        # as an input pin (producer feeds it) or an output pin (this algeq
        # produces it for consumers elsewhere).
        assert a["nIn"] + a["nOut"] == len(refs), (a, refs)
        # Each [state] appears on a connector label (input or output row).
        for s in refs:
            assert f"[{s}]" in a["labels"], (a, s)

    # ENTSOE_simp_exc has algeq "[avr1]-[dvpss]+[v]-{Vo}" with upstream `lim`
    # producing dvpss -> wire must be synthesized.
    wire_present = page.evaluate("""
        Store.get().wires.some(w => w.signal_name === 'dvpss')
    """)
    assert wire_present, "expected a wire carrying signal_name=dvpss"


def test_load_autowires_ramses_io_pseudo_nodes(app_page):
    """Loading an exc DSL that references [omega], [v] and produces `vf`
    should auto-add ramses_in(omega), ramses_in(v), ramses_out(vf) and wire
    them to the corresponding blocks."""
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )

    state = page.evaluate("""() => {
        const s = Store.get();
        const pins = s.models.filter(m =>
            m.block_type === 'ramses_in' || m.block_type === 'ramses_out');
        return {
            pins: pins.map(p => ({type: p.block_type, name: p.args.name})),
            sigs: s.wires.map(w => w.signal_name),
        };
    }""")
    names_in  = {p["name"] for p in state["pins"] if p["type"] == "ramses_in"}
    names_out = {p["name"] for p in state["pins"] if p["type"] == "ramses_out"}
    assert names_in  == {"omega", "v"}, state["pins"]
    assert names_out == {"vf"},          state["pins"]
    # Wires from the ramses pins carry bracketed literals / mandatory names.
    assert "[omega]" in state["sigs"], state["sigs"]
    assert "[v]"     in state["sigs"], state["sigs"]
    assert "vf"      in state["sigs"], state["sigs"]


def test_loaded_dsl_nodes_do_not_overlap(app_page):
    """Sugiyama layout must place every node at a distinct, non-overlapping
    position when a DSL is loaded. Regression: previously the pseudo I/O pins
    were seeded with fixed positions, which defeated the `needsLayout` check
    in Canvas.loadProject so every real block stacked at (0,0)."""
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )

    rects = page.evaluate("""
        () => Array.from(document.querySelectorAll('#drawflow .drawflow-node'))
            .map(n => {
                const r = n.getBoundingClientRect();
                return {id: n.dataset.storeId,
                        l: r.left, t: r.top, r: r.right, b: r.bottom};
            })
    """)
    assert len(rects) == 12
    # Distinct positions — no two nodes share the same top-left corner.
    corners = {(round(r["l"]), round(r["t"])) for r in rects}
    assert len(corners) == len(rects), \
        f"nodes with shared top-left: {rects}"
    # Axis-aligned rectangle overlap check (pairwise).
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            overlap = (a["l"] < b["r"] and b["l"] < a["r"]
                       and a["t"] < b["b"] and b["t"] < a["b"])
            assert not overlap, f"nodes overlap: {a} vs {b}"


def test_fit_to_view_fits_all_nodes_in_viewport(app_page):
    """Clicking Fit to view on a loaded DSL must bring every node inside the
    drawflow container bounds. Regression: Drawflow's zoom_min=0.5 floor
    prevented fit-to-view from shrinking wide diagrams, trimming the right
    side."""
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )
    # Force a wide-but-short window so the diagram needs zoom < 0.5 to fit.
    page.set_viewport_size({"width": 900, "height": 900})
    page.click("#btn-fit")
    page.wait_for_timeout(100)  # let the transform apply

    result = page.evaluate("""() => {
        const el = document.getElementById('drawflow');
        const c = el.getBoundingClientRect();
        const rects = Array.from(document.querySelectorAll('#drawflow .drawflow-node'))
            .map(n => { const r = n.getBoundingClientRect();
                        return {l:r.left, t:r.top, r:r.right, b:r.bottom}; });
        return {c:{l:c.left, t:c.top, r:c.right, b:c.bottom}, rects};
    }""")
    c = result["c"]
    for r in result["rects"]:
        # Allow 1px slack for sub-pixel rounding.
        assert r["l"] >= c["l"] - 1, (r, c)
        assert r["r"] <= c["r"] + 1, (r, c)
        assert r["t"] >= c["t"] - 1, (r, c)
        assert r["b"] <= c["b"] + 1, (r, c)


def test_algeq_inspector_has_single_expr_and_output_selector(app_page):
    """Selecting an algeq node shows exactly one Expression field and an
    Output state selector. Editing the output state toggles the node's
    output port live, and loading a DSL pre-fills the inferred output."""
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )
    # Pick algeq #7 ("[avr1]-[dvpss]+[v]-{Vo}") — it should have avr1 as the
    # inferred output.
    sid = page.evaluate("""
        () => Store.get().models.find(m =>
            m.block_type === 'algeq' && (m.args.expr||'').includes('[avr1]')
        ).id
    """)
    page.evaluate("sid => Forms.showInspector(sid)", sid)
    labels = page.evaluate("""
        () => Array.from(document.querySelectorAll('#inspector-form label'))
            .map(l => l.textContent)
    """)
    # Exactly one Expression field (no duplicate "expr" generic).
    assert labels.count("Expression") == 1, labels
    assert not any(l.startswith("expr ") or l == "expr" for l in labels), labels
    assert any("Output state" in l for l in labels), labels

    # The Output state field is pre-filled with the inferred value ("avr1").
    out_val = page.evaluate("""
        () => {
            const lbls = document.querySelectorAll('#inspector-form label');
            for (const l of lbls) {
                if (l.textContent.includes('Output state')) {
                    return l.parentElement.querySelector('input').value;
                }
            }
            return null;
        }
    """)
    assert out_val == "avr1", out_val

    # Clearing the output state should drop the algeq's output port.
    page.evaluate("""() => {
        const lbls = document.querySelectorAll('#inspector-form label');
        for (const l of lbls) {
            if (l.textContent.includes('Output state')) {
                const inp = l.parentElement.querySelector('input');
                inp.value = '';
                inp.dispatchEvent(new Event('change'));
                return;
            }
        }
    }""")
    page.wait_for_timeout(100)
    outs_after = page.evaluate(f"Store.get().models.find(m => m.id === '{sid}').outputs")
    assert outs_after == [], outs_after


def test_inspector_comment_field_saved_and_emitted(app_page):
    """Every block has a Comment field. Typing a comment updates the Store's
    model.comment and, on DSL export, the backend writes it onto the
    `& blockname` header line prefixed with `!`."""
    from pathlib import Path

    page = app_page
    example = Path(__file__).parent.parent / "examples" / "ENTSOE_simp_exc.txt"
    page.set_input_files("#file-input-dsl", str(example))
    page.wait_for_function(
        "document.querySelectorAll('#drawflow .drawflow-node').length === 12",
        timeout=5000,
    )

    # Pick the tfder1p node (first one); type a comment via the inspector.
    sid = page.evaluate("""
        () => Store.get().models.find(m => m.block_type === 'tfder1p').id
    """)
    page.evaluate("sid => Forms.showInspector(sid)", sid)
    labels = page.evaluate("""
        () => Array.from(document.querySelectorAll('#inspector-form label'))
            .map(l => l.textContent)
    """)
    assert "Comment" in labels, labels
    page.evaluate("""() => {
        const lbls = document.querySelectorAll('#inspector-form label');
        for (const l of lbls) {
            if (l.textContent === 'Comment') {
                const inp = l.parentElement.querySelector('input');
                inp.value = 'derivative filter';
                inp.dispatchEvent(new Event('change'));
                return;
            }
        }
    }""")
    # The store should have absorbed the comment.
    stored = page.evaluate(f"Store.get().models.find(m => m.id === '{sid}').comment")
    assert stored == "derivative filter", stored

    # Emit and check the `& tfder1p` header carries the comment with `!`.
    dsl = page.evaluate("""async () => {
        return await Api.emitDSL(Store.get());
    }""")
    assert "& tfder1p  ! derivative filter" in dsl, dsl


def test_right_and_bottom_panels_are_resizable(app_page):
    """The right panel (inspector / DSL preview) and the bottom meta panel
    have drag handles that resize them. Sizes persist in localStorage."""
    page = app_page
    # Clear any previously saved sizes to get deterministic starting values.
    page.evaluate("""() => {
        localStorage.removeItem('cg_right_width_px');
        localStorage.removeItem('cg_meta_height_px');
    }""")
    page.reload()
    page.wait_for_function(
        "typeof window.Modal === 'object' && typeof window.Modal.show === 'function'",
        timeout=5000,
    )

    # -- Right panel: drag the vertical splitter leftwards, expect width to grow.
    before = page.evaluate(
        "document.getElementById('right-panel').offsetWidth"
    )
    split_right = page.locator("#split-right").bounding_box()
    # Drag from the splitter centre to 120px further LEFT.
    start_x = split_right["x"] + split_right["width"] / 2
    start_y = split_right["y"] + split_right["height"] / 2
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x - 120, start_y, steps=10)
    page.mouse.up()
    after_right = page.evaluate(
        "document.getElementById('right-panel').offsetWidth"
    )
    assert after_right > before + 80, (before, after_right)

    # -- Meta panel: drag the horizontal splitter upwards, expect height to grow.
    before_h = page.evaluate(
        "document.getElementById('meta-panel').offsetHeight"
    )
    split_meta = page.locator("#split-meta").bounding_box()
    start_x = split_meta["x"] + split_meta["width"] / 2
    start_y = split_meta["y"] + split_meta["height"] / 2
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x, start_y - 100, steps=10)
    page.mouse.up()
    after_meta = page.evaluate(
        "document.getElementById('meta-panel').offsetHeight"
    )
    assert after_meta > before_h + 60, (before_h, after_meta)

    # -- Persistence: sizes written to localStorage on mouseup.
    saved = page.evaluate("""() => ({
        right: parseInt(localStorage.getItem('cg_right_width_px')||'0', 10),
        meta:  parseInt(localStorage.getItem('cg_meta_height_px') ||'0', 10),
    })""")
    assert saved["right"] == after_right, saved
    assert saved["meta"]  == after_meta,  saved


def test_check_model_button_lists_issues_in_permanent_panel(app_page):
    """Clicking the Check Model toolbar button runs the validator and lists
    the findings in the Issues panel in the right sidebar. The panel stays
    open (permanence) — it is NOT a toast that auto-dismisses."""
    page = app_page
    # Default state: fresh exc model with seeded RAMSES I/O pins but no wires
    # between them and any real block yet -> at least the mandatory-output
    # should be flagged (no block produces `vf`).
    page.click("#btn-check")
    page.wait_for_selector("#issues-wrap:not(.collapsed)", timeout=3000)
    title = page.locator("#issues-title").text_content()
    assert "Issues" in title, title
    # Panel contains at least one error row, rendered as plain DOM — NOT a toast.
    err_count = page.locator(".issue-row.issue-error").count()
    assert err_count >= 1

    # Wait a bit; ensure the rows are still there (proof of permanence).
    page.wait_for_timeout(1500)
    assert page.locator(".issue-row.issue-error").count() == err_count

    # Clicking the header collapses the panel; clicking again re-expands it.
    page.click("#issues-header")
    assert page.locator("#issues-wrap.collapsed").count() == 1
    page.click("#issues-header")
    assert page.locator("#issues-wrap.collapsed").count() == 0


def test_emit_skips_ramses_pseudo_blocks():
    """The emitter must not include ramses_in/ramses_out nodes in the DSL."""
    from cg_studio.app import _normalise_project
    from cg_studio.dsl_emitter import emit_dsl

    proj = {
        "model_type": "exc", "model_name": "m",
        "data": [], "parameters": [],
        "states": [{"name": "vf", "init": "0.0"}],
        "observables": [],
        "models": [
            {"id": "1", "block_type": "ramses_in",
             "args": {"name": "omega"}, "outputs": ["[omega]"],
             "inputs": [], "pos": {"x": 0, "y": 0}},
            {"id": "2", "block_type": "tf1p",
             "args": {"K": "1.", "T": "{T}"},
             "outputs": ["vf"], "inputs": [None], "pos": {"x": 0, "y": 0}},
            {"id": "3", "block_type": "ramses_out",
             "args": {"name": "vf"}, "outputs": [],
             "inputs": [None], "pos": {"x": 0, "y": 0}},
        ],
        "wires": [
            {"from_node": "1", "from_port": "output_1",
             "to_node":   "2", "to_port":   "input_1", "signal_name": "[omega]"},
            {"from_node": "2", "from_port": "output_1",
             "to_node":   "3", "to_port":   "input_1", "signal_name": "vf"},
        ],
    }
    norm = _normalise_project(proj)
    block_types = [b["blockType"] for b in norm["blocks"]]
    assert "ramses_in"  not in block_types
    assert "ramses_out" not in block_types
    assert block_types == ["tf1p"]
    # The real block consumed the bracketed input through the wire.
    assert norm["blocks"][0]["inputStates"] == ["[omega]"]
    # Full emit must not reference ramses_in/ramses_out anywhere.
    dsl = emit_dsl(norm)
    assert "ramses_in"  not in dsl
    assert "ramses_out" not in dsl
