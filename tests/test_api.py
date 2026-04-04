"""
tests/test_api.py
=================
FastAPI integration tests using httpx + FastAPI TestClient.
Run with:  pytest tests/test_api.py -v
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

# ── fixtures ─────────────────────────────────────────────────────────────────

DSL_EXC = """exc
ENTSOE_simp

%data

TW1
TA
KE
TE
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
[avr1]-[v]+{Vo}
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

DSL_TOR = """tor
GOV_simple

%data

R
T1
T2
VMIN
VMAX

%parameters

C   = [tm]*{R}

%states

dp1  = [tm]
Pm   = [tm]

%observables

Pm

%models

& tf1plim
dp1
Pm
1.
{T1}
{VMIN}
{VMAX}
& algeq
[tm]*[omega]-[Pm]
"""

DSL_INJ = """inj
INJ_test

%data

T

%parameters

%states

ix  = 0.
iy  = 0.

%observables

ix
iy

%models

& algeq
[ix]
& algeq
[iy]
"""

DSL_TWOP = """twop
TWOP_test

%data

R
X

%parameters

%states

ix1  = 0.
iy1  = 0.
ix2  = 0.
iy2  = 0.

%observables

ix1

%models

& f_twop_bus1
ix1
iy1
& f_twop_bus2
ix2
iy2
"""


# ── /blocks ──────────────────────────────────────────────────────────────────

class TestBlocks:
    def test_get_blocks_status(self):
        r = client.get("/blocks")
        assert r.status_code == 200

    def test_get_blocks_is_dict(self):
        r = client.get("/blocks")
        assert isinstance(r.json(), dict)

    def test_get_blocks_has_algeq(self):
        r = client.get("/blocks")
        assert "algeq" in r.json()

    def test_get_blocks_has_tf1plim(self):
        r = client.get("/blocks")
        assert "tf1plim" in r.json()

    def test_get_blocks_schema(self):
        r = client.get("/blocks")
        catalogue = r.json()
        for key, block in catalogue.items():
            assert "label" in block,    f"{key}: missing 'label'"
            assert "category" in block, f"{key}: missing 'category'"
            assert "dsl_lines" in block,f"{key}: missing 'dsl_lines'"


# ── /parse ───────────────────────────────────────────────────────────────────

class TestParse:
    def test_parse_exc_status(self):
        r = client.post("/parse", json={"dsl_text": DSL_EXC})
        assert r.status_code == 200

    def test_parse_exc_model_type(self):
        r = client.post("/parse", json={"dsl_text": DSL_EXC})
        assert r.json()["modelType"] == "exc"

    def test_parse_exc_model_name(self):
        r = client.post("/parse", json={"dsl_text": DSL_EXC})
        assert r.json()["modelName"] == "ENTSOE_simp"

    def test_parse_exc_data(self):
        r = client.post("/parse", json={"dsl_text": DSL_EXC})
        names = [d["name"] for d in r.json()["data"]]
        assert "KE" in names
        assert "TE" in names

    def test_parse_exc_blocks(self):
        r = client.post("/parse", json={"dsl_text": DSL_EXC})
        assert len(r.json()["blocks"]) == 3

    def test_parse_exc_no_errors(self):
        r = client.post("/parse", json={"dsl_text": DSL_EXC})
        assert r.json()["errors"] == []

    def test_parse_tor(self):
        r = client.post("/parse", json={"dsl_text": DSL_TOR})
        p = r.json()
        assert p["modelType"] == "tor"
        assert p["errors"] == []

    def test_parse_inj(self):
        r = client.post("/parse", json={"dsl_text": DSL_INJ})
        p = r.json()
        assert p["modelType"] == "inj"
        assert p["errors"] == []

    def test_parse_twop(self):
        r = client.post("/parse", json={"dsl_text": DSL_TWOP})
        p = r.json()
        assert p["modelType"] == "twop"
        assert p["errors"] == []

    def test_parse_bad_request_missing_field(self):
        r = client.post("/parse", json={})
        assert r.status_code == 422

    def test_parse_empty_dsl_returns_422_or_project(self):
        r = client.post("/parse", json={"dsl_text": ""})
        # Either a 422 (strict) or an error-annotated project — both acceptable
        assert r.status_code in (200, 422)

    def test_parse_project_has_required_keys(self):
        r = client.post("/parse", json={"dsl_text": DSL_EXC})
        p = r.json()
        for key in ("modelType", "modelName", "data", "parameters",
                    "states", "observables", "blocks", "errors"):
            assert key in p, f"Missing key: {key}"


# ── /emit ────────────────────────────────────────────────────────────────────

class TestEmit:
    def _project(self, dsl):
        return client.post("/parse", json={"dsl_text": dsl}).json()

    def test_emit_exc_status(self):
        proj = self._project(DSL_EXC)
        r = client.post("/emit", json={"project": proj})
        assert r.status_code == 200

    def test_emit_returns_dsl_text_key(self):
        proj = self._project(DSL_EXC)
        r = client.post("/emit", json={"project": proj})
        assert "dsl_text" in r.json()

    def test_emit_exc_sections_present(self):
        proj = self._project(DSL_EXC)
        dsl = client.post("/emit", json={"project": proj}).json()["dsl_text"]
        for sec in ("%data", "%parameters", "%states", "%observables", "%models"):
            assert sec in dsl, f"Missing section: {sec}"

    def test_emit_exc_model_header(self):
        proj = self._project(DSL_EXC)
        dsl = client.post("/emit", json={"project": proj}).json()["dsl_text"]
        lines = dsl.splitlines()
        assert lines[0] == "exc"
        assert lines[1] == "ENTSOE_simp"

    def test_emit_tor_roundtrip(self):
        proj = self._project(DSL_TOR)
        dsl = client.post("/emit", json={"project": proj}).json()["dsl_text"]
        assert "tor" in dsl
        assert "& tf1plim" in dsl

    def test_emit_inj_roundtrip(self):
        proj = self._project(DSL_INJ)
        dsl = client.post("/emit", json={"project": proj}).json()["dsl_text"]
        assert "inj" in dsl
        assert "& algeq" in dsl

    def test_emit_twop_roundtrip(self):
        proj = self._project(DSL_TWOP)
        dsl = client.post("/emit", json={"project": proj}).json()["dsl_text"]
        assert "twop" in dsl
        assert "& f_twop_bus1" in dsl
        assert "& f_twop_bus2" in dsl

    def test_emit_bad_request_missing_project(self):
        r = client.post("/emit", json={})
        assert r.status_code == 422

    def test_emit_preserves_data_names(self):
        proj = self._project(DSL_EXC)
        dsl = client.post("/emit", json={"project": proj}).json()["dsl_text"]
        for name in ("KE", "TE", "EMIN", "EMAX"):
            assert name in dsl

    def test_emit_preserves_state_names(self):
        proj = self._project(DSL_EXC)
        dsl = client.post("/emit", json={"project": proj}).json()["dsl_text"]
        assert "avr1" in dsl
        assert "avr2" in dsl

    def test_emit_continuation_marker(self):
        proj = self._project(DSL_EXC)
        dsl = client.post("/emit", json={"project": proj}).json()["dsl_text"]
        param_lines = [l for l in dsl.splitlines() if "Vo" in l and "=" in l]
        assert len(param_lines) >= 1
        assert param_lines[0].rstrip().endswith("&")


# ── /config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_get_config_status(self):
        r = client.get("/config")
        assert r.status_code == 200

    def test_get_config_has_required_keys(self):
        r = client.get("/config")
        cfg = r.json()
        for key in ("codegen_path", "host", "port"):
            assert key in cfg, f"Config missing key: {key}"

    def test_put_config_codegen_path(self):
        original = client.get("/config").json().get("codegen_path", "codegen")
        r = client.put("/config", json={"codegen_path": "/tmp/codegen_test"})
        assert r.status_code == 200
        assert r.json()["config"]["codegen_path"] == "/tmp/codegen_test"
        # restore
        client.put("/config", json={"codegen_path": original})

    def test_put_config_partial_update(self):
        r = client.put("/config", json={"port": 9999})
        assert r.status_code == 200
        # restore
        client.put("/config", json={"port": 8765})

    def test_put_config_preserves_other_fields(self):
        original = client.get("/config").json()
        client.put("/config", json={"codegen_path": "__test__"})
        updated = client.get("/config").json()
        assert updated["host"] == original["host"]
        assert updated["port"] == original["port"]
        # restore
        client.put("/config", json={"codegen_path": original["codegen_path"]})


# ── /run_codegen (binary absent — graceful failure) ──────────────────────────

class TestRunCodegen:
    def test_run_codegen_missing_binary_returns_500(self):
        # Point to a non-existent binary so we test the error path cleanly
        client.put("/config", json={"codegen_path": "__no_such_binary_xyz__"})
        r = client.post("/run_codegen", json={
            "dsl_text": DSL_EXC,
            "model_type": "exc",
            "model_name": "ENTSOE_simp"
        })
        assert r.status_code == 500
        assert "codegen" in r.json()["detail"].lower()
        # restore
        client.put("/config", json={"codegen_path": "codegen"})

    def test_run_codegen_bad_request_missing_dsl(self):
        r = client.post("/run_codegen", json={})
        assert r.status_code == 422

    def test_run_codegen_infers_type_name_from_dsl(self):
        """When model_type/model_name are omitted, server infers them from dsl_text."""
        client.put("/config", json={"codegen_path": "__no_such_binary_xyz__"})
        r = client.post("/run_codegen", json={"dsl_text": DSL_TOR})
        # 500 because binary absent — but request was accepted (not 422)
        assert r.status_code == 500
        # restore
        client.put("/config", json={"codegen_path": "codegen"})


# ── mandatory outputs ────────────────────────────────────────────────────────

class TestMandatoryOutputs:
    def test_mandatory_outputs_status(self):
        r = client.get("/mandatory_outputs")
        assert r.status_code == 200

    def test_mandatory_outputs_contains_all_types(self):
        data = client.get("/mandatory_outputs").json()
        for mtype in ("exc", "tor", "inj", "twop"):
            assert mtype in data

    def test_mandatory_outputs_values(self):
        data = client.get("/mandatory_outputs").json()
        assert "vf" in data["exc"]
        assert "tm" in data["tor"]
        assert set(data["inj"]) == {"ix", "iy"}
        assert set(data["twop"]) == {"ix1", "iy1", "ix2", "iy2"}


# ── static / SPA fallback ─────────────────────────────────────────────────────

class TestStatic:
    def test_root_returns_html(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_blocks_json_served(self):
        # /blocks is the API route, not the static file — but both should work
        r = client.get("/blocks")
        assert r.status_code == 200
