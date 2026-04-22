"""
test_validate.py — run the JS validate module under Node to exercise the
floating-state detection that the frontend uses on DSL load + export.

Skipped cleanly if `node` is not on PATH.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VALIDATE_JS = ROOT / "src" / "cg_studio" / "frontend" / "js" / "validate.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node.js not on PATH"
)


def _run_validate(proj: dict) -> list[dict]:
    script = (
        "const v = require(%r);"
        "const proj = JSON.parse(process.argv[1]);"
        "process.stdout.write(JSON.stringify(v.findFloatingStateIssues(proj)));"
    ) % str(VALIDATE_JS)
    res = subprocess.run(
        ["node", "-e", script, json.dumps(proj)],
        capture_output=True, text=True, timeout=10,
    )
    assert res.returncode == 0, f"node failed: {res.stderr}"
    return json.loads(res.stdout)


def test_no_issues_when_everything_is_wired():
    proj = {
        "models": [
            {"id": "1", "block_type": "tfder1p", "outputs": ["domega"],
             "inputs": [None]},
            {"id": "2", "block_type": "tf1p",    "outputs": ["Vc"],
             "inputs": [None]},
        ],
        "wires": [
            {"from_node": "1", "from_port": "output_1",
             "to_node": "2", "to_port": "input_1",
             "signal_name": "domega"},
        ],
    }
    assert _run_validate(proj) == []


def test_flags_floating_literal_when_other_block_produces_the_state():
    # tf1p has Vc1 sitting as a LITERAL input (no wire) while an algeq
    # produces Vc1 as its output — user forgot/deleted the wire.
    proj = {
        "models": [
            {"id": "1", "block_type": "algeq", "outputs": ["Vc1"],
             "inputs": ["[v]"]},
            {"id": "2", "block_type": "tf1p",  "outputs": ["Vc"],
             "inputs": ["Vc1"]},
        ],
        "wires": [],
    }
    issues = _run_validate(proj)
    assert len(issues) == 1
    assert issues[0]["state"]    == "Vc1"
    assert issues[0]["model_id"] == "2"
    assert issues[0]["port"]     == 0
    assert "1" in issues[0]["peers"]


def test_flags_floating_when_two_algeqs_share_a_state_without_wire():
    # Two algeqs both carry "[Id]" on input ports with no wire between them.
    # Both are flagged.
    proj = {
        "models": [
            {"id": "1", "block_type": "algeq", "outputs": [],
             "inputs": ["[Id]"]},
            {"id": "2", "block_type": "algeq", "outputs": [],
             "inputs": ["[Id]"]},
        ],
        "wires": [],
    }
    issues = _run_validate(proj)
    states_flagged = {(i["state"], i["model_id"]) for i in issues}
    assert ("Id", "1") in states_flagged
    assert ("Id", "2") in states_flagged


def test_no_issue_when_only_one_block_references_state():
    proj = {
        "models": [
            {"id": "1", "block_type": "algeq", "outputs": [],
             "inputs": ["[orphan]"]},
        ],
        "wires": [],
    }
    assert _run_validate(proj) == []


def test_wired_input_on_same_state_satisfies_the_check():
    # An algeq with the state on a wired port and another block producing it
    # via a wire is fine — no literal is floating.
    proj = {
        "models": [
            {"id": "1", "block_type": "tf1plim", "outputs": ["vf"],
             "inputs": [None]},
            {"id": "2", "block_type": "algeq",   "outputs": [],
             "inputs": [None]},
        ],
        "wires": [
            {"from_node": "1", "from_port": "output_1",
             "to_node": "2", "to_port": "input_1", "signal_name": "vf"},
        ],
    }
    assert _run_validate(proj) == []


def test_brackets_equal_plain_name_for_comparison():
    # tf1p has input stored PLAIN ("Vc1") while another block has it
    # BRACKETED ("[Vc1]") — comparison should strip brackets.
    proj = {
        "models": [
            {"id": "1", "block_type": "algeq", "outputs": [],
             "inputs": ["[Vc1]"]},
            {"id": "2", "block_type": "tf1p",  "outputs": ["V"],
             "inputs": ["Vc1"]},
        ],
        "wires": [],
    }
    issues = _run_validate(proj)
    assert len(issues) == 2  # both sides flagged
    states = {i["state"] for i in issues}
    assert states == {"Vc1"}
