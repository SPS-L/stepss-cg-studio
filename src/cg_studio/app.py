"""
app.py
======
FastAPI server for the CODEGEN Visual Block Editor.

Start:
    cg-studio
    python -m cg_studio

Endpoints
---------
GET  /              -> serves frontend/index.html  (via StaticFiles html=True)
GET  /favicon.ico   -> returns frontend/favicon.svg (suppresses browser 404)
GET  /blocks        -> returns blocks.json catalogue
POST /parse         -> DSL text -> ModelProject JSON
POST /emit          -> ModelProject JSON -> DSL text
POST /run_codegen   -> DSL text -> run codegen binary -> return .f90 text
GET  /config        -> current config.json
PUT  /config        -> update config.json

Static serving strategy
-----------------------
FastAPI processes routes in registration order.  All API routes are registered
first.  The StaticFiles mount is added LAST at "/" with html=True so that:
  - /blocks, /parse, /emit, /run_codegen, /config  ->  handled by API routes
  - /css/style.css, /js/main.js, /blocks.json       ->  served from frontend/
  - /  (or any unknown path)                         ->  falls back to index.html
"""

from __future__ import annotations

import importlib.resources
import json
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cg_studio.config import load_config as _load_config, save_config as _save_config, resolve_codegen as _resolve_codegen
from cg_studio.dsl_parser import parse_dsl as _parse, MANDATORY_OUTPUTS
from cg_studio.dsl_emitter import emit_dsl as _emit

# -- Paths -------------------------------------------------------------------
_PKG_FILES = importlib.resources.files("cg_studio")
FRONTEND_DIR = _PKG_FILES / "frontend"


# -- FastAPI app -------------------------------------------------------------
app = FastAPI(
    title="CODEGEN Visual Block Editor",
    description="STEPSS CODEGEN DSL visual editor backend",
    version="1.0.0",
)


# -- Pydantic models ---------------------------------------------------------
class ParseRequest(BaseModel):
    dsl_text: str

class EmitRequest(BaseModel):
    project: dict

class RunCodegenRequest(BaseModel):
    dsl_text: str
    model_type: str = ""
    model_name: str = ""

class ConfigUpdateRequest(BaseModel):
    codegen_path: str | None = None
    workspace_dir: str | None = None
    host: str | None = None
    port: int | None = None


# -- API routes (must be registered BEFORE the static catch-all) -------------

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return favicon.svg for browsers that always request /favicon.ico."""
    with importlib.resources.as_file(_PKG_FILES / "frontend" / "favicon.svg") as favicon_path:
        if favicon_path.exists():
            return FileResponse(str(favicon_path), media_type="image/svg+xml")
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get("/blocks")
async def get_blocks():
    """Return the full block catalogue from frontend/blocks.json."""
    with importlib.resources.as_file(_PKG_FILES / "frontend" / "blocks.json") as blocks_path:
        if not blocks_path.exists():
            raise HTTPException(status_code=404, detail="blocks.json not found")
        return JSONResponse(content=json.loads(blocks_path.read_text(encoding="utf-8")))


@app.get("/mandatory_outputs")
async def get_mandatory_outputs():
    """Return mandatory output states per model type."""
    return JSONResponse(content=MANDATORY_OUTPUTS)


@app.post("/parse")
async def parse_dsl(req: ParseRequest):
    """Parse CODEGEN DSL text -> ModelProject JSON."""
    try:
        result = _parse(req.dsl_text)
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _normalise_project(proj: dict) -> dict:
    """Translate frontend store shape -> backend emitter shape if needed."""
    if "modelType" in proj:
        return proj  # already backend shape
    out = dict(proj)
    out["modelType"] = proj.get("model_type", "exc")
    out["modelName"] = proj.get("model_name", "my_model")
    # Convert models[] (frontend) -> blocks[] (backend)
    fe_models = proj.get("models", [])
    wires = proj.get("wires", [])
    blocks = []
    for m in fe_models:
        # Build inputStates from wires targeting this model
        n_inputs = len(m.get("inputs", []))
        input_states = [""] * n_inputs
        for w in wires:
            if w.get("to_node") == m.get("id"):
                port = w.get("to_port", "input_1")
                idx = int(port.replace("input_", "")) - 1 if port.startswith("input_") else 0
                if 0 <= idx < n_inputs:
                    input_states[idx] = w.get("signal_name", "")
        blocks.append({
            "blockType": m.get("block_type", ""),
            "outputState": (m.get("outputs") or [""])[0],
            "inputStates": input_states,
            "args": m.get("args", {}),
            "comment": m.get("comment", ""),
            "rawArgLines": m.get("rawArgLines", []),
        })
    out["blocks"] = blocks
    # Normalise states initExpr
    out["states"] = [
        {**s, "initExpr": s.get("initExpr", s.get("init", ""))}
        for s in proj.get("states", [])
    ]
    # Observables: backend expects list of strings
    obs = proj.get("observables", [])
    if obs and isinstance(obs[0], dict):
        out["observables"] = [o.get("name", "") for o in obs]
    return out


@app.post("/emit")
async def emit_dsl(req: EmitRequest):
    """Convert ModelProject JSON -> DSL .txt string."""
    try:
        dsl_text = _emit(_normalise_project(req.project))
        return JSONResponse(content={"dsl_text": dsl_text})
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/run_codegen")
async def run_codegen(req: RunCodegenRequest):
    """
    Save DSL text to a temp file, invoke the codegen binary, return .f90 text.
    The codegen binary is called as: codegen -t<path_to_dsl_file>
    """
    cfg = _load_config()
    codegen_bin = _resolve_codegen(cfg.get("codegen_path", "bundled"))
    if codegen_bin is None:
        import platform as _plat
        if _plat.system() == "Darwin":
            detail = ("CODEGEN binary is not yet available for macOS. "
                      "Please provide your own binary via Settings "
                      "(gear icon) > Codegen binary path.")
        else:
            detail = ("CODEGEN binary not found. Reinstall stepss-cg-studio "
                      "with pip or set the path in Settings.")
        raise HTTPException(status_code=500, detail=detail)

    lines = [l.strip() for l in req.dsl_text.splitlines() if l.strip()]
    model_type = req.model_type or (lines[0] if lines else "exc")
    model_name = req.model_name or (lines[1] if len(lines) > 1 else "model")
    dsl_filename = f"{model_name}.txt"
    f90_filename = f"{model_type}_{model_name}.f90"

    with tempfile.TemporaryDirectory() as tmp_dir:
        dsl_path = Path(tmp_dir) / dsl_filename
        dsl_path.write_text(req.dsl_text, encoding="utf-8")

        try:
            result = subprocess.run(
                [str(codegen_bin), f"-t{dsl_path}"],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail=f"codegen binary not found at: {str(codegen_bin)!r}. "
                       "Update the path in Settings (gear icon).",
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=500, detail="codegen timed out after 30 s")

        f90_path = Path(tmp_dir) / f90_filename
        f90_text = f90_path.read_text(encoding="utf-8") if f90_path.exists() else ""

        return JSONResponse(content={
            "f90_text": f90_text,
            "f90_filename": f90_filename,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0 and bool(f90_text),
        })


@app.get("/config")
async def get_config():
    return JSONResponse(content=_load_config())


@app.put("/config")
async def update_config(req: ConfigUpdateRequest):
    cfg = _load_config()
    if req.codegen_path is not None:
        cfg["codegen_path"] = req.codegen_path
    if req.workspace_dir is not None:
        cfg["workspace_dir"] = req.workspace_dir
    if req.host is not None:
        cfg["host"] = req.host
    if req.port is not None:
        cfg["port"] = req.port
    _save_config(cfg)
    return JSONResponse(content={"status": "ok", "config": cfg})


# -- Static file serving (MUST be last — catches everything else) ------------
# html=True makes StaticFiles serve index.html for unknown paths (SPA fallback).
_frontend_ctx = importlib.resources.as_file(FRONTEND_DIR)
_frontend_path = _frontend_ctx.__enter__()
app.mount("/", StaticFiles(directory=str(_frontend_path), html=True), name="frontend")


# -- Entry point -------------------------------------------------------------
if __name__ == "__main__":
    from cg_studio.cli import main
    main()
