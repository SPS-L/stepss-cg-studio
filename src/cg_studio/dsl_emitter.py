"""
dsl_emitter.py
==============
Serialises a ModelProject dict back to a valid CODEGEN DSL .txt string.

The %models section is emitted in the ORDER the blocks appear in the
project["blocks"] list.  The canvas topological sort (Phase 2) should
reorder that list before calling emit_dsl().
"""

from __future__ import annotations
import json
import os
import re
from typing import Any


def _load_blocks(blocks_path: str | None = None) -> dict[str, Any]:
    if blocks_path is None:
        import importlib.resources
        ref = importlib.resources.files("cg_studio") / "frontend" / "blocks.json"
        with importlib.resources.as_file(ref) as p:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    with open(blocks_path, encoding="utf-8") as fh:
        return json.load(fh)


def emit_dsl(project: dict[str, Any], blocks_path: str | None = None) -> str:
    """Convert ModelProject dict -> DSL .txt string."""
    blocks_catalogue = _load_blocks(blocks_path)
    out: list[str] = []

    # -- Header ---------------------------------------------------------------
    out.append(project["modelType"])
    out.append(project["modelName"])
    out.append("")

    # -- %data ----------------------------------------------------------------
    out.append("%data")
    out.append("")
    for d in project.get("data", []):
        line = d["name"]
        if d.get("comment"):
            line = f"{line}  ! {d['comment']}"
        out.append(line)
    out.append("")

    # -- %parameters ----------------------------------------------------------
    out.append("%parameters")
    out.append("")
    for p in project.get("parameters", []):
        suffix = "  &" if p.get("continuation") else ""
        out.append(f"{p['name']:<16} = {p['expr']}{suffix}")
    out.append("")

    # -- %states --------------------------------------------------------------
    out.append("%states")
    out.append("")
    for s in project.get("states", []):
        line = f"{s['name']:<16} = {s['initExpr']}"
        if s.get("comment"):
            line = f"{line}  ! {s['comment']}"
        out.append(line)
    out.append("")

    # -- %observables ---------------------------------------------------------
    out.append("%observables")
    out.append("")
    for obs in project.get("observables", []):
        out.append(obs)
    out.append("")

    # -- %models --------------------------------------------------------------
    out.append("%models")
    out.append("")
    for block in project.get("blocks", []):
        block_name = block["blockType"]
        comment = block.get("comment", "")
        comment_col = f"  {comment}" if comment else ""
        out.append(f"& {block_name}{comment_col}")

        block_def = blocks_catalogue.get(block_name)
        if block_def is None:
            for raw in block.get("rawArgLines", []):
                out.append(raw)
            continue

        dsl_line_templates = block_def.get("dsl_lines", [])
        input_states = block.get("inputStates", [])
        output_state = block.get("outputState", "")
        args = block.get("args", {})

        for tmpl in dsl_line_templates:
            if tmpl == "{{input}}":
                out.append(input_states[0] if input_states else "")
            elif tmpl == "{{output}}":
                out.append(output_state)
            elif tmpl == "{{inputs}}":
                for inp in input_states:
                    out.append(inp)
            else:
                m = re.search(r"\{\{(\w+)\}\}", tmpl)
                if m:
                    key = m.group(1)
                    out.append(args.get(key, ""))
                else:
                    out.append(tmpl)

    return "\n".join(out) + "\n"
