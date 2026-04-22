"""
test_check_model.py — exercises the JS CheckModel.run() validator under Node.

Skipped cleanly if `node` is not on PATH.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECK_JS = ROOT / "src" / "cg_studio" / "frontend" / "js" / "check_model.js"
VALIDATE_JS = ROOT / "src" / "cg_studio" / "frontend" / "js" / "validate.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node.js not on PATH"
)


def _run(proj: dict, opts: dict) -> list[dict]:
    # Load Validate first (CheckModel delegates floating-state detection to it),
    # then check_model. Both set window.* — emulate via a fake `window` object.
    script = (
        "const window = {};"
        "require(%r);"
        "global.Validate = window.Validate;"
        "require(%r);"
        "const proj = JSON.parse(process.argv[1]);"
        "const opts = JSON.parse(process.argv[2]);"
        "process.stdout.write(JSON.stringify(window.CheckModel.run(proj, opts)));"
    ) % (str(VALIDATE_JS), str(CHECK_JS))
    res = subprocess.run(
        ["node", "-e", script, json.dumps(proj), json.dumps(opts)],
        capture_output=True, text=True, timeout=10,
    )
    assert res.returncode == 0, f"node failed: {res.stderr}"
    return json.loads(res.stdout)


OPTS_EXC = {
    "ramsesInputs":  {"exc": ["v", "p", "q", "omega"]},
    "ramsesOutputs": {"exc": ["vf"]},
}
OPTS_INJ = {
    "ramsesInputs":  {"inj": ["vx", "vy", "omega"]},
    "ramsesOutputs": {"inj": ["ix", "iy"]},
}


def _cats(issues):
    return [i["category"] for i in issues]


def test_clean_exc_model_has_no_issues():
    proj = {
        "model_type": "exc", "model_name": "m",
        "data": [{"name": "K"}], "parameters": [], "states": [], "observables": [],
        "models": [
            {"id": "1", "block_type": "ramses_in",  "args": {"name": "omega"},
             "inputs": [], "outputs": ["[omega]"]},
            {"id": "2", "block_type": "tf1p",       "args": {"K": "{K}", "T": "1."},
             "inputs": [None], "outputs": ["vf"]},
            {"id": "3", "block_type": "ramses_out", "args": {"name": "vf"},
             "inputs": [None], "outputs": []},
        ],
        "wires": [
            {"from_node": "1", "from_port": "output_1",
             "to_node": "2",   "to_port": "input_1", "signal_name": "[omega]"},
            {"from_node": "2", "from_port": "output_1",
             "to_node": "3",   "to_port": "input_1", "signal_name": "vf"},
        ],
    }
    assert _run(proj, OPTS_EXC) == []


def test_mandatory_output_missing_for_exc():
    proj = {
        "model_type": "exc", "model_name": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "models": [
            {"id": "1", "block_type": "ramses_in", "args": {"name": "omega"},
             "inputs": [], "outputs": ["[omega]"]},
        ],
        "wires": [],
    }
    cats = _cats(_run(proj, OPTS_EXC))
    assert "mandatory_output" in cats
    # Also flags the RAMSES input not being connected (no wire from ramses_in).
    assert "ramses_input" in cats


def test_inj_requires_both_vx_and_vy():
    proj = {
        "model_type": "inj", "model_name": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "models": [
            {"id": "1", "block_type": "ramses_in", "args": {"name": "vx"},
             "inputs": [], "outputs": ["[vx]"]},
            {"id": "2", "block_type": "algeq", "args": {"expr": "[vx]-[ix]"},
             "inputs": ["[vx]"], "outputs": ["ix"]},
            # Missing vy ramses_in on purpose.
            {"id": "3", "block_type": "ramses_out", "args": {"name": "ix"},
             "inputs": [None], "outputs": []},
            {"id": "4", "block_type": "ramses_out", "args": {"name": "iy"},
             "inputs": [None], "outputs": []},
        ],
        "wires": [
            {"from_node": "1", "from_port": "output_1",
             "to_node": "2",   "to_port": "input_1", "signal_name": "[vx]"},
            {"from_node": "2", "from_port": "output_1",
             "to_node": "3",   "to_port": "input_1", "signal_name": "ix"},
        ],
    }
    issues = _run(proj, OPTS_INJ)
    msgs = [i["message"] for i in issues]
    assert any("vy" in m for m in msgs), msgs
    # ix is produced (wired); iy is NOT → also expect a mandatory_output issue.
    assert any(i["category"] == "mandatory_output" and "iy" in i["message"]
               for i in issues), issues


def test_disconnected_input_port_flagged():
    proj = {
        "model_type": "exc", "model_name": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "models": [
            {"id": "1", "block_type": "tf1p", "args": {}, "inputs": [None],
             "outputs": ["vf"]},  # no wire into input_1, no literal => disconnected
            {"id": "2", "block_type": "ramses_out", "args": {"name": "vf"},
             "inputs": [None], "outputs": []},
        ],
        "wires": [
            {"from_node": "1", "from_port": "output_1",
             "to_node": "2",   "to_port": "input_1", "signal_name": "vf"},
        ],
    }
    cats = _cats(_run(proj, OPTS_EXC))
    assert "disconnected_input" in cats


def test_undeclared_parameter_flagged():
    proj = {
        "model_type": "exc", "model_name": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "models": [
            {"id": "1", "block_type": "tf1p",
             "args": {"K": "{UNKNOWN}", "T": "1."},
             "inputs": [None], "outputs": ["vf"]},
        ],
        "wires": [],
    }
    issues = _run(proj, OPTS_EXC)
    assert any(i["category"] == "undeclared_param" and "UNKNOWN" in i["message"]
               for i in issues), issues


def test_undeclared_state_flagged():
    proj = {
        "model_type": "exc", "model_name": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "models": [
            {"id": "1", "block_type": "algeq",
             "args": {"expr": "[ghost]-1"},
             "inputs": ["[ghost]"], "outputs": []},
        ],
        "wires": [],
    }
    issues = _run(proj, OPTS_EXC)
    assert any(i["category"] == "undeclared_state" and "ghost" in i["message"]
               for i in issues), issues


def test_uninitialised_parameter_and_state_flagged():
    proj = {
        "model_type": "exc", "model_name": "m",
        "data": [{"name": "D"}],
        "parameters": [{"name": "P", "expr": ""}],   # missing init -> error
        "states":     [{"name": "S", "init": ""}],   # missing init -> warning
        "observables": [],
        "models": [],
        "wires": [],
    }
    issues = _run(proj, OPTS_EXC)
    cats = _cats(issues)
    assert "param_no_init" in cats
    assert "state_no_init" in cats


def test_floating_state_reported_via_check_panel():
    """CheckModel surfaces Validate.findFloatingStateIssues as warnings."""
    proj = {
        "model_type": "exc", "model_name": "m",
        "data": [], "parameters": [], "states": [], "observables": [],
        "models": [
            {"id": "1", "block_type": "algeq", "args": {"expr": "[Vc1]-1"},
             "inputs": ["[Vc1]"], "outputs": []},
            {"id": "2", "block_type": "tf1p", "args": {"K": "1", "T": "1"},
             "inputs": ["Vc1"], "outputs": ["vf"]},
        ],
        "wires": [],
    }
    issues = _run(proj, OPTS_EXC)
    assert any(i["category"] == "floating_state" and "Vc1" in i["message"]
               for i in issues), issues
