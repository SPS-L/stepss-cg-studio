"""Parse a CODEGEN DSL .txt file into a ModelProject dict.

The ModelProject schema mirrors the .cgproj JSON format:
{
    "version": 1,
    "modelType": "exc" | "tor" | "inj" | "twop",
    "modelName": str,
    "data": [{"name": str, "comment": str}],
    "parameters": [{"name": str, "expr": str, "continuation": bool}],
    "states": [{"name": str, "initExpr": str}],
    "observables": [str],
    "canvas": {
        "drawflow": {},          # populated by the frontend on load
        "nodeMap": {             # populated by _build_node_map()
            "node_N": {
                "blockType": str,
                "comment": str,
                "inputState": str | None,
                "outputState": str | None,
                "extraInputs": [str],   # for multi-input blocks
                "args": {str: str}
            }
        },
        "layout": []   # [{"id": str, "x": int, "y": int}]
    }
}
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Block argument schema  (loaded lazily from blocks.json)
# ---------------------------------------------------------------------------
_BLOCKS: dict[str, dict] | None = None


def _get_blocks() -> dict[str, dict]:
    global _BLOCKS
    if _BLOCKS is None:
        blocks_path = Path(__file__).parent.parent / "frontend" / "blocks.json"
        with open(blocks_path, encoding="utf-8") as f:
            _BLOCKS = json.load(f)
    return _BLOCKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
VALID_TYPES = {"exc", "tor", "inj", "twop"}


def _strip_inline_comment(line: str) -> tuple[str, str]:
    """Return (value, comment) split on first '!'."""
    pos = line.find("!")
    if pos == -1:
        return line.strip(), ""
    return line[:pos].strip(), line[pos + 1:].strip()


def _nonblank(lines: list[str], idx: int) -> int:
    """Advance idx past blank lines; return new idx."""
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    return idx


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------
def parse_dsl(text: str) -> dict[str, Any]:
    """Parse DSL text and return a ModelProject dict."""
    raw = text.splitlines()
    lines = [l.rstrip() for l in raw]
    n = len(lines)

    if n < 2:
        raise ValueError("DSL file must have at least 2 lines (model type + model name).")

    model_type = lines[0].strip().lower()
    if model_type not in VALID_TYPES:
        raise ValueError(f"Unknown model type '{model_type}'. Expected one of {VALID_TYPES}.")

    model_name = lines[1].strip()
    if not model_name:
        raise ValueError("Model name (line 2) is empty.")

    # Find section start indices
    section_idx: dict[str, int] = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        for kw in ("%data", "%parameters", "%states", "%observables", "%models"):
            if stripped.startswith(kw):
                section_idx[kw] = i
                break

    for kw in ("%data", "%parameters", "%states", "%observables", "%models"):
        if kw not in section_idx:
            raise ValueError(f"Required section '{kw}' not found in DSL.")

    def section_lines(start_kw: str, end_kw: str) -> list[str]:
        start = section_idx[start_kw] + 1
        end = section_idx[end_kw]
        return [l for l in lines[start:end] if l.strip() != ""]

    # %data
    data: list[dict] = []
    for line in section_lines("%data", "%parameters"):
        val, cmt = _strip_inline_comment(line)
        if val:
            data.append({"name": val, "comment": cmt})

    # %parameters  (lines may have trailing & for continuation)
    parameters: list[dict] = []
    for line in section_lines("%parameters", "%states"):
        val, _cmt = _strip_inline_comment(line)
        if not val:
            continue
        continuation = val.endswith("&")
        val = val.rstrip("& ").strip()
        eq = val.find("=")
        if eq == -1:
            raise ValueError(f"Parameter line missing '=': {line!r}")
        name = val[:eq].strip()
        expr = val[eq + 1:].strip()
        parameters.append({"name": name, "expr": expr, "continuation": continuation})

    # %states
    states: list[dict] = []
    for line in section_lines("%states", "%observables"):
        val, _cmt = _strip_inline_comment(line)
        if not val:
            continue
        eq = val.find("=")
        if eq == -1:
            raise ValueError(f"State line missing '=': {line!r}")
        name = val[:eq].strip()
        init = val[eq + 1:].strip()
        states.append({"name": name, "initExpr": init})

    # %observables
    observables: list[str] = []
    for line in section_lines("%observables", "%models"):
        val, _ = _strip_inline_comment(line)
        if val:
            tok = val.split()
            if tok:
                observables.append(tok[0])

    # %models  -> raw lines from section start to end of file
    models_start = section_idx["%models"] + 1
    models_raw = lines[models_start:]

    node_map, layout = _build_node_map(models_raw)

    return {
        "version": 1,
        "modelType": model_type,
        "modelName": model_name,
        "data": data,
        "parameters": parameters,
        "states": states,
        "observables": observables,
        "canvas": {
            "drawflow": {},
            "nodeMap": node_map,
            "layout": layout,
        },
    }


# ---------------------------------------------------------------------------
# Block instance parser
# ---------------------------------------------------------------------------
def _build_node_map(
    models_raw: list[str],
) -> tuple[dict[str, dict], list[dict]]:
    """Parse %models lines into nodeMap and a suggested layout."""
    blocks = _get_blocks()
    nodes: dict[str, dict] = {}
    node_counter = 0

    i = 0
    lines = [l for l in models_raw]  # keep blanks for line-counting

    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or not line.startswith("&"):
            continue

        # Parse:  & blockname   optional comment
        parts = line[1:].split(None, 1)
        if not parts:
            continue
        block_type = parts[0].strip().lower()
        comment = parts[1].strip() if len(parts) > 1 else ""

        if block_type not in blocks:
            raise ValueError(f"Unknown block type in %models: '{block_type}'")

        bdef = blocks[block_type]
        n_arg_lines = len(bdef["dsl_lines"])

        # Collect argument lines (skip blank lines between block header and args)
        arg_lines: list[str] = []
        while len(arg_lines) < n_arg_lines and i < len(lines):
            raw_arg = lines[i].strip()
            i += 1
            if raw_arg == "":
                continue
            if raw_arg.startswith("&"):
                # hit next block header without enough args
                i -= 1  # put it back
                break
            arg_lines.append(raw_arg)

        node_id = f"node_{node_counter}"
        node_counter += 1

        node = _build_node(node_id, block_type, comment, arg_lines, bdef)
        nodes[node_id] = node

    layout = _auto_layout(nodes)
    return nodes, layout


def _build_node(
    node_id: str,
    block_type: str,
    comment: str,
    arg_lines: list[str],
    bdef: dict,
) -> dict:
    """Map positional DSL arg lines onto a node dict using dsl_lines templates."""
    dsl_tpl = bdef["dsl_lines"]
    arg_defs = bdef.get("args", [])

    input_state: str | None = None
    output_state: str | None = None
    extra_inputs: list[str] = []
    args: dict[str, str] = {}

    for idx, tpl in enumerate(dsl_tpl):
        val = arg_lines[idx] if idx < len(arg_lines) else ""
        if tpl == "{{input}}":
            input_state = val
        elif tpl == "{{output}}":
            output_state = val
        elif tpl == "{{extra_input}}":
            extra_inputs.append(val)
        elif tpl.startswith("{{") and tpl.endswith("}}"):
            arg_name = tpl[2:-2]
            args[arg_name] = val
        else:
            # literal template with embedded placeholders
            args[str(idx)] = val

    # For algeq: the single line is the expression
    if block_type == "algeq" and arg_lines:
        args["expr"] = arg_lines[0]
        output_state = arg_lines[0]  # residual label

    return {
        "blockType": block_type,
        "comment": comment,
        "inputState": input_state,
        "outputState": output_state,
        "extraInputs": extra_inputs,
        "args": args,
    }


# ---------------------------------------------------------------------------
# Auto-layout: left-to-right topological layers
# ---------------------------------------------------------------------------
VX = 220   # horizontal spacing per layer (px)
VY = 120   # vertical spacing within a layer (px)
X0 = 60    # left margin
Y0 = 60    # top margin


def _auto_layout(node_map: dict[str, dict]) -> list[dict]:
    """Assign (x, y) canvas positions using a simple layer-based layout.

    Nodes whose inputState matches the outputState of a preceding node are
    placed one layer to the right.
    """
    # Build output->node_id index
    out_to_id: dict[str, str] = {}
    for nid, node in node_map.items():
        out = node.get("outputState")
        if out:
            out_to_id[out] = nid

    # Assign layer via BFS
    layers: dict[str, int] = {}
    changed = True
    for nid in node_map:
        layers[nid] = 0

    while changed:
        changed = False
        for nid, node in node_map.items():
            inp = node.get("inputState")
            if inp and inp in out_to_id:
                pred_id = out_to_id[inp]
                new_layer = layers[pred_id] + 1
                if new_layer > layers[nid]:
                    layers[nid] = new_layer
                    changed = True

    # Group by layer
    layer_groups: dict[int, list[str]] = {}
    for nid, layer in layers.items():
        layer_groups.setdefault(layer, []).append(nid)

    layout: list[dict] = []
    for layer_idx in sorted(layer_groups):
        for row_idx, nid in enumerate(layer_groups[layer_idx]):
            layout.append({
                "id": nid,
                "x": X0 + layer_idx * VX,
                "y": Y0 + row_idx * VY,
            })

    return layout
