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
| 1 | **Deployment target** | Local Python server launched as `cg-studio` (or `python -m cg_studio`) — enables live "Run Codegen" round-trip via subprocess |
| 2 | **Distribution** | PyPI wheel with bundled per-platform CODEGEN binary under `cg_studio/bin/`; user can override the binary path via Settings |
| 3 | **Primary users** | Both experienced developers and students — welcoming UI, but no-overhead for power users |
| 4 | **Block wiring model** | Named wire / port approach — each block has named input/output ports; connecting writes the signal name |
| 5 | **`%parameters` editing** | Structured table forms for all metadata sections; canvas only covers `%models` |
| 6 | **Block catalogue extensibility** | `cg_studio/frontend/blocks.json` — add one JSON entry per new block; no code changes |
| 7 | **`algeq` representation** | Special formula node on canvas with typed expression field and one implicit output port |
| 8 | **Persistence format** | `.json` file containing full ModelProject state including canvas positions (lossless round-trip) |

---

## 3. Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Packaging | `pyproject.toml` (setuptools, PyPI-published) | `pip install stepss-cg-studio` → `cg-studio` console script |
| Backend API | FastAPI + uvicorn | Fast async Python, auto-docs at `/docs`, zero config |
| DSL parse/emit | Pure Python (`dsl_parser.py`, `dsl_emitter.py`) | No extra dependencies |
| Canvas | [Drawflow](https://github.com/jerosoler/Drawflow) (MIT, CDN) | Drag-drop node graph, zero-build JS |
| DSL preview | Custom regex highlighter in `<pre>` element | Zero-dependency syntax colouring for DSL sections, numbers, params, variables |
| E2E tests | Playwright for Python | Browser automation, pip-installable, no Node.js needed |
| Right-panel forms | Vanilla JS + HTML5 | No framework overhead |
| State store | In-memory JS object (`store.js`) | ModelProject JSON mirrors backend |
| Tests | pytest + httpx | Standard Python test runner + FastAPI TestClient |
| CI | GitHub Actions | Runs pytest on push/PR, Python 3.10–3.12; builds & publishes wheels on `v*` tags |

### Deployment

- Install: `pip install stepss-cg-studio` (or `pip install -e ".[dev]"` for a dev checkout).
- Run: `cg-studio` (console script, installed by pip) — or `python -m cg_studio`. Default URL `http://localhost:8765`; the launcher auto-opens the browser unless `--no-browser` is passed.
- The frontend (HTML/CSS/JS + `blocks.json`) ships inside the Python package at `cg_studio/frontend/` and is served from there via `importlib.resources`.
- The CODEGEN binary is looked up in this order: (1) user override from Settings, (2) bundled binary inside the wheel at `cg_studio/bin/codegen[.exe]`, (3) `codegen` on `PATH`. Platform-specific wheels ship the matching binary; macOS currently has no bundled binary and requires the user to point Settings at a local build.
- Platform: Windows / Linux / macOS (RAMSES itself runs on Windows 64-bit only).

---

## 4. Repository Structure

```
stepss-cg-studio/
├── .github/
│   └── workflows/
│       └── ci.yml              # pytest on push/PR (3.10–3.12); build & PyPI publish on v* tags
├── pyproject.toml              # Packaging, deps, console script, pytest config
├── src/
│   └── cg_studio/              # Installable Python package
│       ├── __init__.py         # __version__
│       ├── __main__.py         # `python -m cg_studio` → cli.main
│       ├── cli.py              # `cg-studio` console script (argparse, uvicorn.run)
│       ├── app.py              # FastAPI server + routes + static mount
│       ├── config.py           # Platform config dir, codegen resolver, load/save
│       ├── dsl_parser.py       # DSL .txt → ModelProject dict
│       ├── dsl_emitter.py      # ModelProject dict → DSL .txt
│       ├── bin/                # Bundled CODEGEN binaries (populated per-wheel)
│       └── frontend/           # Packaged static assets
│           ├── index.html
│           ├── favicon.svg
│           ├── blocks.json     # Block catalogue — extend here for new blocks
│           ├── css/style.css
│           └── js/
│               ├── main.js              # Bootstrap, toolbar, shortcuts, Settings modal
│               ├── canvas.js            # Drawflow wrapper + Sugiyama auto-layout
│               ├── palette.js           # Grouped/searchable block palette
│               ├── forms.js             # Metadata tables + block inspector
│               ├── dsl_preview.js       # Debounced live DSL preview + regex highlight
│               ├── store.js             # ModelProject, Kahn topo-sort, 60-step undo/redo
│               ├── api.js               # fetch() wrappers for backend endpoints
│               ├── project_adapter.js   # Parser-shape → Store-shape on DSL load
│               └── sidebar.js           # (unused) ES-module variant of palette.js
├── examples/
│   ├── ENTSOE_simp_exc.txt     # Example EXC DSL (PSS + AVR chain)
│   └── ENTSOE_simp_tor.txt     # Example TOR DSL (governor chain)
├── tests/
│   ├── conftest.py             # Playwright fixture: starts uvicorn, yields base URL
│   ├── test_parser.py          # 26 tests — parse, emit, round-trip, blocks.json, examples
│   ├── test_api.py             # 41 tests — /blocks, /parse, /emit, /run_codegen, /config, /mandatory_outputs, static
│   ├── test_config.py          # 12 tests — config dir / workspace / load / save / resolve_codegen
│   ├── test_cli.py             # 3 tests — cli argparse + browser open behaviour
│   └── test_e2e.py             # 10 Playwright tests — load, theme, palette, modals, shortcuts
├── docs/
│   ├── DESIGN.md               # This document
│   └── specs/                  # Feature specs (e.g. PyPI packaging design/plan)
├── run.bat                     # Windows launcher → `python -m cg_studio`
└── run.sh                      # Linux/macOS launcher → `python -m cg_studio`
```

There is **no top-level `server/` or `frontend/` directory and no `requirements.txt`** — the backend and the static frontend are both inside the installable `cg_studio` package, and all dependencies are declared in `pyproject.toml`.

---

## 5. Data Model

### 5.1 ModelProject JSON Schema

The **frontend store** (`store.js`) holds the canonical runtime representation. This is also the shape written to disk on "Save Project".

```json
{
  "model_type": "exc",
  "model_name": "my_model",
  "data": [
    { "name": "TA", "value": "", "comment": "" }
  ],
  "parameters": [
    { "name": "Vo", "expr": "v+(vf/{KE})+([vf]/{KA})", "comment": "" }
  ],
  "states": [
    { "name": "avr1", "init": "vf/{KE}", "comment": "" }
  ],
  "observables": [
    { "name": "vf", "expr": "" }
  ],
  "models": [
    {
      "id": "nkx3a7bf2c",
      "df_id": 1,
      "block_type": "tf1plim",
      "label": "TF 1P Lim",
      "color": "#2563eb",
      "args": { "K": "1.", "T": "{TA}", "lo": "{EMIN}", "hi": "{EMAX}" },
      "outputs": ["vf"],
      "inputs": [null],
      "pos": { "x": 300, "y": 150 }
    }
  ],
  "wires": [
    {
      "from_node": "nkx3a7bf2c",
      "from_port": "output_1",
      "to_node": "nkx4b8cg3d",
      "to_port": "input_1",
      "signal_name": "avr2"
    }
  ],
  "canvas_meta": {}
}
```

**Field notes:**
- `models[].id` — unique string ID generated by `Store.nextId()` (timestamp + random suffix).
- `models[].df_id` — Drawflow's internal integer node ID; used to map between store and canvas DOM.
- `models[].outputs` — array of output signal names (one per output port); auto-generated on drop, editable in the Block Inspector.
- `models[].inputs` — array of `null` slots (one per input port); wiring is tracked in `wires[]`, not here.
- `wires[]` — explicit edge list with Drawflow port classes (`output_1`, `input_1`).
- `canvas_meta` — reserved for future canvas-level metadata (zoom, scroll offset).

#### Backend ↔ Frontend model mapping

The backend parser (`dsl_parser.py`) returns a different shape that the frontend transforms on load:

| Backend (parser output) | Frontend (store) |
|------------------------|------------------|
| `modelType` (camelCase) | `model_type` (snake_case) |
| `modelName` | `model_name` |
| `blocks[]` with `inputStates`/`outputState`/`rawArgLines` | `models[]` with `outputs`/`inputs` + separate `wires[]` |
| `canvas.nodeMap` / `canvas.drawflow` | per-model `pos` + `canvas_meta` |
| `states[].initExpr` | `states[].init` |
| `errors[]` | (surfaced as toast on load, not persisted) |

The translation happens in `main.js` during DSL load (`Api.parseDSL()` → `Store.set()`) and in the `/emit` endpoint during emit. The backend's `POST /emit` handler calls `_normalise_project()` (`app.py`) which detects the frontend shape (presence of `model_type` instead of `modelType`) and maps `models[]`+`wires[]` → `blocks[]` with `inputStates` reconstructed from the wire list before delegating to `emit_dsl()`. The frontend therefore sends its native store shape to `/emit`; no client-side translation layer is needed.

### 5.2 Project File Format (`.json`)

Saved directly as the frontend `ModelProject` object (see §5.1) via `JSON.stringify(p, null, 2)`.
File extension: `.json`. No envelope — the root object **is** the ModelProject.

- **Save** (`main.js`): `Store.get()` → `JSON.stringify` → download as `<model_name>.json`
- **Load** (`main.js`): `JSON.parse(text)` → `Store.set(proj)` → `Canvas.loadProject()`

`.f90` files are **export only** — they cannot be imported.

---

## 6. Block Catalogue (`cg_studio/frontend/blocks.json`)

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
| Transfer Functions | `tf1p`, `tf1p1z`, `tf1plim`, `tf1pvlim`, `tf1p2lim`, `tf1p2limr`, `tf2p2z`, `tfder1p` |
| Limiters | `lim`, `limvb`, `inlim`, `invlim` |
| Controllers | `int`, `pictl`, `pictllim`, `pictl2lim`, `pictlieee` |
| Min/Max/Gates | `max2v`, `max1v1c`, `min2v`, `min1v1c` |
| Nonlinear | `abs`, `db`, `hyst`, `nint`, `swsign`, `switch2`–`switch5`, `pwlin3`–`pwlin6` |
| Timers | `timer1`–`timer5`, `timer11`, `timersc1`–`timersc6`, `tsa` |
| Automata | `fsa` |
| Power System | `f_inj`, `f_twop_bus1`, `f_twop_bus2` |

**Total: 52 blocks** (as counted from `blocks.json`). Add new blocks by appending entries to `blocks.json` — no JavaScript or Python changes required.

The `fsa` (finite-state automaton) block uses a multi-line free-form body (`{{fsa_body}}`) rather than the fixed positional templates used by other blocks; its contents are the `#N` state / `->M` transition syntax documented in the codegen specification.

---

## 7. Backend Architecture

### 7.1 API Endpoints

| Method | Path | Request body | Response |
|--------|------|-------------|----------|
| `GET` | `/` | — | `index.html` (SPA fallback via `StaticFiles(html=True)`) |
| `GET` | `/favicon.ico` | — | `frontend/favicon.svg` (or 204) |
| `GET` | `/blocks` | — | `blocks.json` catalogue |
| `GET` | `/mandatory_outputs` | — | `{exc:[…], tor:[…], inj:[…], twop:[…]}` map from `dsl_parser.MANDATORY_OUTPUTS` |
| `POST` | `/parse` | `{ "dsl_text": "..." }` | ModelProject JSON |
| `POST` | `/emit` | `{ "project": {...} }` | `{ "dsl_text": "..." }` |
| `POST` | `/run_codegen` | `{ "dsl_text": "...", "model_type": "...", "model_name": "..." }` | `{ "f90_text", "f90_filename", "stdout", "stderr", "returncode", "success" }` |
| `GET` | `/config` | — | current config dict |
| `PUT` | `/config` | any subset of `codegen_path`, `workspace_dir`, `host`, `port` | `{ "status": "ok", "config": {...} }` |

API routes are registered **before** the static-files mount so that unknown paths fall back to `index.html` (SPA routing) while known API paths stay intact. Auto-generated Swagger UI at `http://localhost:8765/docs`.

### 7.2 DSL Parser (`cg_studio/dsl_parser.py`)

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

### 7.3 DSL Emitter (`cg_studio/dsl_emitter.py`)

**Entry point:** `emit_dsl(project: dict) -> str`

Emits sections in canonical order: header → `%data` → `%parameters` → `%states` → `%observables` → `%models`.

For `%models`, blocks are emitted in the **list order** of `project["blocks"]`. The frontend store does not currently reorder `models[]` using the topological sort before calling `/emit` (see §8.5 and §10.3) — block order therefore follows insertion / import order, and the user can shuffle it manually by deleting/recreating nodes if needed.

For each block, the emitter reverse-maps `inputStates`/`outputState`/`args` back into the `dsl_lines` template sequence. Unknown blocks fall back to `rawArgLines`.

### 7.4 `codegen` Subprocess (`/run_codegen`)

1. Resolve the codegen binary via `config.resolve_codegen()` — user override → bundled binary under `cg_studio/bin/` → `codegen` on `PATH`. If none resolve, return HTTP 500 with a platform-aware hint (the macOS message tells the user to supply their own binary via Settings, since no macOS binary is bundled).
2. Infer `model_type` / `model_name` from the first two non-empty DSL lines if the request did not supply them.
3. Write `dsl_text` to a temp file `<model_name>.txt` in a `tempfile.TemporaryDirectory()` (cwd set to that directory so codegen writes its output there).
4. Invoke `<codegen> -t<path_to_dsl_file>` with a 30-second timeout.
5. Read `<model_type>_<model_name>.f90` from the temp dir.
6. Return `f90_text`, `f90_filename`, `stdout`, `stderr`, `returncode`, and a `success` flag (`returncode == 0` *and* non-empty f90 text).

---

## 8. Frontend Architecture

### 8.1 UI Layout

```
+----------------------------------------------------------------------+
|  TOOLBAR: Type [EXC v] Name [________]                               |
|  New | Load DSL | Load Project | Save Project | Export DSL           |
|  > Run Codegen | Settings                                            |
+------------+-------------------------------+-------------------------+
|            |  [Undo][Redo][Del]  [Fit]     |  Block Inspector        |
|  SIDEBAR   |  status: "3 blocks, 2 wires"  |  (selected block        |
|            +-------------------------------+   output signals +      |
|  Block     |                               |   args form)            |
|  palette   |                               |                         |
|  [search]  |       CANVAS (Drawflow)       +-------------------------+
|            |       drag-drop-connect        |  DSL Preview            |
|  grouped   |                               |  (syntax-highlighted    |
|  by cat.,  |                               |   <pre> with regex      |
|  collaps-  +-------------------------------+   colouring)            |
|  ible      |  [%data][%params][%states]    |  [Copy to clipboard]    |
|            |  [%observables]               |                         |
|            |  editable metadata tables     |                         |
+------------+-------------------------------+-------------------------+
|  Toast notifications (bottom overlay)                                |
+----------------------------------------------------------------------+
```

Three-column layout: left sidebar (palette), center column (canvas toolbar + Drawflow canvas + metadata tabs), right panel (block inspector + DSL preview). Model type/name selectors are in the top bar, not in a right-panel tab.

### 8.2 JS Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `store.js` | Canonical `ModelProject` state; Kahn's topological sort; undo/redo ring buffer (60 steps); event bus for cross-module updates |
| `api.js` | `fetch()` wrappers for all backend endpoints; error normalisation |
| `project_adapter.js` | Converts backend `/parse` output → frontend store shape (catalogue-aware `models[]`, synthesized `wires[]`, preserved literal inputs). Also Node-testable. |
| `canvas.js` | Drawflow initialisation; drag-from-sidebar; port connection → signal name assignment; Sugiyama auto-layout for DSL import |
| `palette.js` | Renders block palette grouped by category; live search filter; drag-start handler |
| `forms.js` | Right-panel tabs: model meta, data table, params table, states table, block props form |
| `dsl_preview.js` | Debounced (600 ms) live DSL re-render on every `store` change; copy-to-clipboard; custom regex-based syntax highlighting in a `<pre>` element (no external library) |
| `sidebar.js` | Unused ES-module variant of `palette.js` (not loaded by `index.html`) |
| `main.js` | App bootstrap; toolbar button handlers (New, Load DSL, Load Project, Save DSL, Save Project, Run Codegen); Ctrl+Z/Y/S keyboard shortcuts; file I/O (`FileReader`, `Blob` download); Settings modal wired to `GET/PUT /config`; toast notifications |

### 8.3 Canvas Interaction Model

- **Drag from palette** → drop on canvas → Drawflow creates a node; `store.js` adds a `models[]` entry with auto-generated output signal names. The signal prefix is the first three alphabetic characters of the block key (`tf1plim` → `tfp`), with an incrementing numeric suffix chosen by `Store.freshSignal()` to avoid collisions.
- **Connect output port → input port** → `store.js` appends a `wires[]` entry whose `signal_name` is the source block's output signal. Target `inputStates` are reconstructed from `wires[]` on `/emit` (inside `_normalise_project`); the store deliberately does *not* mirror them into `models[].inputs`.
- **Click node (select)** → activates Block Inspector panel, renders editable output signal names and the `args` form (driven by `blocks.json.args[]`). Uses Drawflow's `nodeSelected` event.
- **Delete key / toolbar Del** → removes the selected node, its incident wires, and the `models[]` entry from `store.js`.
- **Multi-input blocks** (`max2v`, `min2v`, `switch2`–`switch5`) render N left-side ports; each port has its own `input_N` class and can be wired independently.

### 8.4 Signal Name Resolution

Signal identifiers are plain strings in `ModelProject`. Notation conventions:

| DSL text | Stored in ModelProject | Emitter output |
|----------|----------------------|----------------|
| `[omega]` | `"omega"` | `[omega]` |
| `{KE}` | `"{KE}"` | `{KE}` (verbatim) |
| `avr2` (state) | `"avr2"` | `avr2` |

The emitter wraps RAMSES built-in variable names in `[...]` when it encounters them in `inputStates`. Signal names are currently typed manually in the Block Inspector form — there is no frontend autocomplete yet. The `RAMSES_INPUTS` dict in `dsl_parser.py` is the authoritative source for valid input variables per model type; a future enhancement could offer autocomplete suggestions from it.

### 8.5 Topological Sort (Kahn's Algorithm)

`Store.topoSort()` runs Kahn's algorithm over the block graph:

1. Build adjacency directly from `wires[]` (`from_node → to_node`).
2. Find all nodes with in-degree 0 → initial queue.
3. Drain queue, appending each block `id` to the sorted list.
4. If the sorted list length < total blocks → return `null` (cycle detected).

**Current usage:** the sort result is consumed by `main._status()` on every store change to display either the "3 blocks, 2 wires" status or a red "⚠ Cycle detected" banner. It does **not** reorder `proj.models` before `/emit` — the emitter currently processes blocks in whatever order they appear in `proj.models`, and `_normalise_project` iterates the same order. If the user drops or loads blocks out of dependency order, the emitted DSL will reflect that order; fixing this to use the topo-sort result before emit is a known follow-up.

The sort is purely wire-based — it does not parse `algeq` expressions to extract variable references, so the ordering constraint in §10.4 is only enforced for `algeq` outputs that are explicitly wired to their consumers.

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

All planned phases are complete; the table is kept as a historical record of what each phase delivered.

| Phase | Status | Deliverable | Key files |
|-------|--------|-------------|-----------|
| **1** | ✅ Done | Backend: parser, emitter, FastAPI endpoints, `blocks.json` catalogue, parser tests, CI matrix | `src/cg_studio/{dsl_parser,dsl_emitter,app}.py`, `src/cg_studio/frontend/blocks.json`, `tests/test_parser.py`, `.github/workflows/ci.yml` |
| **2** | ✅ Done | Full SPA: Drawflow canvas, palette, live DSL preview, metadata tables, block inspector, toolbar | `src/cg_studio/frontend/js/*.js`, `src/cg_studio/frontend/index.html`, `src/cg_studio/frontend/css/style.css` |
| **3** | ✅ Done | Sugiyama auto-layout for DSL import, Settings modal wired to `GET/PUT /config`, API integration tests | `src/cg_studio/frontend/js/canvas.js` (`sugiyamaLayout`), `src/cg_studio/frontend/js/main.js` (settings handlers), `tests/test_api.py` |
| **4** | ✅ Done | Project save/load (`.json`, lossless round-trip), DSL `.txt` import that triggers Sugiyama layout when no canvas metadata is present | `src/cg_studio/frontend/js/main.js` (file I/O handlers), `src/cg_studio/frontend/js/canvas.js` (`loadProject`) |
| **5** | ✅ Done | Run Codegen end-to-end: resolver for user/bundled/PATH binary, `.f90` preview modal with download, subprocess error display | `src/cg_studio/frontend/js/main.js` (Run Codegen handler), `src/cg_studio/app.py` (`/run_codegen`), `src/cg_studio/config.py` (`resolve_codegen`) |
| **6** | ✅ Done | Polish: mandatory-output validation modal, model-type colour themes, Playwright E2E suite | `src/cg_studio/frontend/js/main.js`, `tests/test_e2e.py`, `tests/conftest.py` |
| **7** | ✅ Done | PyPI packaging: `src/` layout, `cg-studio` console script, bundled codegen binary per-platform, tag-triggered build + publish workflow | `pyproject.toml`, `src/cg_studio/cli.py`, `src/cg_studio/config.py` (`resolve_codegen`), `.github/workflows/ci.yml` (build / publish jobs) |

### Quick Start

```bash
pip install stepss-cg-studio        # or: pip install -e ".[dev]" for a dev checkout
cg-studio                           # auto-opens http://localhost:8765
# Tests (dev checkout):
pytest tests/ -v                    # 92 tests — parser, API, config, CLI, E2E (Playwright)
```

In the browser — drag blocks from the palette, connect ports, fill in the metadata tables, then:
- **Export DSL** → downloads `<model_name>.txt` after validating mandatory outputs
- **▶ Run Codegen** → invokes the resolved `codegen` binary, previews the `.f90`, offers download
- **Save Project** → downloads `<model_name>.json` (lossless round-trip including canvas positions)
- **Load Project / Load DSL** → restores a project, or parses a raw `.txt` and auto-lays it out
- **⚙ Settings** → edit `codegen_path`, `host`, `port` (persisted to the platform config dir; see §12)

---

## 10. Key Engineering Challenges

### 10.1 `_parse_blocks()` argument-line counting

The `%models` section is a flat sequential list — there are no block-closing delimiters. The parser must look up each `& blockname` in `blocks.json` to know exactly how many positional lines to consume. Unknown block names emit a warning and skip to the next `&` line, preserving `rawArgLines` for lossless re-emission.

### 10.2 Auto-layout on DSL import

Implemented in `canvas.js` as `sugiyamaLayout(proj)`. The three-pass barycentric approach gives visually reasonable layouts for the typical PSS/AVR/governor chains found in RAMSES models (linear chains with occasional fan-in/fan-out).

### 10.3 Topological sort and cycle detection

`Store.topoSort()` runs Kahn's algorithm on every store change (via `main._status()`) to decide whether to show "N blocks, M wires" or a red "⚠ Cycle detected" status banner. A cycle does **not** crash the app. The sort result is *not* currently fed back into `/emit`, so the emitter relies on the user (or the Sugiyama import step) to present blocks in a sensible order. Feedback loops are valid in RAMSES models (e.g. integrators in a control loop) and must be broken by declaring the fed-back signal as a `%state` with an explicit init expression — the UI does not yet guide the user through this.

### 10.4 `algeq` ordering constraint

An `algeq` block that computes state `X` is an implicit equation. Its position in the `%models` list must precede the first block that uses `X` as an input. In the catalogue, `algeq` has a single `residual` output port, so when the user wires that port to a downstream block the topological sort in `store.js` orders it like any other block. However, the sort is purely **wire-based** — if an `algeq` references a state inside its free-text expression without a wire, the ordering constraint is not enforced automatically. See §8.5.

### 10.5 Frontend ↔ Backend model translation

The backend parser (`dsl_parser.py`) returns a `ModelProject` with camelCase keys and a flat `blocks[]` array where wiring is encoded per-block (`inputStates`/`outputState`). The frontend store (`store.js`) uses snake_case keys, a separate `wires[]` array, and per-node `outputs[]`/`inputs[]` with Drawflow node IDs (`df_id`). See §5.1 for the full mapping table.

The translation happens in two symmetric places:

- **Load**: `main.js` calls `Api.parseDSL()` → the backend returns the parser shape → `ProjectAdapter.parsedToFrontend(parsed, blocks)` (in `frontend/js/project_adapter.js`) rebuilds the store shape: `blocks[]` becomes `models[]` enriched with catalogue metadata (label/color/inputs/outputs) and `pos:{x:0,y:0}` to trigger Sugiyama layout; a synthetic `wires[]` is derived by matching each input slot to the first upstream block whose `outputState` equals that signal; unresolved literals (RAMSES inputs like `[omega]`, parameter refs like `{KE}`, state names with no producing block) are kept as plain strings in `models[i].inputs[j]`.
- **Emit**: `dsl_preview.js` calls `Api.emitDSL(Store.get())`. The `/emit` handler calls `app._normalise_project()` which detects the shape (`model_type` vs `modelType`), seeds `inputStates[]` from `models[i].inputs[j]` literals, then lets `wires[]` entries override each targeted slot with the wire's `signal_name`, and finally invokes `emit_dsl()`.

Schema changes must therefore be reflected in both `project_adapter.parsedToFrontend()` and `app._normalise_project()`, plus `store.js` and the forms if they add/remove fields.

### 10.6 RAMSES variable namespacing

RAMSES built-in input variables differ per model type (e.g. `exc` has `[v]`, `[omega]`, `[if]`, `[vf]`; `inj` has `[vx]`, `[vy]`, `[ix]`, `[iy]`). Any future signal autocomplete or validation must filter available input signals by `model_type`. The `RAMSES_INPUTS` dict in `dsl_parser.py` is the authoritative source.

---

## 11. Testing Strategy

| Test type | Location | Count | Coverage |
|-----------|----------|-------|----------|
| Parser / emitter unit tests | `tests/test_parser.py` | 26 | Model type/name, all sections, block types (exc/tor/inj/twop), round-trip, `blocks.json` integrity, example files |
| API integration tests | `tests/test_api.py` | 41 | All endpoints via FastAPI `TestClient`: `/blocks`, `/parse`, `/emit`, `/run_codegen`, `/config`, `/mandatory_outputs`, static serving |
| Config module tests | `tests/test_config.py` | 12 | Platform config dir, default workspace, `load`/`save_config`, `resolve_codegen` (user override / bundled / PATH / missing) |
| CLI tests | `tests/test_cli.py` | 3 | `cg-studio` argparse: default browser open, `--no-browser`, `--port` override |
| Project adapter (Node) | `tests/test_project_adapter.py` | 3 | Runs `project_adapter.js` under Node against real parser output — verifies DSL-load path without a browser |
| Frontend E2E | `tests/test_e2e.py` | 11 | Playwright (chromium): app loading, theming, palette search, validation overlay, modals, keyboard shortcuts, DSL-file load round-trip |

**Total: 96 tests.** Run with: `pytest tests/ -v`. CI runs the entire suite on Python 3.10 / 3.11 / 3.12 against Ubuntu (the Playwright browsers are installed in the CI workflow; `node` is preinstalled on GitHub-hosted runners, so the adapter tests also run there).

---

## 12. Configuration

Configuration is handled by `src/cg_studio/config.py`. There is **no config file inside the repository**; the runtime config lives in the platform's user config directory and is created with defaults on first run.

| OS | Config path |
|----|-------------|
| Linux | `$XDG_CONFIG_HOME/cg-studio/config.json` (falls back to `~/.config/cg-studio/config.json`) |
| macOS | `~/.config/cg-studio/config.json` (same XDG rule) |
| Windows | `%LOCALAPPDATA%\cg-studio\config.json` (falls back to `~/AppData/Local/cg-studio/config.json`) |

Default contents:

```json
{
  "codegen_path": "bundled",
  "workspace_dir": "<platform default>",
  "host": "127.0.0.1",
  "port": 8765
}
```

| Field | Default | Notes |
|-------|---------|-------|
| `codegen_path` | `"bundled"` | Sentinel that triggers the bundled-binary / PATH resolution chain in `resolve_codegen()`. Set to an absolute path to override. |
| `workspace_dir` | `~/cg-studio-workspace` on Linux/macOS, `~/Documents/cg-studio-workspace` on Windows | Reserved for future persistent workspace |
| `host` | `"127.0.0.1"` | Bind address; change to `"0.0.0.0"` for network access (restart required) |
| `port` | `8765` | HTTP port (restart required) |

Editable at runtime via `PUT /config` (Swagger UI at `/docs`) or the ⚙ Settings button in the UI. `cli.py` also accepts `--host` / `--port` flags that override the config for a single run without persisting.

---

## 13. License

MIT — see `LICENSE` in the repository root.

Developed by the [Sustainable Power Systems Lab (SPS-L)](https://sps-lab.org), Cyprus University of Technology.
RAMSES and the CODEGEN DSL are owned by the University of Liège / SPS-L under the Academic Public License.
