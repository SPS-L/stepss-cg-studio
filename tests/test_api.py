"""
tests/test_api.py
=================
API integration tests for the FastAPI backend.

Runs against a TestClient (no live server required).
Requires:  pip install httpx

Run with:  pytest tests/test_api.py -v
"""

import os
import sys
import json
import pytest

# Make sure server/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

# ── Fixtures ────────────────────────────────────────────────────────────────

EXC_DSL = """exc
test_exc

%data

TA
TE
KE
EMIN
EMAX

%parameters

Vo  = v+(vf/{KE})  &

%states

avr1    = vf/{KE}
avr2    = vf/{KE}

%observables

vf

%models

& algeq
[avr1]-[v]-{Vo}
& tf1p1z
avr1
avr2
1.
{TA}
{TA}
& tf1plim
avr2
vf
{KE}
{TE}
{EMIN}
{EMAX}
"""

MINIMAL_PROJECT = {
    "modelType": "exc",
    "model_name": "test_exc",
    "data": [{"name": "TA", "comment": ""}],
    "parameters": [{"name": "Vo", "expr": "v+(vf/{KE})", "continuation": True}],
    "states": [{"name": "avr1", "initExpr": "0.", "comment": ""}],
    "observables": ["vf"],
    "blocks": [
        {
            "id": "n001",
            "blockType": "algeq",
            "comment": "",
            "args": {"expr": "[avr1]-[v]-{Vo}"},
            "inputStates": [],
            "outputState": "avr1",
            "rawArgLines": []
        }
    ],
    "wires": [],
    "canvas_meta": {},
    "errors": []
}


# ── /blocks ──────────────────────────────────────────────────────────────────

def test_get_blocks_returns_dict():
    r = client.get("/blocks")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert len(data) > 0


def test_get_blocks_has_required_keys():
    r = client.get("/blocks")
    catalogue = r.json()
    for name, block in list(catalogue.items())[:5]:  # spot-check first 5
        assert "label"    in block, f"{name} missing 'label'"
        assert "category" in block, f"{name} missing 'category'"
        assert "dsl_lines" in block, f"{name} missing 'dsl_lines'"


def test_get_blocks_contains_core_blocks():
    r = client.get("/blocks")
    cat = r.json()
    for b in ["algeq", "tf1p", "tf1plim", "lim", "pictl"]:
        assert b in cat, f"Core block '{b}' missing"


# ── /parse ────────────────────────────────────────────────────────────────────

def test_parse_returns_model_type():
    r = client.post("/parse", json={"dsl_text": EXC_DSL})
    assert r.status_code == 200
    p = r.json()
    assert p["modelType"] == "exc"


def test_parse_returns_model_name():
    r = client.post("/parse", json={"dsl_text": EXC_DSL})
    p = r.json()
    assert p["modelName"] == "test_exc"


def test_parse_data_section():
    r = client.post("/parse", json={"dsl_text": EXC_DSL})
    p = r.json()
    names = [d["name"] for d in p["data"]]
    assert "TA" in names
    assert "KE" in names


def test_parse_states_section():
    r = client.post("/parse", json={"dsl_text": EXC_DSL})
    p = r.json()
    state_names = [s["name"] for s in p["states"]]
    assert "avr1" in state_names
    assert "avr2" in state_names


def test_parse_blocks():
    r = client.post("/parse", json={"dsl_text": EXC_DSL})
    p = r.json()
    assert len(p["blocks"]) == 3
    btypes = [b["blockType"] for b in p["blocks"]]
    assert "algeq" in btypes
    assert "tf1plim" in btypes


def test_parse_no_errors():
    r = client.post("/parse", json={"dsl_text": EXC_DSL})
    p = r.json()
    assert p["errors"] == []


def test_parse_empty_body_returns_422():
    r = client.post("/parse", json={})
    assert r.status_code == 422


def test_parse_invalid_json_returns_422():
    r = client.post("/parse",
                    content="not json",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422


# ── /emit ─────────────────────────────────────────────────────────────────────

def test_emit_round_trip_type_name():
    r = client.post("/parse", json={"dsl_text": EXC_DSL})
    proj = r.json()
    r2 = client.post("/emit", json={"project": proj})
    assert r2.status_code == 200
    dsl = r2.json()["dsl_text"]
    lines = dsl.splitlines()
    assert lines[0] == "exc"
    assert lines[1] == "test_exc"


def test_emit_contains_all_sections():
    r  = client.post("/parse", json={"dsl_text": EXC_DSL})
    r2 = client.post("/emit",  json={"project": r.json()})
    dsl = r2.json()["dsl_text"]
    for sec in ["%data", "%parameters", "%states", "%observables", "%models"]:
        assert sec in dsl, f"Missing section: {sec}"


def test_emit_block_headers():
    r  = client.post("/parse", json={"dsl_text": EXC_DSL})
    r2 = client.post("/emit",  json={"project": r.json()})
    dsl = r2.json()["dsl_text"]
    assert "& algeq"   in dsl
    assert "& tf1plim" in dsl


def test_emit_data_names_present():
    r  = client.post("/parse", json={"dsl_text": EXC_DSL})
    r2 = client.post("/emit",  json={"project": r.json()})
    dsl = r2.json()["dsl_text"]
    for name in ["TA", "TE", "KE", "EMIN", "EMAX"]:
        assert name in dsl


def test_emit_empty_project_returns_422():
    r = client.post("/emit", json={})
    assert r.status_code == 422


def test_emit_minimal_project():
    r = client.post("/emit", json={"project": MINIMAL_PROJECT})
    assert r.status_code == 200
    dsl = r.json()["dsl_text"]
    assert "exc" in dsl


# ── /config ───────────────────────────────────────────────────────────────────

def test_get_config_returns_dict():
    r = client.get("/config")
    assert r.status_code == 200
    cfg = r.json()
    assert isinstance(cfg, dict)


def test_get_config_has_expected_keys():
    r = client.get("/config")
    cfg = r.json()
    for key in ["codegen_path", "host", "port"]:
        assert key in cfg, f"config missing key: {key}"


def test_put_config_updates_codegen_path(tmp_path, monkeypatch):
    # Redirect config to a temp file so we don't corrupt the real config
    import app as app_module
    tmp_cfg = tmp_path / "config.json"
    tmp_cfg.write_text(json.dumps({
        "codegen_path": "codegen",
        "workspace_dir": "workspace",
        "host": "127.0.0.1",
        "port": 8765
    }))
    monkeypatch.setattr(app_module, "CONFIG_PATH", tmp_cfg)

    r = client.put("/config", json={"codegen_path": "/usr/local/bin/codegen"})
    assert r.status_code == 200
    updated = r.json()["config"]
    assert updated["codegen_path"] == "/usr/local/bin/codegen"
    # Other fields preserved
    assert updated["port"] == 8765


def test_put_config_updates_port(tmp_path, monkeypatch):
    import app as app_module
    tmp_cfg = tmp_path / "config.json"
    tmp_cfg.write_text(json.dumps({
        "codegen_path": "codegen",
        "workspace_dir": "workspace",
        "host": "127.0.0.1",
        "port": 8765
    }))
    monkeypatch.setattr(app_module, "CONFIG_PATH", tmp_cfg)

    r = client.put("/config", json={"port": 9000})
    assert r.status_code == 200
    assert r.json()["config"]["port"] == 9000


# ── /run_codegen (offline stub test) ─────────────────────────────────────────

def test_run_codegen_missing_binary_returns_500(tmp_path, monkeypatch):
    """When codegen binary doesn't exist, endpoint must return HTTP 500."""
    import app as app_module
    tmp_cfg = tmp_path / "config.json"
    tmp_cfg.write_text(json.dumps({"codegen_path": "/nonexistent/codegen"}))
    monkeypatch.setattr(app_module, "CONFIG_PATH", tmp_cfg)

    r = client.post("/run_codegen", json={
        "dsl_text": EXC_DSL,
        "model_type": "exc",
        "model_name": "test_exc"
    })
    assert r.status_code == 500
    assert "codegen" in r.json()["detail"].lower()


# ── Parse → Emit idempotency ──────────────────────────────────────────────────

def test_parse_emit_parse_idempotent_model_type():
    """parse → emit → parse should yield the same modelType and modelName."""
    r1   = client.post("/parse", json={"dsl_text": EXC_DSL})
    proj = r1.json()
    r2   = client.post("/emit",  json={"project": proj})
    dsl2 = r2.json()["dsl_text"]
    r3   = client.post("/parse", json={"dsl_text": dsl2})
    proj2 = r3.json()
    assert proj2["modelType"] == proj["modelType"]
    assert proj2["modelName"] == proj["modelName"]


def test_parse_emit_parse_idempotent_block_count():
    """Block count must survive a parse → emit → parse round-trip."""
    r1    = client.post("/parse", json={"dsl_text": EXC_DSL})
    proj  = r1.json()
    r2    = client.post("/emit",  json={"project": proj})
    dsl2  = r2.json()["dsl_text"]
    r3    = client.post("/parse", json={"dsl_text": dsl2})
    proj2 = r3.json()
    assert len(proj2["blocks"]) == len(proj["blocks"])


def test_parse_emit_parse_idempotent_state_names():
    """State names must survive a parse → emit → parse round-trip."""
    r1    = client.post("/parse", json={"dsl_text": EXC_DSL})
    proj  = r1.json()
    r2    = client.post("/emit",  json={"project": proj})
    dsl2  = r2.json()["dsl_text"]
    r3    = client.post("/parse", json={"dsl_text": dsl2})
    names1 = {s["name"] for s in proj["states"]}
    names2 = {s["name"] for s in r3.json()["states"]}
    assert names1 == names2
