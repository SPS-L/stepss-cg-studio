"""Tests for dsl_parser.py.

Run from repo root:
    pytest tests/test_parser.py -v
"""
import sys
import json
from pathlib import Path

import pytest

# Make server/ importable
SERVER = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(SERVER))

from dsl_parser import parse_dsl

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
DSL_SAMPLES: dict[str, str] = {
    "tor_ENTSOE_simp": """tor
ENTSOE_simp

%data

R
T1
VMIN
VMAX
T2
T3

%parameters

C   =  [tm]*{R}

%states

dp1  = [tm]
dp2  = [tm]
Pm   = [tm]

%observables

Pm

%models

& algeq
{R}*[dp1]-{C}+[omega]-1.d0
& tf1plim
dp1
dp2
1.
{T1}
{VMIN}
{VMAX}
& tf1p1z
dp2
Pm
1.
{T2}
{T3}
& algeq
[tm]*[omega]-[Pm]
""",
    "exc_ENTSOE_simp": """exc
ENTSOE_simp

%data

TW1
TW2
KS1
T1
T2
T3
T4
VSTMIN
VSTMAX
TA
TB
KE
TE
EMIN
EMAX

%parameters

Vo  = v+(vf/{KE}) &

%states

domega  = 0.
pss1    = 0.
pss2    = 0.
pss3    = 0.
pss4    = 0.
dvpss   = 0.
avr1    = vf/{KE}
avr2    = vf/{KE}

%observables

domega
dvpss
vf

%models

& algeq
[omega]-1.-[domega]
& tfder1p
domega
pss1
{TW1}
{TW1}
& tfder1p
pss1
pss2
{TW2}
{TW2}
& tf1p1z
pss2
pss3
{KS1}
{T1}
{T2}
& tf1p1z
pss3
pss4
1.
{T3}
{T4}
& lim
pss4
dvpss
{VSTMIN}
{VSTMAX}
& algeq
[avr1]-[dvpss]+[v]-{Vo}
& tf1p1z
avr1
avr2
1.
{TA}
{TB}
& tf1plim
avr2
vf
{KE}
{TE}
{EMIN}
{EMAX}
""",
    "inj_BLOCKTEST": """inj
BLOCKTEST

%data

T

%parameters

%states

u     =  1.
x     =  0.
uplim =  1.
lolim = -1000.

%observables

u
x

%models

& algeq
[ix]
& algeq
[iy]
& algeq
[u]-dcos(2*3.14159*t)
& invlim
u
lolim
uplim
x
{T}/(2*3.14159)
& algeq
[uplim]-dexp(-t/3.d0)
& algeq
[lolim]+1000.
""",
}


# ---------------------------------------------------------------------------
# Basic structural tests
# ---------------------------------------------------------------------------
class TestParserStructure:
    def test_model_type_tor(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        assert p["modelType"] == "tor"

    def test_model_name_tor(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        assert p["modelName"] == "ENTSOE_simp"

    def test_model_type_exc(self):
        p = parse_dsl(DSL_SAMPLES["exc_ENTSOE_simp"])
        assert p["modelType"] == "exc"

    def test_model_type_inj(self):
        p = parse_dsl(DSL_SAMPLES["inj_BLOCKTEST"])
        assert p["modelType"] == "inj"

    def test_version_field(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        assert p["version"] == 1

    def test_required_keys(self):
        p = parse_dsl(DSL_SAMPLES["exc_ENTSOE_simp"])
        for key in ("data", "parameters", "states", "observables", "canvas"):
            assert key in p, f"Missing key: {key}"

    def test_canvas_keys(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        canvas = p["canvas"]
        assert "drawflow" in canvas
        assert "nodeMap" in canvas
        assert "layout" in canvas


# ---------------------------------------------------------------------------
# %data section
# ---------------------------------------------------------------------------
class TestData:
    def test_tor_data_count(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        assert len(p["data"]) == 6

    def test_tor_data_names(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        names = [d["name"] for d in p["data"]]
        assert names == ["R", "T1", "VMIN", "VMAX", "T2", "T3"]

    def test_exc_data_count(self):
        p = parse_dsl(DSL_SAMPLES["exc_ENTSOE_simp"])
        assert len(p["data"]) == 15

    def test_inj_data_count(self):
        p = parse_dsl(DSL_SAMPLES["inj_BLOCKTEST"])
        assert len(p["data"]) == 1
        assert p["data"][0]["name"] == "T"


# ---------------------------------------------------------------------------
# %parameters section
# ---------------------------------------------------------------------------
class TestParameters:
    def test_tor_single_parameter(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        assert len(p["parameters"]) == 1
        param = p["parameters"][0]
        assert param["name"] == "C"
        assert "[tm]" in param["expr"]
        assert "{R}" in param["expr"]

    def test_exc_parameter_continuation(self):
        p = parse_dsl(DSL_SAMPLES["exc_ENTSOE_simp"])
        assert len(p["parameters"]) == 1
        param = p["parameters"][0]
        assert param["name"] == "Vo"
        assert param["continuation"] is True

    def test_inj_empty_parameters(self):
        p = parse_dsl(DSL_SAMPLES["inj_BLOCKTEST"])
        assert p["parameters"] == []


# ---------------------------------------------------------------------------
# %states section
# ---------------------------------------------------------------------------
class TestStates:
    def test_tor_state_count(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        assert len(p["states"]) == 3

    def test_tor_state_names(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        names = [s["name"] for s in p["states"]]
        assert "dp1" in names and "dp2" in names and "Pm" in names

    def test_exc_state_count(self):
        p = parse_dsl(DSL_SAMPLES["exc_ENTSOE_simp"])
        assert len(p["states"]) == 8

    def test_inj_state_init_values(self):
        p = parse_dsl(DSL_SAMPLES["inj_BLOCKTEST"])
        state_map = {s["name"]: s["initExpr"] for s in p["states"]}
        assert state_map["u"] == "1."
        assert state_map["x"] == "0."
        assert state_map["lolim"] == "-1000."


# ---------------------------------------------------------------------------
# %observables section
# ---------------------------------------------------------------------------
class TestObservables:
    def test_tor_observables(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        assert p["observables"] == ["Pm"]

    def test_exc_observables(self):
        p = parse_dsl(DSL_SAMPLES["exc_ENTSOE_simp"])
        assert set(p["observables"]) == {"domega", "dvpss", "vf"}

    def test_inj_observables(self):
        p = parse_dsl(DSL_SAMPLES["inj_BLOCKTEST"])
        assert set(p["observables"]) == {"u", "x"}


# ---------------------------------------------------------------------------
# %models / canvas nodeMap
# ---------------------------------------------------------------------------
class TestNodeMap:
    def test_tor_node_count(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        assert len(p["canvas"]["nodeMap"]) == 4

    def test_exc_node_count(self):
        p = parse_dsl(DSL_SAMPLES["exc_ENTSOE_simp"])
        assert len(p["canvas"]["nodeMap"]) == 10

    def test_block_types_tor(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        types = [n["blockType"] for n in p["canvas"]["nodeMap"].values()]
        assert types.count("algeq") == 2
        assert "tf1plim" in types
        assert "tf1p1z" in types

    def test_tf1plim_output_state_tor(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        nodes = list(p["canvas"]["nodeMap"].values())
        tf1plim_nodes = [n for n in nodes if n["blockType"] == "tf1plim"]
        assert len(tf1plim_nodes) == 1
        n = tf1plim_nodes[0]
        assert n["inputState"] == "dp1"
        assert n["outputState"] == "dp2"

    def test_tf1plim_args_tor(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        nodes = list(p["canvas"]["nodeMap"].values())
        tf1plim_nodes = [n for n in nodes if n["blockType"] == "tf1plim"]
        args = tf1plim_nodes[0]["args"]
        assert args["gain"] == "1."
        assert args["T"] == "{T1}"
        assert args["lo"] == "{VMIN}"
        assert args["hi"] == "{VMAX}"

    def test_algeq_expr(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        algeq_nodes = [n for n in p["canvas"]["nodeMap"].values() if n["blockType"] == "algeq"]
        exprs = [n["args"].get("expr", "") for n in algeq_nodes]
        assert any("{R}" in e for e in exprs)


# ---------------------------------------------------------------------------
# Auto-layout
# ---------------------------------------------------------------------------
class TestLayout:
    def test_layout_length_matches_nodes(self):
        p = parse_dsl(DSL_SAMPLES["exc_ENTSOE_simp"])
        assert len(p["canvas"]["layout"]) == len(p["canvas"]["nodeMap"])

    def test_layout_entries_have_xy(self):
        p = parse_dsl(DSL_SAMPLES["tor_ENTSOE_simp"])
        for entry in p["canvas"]["layout"]:
            assert "x" in entry and "y" in entry
            assert entry["x"] >= 0 and entry["y"] >= 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
class TestErrors:
    def test_unknown_model_type(self):
        with pytest.raises(ValueError, match="Unknown model type"):
            parse_dsl("badtype\nMYMODEL\n\n%data\n\n%parameters\n\n%states\n\n%observables\n\n%models\n")

    def test_missing_section(self):
        with pytest.raises(ValueError, match="%models"):
            parse_dsl("exc\nTEST\n\n%data\n\n%parameters\n\n%states\n\n%observables\n")

    def test_too_short(self):
        with pytest.raises(ValueError):
            parse_dsl("exc")
