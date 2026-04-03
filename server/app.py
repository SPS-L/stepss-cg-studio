"""CG-Studio FastAPI backend."""
import json
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import aiofiles

from dsl_parser import parse_dsl
from dsl_emitter import emit_dsl

ROOT = Path(__file__).parent
FRONTEND = ROOT.parent / "frontend"
CONFIG_PATH = ROOT / "config.json"

app = FastAPI(title="CG-Studio", version="0.1.0")


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# Serve frontend static files
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND / "index.html"))


# ---------------------------------------------------------------------------
# Block catalogue
# ---------------------------------------------------------------------------
@app.get("/blocks")
async def get_blocks():
    blocks_path = FRONTEND / "blocks.json"
    async with aiofiles.open(blocks_path) as f:
        return json.loads(await f.read())


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@app.get("/config")
async def get_config():
    return _load_config()


class ConfigUpdate(BaseModel):
    codegen_path: str = ""
    workspace: str = ""


@app.put("/config")
async def update_config(body: ConfigUpdate):
    _save_config(body.model_dump())
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Parse DSL text -> ModelProject JSON
# ---------------------------------------------------------------------------
class ParseRequest(BaseModel):
    dsl_text: str


@app.post("/parse")
async def parse_endpoint(req: ParseRequest):
    try:
        project = parse_dsl(req.dsl_text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return project


# ---------------------------------------------------------------------------
# Emit ModelProject JSON -> DSL text
# ---------------------------------------------------------------------------
class EmitRequest(BaseModel):
    project: dict


@app.post("/emit")
async def emit_endpoint(req: EmitRequest):
    try:
        dsl_text = emit_dsl(req.project)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"dsl_text": dsl_text}


# ---------------------------------------------------------------------------
# Run codegen binary -> .f90
# ---------------------------------------------------------------------------
class CodegenRequest(BaseModel):
    dsl_text: str
    model_type: str
    model_name: str


@app.post("/run_codegen")
async def run_codegen(req: CodegenRequest):
    cfg = _load_config()
    codegen_bin = cfg.get("codegen_path", "").strip()
    if not codegen_bin:
        raise HTTPException(
            status_code=400,
            detail="codegen binary path is not configured. Set it via PUT /config.",
        )
    if not Path(codegen_bin).exists():
        raise HTTPException(
            status_code=400,
            detail=f"codegen binary not found at: {codegen_bin}",
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dsl_file = tmp_path / f"{req.model_name}.txt"
        dsl_file.write_text(req.dsl_text, encoding="utf-8")

        result = subprocess.run(
            [codegen_bin, f"-t{dsl_file}"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        f90_name = f"{req.model_type}_{req.model_name}.f90"
        f90_path = tmp_path / f90_name
        f90_text = f90_path.read_text(encoding="utf-8") if f90_path.exists() else ""

    return {
        "f90_text": f90_text,
        "f90_filename": f90_name,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8765, reload=True)
