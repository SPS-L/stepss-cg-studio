# STEPSS CG Studio — Full Design Plan

> **Repository:** [SPS-L/stepss-cg-studio](https://github.com/SPS-L/stepss-cg-studio)
> **Developed by:** [Sustainable Power Systems Lab (SPS-L)](https://sps-lab.org), Cyprus University of Technology
> **Online documentation:** [https://stepss.sps-lab.org](https://stepss.sps-lab.org)

---

## 1. Project Overview

**STEPSS CG Studio** is a browser-based, drag-and-drop visual editor for assembling RAMSES user-defined device models using the [STEPSS CODEGEN DSL](https://stepss.sps-lab.org/developer/user-models/).

Users build models by connecting blocks on a canvas. The tool generates valid CODEGEN `.txt` DSL files behind the scenes, and can invoke the `codegen` binary to produce `.f90` Fortran 2003 source ready to compile into RAMSES.

### Supported model types

| Type | RAMSES role | Mandatory output states |
|------|-------------|------------------------|
| `exc` | Excitation controller | `vf` |
| `tor` | Torque controller | `tm` |
| `inj` | Current injector | `ix`, `iy` |
| `twop` | Two-port component | `ix1`, `iy1`, `ix2`, `iy2` |

---

## 2. Design Decisions

These decisions were made before implementation and drive the architecture throughout.

| # | Question | Decision |
|---|----------|----------|
| 1 | **Deployment target** | Local Python server (`python server/app.py`) — enables live "Run Codegen" round-trip via subprocess |
| 2 | **Primary users** | Both experienced developers and students — welcoming UI, but no-overhead for power users |
| 3 | **Block wiring model** | Named wire / port approach — each block has named input/output ports; connecting writes the signal name |
| 4 | **`%parameters` editing** | Structured table forms for all metadata sections; canvas only covers `%models` |
| 5 | **Block catalogue extensibility** | `frontend/blocks.json` — add one JSON entry per new block; no code changes |
| 6 | **`algeq` representation** | Special formula node on canvas with typed expression field and one implicit output port |
| 7 | **Persistence format** | `.cgproj` JSON file containing canvas positions + full ModelProject data (lossless round-trip) |

---

## 3. Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Backend API | FastAPI + uvicorn | Fast async Python, auto-docs at `/docs`, zero config |
| DSL parse/emit | Pure Python (`dsl_parser.py`, `dsl_emitter.py`) | No extra dependencies |
| Canvas | [Drawflow](https://github.com/jerosoler/Drawflow) (MIT, CDN) | Drag-drop node graph, zero-build JS |
| DSL preview | [CodeMirror 6](https://codemirror.net/) (MIT, CDN) | Syntax highlighting, minimal footprint |
| Right-panel forms | Vanilla JS + HTML5 | No framework overhead |
| State store | In-memory JS object (`store.js`) | ModelProject JSON mirrors backend |
| Tests | pytest + httpx | Standard Python test runner + FastAPI TestClient |
| CI | GitHub Actions | Runs pytest on push/PR, Python 3.10–3.12 |

### Deployment

- Run: `python server/app.py` → `http://localhost:8765`
- Frontend served as static files from `frontend/`
- `codegen` binary called via `subprocess`; path set in `server/config.json`
- Platform: Windows / Linux / macOS (RAMSES itself runs on Windows 64-bit only)

---

## 4. Repository Structure

```
stepss-cg-studio/
├── .github/
│   └── workflows/
│       └── ci.yml              # pytest on push/PR, Python 3.10–3.12
├── server/
│   ├── app.py                  # FastAPI server (entry point)
│   ├── dsl_parser.py           # DSL .txt → ModelProject dict
│   ├── dsl_emitter.py          # ModelProject dict → DSL .txt
│   └── config.json             # codegen binary path, host, port
├── frontend/
│   ├── index.html              # Single-page app shell (3-column layout)
│   ├── css/
│   │   └── style.css           # Dark-theme stylesheet, Drawflow node overrides
│   ├── js/
│   │   ├── main.js             # App bootstrap + all toolbar button handlers
│   │   ├── canvas.js           # Drawflow wrapper + Sugiyama auto-layout
│   │   ├── palette.js          # Block palette (grouped, searchable, drag-enable)
│   │   ├── forms.js            # Right-panel tabbed forms (meta/data/params/states/block)
│   │   ├── dsl_preview.js      # Debounced live DSL preview with syntax highlight
│   │   ├── store.js            # ModelProject state, Kahn topo-sort, undo/redo (60 steps)
│   │   └── api.js              # fetch() wrappers for all backend endpoints
│   └── blocks.json             # Block catalogue — extend here for new blocks
├── examples/
│   ├── ENTSOE_simp_exc.txt     # Example EXC DSL (PSS + AVR chain)
│   └── ENTSOE_simp_tor.txt     # Example TOR DSL (governor chain)
├── tests/
│   ├── __init__.py
│   ├── test_parser.py          # 25 pytest tests (parse + emit + blocks.json)
│   └── test_api.py             # FastAPI integration tests (TestClient, ~50 tests)
├── docs/
│   └── DESIGN.md               # This document
├── requirements.txt
├── run.bat                     # Windows launcher
└── run.sh                      # Linux/macOS launcher
```

---

## 5. Data Model

### 5.1 ModelProject JSON Schema

The canonical in-memory and on-disk representation shared between frontend and backend.

```json
{
  "version": 1,
  "modelType": "exc | tor | inj | twop",
  "modelName": "string",
  "data": [
    { "name": "TA", "comment": "" }
  ],
  "parameters": [
    { "name": "Vo", "expr": "v+(vf/{KE})+([vf]/{KA})", "continuation": true }
  ],
  "states": [
    { "name": "avr1", "initExpr": "vf/{KE}", "comment": "" }
  ],
  "observables": ["vf", "dvpss"],
  "blocks": [
    {
      "id": 1,
      "blockType": "tf1plim",
      "comment": "AVR first stage",
      "args": { "K": "1.", "T": "{TA}", "lo": "{EMIN}", "hi": "{EMAX}" },
      "inputStates": ["avr2"],
      "outputState": "vf",
      "rawArgLines": []
    }
  ],
  "canvas": {
    "nodeMap": { "1": { "x": 300, "y": 150 } },
    "drawflow": {}
  },
  "errors": []
}
```

**Field notes:**
- `rawArgLines` — preserved verbatim for unknown block types during import, so no DSL is lost.
- `canvas.drawflow` — Drawflow's internal serialisation (stored for exact restore).
- `canvas.nodeMap` — lightweight `{blockId → {x, y}}` for position-only queries.
- `errors` — non-fatal parse warnings; surfaced in the UI error badge.

### 5.2 Project File Format (`.cgproj`)

```json
{
  "format": "cgproj-v1",
  "savedAt": "2026-04-04T00:00:00Z",
  "project": { "<ModelProject JSON as above>" }
}
```

`.f90` files are **export only** — they cannot be imported.

---

## 6. Block Catalogue (`frontend/blocks.json`)

### Schema

```json
{
  "blockname": {
    "label":       "Human-readable name",
    "category":    "Transfer Functions | Limiters | Controllers | ...",
    "description": "Tooltip text shown in sidebar and Props tab",
    "inputs":      ["u"],
    "outputs":     ["y"],
    "color":       "#2563eb",
    "model_types": ["exc","tor","inj","twop"],
    "dsl_lines": [
      "{{input}}",
      "{{output}}",
      "{{K}}",
      "{{T}}"
    ],
    "args": [
      {
        "name":    "K",
        "label":   "Gain K",
        "type":    "expr | state",
        "default": "1."
      }
    ]
  }
}
```

### DSL Line Template Tokens

| Token | Meaning |
|-------|---------|
| `{{input}}` | Single input signal (state name or RAMSES var) |
| `{{output}}` | Output signal name (state) |
| `{{inputs}}` | Multi-input: one line per input signal |
| `{{NAME}}` | Named argument — value stored in `args["NAME"]` |

### Block Categories (current)

| Category | Blocks |
|----------|--------|
| Algebraic | `algeq` |
| Transfer Functions | `tf1p`, `tf1plim`, `tf1pvlim`, `tf1p1z`, `tf2p2z`, `tfder1p` |
| Limiters | `lim`, `limvb`, `inlim`, `invlim` |
| Controllers | `int`, `pictl`, `pictllim`, `pictl2lim`, `pictlieee` |
| Min/Max/Gates | `max2v`, `max1v1c`, `min2v`, `min1v1c` |
| Nonlinear | `abs`, `db`, `hyst`, `nint`, `swsign`, `switch2–5`, `pwlin3–6` |
| Timers | `timer1–5`, `tsa` |
| Power System | `f_inj`, `f_twop_bus1`, `f_twop_bus2` |

**Total: 51 blocks.** Add new blocks by appending entries to `blocks.json` — no JavaScript or Python changes required.

---

## 7. Backend Architecture

### 7.1 API Endpoints

| Method | Path | Request body | Response |
|--------|------|-------------|----------|
| `GET` | `/` | — | `index.html` |
| `GET` | `/blocks` | — | `blocks.json` catalogue |
| `POST` | `/parse` | `{ "dsl_text": "..." }` | ModelProject JSON |
| `POST` | `/emit` | `{ "project": {...} }` | `{ "dsl_text": "..." }` |
| `POST` | `/run_codegen` | `{ "dsl_text": "...", "model_type": "...", "model_name": "..." }` | `{ "f90_text", "f90_filename", "stdout", "stderr", "returncode", "success" }` |
| `GET` | `/config` | — | current `config.json` |
| `PUT` | `/config` | partial config fields | updated `config.json` |

Auto-generated Swagger UI at `http://localhost:8765/docs`.

### 7.2 DSL Parser (`server/dsl_parser.py`)

**Entry point:** `parse_dsl(text: str) -> dict`

Parse sequence:
1. Extract model type (line 1) and model name (line 2)
2. Split remaining lines into sections by `%data`, `%parameters`, `%states`, `%observables`, `%models` markers
3. Parse each section independently:
   - `%data` → list of `{name, comment}`
   - `%parameters` → list of `{name, expr, continuation}` — handles trailing `&` for multi-line display
   - `%states` → list of `{name, initExpr, comment}` — inline `!` comment stripping
   - `%observables` → list of signal name strings
   - `%models` → `_parse_blocks()` (see below)

**`_parse_blocks()` — key algorithm:**
- Scans for lines starting with `&`
- Looks up the block name in `blocks.json` to determine `len(dsl_lines)` — i.e. how many positional argument lines to consume
- Maps each arg line to the corresponding `{{TOKEN}}` in `dsl_lines`, populating `inputStates`, `outputState`, and `args`
- Unknown blocks: emit a warning to `errors[]`, skip to the next `&` line, preserve `rawArgLines`

### 7.3 DSL Emitter (`server/dsl_emitter.py`)

**Entry point:** `emit_dsl(project: dict) -> str`

Emits sections in canonical order: header → `%data` → `%parameters` → `%states` → `%observables` → `%models`.

For `%models`, blocks are emitted in the **list order** of `project["blocks"]`. The frontend's topological sort (Kahn's algorithm in `store.js`) must reorder this list before calling `/emit`.

For each block, the emitter reverse-maps `inputStates`/`outputState`/`args` back into the `dsl_lines` template sequence. Unknown blocks fall back to `rawArgLines`.

### 7.4 `codegen` Subprocess (`/run_codegen`)

1. Write `dsl_text` to a temp file `<model_name>.txt` in a `tempfile.TemporaryDirectory()`
2. Invoke: `codegen -t<path_to_dsl_file>`
3. Read `<model_type>_<model_name>.f90` from the same temp dir
4. Return `f90_text`, `stdout`, `stderr`, `returncode`
5. On `FileNotFoundError` → HTTP 500 with instructions to set `codegen_path` in `config.json`

---

## 8. Frontend Architecture

### 8.1 UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  TOOLBAR: New | Load DSL .txt | Load Project | Save DSL |        │
│           ▶ Run Codegen | Save Project | Undo | Redo             │
├──────────────┬──────────────────────────────┬───────────────────┤
│              │                              │  [Model] tab       │
│   SIDEBAR    │                              │  modelType         │
│              │        CANVAS                │  modelName         │
│  Block       │     (Drawflow)               │  observables       │
│  palette     │                              ├───────────────────┤
│  grouped by  │   drag-drop-connect          │  [Data] tab        │
│  category    │   block nodes                │  %data table       │
│              │                              ├───────────────────┤
│  [search]    │                              │  [Params] tab      │
│              │                              │  %parameters table │
│              │                              ├───────────────────┤
│              │                              │  [States] tab      │
│              │                              │  %states table     │
│              │                              ├───────────────────┤
│              │                              │  [Block] tab       │
│              │                              │  selected block    │
│              │                              │  args form         │
├──────────────┴──────────────────────────────┴───────────────────┤
│  Live DSL Preview (syntax-highlighted)               ⚠ Errors   │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 JS Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `store.js` | Canonical `ModelProject` state; Kahn's topological sort; undo/redo ring buffer (60 steps); event bus for cross-module updates |
| `api.js` | `fetch()` wrappers for all backend endpoints; error normalisation |
| `canvas.js` | Drawflow initialisation; drag-from-sidebar; port connection → signal name assignment; Sugiyama auto-layout for DSL import |
| `palette.js` | Renders block palette grouped by category; live search filter; drag-start handler |
| `forms.js` | Right-panel tabs: model meta, data table, params table, states table, block props form |
| `dsl_preview.js` | Debounced (600 ms) live DSL re-render on every `store` change; copy-to-clipboard; syntax highlight |
| `main.js` | App bootstrap; toolbar button handlers (New, Load DSL, Load Project, Save DSL, Save Project, Run Codegen); Ctrl+Z/Y/S keyboard shortcuts; file I/O (`FileReader`, `Blob` download); Settings modal wired to `GET/PUT /config`; toast notifications |

### 8.3 Canvas Interaction Model

- **Drag from sidebar** → drop on canvas → Drawflow creates a node; `store.js` adds a block entry
- **Connect output port → input port** → sets `inputStates[0]` of target block = `outputState` of source block; auto-generates state name `<blockType><id>` (e.g. `tf1p3`), editable in Block tab
- **Double-click node** → activates Block tab, renders `args` form for that block
- **Right-click → Delete** → removes node, its wires, and the block from `store.js`
- **Multi-input blocks** (`max2v`, `min2v`, `switch2`–`switch5`) render N left-side ports

### 8.4 Signal Name Resolution

Signal identifiers are plain strings in `ModelProject`. Notation conventions:

| DSL text | Stored in ModelProject | Emitter output |
|----------|----------------------|----------------|
| `[omega]` | `"omega"` | `[omega]` |
| `{KE}` | `"{KE}"` | `{KE}` (verbatim) |
| `avr2` (state) | `"avr2"` | `avr2` |

The emitter wraps RAMSES built-in variable names in `[...]` when it encounters them in `inputStates`. The frontend autocomplete for port connections offers: declared states + RAMSES inputs for the current model type.

### 8.5 Topological Sort (Kahn's Algorithm)

Before `/emit` is called, `store.js` runs Kahn's algorithm over the block graph:

1. Build adjacency from `outputState → [blocks whose inputStates contain it]`
2. Find all nodes with in-degree 0 (no unresolved inputs) → initial queue
3. Drain queue, appending each block to the sorted list
4. If the sorted list length < total blocks → cycle detected → error banner, `/emit` blocked

`algeq` blocks that reference state X must be placed **before** the block that produces X as `outputState`. This is enforced by treating `algeq` expression variable references as edges.

### 8.6 Auto-layout (Sugiyama) on DSL Import

When importing a `.txt` file (no canvas metadata), Drawflow node positions are assigned using a **Sugiyama layered-graph placement** computed in `canvas.js`:

1. Build a DAG from block signal dependencies; break cycles via DFS back-edge removal
2. Assign each block to a layer (longest-path from a source node)
3. Three-pass barycentric crossing reduction (down → up → down)
4. Map `(layer, position-within-layer)` → pixel coordinates
   - Horizontal spacing: 260 px per layer
   - Vertical spacing: 130 px per position

Feedback loops (e.g. integrators) are handled by identifying back-edges during DFS and removing them from the layout graph — the corresponding wires are still drawn on canvas.

---

## 9. Phase Roadmap

| Phase | Status | Deliverable | Key files |
|-------|--------|-------------|-----------|
| **1** | ✅ **Done** | Backend: parser, emitter, API, blocks.json (51 blocks), tests, CI | `server/*.py`, `frontend/blocks.json`, `tests/test_parser.py`, `.github/workflows/ci.yml` |
| **2** | ✅ **Done** | Full SPA: canvas (Drawflow), palette, live DSL preview, forms, toolbar, settings modal | `frontend/js/*.js`, `frontend/index.html`, `frontend/css/style.css` |
| **3** | ✅ **Done** | Sugiyama auto-layout (in `canvas.js`), settings modal wired to `/config`, API integration tests | `tests/test_api.py`, `docs/DESIGN.md` |
| **4** | 🔲 Next | Project save/load (`.cgproj` JSON), DSL `.txt` import with full position restore | `frontend/js/main.js` (save/load handlers) |
| **5** | 🔲 | Run Codegen end-to-end: `.f90` download, subprocess error display, stdout/stderr modal | `frontend/js/api.js`, `server/app.py` |
| **6** | 🔲 | Polish: validation overlay (mandatory outputs), colour themes per model type, E2E tests | Playwright / Cypress |

### Completed Phases — Quick Start

```bash
git clone https://github.com/SPS-L/stepss-cg-studio
cd stepss-cg-studio
pip install -r requirements.txt
pytest tests/ -v          # ~75 tests (test_parser + test_api)
python server/app.py      # → http://localhost:8765
```

Open `http://localhost:8765` — drag blocks from the palette, connect ports, fill in the metadata tables, then:
- **Export DSL** → downloads `<model_name>.txt`
- **▶ Run Codegen** → invokes the `codegen` binary, previews the `.f90`, offers download
- **Save Project** → saves `<model_name>.json` (lossless `.cgproj` round-trip)
- **Load Project** → restores canvas + all metadata
- **⚙ Settings** → set the `codegen` binary path without editing `config.json` by hand

---

## 10. Key Engineering Challenges

### 10.1 `_parse_blocks()` argument-line counting

The `%models` section is a flat sequential list — there are no block-closing delimiters. The parser must look up each `& blockname` in `blocks.json` to know exactly how many positional lines to consume. Unknown block names emit a warning and skip to the next `&` line, preserving `rawArgLines` for lossless re-emission.

### 10.2 Auto-layout on DSL import

Implemented in `canvas.js` as `sugiyamaLayout(proj)`. The three-pass barycentric approach gives visually reasonable layouts for the typical PSS/AVR/governor chains found in RAMSES models (linear chains with occasional fan-in/fan-out).

### 10.3 Topological sort and cycle detection

`store.js` runs Kahn's algorithm before every `/emit` call. A cycle (feedback loop in the model) does **not** crash the app — it triggers an error banner listing the involved block IDs and blocks the DSL export until resolved. Note: feedback loops are valid in RAMSES models (e.g. integrators in a control loop) and must be broken by declaring the fed-back signal as a `%state` with an explicit init expression — the UI should guide the user to do this.

### 10.4 `algeq` ordering constraint

An `algeq` block that computes state `X` is an implicit equation. Its position in the `%models` list must precede the first block that uses `X` as an input. The topological sort treats `algeq` outputs like any other state output for ordering purposes.

### 10.5 RAMSES variable namespacing

RAMSES built-in input variables differ per model type (e.g. `exc` has `[v]`, `[omega]`, `[if]`, `[vf]`; `inj` has `[vx]`, `[vy]`, `[ix]`, `[iy]`). The sidebar autocomplete and validation must filter available input signals by `modelType`. The `RAMSES_INPUTS` dict in `dsl_parser.py` is the authoritative source.

---

## 11. Testing Strategy

| Test type | Location | Count | Coverage |
|-----------|----------|-------|----------|
| Parser unit tests | `tests/test_parser.py` | 25 | Model type/name, all sections, block types, round-trip, `blocks.json` integrity, example files |
| API integration tests | `tests/test_api.py` | ~50 | All endpoints: `/blocks`, `/parse`, `/emit`, `/run_codegen`, `/config`, static serving |
| Frontend E2E | _Phase 6_ | — | Playwright / Cypress drag-drop smoke tests |

Run with: `pytest tests/ -v`

---

## 12. Configuration

`server/config.json`:

```json
{
  "codegen_path": "codegen",
  "workspace_dir": "workspace",
  "host": "127.0.0.1",
  "port": 8765
}
```

| Field | Default | Notes |
|-------|---------|-------|
| `codegen_path` | `"codegen"` | Full path to `codegen.exe` on Windows, or `codegen` if on `PATH` |
| `workspace_dir` | `"workspace"` | Reserved for future persistent workspace |
| `host` | `"127.0.0.1"` | Bind address; change to `"0.0.0.0"` for network access |
| `port` | `8765` | HTTP port |

Editable at runtime via `PUT /config` (Swagger UI at `/docs`) or the ⚙ Settings button in the UI.

---

## 13. License

MIT — see `LICENSE` in the repository root.

Developed by the [Sustainable Power Systems Lab (SPS-L)](https://sps-lab.org), Cyprus University of Technology.
RAMSES and the CODEGEN DSL are owned by the University of Liège / SPS-L under the Academic Public License.
