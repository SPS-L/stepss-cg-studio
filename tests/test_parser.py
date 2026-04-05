"""
tests/test_parser.py
====================
Round-trip tests: parse DSL .txt -> emit -> compare structural equivalence.
Run with:  pytest tests/test_parser.py -v
"""

import os
import json
import pytest

from cg_studio.dsl_parser import parse_dsl, RAMSES_INPUTS, MANDATORY_OUTPUTS
from cg_studio.dsl_emitter import emit_dsl

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")

FIXTURE_EXC_SIMPLE = """exc
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

Vo  = v+(vf/{KE})  &

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
"""

FIXTURE_TOR_SIMPLE = """tor
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
"""

FIXTURE_INJ_SIMPLE = """inj
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
"""


def _parse(text: str) -> dict:
    return parse_dsl(text)


def _roundtrip(text: str) -> tuple[dict, str]:
    project = _parse(text)
    emitted = emit_dsl(project)
    return project, emitted


# ---- Parsing tests ----------------------------------------------------------

def test_parse_model_type_name():
    p = _parse(FIXTURE_EXC_SIMPLE)
    assert p["modelType"] == "exc"
    assert p["modelName"] == "ENTSOE_simp"
    assert not p["errors"]


def test_parse_data_section():
    p = _parse(FIXTURE_EXC_SIMPLE)
    data_names = [d["name"] for d in p["data"]]
    assert "TW1" in data_names
    assert "KE" in data_names
    assert len(data_names) == 15


def test_parse_parameters():
    p = _parse(FIXTURE_EXC_SIMPLE)
    assert len(p["parameters"]) == 1
    assert p["parameters"][0]["name"] == "Vo"
    assert p["parameters"][0]["continuation"] is True


def test_parse_states():
    p = _parse(FIXTURE_EXC_SIMPLE)
    state_names = [s["name"] for s in p["states"]]
    assert "domega" in state_names
    assert "avr2" in state_names
    assert len(state_names) == 8


def test_parse_observables():
    p = _parse(FIXTURE_EXC_SIMPLE)
    assert "vf" in p["observables"]
    assert "dvpss" in p["observables"]


def test_parse_blocks_count():
    p = _parse(FIXTURE_EXC_SIMPLE)
    assert len(p["blocks"]) == 9


def test_parse_block_types():
    p = _parse(FIXTURE_EXC_SIMPLE)
    btypes = [b["blockType"] for b in p["blocks"]]
    assert "algeq" in btypes
    assert "tfder1p" in btypes
    assert "tf1p1z" in btypes
    assert "lim" in btypes
    assert "tf1plim" in btypes


def test_parse_tor():
    p = _parse(FIXTURE_TOR_SIMPLE)
    assert p["modelType"] == "tor"
    assert len(p["data"]) == 6
    assert len(p["blocks"]) == 4


def test_parse_inj():
    p = _parse(FIXTURE_INJ_SIMPLE)
    assert p["modelType"] == "inj"
    assert len(p["data"]) == 1
    assert len(p["blocks"]) == 6


def test_parse_no_errors_on_valid_dsl():
    for fixture in [FIXTURE_EXC_SIMPLE, FIXTURE_TOR_SIMPLE, FIXTURE_INJ_SIMPLE]:
        p = _parse(fixture)
        assert p["errors"] == [], f"Unexpected parse errors: {p['errors']}"


def test_ramses_inputs_defined():
    for mtype in ["exc", "tor", "inj", "twop"]:
        assert mtype in RAMSES_INPUTS
        assert len(RAMSES_INPUTS[mtype]) > 0


def test_mandatory_outputs_defined():
    assert MANDATORY_OUTPUTS["exc"] == ["vf"]
    assert set(MANDATORY_OUTPUTS["inj"]) == {"ix", "iy"}
    assert set(MANDATORY_OUTPUTS["twop"]) == {"ix1", "iy1", "ix2", "iy2"}


# ---- Emission tests ---------------------------------------------------------

def test_emit_contains_sections():
    _, emitted = _roundtrip(FIXTURE_EXC_SIMPLE)
    for section in ["%data", "%parameters", "%states", "%observables", "%models"]:
        assert section in emitted, f"Missing section: {section}"


def test_emit_model_type_name():
    _, emitted = _roundtrip(FIXTURE_EXC_SIMPLE)
    lines = emitted.splitlines()
    assert lines[0] == "exc"
    assert lines[1] == "ENTSOE_simp"


def test_emit_data_names_present():
    _, emitted = _roundtrip(FIXTURE_EXC_SIMPLE)
    for name in ["TW1", "TW2", "KS1", "KE", "TE"]:
        assert name in emitted


def test_emit_states_present():
    _, emitted = _roundtrip(FIXTURE_EXC_SIMPLE)
    assert "domega" in emitted
    assert "avr2" in emitted


def test_emit_block_headers_present():
    _, emitted = _roundtrip(FIXTURE_EXC_SIMPLE)
    assert "& algeq" in emitted
    assert "& tfder1p" in emitted
    assert "& tf1p1z" in emitted


def test_emit_tor_roundtrip():
    p, emitted = _roundtrip(FIXTURE_TOR_SIMPLE)
    assert p["modelType"] == "tor"
    assert "& tf1plim" in emitted
    assert "& tf1p1z" in emitted


def test_emit_continuation_marker():
    _, emitted = _roundtrip(FIXTURE_EXC_SIMPLE)
    param_lines = [l for l in emitted.splitlines() if "Vo" in l and "=" in l]
    assert len(param_lines) >= 1
    assert param_lines[0].rstrip().endswith("&")


# ---- blocks.json integrity tests -------------------------------------------

def _blocks_json_path():
    here = os.path.dirname(os.path.abspath(__file__))
    # Try installed package location first, then legacy frontend/ location
    candidate = os.path.join(here, "..", "src", "cg_studio", "frontend", "blocks.json")
    if os.path.exists(candidate):
        return candidate
    return os.path.join(here, "..", "frontend", "blocks.json")


def test_blocks_json_loadable():
    blocks_path = _blocks_json_path()
    assert os.path.exists(blocks_path), "frontend/blocks.json not found"
    with open(blocks_path) as f:
        catalogue = json.load(f)
    assert isinstance(catalogue, dict)
    assert len(catalogue) > 0


def test_blocks_json_required_keys():
    blocks_path = _blocks_json_path()
    with open(blocks_path) as f:
        catalogue = json.load(f)
    required_keys = {"label", "category", "dsl_lines"}
    for block_name, block_def in catalogue.items():
        missing = required_keys - set(block_def.keys())
        assert not missing, f"Block '{block_name}' missing keys: {missing}"


def test_blocks_json_contains_core_blocks():
    blocks_path = _blocks_json_path()
    with open(blocks_path) as f:
        catalogue = json.load(f)
    core = ["algeq", "tf1p", "tf1plim", "tf1p1z", "lim", "limvb",
            "pictl", "pictllim", "tfder1p", "max2v", "min2v",
            "f_inj", "f_twop_bus1", "f_twop_bus2"]
    for block in core:
        assert block in catalogue, f"Core block '{block}' missing from blocks.json"


# ---- Example file tests (skipped if examples dir absent) -------------------

def _get_example_txts():
    if not os.path.isdir(EXAMPLES_DIR):
        return []
    return [
        os.path.join(EXAMPLES_DIR, f)
        for f in os.listdir(EXAMPLES_DIR)
        if f.endswith(".txt")
    ]


@pytest.mark.parametrize("fpath", _get_example_txts())
def test_example_file_parses_without_errors(fpath):
    with open(fpath, encoding="utf-8") as f:
        text = f.read()
    p = _parse(text)
    assert p["modelType"] in ("exc", "tor", "inj", "twop"), \
        f"{fpath}: unexpected modelType {p['modelType']!r}"
    assert p["errors"] == [], f"{fpath} parse errors: {p['errors']}"


@pytest.mark.parametrize("fpath", _get_example_txts())
def test_example_file_emits_sections(fpath):
    with open(fpath, encoding="utf-8") as f:
        text = f.read()
    p = _parse(text)
    emitted = emit_dsl(p)
    for sec in ["%data", "%parameters", "%states", "%observables", "%models"]:
        assert sec in emitted, f"{fpath}: missing {sec} in emitted DSL"
