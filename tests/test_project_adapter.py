"""
test_project_adapter.py — run the JS project_adapter module under Node against
the real backend parser output, so we can verify the DSL-load path without
needing a real browser (which in restricted sandboxes can't reach the Drawflow
CDN).

Skips cleanly if `node` is not on PATH.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cg_studio.dsl_parser import parse_dsl

ROOT = Path(__file__).resolve().parent.parent
ADAPTER_JS = ROOT / "src" / "cg_studio" / "frontend" / "js" / "project_adapter.js"
BLOCKS_JSON = ROOT / "src" / "cg_studio" / "frontend" / "blocks.json"
EXAMPLES = ROOT / "examples"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node.js not on PATH"
)


def _run_adapter(parsed: dict, opts: dict | None = None) -> dict:
    """Load project_adapter.js in Node and invoke parsedToFrontend()."""
    blocks = json.loads(BLOCKS_JSON.read_text(encoding="utf-8"))
    script = (
        "const adapter = require(%r);"
        "const parsed  = JSON.parse(process.argv[1]);"
        "const blocks  = JSON.parse(process.argv[2]);"
        "const opts    = JSON.parse(process.argv[3]);"
        "process.stdout.write(JSON.stringify(adapter.parsedToFrontend(parsed, blocks, opts)));"
    ) % str(ADAPTER_JS)
    res = subprocess.run(
        ["node", "-e", script,
         json.dumps(parsed), json.dumps(blocks), json.dumps(opts or {})],
        capture_output=True, text=True, timeout=20,
    )
    assert res.returncode == 0, f"node failed: {res.stderr}"
    return json.loads(res.stdout)


def test_exc_example_converts_to_frontend_shape():
    """ENTSOE_simp_exc.txt → 9 models, pss/avr chain wired, states & observables mapped."""
    text = (EXAMPLES / "ENTSOE_simp_exc.txt").read_text(encoding="utf-8")
    parsed = parse_dsl(text)
    proj = _run_adapter(parsed)

    assert proj["model_type"] == "exc"
    assert proj["model_name"] == "ENTSOE_simp"
    assert len(proj["models"]) == 9
    assert len(proj["states"]) == 8
    assert len(proj["observables"]) == 3
    # Observables come back as objects keyed by `name`
    assert all(isinstance(o, dict) and "name" in o for o in proj["observables"])
    # States use `init` (forms.js expects this) — not `initExpr`
    assert all("init" in s for s in proj["states"])

    # IDs are stringified at the adapter boundary so they compare equal to
    # the DOM's el.dataset.storeId (which is always a string).
    # PSS chain (2→3→4→5→6) + AVR chain (8→9) = 5 wires
    ids = {m["id"] for m in proj["models"]}
    assert ids == {"1", "2", "3", "4", "5", "6", "7", "8", "9"}
    edges = {(w["from_node"], w["to_node"]) for w in proj["wires"]}
    assert {("2", "3"), ("3", "4"), ("4", "5"), ("5", "6"), ("8", "9")}.issubset(edges), edges

    # All models carry block-catalogue metadata (label, color, inputs/outputs)
    for m in proj["models"]:
        assert m["block_type"]
        assert "label" in m and "color" in m
        assert "pos" in m  # Sugiyama trigger

    # tf1p1z (id=8) reads `avr1` as input. Since no regular block produces
    # avr1, the algeq whose expression references [avr1] is promoted to be
    # its producer and a wire is synthesized — so inputs[0] is now None,
    # and exactly one wire carries signal_name='avr1' into tf1p1z.
    tf = next(m for m in proj["models"] if m["id"] == "8")
    assert tf["inputs"] == [None]
    assert any(
        w["to_node"] == "8" and w["signal_name"] == "avr1"
        for w in proj["wires"]
    ), proj["wires"]


def test_tor_example_converts_to_frontend_shape():
    text = (EXAMPLES / "ENTSOE_simp_tor.txt").read_text(encoding="utf-8")
    parsed = parse_dsl(text)
    proj = _run_adapter(parsed)

    assert proj["model_type"] == "tor"
    assert len(proj["models"]) == 4
    # tf1plim (id=2) feeds tf1p1z (id=3) — IDs are stringified
    edges = {(w["from_node"], w["to_node"]) for w in proj["wires"]}
    assert ("2", "3") in edges


def test_algeq_gets_one_input_per_state_ref_and_wires():
    """algeq expression `[omega]-1.-[domega]` should yield 2 input slots on
    the algeq model, and a wire should be synthesized from any upstream block
    whose outputState matches one of those states ([domega] <- tfder1p)."""
    parsed = {
        "modelType": "exc",
        "modelName": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "blocks": [
            {"id": 1, "blockType": "tfder1p",
             "comment": "", "args": {},
             "inputStates": ["[omega]"], "outputState": "domega",
             "rawArgLines": []},
            {"id": 2, "blockType": "algeq",
             "comment": "", "args": {"expr": "[omega]-1.-[domega]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": ["[omega]-1.-[domega]"]},
        ],
        "errors": [],
    }
    proj = _run_adapter(parsed)
    algeq = next(m for m in proj["models"] if m["block_type"] == "algeq")
    # Two connector slots, one per [state].
    assert len(algeq["inputs"]) == 2, algeq["inputs"]
    # algeq has no output signal.
    assert algeq["outputs"] == []
    # Unwired state stays as bracketed literal on the connector.
    assert "[omega]" in algeq["inputs"]
    # Wired state becomes null; a wire carries the signal_name = "domega".
    assert None in algeq["inputs"]
    tfder = next(m for m in proj["models"] if m["block_type"] == "tfder1p")
    assert any(
        w["from_node"] == tfder["id"] and w["to_node"] == algeq["id"]
        and w["signal_name"] == "domega"
        for w in proj["wires"]
    ), proj["wires"]


def test_algeq_promotes_to_producer_for_states_no_one_else_produces():
    """When a state is referenced in an algeq's expression AND consumed by
    another block, but NO block explicitly produces it, the algeq should be
    promoted to producer: it gets an output port for that state and a wire
    is synthesized to the consumer. (User's exc_AC1A scenario: Vc1 in algeq
    wiring to tf1p's Vc1 input; VRminusVFE in algeq wiring to inlim.)"""
    parsed = {
        "modelType": "exc",
        "modelName": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "blocks": [
            {"id": 1, "blockType": "algeq",
             "comment": "", "args": {"expr": "[Vc1]-[v]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": ["[Vc1]-[v]"]},
            {"id": 2, "blockType": "tf1p",
             "comment": "", "args": {"K": "1.", "T": "{TR}"},
             "inputStates": ["Vc1"], "outputState": "Vc",
             "rawArgLines": []},
            {"id": 3, "blockType": "algeq",
             "comment": "", "args": {"expr": "[VRminusVFE]-[VR]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": ["[VRminusVFE]-[VR]"]},
            {"id": 4, "blockType": "inlim",
             "comment": "", "args": {"T": "{TE}", "lo": "0", "hi": "9999"},
             "inputStates": ["VRminusVFE"], "outputState": "VE",
             "rawArgLines": []},
        ],
        "errors": [],
    }
    proj = _run_adapter(parsed)
    algeq_vc1 = next(m for m in proj["models"] if m["id"] == "1")
    algeq_vr  = next(m for m in proj["models"] if m["id"] == "3")
    assert "Vc1"         in algeq_vc1["outputs"], algeq_vc1
    assert "VRminusVFE"  in algeq_vr["outputs"],  algeq_vr

    # Wires: algeq #1 -> tf1p #2 carrying Vc1; algeq #3 -> inlim #4 carrying
    # VRminusVFE. And tf1p's Vc1 input slot is now null (wired, not literal).
    tf1p  = next(m for m in proj["models"] if m["id"] == "2")
    inlim = next(m for m in proj["models"] if m["id"] == "4")
    assert tf1p["inputs"]  == [None], tf1p
    assert inlim["inputs"] == [None], inlim
    assert any(
        w["from_node"] == "1" and w["to_node"] == "2"
        and w["signal_name"] == "Vc1" for w in proj["wires"]
    ), proj["wires"]
    assert any(
        w["from_node"] == "3" and w["to_node"] == "4"
        and w["signal_name"] == "VRminusVFE" for w in proj["wires"]
    ), proj["wires"]


def test_algeq_wires_earlier_consumers_to_a_later_producer():
    """Regression: when a shared state (e.g. [Id] in HVDC_LCC) is promoted
    to be the output of algeq #9, every EARLIER algeq that references [Id]
    must also get a wire from that producer. Previously the adapter ran a
    single-pass classification so earlier algeqs saw "[Id]" as a literal at
    the time they were processed and never got rewired."""
    parsed = {
        "modelType": "twop",
        "modelName": "hvdc",
        "data": [], "parameters": [], "states": [], "observables": [],
        "blocks": [
            # Earlier algeqs all consume [Id]. Each picks its own output state
            # (A, B, C respectively) so Id is NOT what they promote.
            {"id": 1, "blockType": "algeq",
             "comment": "", "args": {"expr": "[A]-[Id]*2"},
             "inputStates": [], "outputState": "",
             "rawArgLines": ["[A]-[Id]*2"]},
            {"id": 2, "blockType": "algeq",
             "comment": "", "args": {"expr": "[B]+[Id]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": ["[B]+[Id]"]},
            {"id": 3, "blockType": "algeq",
             "comment": "", "args": {"expr": "[C]*[Id]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": ["[C]*[Id]"]},
            # The last algeq is the one semantically defining Id.
            {"id": 4, "blockType": "algeq",
             "comment": "", "args": {"expr": "[A]-[B]-{K}*[Id]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": ["[A]-[B]-{K}*[Id]"]},
        ],
        "errors": [],
    }
    proj = _run_adapter(parsed)
    # Exactly one algeq ends up owning Id. Who owns it depends on the
    # adapter's ordering choice — the invariant we care about is that EVERY
    # OTHER algeq that references [Id] has a wire from that owner. Before
    # the two-phase fix, earlier algeqs were frozen with "[Id]" as a literal
    # before the owner was picked.
    owners = [m["id"] for m in proj["models"] if "Id" in m["outputs"]]
    assert len(owners) == 1, owners
    owner = owners[0]
    algeqs_with_Id = [
        m for m in proj["models"]
        if m["block_type"] == "algeq" and "[Id]" in (m["args"] or {}).get("expr", "")
    ]
    assert len(algeqs_with_Id) == 4
    for m in algeqs_with_Id:
        if m["id"] == owner:
            continue
        wires = [
            w for w in proj["wires"]
            if w["from_node"] == owner and w["to_node"] == m["id"]
            and w["signal_name"] == "Id"
        ]
        assert len(wires) == 1, (m["id"], proj["wires"])


def test_algeq_output_pick_prefers_state_with_fewest_peers():
    """HVDC regression: algeq whose expression is the `mu rectifier` equation
    references [alpha] (shared with many other algeqs) and [mur] (shared
    with only two). The adapter must pick the locally-defined state (mur),
    not the widely-referenced one (alpha), so [mur] gets an output port and
    the consumer algeqs get wired to it."""
    parsed = {
        "modelType": "twop",
        "modelName": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "blocks": [
            # algeq defining mur (our target) — also references alpha and Id.
            {"id": 1, "blockType": "algeq",
             "comment": "", "args": {"expr": "dcos([alpha]+[mur])-[Id]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
            # Three consumers of mur (and alpha, and Id).
            {"id": 2, "blockType": "algeq",
             "comment": "", "args": {"expr": "[vy1]*[mur]*[alpha]*[Id]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
            {"id": 3, "blockType": "algeq",
             "comment": "", "args": {"expr": "[vx1]*[mur]*[alpha]*[Id]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
            # Another algeq referencing alpha/Id (adds to alpha's ref count).
            {"id": 4, "blockType": "algeq",
             "comment": "", "args": {"expr": "[Iord]-[Id]-[alpha]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
        ],
        "errors": [],
    }
    proj = _run_adapter(parsed)
    a1 = next(m for m in proj["models"] if m["id"] == "1")
    # alpha (referenced by 3 other algeqs) should NOT be picked; mur
    # (referenced by only 2 others) is the correct local definition.
    assert a1["outputs"] == ["mur"], a1
    # The inferred output is surfaced on args so the inspector shows it.
    assert a1["args"].get("output_states") == ["mur"], a1["args"]
    # Consumers algeq #2 and #3 get wired to algeq #1 on signal mur.
    for cid in ("2", "3"):
        wires = [w for w in proj["wires"]
                 if w["from_node"] == "1" and w["to_node"] == cid
                 and w["signal_name"] == "mur"]
        assert len(wires) == 1, (cid, proj["wires"])


def test_algeq_inspector_output_states_are_respected_by_adapter():
    """If the project already carries args.output_states (e.g. user edited
    an algeq's outputs in the inspector and saved .cgproj), the adapter
    honours it instead of auto-picking."""
    parsed = {
        "modelType": "twop", "modelName": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "blocks": [
            {"id": 1, "blockType": "algeq",
             "comment": "",
             "args": {"expr": "[a]+[b]+[c]", "output_states": ["b", "c"]},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
            # Consumers of b and c.
            {"id": 2, "blockType": "algeq",
             "comment": "", "args": {"expr": "[b]+[d]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
            {"id": 3, "blockType": "algeq",
             "comment": "", "args": {"expr": "[c]+[d]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
        ],
        "errors": [],
    }
    proj = _run_adapter(parsed)
    a1 = next(m for m in proj["models"] if m["id"] == "1")
    assert a1["outputs"] == ["b", "c"], a1
    # Wires: algeq #1 output_1 (b) -> algeq #2, output_2 (c) -> algeq #3.
    ws = [w for w in proj["wires"] if w["from_node"] == "1"]
    ports = sorted((w["from_port"], w["to_node"], w["signal_name"]) for w in ws)
    assert ("output_1", "2", "b") in ports, ports
    assert ("output_2", "3", "c") in ports, ports


def test_algeq_does_not_promote_reserved_ramses_name_over_user_state():
    """Regression: in exc_AC1A the algeq `{KD}*[if]+(...)*[VE]-[VFE]` uses
    `if` which is a RAMSES-reserved name (field current) that is *not* in
    the palette's input list. The previous heuristic counted `if` as just
    another state with fewer references than VFE, so the algeq was promoted
    to define `if` — leaving VFE floating across two algeqs. Now the
    adapter treats every RAMSES-reserved name (minus mandatory outputs) as
    a literal, so VFE wins and consumers get wired."""
    parsed = {
        "modelType": "exc",
        "modelName": "AC1A",
        "data": [], "parameters": [], "states": [], "observables": [],
        "blocks": [
            # algeq A: references VFE (and VRminusVFE that some later block reads)
            {"id": 1, "blockType": "algeq",
             "comment": "", "args": {"expr": "[VRminusVFE]-[VR]+[VFE]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
            # Consumer that pins VRminusVFE down so it has a non-algeq usage
            {"id": 2, "blockType": "inlim",
             "comment": "", "args": {"T": "{TE}", "lo": "0", "hi": "9999"},
             "inputStates": ["VRminusVFE"], "outputState": "VE",
             "rawArgLines": []},
            # algeq B: this is the one that should promote VFE.
            {"id": 3, "blockType": "algeq",
             "comment": "",
             "args": {"expr": "{KD}*[if]+({KE}+satur([VE],{VE1}))*[VE]-[VFE]"},
             "inputStates": [], "outputState": "",
             "rawArgLines": []},
            # Downstream consumer of VFE as plain input.
            {"id": 4, "blockType": "tfder1p",
             "comment": "", "args": {"K": "{KF}", "T": "{TF}"},
             "inputStates": ["VFE"], "outputState": "VF",
             "rawArgLines": []},
        ],
        "errors": [],
    }
    opts = {
        "ramsesInputs":  {"exc": ["v", "p", "q", "omega"]},
        "ramsesOutputs": {"exc": ["vf"]},
        "ramsesReserved": {"exc": ["v", "p", "q", "omega", "if", "vf"]},
    }
    proj = _run_adapter(parsed, opts)
    alg_b = next(m for m in proj["models"] if m["id"] == "3")
    # algeq B must promote VFE (the real state it defines), NOT `if` (reserved).
    assert alg_b["outputs"] == ["VFE"], alg_b
    # Wire from algeq B's VFE output into algeq A's [VFE] input slot.
    to_A = [w for w in proj["wires"]
            if w["from_node"] == "3" and w["to_node"] == "1"
            and w["signal_name"] == "VFE"]
    assert len(to_A) == 1, proj["wires"]
    # And into tfder1p's VFE input.
    to_tfder = [w for w in proj["wires"]
                if w["from_node"] == "3" and w["to_node"] == "4"
                and w["signal_name"] == "VFE"]
    assert len(to_tfder) == 1, proj["wires"]
    # `if` is NOT promoted anywhere; it stays on algeq B's input as a literal.
    algB_inputs = alg_b["inputs"]
    assert "[if]" in algB_inputs, algB_inputs


def test_ramses_inputs_are_preserved_as_literals():
    """Inputs like [omega] / {KE} have no upstream block; they stay as literal
    strings in models[i].inputs so the emitter can round-trip them."""
    parsed = {
        "modelType": "exc",
        "modelName": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "blocks": [{
            "id": 1, "blockType": "tf1p",
            "comment": "", "args": {"K": "1.", "T": "{TA}"},
            "inputStates": ["[omega]"],
            "outputState": "y",
            "rawArgLines": [],
        }],
        "errors": [],
    }
    proj = _run_adapter(parsed)
    m = proj["models"][0]
    assert m["inputs"] == ["[omega]"]
    assert proj["wires"] == []
