# CODEGEN Visual Block Editor — Full Design Plan

## Overview

This document describes the complete design for `cg-studio`, a browser-based drag-and-drop block diagram editor that generates and parses CODEGEN DSL `.txt` files for RAMSES user-defined device models. The tool is backed by a lightweight Python local server, enabling direct shell-out to `codegen.exe` / `codegen` for `.f90` generation in one click.

**Project codename:** `cg-studio`  
**Repository:** `SPS-L/stepss-cg-studio`  
**License:** MIT

---

## Architecture Decision Summary

| Concern | Decision | Rationale |
|---------|----------|-----------|
| Deployment | Local Python server (`python app.py`) | Enables live codegen→f90 shell-out; trivially cross-platform; no packaging overhead |
| Frontend framework | Vanilla JS + [Drawflow](https://github.com/jerosoler/Drawflow) | Zero-dependency drag-and-drop graph library, MIT licensed |
| Backend | FastAPI (Python ≥ 3.10) | Single-file server, async, subprocess support; `pip install fastapi uvicorn` |
| Users | PhD/MSc students + power users | Structured forms + validation; raw DSL preview always visible |
| Signal wiring | Named-port / autocomplete | Each block port carries the state variable name; matches DSL semantics |
| Section split | Canvas = `%models`; forms = everything else | `%parameters` contains free-form algebraic expressions |
| `algeq` on canvas | Formula node with one output port | Preserves signal-flow topology |
| Block catalogue | `blocks.json` (hand-maintained) | Adding a new block = one JSON entry, no code change |
| Persistence | `.cgproj` JSON file | Stores canvas layout + full DSL model data |

---

## Technology Stack

### Backend (`server/`)
- **Python ≥ 3.10** with `fastapi`, `uvicorn`, `aiofiles`
- `subprocess.run()` to invoke `codegen` binary (path in `config.json`)
- Serves frontend static files at `/`

### Frontend (`frontend/`)
- **HTML + CSS + Vanilla JS** — no build step
- **[Drawflow](https://github.com/jerosoler/Drawflow)** — block-diagram canvas (MIT)
- **[CodeMirror 6](https://codemirror.net/)** — DSL preview with syntax highlighting (MIT)
- **[Pico CSS](https://picocss.com/)** — minimal classless styling (MIT)

---

## Internal Model Data Structure (`.cgproj` schema)

```json
{
  "version": 1,
  "modelType": "exc",
  "modelName": "ST1A",
  "data": [
    {"name": "KA", "comment": "AVR gain"},
    {"name": "TA", "comment": "AVR time constant"}
  ],
  "parameters": [
    {"name": "VREF", "expr": "vcomp([v],[p],[q],{Kv},{Rc},{Xc})+([vf]/{KA})", "continuation": true}
  ],
  "states": [
    {"name": "Vc",  "initExpr": "vcomp([v],[p],[q],{Kv},{Rc},{Xc})"},
    {"name": "VA",  "initExpr": "[vf]"}
  ],
  "observables": ["VA", "vf"],
  "canvas": {
    "drawflow": {},
    "nodeMap": {
      "node_1": {"blockType": "tf1p", "comment": "voltage measurement",
                 "inputState": "Vc1", "outputState": "Vc",
                 "args": {"gain": "1.d0", "T": "{TR}"}},
      "node_2": {"blockType": "lim", "comment": "deltaV limiter",
                 "inputState": "deltaV", "outputState": "V1",
                 "args": {"lo": "{VIMIN}", "hi": "{VIMAX}"}}
    }
  }
}
```

---

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves `frontend/index.html` |
| `GET` | `/blocks` | Returns `blocks.json` catalogue |
| `POST` | `/parse` | DSL text → ModelProject JSON |
| `POST` | `/emit` | ModelProject JSON → DSL text |
| `POST` | `/run_codegen` | Saves DSL, shells to codegen, returns `.f90` |
| `GET` | `/config` | Read `config.json` |
| `PUT` | `/config` | Update `config.json` |

---

## UI Layout

```
┌────────────────────────────────────────────────────────────────┐
│  Header: [Model Type ▼] [Model Name] [New][Open][Save][Export DSL][Run Codegen]  │
├──────────┬──────────────────────────────────┬─────────────────┐
│  Block   │                                  │  DSL Preview   │
│  Palette │        Canvas (Drawflow)          │  (CodeMirror)  │
│          │                                  │                │
│ ▶ TFs    │  ┌────┐    ┌────┐    ┌──────┐   │  exc           │
│   tf1p   │  │algeq├──▶│tf1p├──▶│tf1plim│  │  ST1A          │
│ ▶ Limits │  └────┘    └────┘    └──────┘   │  %data ...     │
│ ▶ PI/PID │                                  │  %models ...   │
├──────────┴──────────────────────────────────┤                │
│  Properties Panel (selected node)           │                │
│  Block: tf1p  State name: [Vc]              │                │
│  Gain K: [1.d0]   Time const T: [{TR}]       └────────────────┘
├────────────────────────────────────────────────────────┘
│  Tabs: [%data] [%parameters] [%states] [%observables]        │
└────────────────────────────────────────────────────────┘
```

---

## Model Type — RAMSES Interface Variables

| Model | RAMSES Inputs | Mandatory Output(s) |
|-------|--------------|---------------------|
| `exc` | `v`, `p`, `q`, `omega`, `if`, `vf` | `vf` |
| `tor` | `p`, `omega`, `tm` | `tm` |
| `inj` | `omega`, `vx`, `vy`, `ix`, `iy` | `ix`, `iy` |
| `twop` | `omega1`, `omega2`, `vx1`, `vy1`, `vx2`, `vy2`, `ix1`, `iy1`, `ix2`, `iy2` | `ix1`, `iy1`, `ix2`, `iy2` |

---

## Validation Rules

- State name uniqueness across all nodes
- Reserved name check (RAMSES input variables per model type)
- Mandatory output coverage per model type (`vf`, `tm`, `ix`+`iy`, `ix1`+`iy1`+`ix2`+`iy2`)
- `f_inj` / `f_twop_bus*` blocks only available for the correct model type
- Data/state/parameter name collision check
- Equation balance: `n_equations == n_states`
- Topological sort succeeds (no wired cycles)

---

## Build Roadmap

### Phase 1 — Foundation
- [x] `dsl_parser.py` with tests
- [x] `dsl_emitter.py` with tests
- [x] `blocks.json` full catalogue
- [x] FastAPI server skeleton with all endpoints
- [ ] Drawflow canvas + block palette
- [ ] Drag-drop placement with auto-named ports

### Phase 2 — Core Authoring
- [ ] Wire connections + port-name synchronisation
- [ ] Properties Panel
- [ ] Live DSL preview (CodeMirror)
- [ ] `%data` / `%states` / `%observables` form tabs
- [ ] Client-side validation

### Phase 3 — Import & Codegen Integration
- [ ] Canvas auto-layout from parsed blocks (topological / Sugiyama)
- [ ] “Open DSL” button (file picker → parse → canvas)
- [ ] `/run_codegen` integration + config UI
- [ ] `.cgproj` save/load

### Phase 4 — Polish
- [ ] RAMSES input terminal nodes on canvas edge
- [ ] Undo/redo stack
- [ ] Bundled example projects
- [ ] Full README + screenshots
