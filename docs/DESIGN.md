# CODEGEN Visual Block Editor — Architectural Design Plan

## Vision

A FastAPI-backed, browser-based, drag-and-drop editor for assembling
RAMSES user-defined device models (EXC / TOR / INJ / TWOP) via the STEPSS CODEGEN DSL.
No build step. Run with `python server/app.py`.

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Backend API | FastAPI + uvicorn | Fast async Python, auto-docs at `/docs` |
| DSL parse/emit | Pure Python (`dsl_parser.py`, `dsl_emitter.py`) | No extra deps |
| Canvas | Drawflow (MIT, CDN) | Drag-drop node graph, zero-build JS |
| DSL preview | CodeMirror 6 (MIT, CDN) | Syntax highlight, minimal footprint |
| Forms | Vanilla JS + HTML5 | No framework overhead |
| State store | In-memory JS object (`store.js`) | ModelProject JSON mirrors backend |
| Tests | pytest | Standard Python |

---

## Deployment

- **Local Python server** (`python server/app.py` → `http://localhost:8765`)
- Frontend served as static files from `frontend/`
- `codegen.exe` called via subprocess; path configured in `server/config.json`
- Works on Windows, Linux, macOS (RAMSES itself is Windows-only)

---

## ModelProject JSON Schema

```json
{
  "version": 1,
  "modelType": "exc | tor | inj | twop",
  "modelName": "string",
  "data": [
    { "name": "TA", "comment": "" }
  ],
  "parameters": [
    { "name": "Vo", "expr": "v+(vf/{KE})", "continuation": true }
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

---

## Block Catalogue Schema (`frontend/blocks.json`)

```json
{
  "blockname": {
    "label":       "Human-readable name",
    "category":    "Transfer Functions | Limiters | Controllers | ...",
    "description": "Tooltip text",
    "inputs":      ["u"],
    "outputs":     ["y"],
    "color":       "#hexcolor",
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

### DSL Line Templates

| Template token | Meaning |
|---------------|---------|
| `{{input}}`  | Single input signal name (state or RAMSES var) |
| `{{inputs}}` | Multi-input: emit each input on its own line |
| `{{output}}` | Output signal name (state) |
| `{{name}}`   | Named parameter (becomes `args["name"]`) |

---

## UI Architecture (Phase 2)

```
index.html
├── #sidebar        Block palette (grouped by category, expandable)
├── #canvas         Drawflow canvas (drag-drop wiring)
├── #panel-right    Tabbed panel:
│   ├── tab: Model  modelType / modelName / observables
│   ├── tab: Data   %data table (name, comment)
│   ├── tab: Params %parameters table (name, expr, continuation)
│   ├── tab: States %states table (name, initExpr, comment)
│   └── tab: Props  Selected block properties form
├── #dsl-preview    Live CodeMirror 6 read-only DSL preview
└── #toolbar        New | Load .txt | Load .cgproj | Save DSL | Run Codegen | Save .cgproj
```

---

## Canvas Interaction Model

- **Drag from sidebar** → drop on canvas → creates a Drawflow node
- **Output port** (right side of node) → **input port** (left side of next node)
  - Connecting two nodes sets `inputStates[0]` of target = `outputState` of source
  - Auto-generates state name: `<blockType><id>` (e.g., `tf1p3`) — editable in Props tab
- **Double-click a node** → opens Props tab, showing its `args` as a form
- **Right-click → Delete** — removes node + all its wires
- **Multi-input blocks** (max2v, min2v, switch*) render multiple left-side ports

### Signal Name Resolution

All signal identifiers are **strings** — either state variable names from
`%states` or RAMSES built-in variables (`[var]` in DSL, stored bare as `v`, `omega`, etc.).
The emitter wraps RAMSES inputs in `[...]` and data params in `{...}` automatically.

### Topological Sort (emit order)

Before calling `emit_dsl()`, the frontend performs Kahn’s algorithm topological sort
over the block graph (edges = wires). Cycles trigger an error banner.

---

## Project File Format (`.cgproj`)

```json
{
  "format": "cgproj-v1",
  "savedAt": "2026-04-01T12:00:00Z",
  "project": { "<ModelProject JSON>" }
}
```

Canvas positions stored in `project.canvas.nodeMap`.

---

## API Endpoints

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/` | — | `index.html` |
| GET | `/blocks` | — | `blocks.json` |
| POST | `/parse` | `{ "dsl_text": "..." }` | ModelProject JSON |
| POST | `/emit` | `{ "project": {...} }` | `{ "dsl_text": "..." }` |
| POST | `/run_codegen` | `{ "dsl_text": "..." }` | `{ "f90_text", "stdout", "returncode" }` |
| GET | `/config` | — | config JSON |
| PUT | `/config` | partial config JSON | updated config JSON |

---

## Phase Roadmap

| Phase | Deliverable | Key files |
|-------|------------|-----------|
| 1 | Backend: parser, emitter, API, blocks.json, tests | `server/*.py`, `frontend/blocks.json` |
| 2 | Frontend canvas + sidebar + DSL preview | `frontend/js/*.js`, `frontend/index.html` |
| 3 | Right-panel forms (data/params/states) | `frontend/js/forms.js` |
| 4 | Project save/load (.cgproj), import DSL .txt | `frontend/js/main.js` |
| 5 | Run Codegen button, .f90 download, error display | `frontend/js/api.js` |
| 6 | Polish: undo/redo, validation overlay, colour themes | — |

---

## Key Engineering Challenges

1. **`_parse_blocks()` in `dsl_parser.py`** — must look up each `& blockname` in
   `blocks.json` to know how many argument lines to consume before the next `&`.
   Unknown block names emit a warning and skip to the next `&` line.

2. **Auto-layout on import** — when loading a `.txt` DSL (no canvas metadata),
   Drawflow positions are assigned using a Sugiyama layered-graph placement
   computed in `frontend/js/canvas.js` from the signal dependency graph.

3. **Topological sort** — `store.js` must detect cycles and report them as user
   errors rather than silently emitting broken DSL.

4. **`algeq` positioning** — an `algeq` referencing state X must appear
   *before* the block that introduces X in the block sequence.

---

## License

MIT. See repository root.
