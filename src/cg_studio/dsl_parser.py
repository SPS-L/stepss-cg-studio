"""
dsl_parser.py
=============
Parses a CODEGEN DSL .txt file into a ModelProject dictionary.

DSL structure (sequential sections):
  line 1 : model type  (exc | tor | inj | twop)
  line 2 : model name
  blank
  %data
    one parameter name per line
  %parameters
    NAME = expression  [optional trailing &  for multi-line display]
  %states
    NAME = init_expression
  %observables
    signal_name
  %models
    & blockname  [optional comment]
    <positional argument lines as defined in blocks.json>

Template conventions in blocks.json dsl_lines:
  {{input}}    -> single input; stored as inputStates[0]
  {{input1}}   -> first of N inputs; appended to inputStates in order
  {{input2}}   -> second of N inputs; appended to inputStates in order
  {{inputN}}   -> Nth input (any positive integer suffix)
  {{output}}   -> output state name; stored as outputState
  {{inputs}}   -> semicolon-separated list of inputs (legacy multi-input)
  {{NAME}}     -> any other name -> stored in args dict keyed by NAME
"""

import json
import os
import re
from typing import Any

# --------------------------------------------------------------------------- #
# RAMSES input variables per model type (reserved - cannot be state names)    #
# --------------------------------------------------------------------------- #
RAMSES_INPUTS: dict[str, list[str]] = {
    "exc":  ["v", "p", "q", "omega", "if", "vf"],
    "tor":  ["p", "omega", "tm"],
    "inj":  ["omega", "vx", "vy", "ix", "iy"],
    "twop": ["omega1", "omega2", "vx1", "vy1", "vx2", "vy2",
             "ix1", "iy1", "ix2", "iy2"],
}

# Mandatory output states per model type
MANDATORY_OUTPUTS: dict[str, list[str]] = {
    "exc":  ["vf"],
    "tor":  ["tm"],
    "inj":  ["ix", "iy"],
    "twop": ["ix1", "iy1", "ix2", "iy2"],
}

# Regex to detect numbered input templates: {{input1}}, {{input2}}, ...
_INPUT_N_RE = re.compile(r"^\{\{input(\d+)\}\}$")


def _load_blocks(blocks_path: str | None = None) -> dict[str, Any]:
    """Load blocks.json catalogue.  Returns dict keyed by block name."""
    if blocks_path is None:
        import importlib.resources
        ref = importlib.resources.files("cg_studio") / "frontend" / "blocks.json"
        with importlib.resources.as_file(ref) as p:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    with open(blocks_path, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def parse_dsl(text: str, blocks_path: str | None = None) -> dict[str, Any]:
    """Parse DSL text -> ModelProject dict.

    Returns
    -------
    dict with keys:
        version, modelType, modelName,
        data        : [{name, comment}]
        parameters  : [{name, expr, continuation}]
        states      : [{name, initExpr, comment}]
        observables : [str]
        blocks      : [{id, blockType, comment, args, inputStates, outputState}]
        errors      : [str]   -- non-fatal parse warnings
    """
    blocks_catalogue = _load_blocks(blocks_path)
    lines = text.splitlines()
    errors: list[str] = []

    def _strip(line: str) -> str:
        return line.strip()

    # -- 1. Model type & name -------------------------------------------------
    non_empty = [l for l in lines if _strip(l)]
    if len(non_empty) < 2:
        return _error_project("DSL file must start with model type and model name.")

    model_type = _strip(non_empty[0]).lower()
    if model_type not in ("exc", "tor", "inj", "twop"):
        return _error_project(f"Unknown model type: {non_empty[0]!r}")

    model_name = _strip(non_empty[1])

    # -- 2. Split into sections -----------------------------------------------
    section_order = ["%data", "%parameters", "%states", "%observables", "%models"]
    section_content: dict[str, list[str]] = {s: [] for s in section_order}
    current_section = None

    for line in lines[2:]:
        stripped = _strip(line)
        matched = False
        for sec in section_order:
            if stripped.startswith(sec):
                current_section = sec
                matched = True
                break
        if matched:
            continue
        if current_section is not None and stripped != "":
            section_content[current_section].append(stripped)

    # -- 3. %data -------------------------------------------------------------
    data: list[dict] = []
    for line in section_content["%data"]:
        tokens = line.split()
        name = tokens[0]
        comment = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        data.append({"name": name, "comment": comment})

    # -- 4. %parameters -------------------------------------------------------
    parameters: list[dict] = []
    for line in section_content["%parameters"]:
        excl = line.find("!")
        clean = line[:excl].strip() if excl >= 0 else line.strip()
        continuation = clean.endswith("&")
        if continuation:
            clean = clean[:-1].strip()
        eq = clean.find("=")
        if eq < 0:
            errors.append(f"%parameters: missing '=' in line: {line!r}")
            continue
        name = clean[:eq].strip()
        expr = clean[eq + 1:].strip()
        parameters.append({"name": name, "expr": expr, "continuation": continuation})

    # -- 5. %states -----------------------------------------------------------
    states: list[dict] = []
    for line in section_content["%states"]:
        excl = line.find("!")
        comment = line[excl + 1:].strip() if excl >= 0 else ""
        clean = (line[:excl].strip() if excl >= 0 else line).strip()
        eq = clean.find("=")
        if eq < 0:
            errors.append(f"%states: missing '=' in line: {line!r}")
            continue
        name = clean[:eq].strip()
        init_expr = clean[eq + 1:].strip()
        states.append({"name": name, "initExpr": init_expr, "comment": comment})

    # -- 6. %observables ------------------------------------------------------
    observables: list[str] = []
    for line in section_content["%observables"]:
        tokens = line.split()
        if tokens:
            observables.append(tokens[0])

    # -- 7. %models - parse blocks --------------------------------------------
    blocks = _parse_blocks(section_content["%models"], blocks_catalogue, errors)

    return {
        "version": 1,
        "modelType": model_type,
        "modelName": model_name,
        "data": data,
        "parameters": parameters,
        "states": states,
        "observables": observables,
        "blocks": blocks,
        "canvas": {"nodeMap": {}, "drawflow": {}},
        "errors": errors,
    }


def _parse_blocks(model_lines: list[str], catalogue: dict, errors: list[str]) -> list[dict]:
    """Parse the %models section into a list of block instances."""
    blocks: list[dict] = []
    block_id = 0
    i = 0
    while i < len(model_lines):
        line = model_lines[i]
        if not line.startswith("&"):
            errors.append(f"%models: expected '& blockname', got: {line!r}")
            i += 1
            continue

        parts = line[1:].split(None, 1)
        block_name = parts[0].strip().lower()
        comment = parts[1].strip() if len(parts) > 1 else ""

        block_def = catalogue.get(block_name)
        if block_def is None:
            errors.append(f"%models: unknown block '{block_name}' - skipping")
            i += 1
            while i < len(model_lines) and not model_lines[i].startswith("&"):
                i += 1
            continue

        n_arg_lines = len(block_def.get("dsl_lines", []))
        arg_lines: list[str] = []
        i += 1
        while len(arg_lines) < n_arg_lines and i < len(model_lines):
            if model_lines[i].startswith("&"):
                errors.append(
                    f"%models: block '{block_name}' (id={block_id}) expected "
                    f"{n_arg_lines} arg lines, got {len(arg_lines)}"
                )
                break
            arg_lines.append(model_lines[i])
            i += 1

        args: dict[str, str] = {}
        dsl_line_templates = block_def.get("dsl_lines", [])
        # inputStates collected in slot order for {{input1}}, {{input2}}, ...
        input_state_slots: dict[int, str] = {}
        input_states: list[str] = []
        output_state: str = ""

        for idx, tmpl in enumerate(dsl_line_templates):
            val = arg_lines[idx] if idx < len(arg_lines) else ""

            if tmpl == "{{input}}":
                input_states = [val]
            elif tmpl == "{{output}}":
                output_state = val
            elif tmpl == "{{inputs}}":
                input_states = [v.strip() for v in val.split(";")]
            else:
                # Check for numbered input: {{input1}}, {{input2}}, ...
                m_in = _INPUT_N_RE.match(tmpl)
                if m_in:
                    slot = int(m_in.group(1))
                    input_state_slots[slot] = val
                else:
                    m = re.search(r"\{\{(\w+)\}\}", tmpl)
                    if m:
                        args[m.group(1)] = val
                    else:
                        args[f"arg{idx}"] = val

        # Merge numbered input slots into inputStates in ascending slot order
        if input_state_slots:
            input_states = [input_state_slots[k] for k in sorted(input_state_slots)]

        block_id += 1
        blocks.append({
            "id": block_id,
            "blockType": block_name,
            "comment": comment,
            "args": args,
            "inputStates": input_states,
            "outputState": output_state,
            "rawArgLines": arg_lines,
        })

    return blocks


def _error_project(msg: str) -> dict:
    return {
        "version": 1,
        "modelType": "",
        "modelName": "",
        "data": [],
        "parameters": [],
        "states": [],
        "observables": [],
        "blocks": [],
        "canvas": {"nodeMap": {}, "drawflow": {}},
        "errors": [msg],
    }
