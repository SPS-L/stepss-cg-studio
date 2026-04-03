"""Emit a CODEGEN DSL .txt string from a ModelProject dict.

Topological sort (Kahn's algorithm) is applied to the nodeMap so that
blocks are emitted in dependency order matching CODEGEN's sequential
evaluation model.
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

_BLOCKS: dict[str, dict] | None = None


def _get_blocks() -> dict[str, dict]:
    global _BLOCKS
    if _BLOCKS is None:
        blocks_path = Path(__file__).parent.parent / "frontend" / "blocks.json"
        with open(blocks_path, encoding="utf-8") as f:
            _BLOCKS = json.load(f)
    return _BLOCKS


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def emit_dsl(project: dict[str, Any]) -> str:
    """Serialize a ModelProject dict to a CODEGEN DSL string."""
    lines: list[str] = []

    model_type = project.get("modelType", "exc")
    model_name = project.get("modelName", "UNNAMED")

    lines.append(model_type)
    lines.append(model_name)
    lines.append("")

    # ------------------------------------------------------------------
    # %data
    # ------------------------------------------------------------------
    lines.append("%data")
    lines.append("")
    for d in project.get("data", []):
        name = d.get("name", "").strip()
        if name:
            lines.append(name)
    lines.append("")

    # ------------------------------------------------------------------
    # %parameters
    # ------------------------------------------------------------------
    lines.append("%parameters")
    lines.append("")
    for p in project.get("parameters", []):
        name = p.get("name", "").strip()
        expr = p.get("expr", "").strip()
        if not name:
            continue
        suffix = "  &" if p.get("continuation") else ""
        lines.append(f"{name:<8} = {expr}{suffix}")
    lines.append("")

    # ------------------------------------------------------------------
    # %states
    # ------------------------------------------------------------------
    lines.append("%states")
    lines.append("")
    for s in project.get("states", []):
        name = s.get("name", "").strip()
        init = s.get("initExpr", "0.").strip()
        if name:
            lines.append(f"{name:<8} = {init}")
    lines.append("")

    # ------------------------------------------------------------------
    # %observables
    # ------------------------------------------------------------------
    lines.append("%observables")
    lines.append("")
    for obs in project.get("observables", []):
        if obs:
            lines.append(obs)
    lines.append("")

    # ------------------------------------------------------------------
    # %models
    # ------------------------------------------------------------------
    lines.append("%models")
    lines.append("")

    node_map: dict[str, dict] = project.get("canvas", {}).get("nodeMap", {})
    if node_map:
        sorted_ids = _topological_sort(node_map)
        blocks = _get_blocks()
        for nid in sorted_ids:
            node = node_map[nid]
            block_type = node.get("blockType", "")
            comment = node.get("comment", "")
            if block_type not in blocks:
                lines.append(f"& {block_type}  ! UNKNOWN BLOCK TYPE")
                continue
            bdef = blocks[block_type]
            header = f"& {block_type}"
            if comment:
                header += f"  {comment}"
            lines.append(header)
            for tpl in bdef["dsl_lines"]:
                lines.append(_resolve_template(tpl, node))
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Template resolution
# ---------------------------------------------------------------------------
def _resolve_template(tpl: str, node: dict) -> str:
    """Substitute {{input}}, {{output}}, {{arg_name}} tokens in a dsl_lines template."""
    val = tpl
    val = val.replace("{{input}}", node.get("inputState") or "")
    val = val.replace("{{output}}", node.get("outputState") or "")
    for arg_name, arg_val in node.get("args", {}).items():
        val = val.replace(f"{{{{{arg_name}}}}}", arg_val)
    return val


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------
def _topological_sort(node_map: dict[str, dict]) -> list[str]:
    """Return node IDs in dependency order.

    An edge exists from node A to node B when A's outputState equals
    B's inputState (or appears in B's extraInputs).

    Nodes not connected to anything are emitted in insertion order
    after all dependency-ordered nodes.
    """
    # Build output->id index
    out_to_id: dict[str, str] = {}
    for nid, node in node_map.items():
        out = node.get("outputState")
        if out:
            out_to_id[out] = nid

    # in-degree and adjacency
    in_degree: dict[str, int] = {nid: 0 for nid in node_map}
    adj: dict[str, list[str]] = {nid: [] for nid in node_map}

    for nid, node in node_map.items():
        deps: list[str] = []
        if node.get("inputState"):
            deps.append(node["inputState"])
        deps.extend(node.get("extraInputs", []))
        for dep_signal in deps:
            pred_id = out_to_id.get(dep_signal)
            if pred_id and pred_id != nid:
                adj[pred_id].append(nid)
                in_degree[nid] += 1

    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    result: list[str] = []

    while queue:
        nid = queue.popleft()
        result.append(nid)
        for succ in adj[nid]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    # Append any remaining (cycle or disconnected) nodes in original order
    emitted = set(result)
    for nid in node_map:
        if nid not in emitted:
            result.append(nid)

    return result
