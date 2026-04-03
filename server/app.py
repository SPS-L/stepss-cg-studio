"""
app.py
======
FastAPI server for the CODEGEN Visual Block Editor.

Start:
    python server/app.py

Endpoints
---------
GET  /              -> serves frontend/index.html
GET  /blocks        -> returns blocks.json catalogue
POST /parse         -> DSL text -> ModelProject JSON
POST /emit          -> ModelProject JSON -> DSL text
POST /run_codegen   -> DSL text -> run codegen binary -> return .f90 text
GET  /config        -> current config.json
PUT  /config        -> update config.json
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# -- Paths -------------------------------------------------------------------
HERE = Path(__file__).parent
ROOT = HERE.parent
FRONTEND_DIR = ROOT / "frontend"
CONFIG_PATH = HERE / "config.json"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"codegen_path": "codegen", "workspace_dir": "workspace",
            "host": "127.0.0.1", "port": 8765}


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# -- FastAPI app -------------------------------------------------------------
app = FastAPI(
    title="CODEGEN Visual Block Editor",
    description="STEPSS CODEGEN DSL visual editor backend",
    version="1.0.0",
)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


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


# -- Routes ------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def serve_index():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"status": "CODEGEN Visual Block Editor API",
                         "docs": "/docs",
                         "note": "Frontend not yet built (Phase 2). Use /docs for API."})


@app.get("/blocks")
async def get_blocks():
    """Return the full block catalogue from frontend/blocks.json."""
    blocks_path = FRONTEND_DIR / "blocks.json"
    if not blocks_path.exists():
        raise HTTPException(status_code=404, detail="blocks.json not found")
    return JSONResponse(content=json.loads(blocks_path.read_text(encoding="utf-8")))


@app.post("/parse")
async def parse_dsl(req: ParseRequest):
    """Parse CODEGEN DSL text -> ModelProject JSON."""
    from dsl_parser import parse_dsl as _parse
    try:
        result = _parse(req.dsl_text)
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/emit")
async def emit_dsl(req: EmitRequest):
    """Convert ModelProject JSON -> DSL .txt string."""
    from dsl_emitter import emit_dsl as _emit
    try:
        dsl_text = _emit(req.project)
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
    codegen_bin = cfg.get("codegen_path", "codegen")

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
                [codegen_bin, f"-t{dsl_path}"],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail=f"codegen binary not found at: {codegen_bin!r}. "
                       "Update the path in server/config.json.",
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


# -- Entry point -------------------------------------------------------------
if __name__ == "__main__":
    import sys
    cfg = _load_config()
    sys.path.insert(0, str(HERE))
    uvicorn.run(
        "app:app",
        host=cfg.get("host", "127.0.0.1"),
        port=cfg.get("port", 8765),
        reload=True,
        reload_dirs=[str(HERE)],
        app_dir=str(HERE),
    )
