# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

STEPSS CG Studio is a browser-based drag-and-drop block diagram editor for building CODEGEN DSL models for RAMSES power system device modeling. Full-stack app: Python FastAPI backend + vanilla JS frontend (no build step).

Four model types: `exc` (excitation), `tor` (torque), `inj` (injector), `twop` (two-port). Each has specific RAMSES input variables and mandatory output states defined in `dsl_parser.py` (`RAMSES_INPUTS`, `MANDATORY_OUTPUTS`).

## Commands

```bash
# Install dependencies (dev extras include pytest + Playwright)
pip install -e ".[dev]"

# Run all tests (~140 tests)
pytest tests/ -v

# Run specific test files
pytest tests/test_parser.py -v
pytest tests/test_api.py -v

# Run a single test
pytest tests/test_parser.py::test_function_name -v

# Start server (http://localhost:8765)
cg-studio                 # console script, opens browser
python -m cg_studio       # equivalent module form
```

CI runs pytest on Python 3.10–3.12 via GitHub Actions (`.github/workflows/ci.yml`).

## Architecture

### Backend (`src/cg_studio/`)

- **`app.py`** — FastAPI server. API routes registered before static file mount (SPA fallback). Key endpoints: `POST /parse`, `POST /emit`, `POST /run_codegen`, `GET /blocks`, `GET /mandatory_outputs`, `GET /ramses_inputs`, `GET /ramses_reserved`, `GET/PUT /config`.
- **`dsl_parser.py`** — Converts DSL `.txt` → `ModelProject` dict. The critical `_parse_blocks()` method counts argument lines by looking up block name in `blocks.json` to determine `len(dsl_lines)`. Maps positional lines to template tokens (`{{input}}`, `{{output}}`, `{{K}}`, etc.). Exposes three name dicts: `RAMSES_INPUT_STATES` (palette-visible inputs), `MANDATORY_OUTPUTS`, and `RAMSES_INPUTS` (full reserved-name list incl. `if` for exc).
- **`dsl_emitter.py`** — Inverse of parser: `ModelProject` dict → DSL `.txt`. Expects blocks in topologically-sorted order (frontend must sort before calling `/emit`). Normalises block comments to start with `!`.
- **`config.py`** — Platform-aware config store. Reads/writes `config.json` under `%LOCALAPPDATA%\cg-studio\` (Windows) or `~/.config/cg-studio/` (Linux/macOS). Keys: codegen binary path, workspace dir, host, port.
- **`cli.py`** — `cg-studio` console script entry point (argparse: `--port`, `--host`, `--no-browser`).

### Frontend (`src/cg_studio/frontend/`)

Vanilla JS SPA, no build step. Drawflow (canvas) loaded from CDN.

- **`store.js`** — Canonical `ModelProject` state, Kahn's topological sort, undo/redo (60-step ring buffer), event bus.
- **`canvas.js`** — Drawflow integration, drag-from-sidebar, port connections → signal assignment, Sugiyama auto-layout (height-aware stacking), dynamic algeq input/output ports, SVG wire labels, node-rebuild on inspector expr edit, Fit-to-view with 50%-origin-aware math.
- **`project_adapter.js`** — Translates the backend's parsed DSL shape into the frontend Store shape. Two-phase algeq classification: pick outputs first (honouring user-declared `args.output_states`, mandatory outputs, then fewest-peer heuristic; reserved names like `if` are never promoted), then classify inputs against the complete producer index. Auto-seeds `ramses_in`/`ramses_out` pseudo-nodes for used RAMSES I/O.
- **`palette.js`** — Block palette UI grouped by category with search filter. Synthesises a dynamic "I/O (`modelType`)" category with per-signal draggable pins.
- **`main.js`** — App bootstrap, toolbar handlers, keyboard shortcuts (Ctrl+Z/Y/S), file I/O, Settings modal, New-model type picker, RAMSES-I/O seeding on "New", floating-state warnings on load / export gate.
- **`forms.js`** — Right-panel tabs: model metadata; per-block inspector (output-signal rename + cascading wire updates, algeq single Expression field + Output states, Comment field on every block).
- **`dsl_preview.js`** — Debounced (600ms) live DSL preview.
- **`validate.js`** — `Validate.findFloatingStateIssues(proj)` — detects state literals that should be wires.
- **`check_model.js`** — `CheckModel.run(proj, opts)` — the full set of structural checks driven by the toolbar Check Model (✓) button. Renders into the permanent Issues panel in the right sidebar.
- **`resizers.js`** — Click-and-drag splitters for the right sidebar and bottom meta panel; sizes persisted in `localStorage`.
- **`api.js`** — `fetch()` wrappers for backend endpoints.

### Key Data Flow

1. User connects blocks on canvas → `store.js` updates `ModelProject.blocks[].inputStates`/`outputState`
2. Topological sort (Kahn's algorithm in `store.js`) orders blocks before emit
3. `POST /emit` converts ordered `ModelProject` → DSL text
4. DSL preview updates live via debounced store listener

### Block Catalogue (`frontend/blocks.json`)

54 blocks across categories (Transfer Functions, Limiters, Controllers, etc.). Each entry defines `dsl_lines` templates, `args` schema, `inputs`/`outputs`, and `category`. **Extending: add a JSON entry here — no code changes needed.**

Template tokens in `dsl_lines`: `{{input}}`, `{{input1}}`/`{{input2}}` (multi-input), `{{output}}`, `{{NAME}}` (named args).

### Signal Naming Convention

- `[omega]` — RAMSES built-in variable (bracket-wrapped in DSL)
- `{KE}` — data/parameter reference (brace-wrapped, stored verbatim)
- `avr2` — internal state name (plain in DSL)

### Lossless Round-Trip

Unknown block types preserve `rawArgLines` through parse → edit → emit cycles. The `.cgproj` project format stores full `ModelProject` + canvas positions.

## Upstream Codegen Specifications

The CODEGEN binary (https://github.com/SPS-L/stepss-Codegen) is the downstream consumer of DSL files this tool generates. Documentation lives at https://github.com/SPS-L/stepss-docs/.

### CLI Invocation

`CODEGEN -tfilename.txt` (no space between `-t` and filename). Output: `{type}_{name}.f90`.

### DSL File Format (strict order)

```
{modeltype}          ← exc | tor | inj | twop
{modelname}          ← max 16 chars

%data
{one name per line, referenced as {name} elsewhere}

%parameters
name = expression    ← Fortran syntax, & for continuation, ! for comments

%states
name = init_expr     ← ! comments allowed; mandatory outputs (vf/tm/ix/iy) are auto-prepended by codegen

%observables
{one name per line, no brackets/braces}

%models
& blockname          ← ! comment allowed on this line
{arg lines...}       ← one per line: state names or {param}/numeric expressions
```

### Model Types — Inputs and Mandatory Outputs

The palette's **I/O (`modelType`)** category exposes per-signal pins driven by `RAMSES_INPUT_STATES` (inputs) and `MANDATORY_OUTPUTS` (outputs). The user-facing list below reflects what the palette shows and what `btn-new` seeds on a fresh model. Note `if` is a RAMSES-reserved name (can appear in DSL expressions) but is **not** a palette input — the user guide's Table 5.3 incorrectly listed it.

| Type | Palette Inputs | Mandatory Outputs | Extra reserved (not in palette) |
|------|---------------|-------------------|--------------------------------|
| `exc` | `v`, `p`, `q`, `omega` | `vf` | `if` |
| `tor` | `p`, `omega` | `tm` | — |
| `inj` | `vx`, `vy`, `omega` | `ix`, `iy` | — |
| `twop` | `vx1`, `vy1`, `vx2`, `vy2`, `omega1`, `omega2` | `ix1`, `iy1`, `ix2`, `iy2` | — |

The full reserved-name list (which cannot be used for internal states) is the union of the three columns and is exposed via `GET /ramses_reserved`.

Reserved data names: `{sbase}` (inj), `{sbase1}`/`{sbase2}` (twop).

### Expression Syntax

- Fortran: `**` for exponents, `dsqrt()`, `dcos()`, `dsin()`, `dlog10()`, etc.
- Boolean: `.lt.`, `.le.`, `.gt.`, `.ge.`, `.eq.`, `.ne.`
- `{name}` → data/parameter reference (becomes `prm(N)`)
- `[name]` → state/input variable reference (becomes `x(N)`)
- `t` (bare) → simulation time
- Built-in functions: `equal()`, `ppower()`, `qpower()` (inj), `vcomp()`, `satur()`, `vrectif()`, `vinrectif()` (exc)

### Codegen Validation Rules

- Equation count must equal state count
- Mandatory outputs must appear in at least one block as output (via `getstate(.true.)`)
- No duplicate names across data/params/states
- States cannot use input variable names
- `f_inj` only in inj; `f_twop_bus1`/`f_twop_bus2` only in twop
- Max: 500 data, 100 parameters, 500 states, 20-char names, 200-char lines, 300-char expressions

### Block DSL Line Reading

Each block in `%models` reads N argument lines after `& blockname`. Lines are either:
- **State references** (read via `getstate`) — plain state name or input variable
- **Parameter/expressions** (read via `getparam`) — `{data}`, `{param}`, or inline numeric

The `algeq` block is special: its single line is a raw Fortran expression (the algebraic equation set to zero).

### Switch Block Quirk

For `switch2/3/4/5`, DSL line order is: input states, then control selector (read with `getstate(.true.)`), then actual algebraic output (read with `getstate(.false.)`). The control signal — not the output — registers for mandatory output tracking.

### FSA Block Format

```
& fsa
{initial_state_number}
#1
{algebraic equations, same count per state}
->2
{boolean transition condition}
#2
...
##
```

## Interactive Features

### Check Model (toolbar ✓ button)
Runs structural validation via `CheckModel.run()` and displays the report in the permanent Issues panel in the right sidebar. Categories include missing mandatory outputs, missing/disconnected RAMSES I/O per model type, disconnected input ports, floating state references, undeclared parameters / states, and uninitialised `%parameters`/`%states`.

### Floating-state detection (on load / export)
`Validate.findFloatingStateIssues()` runs on DSL & project load (warning toast) and on Export DSL (blocking modal with "Export Anyway"). It flags any state literal sitting on a port of block A while the same state is referenced by another block — i.e. a wire is missing.

### Algeq semantics
Algeq blocks have **0 outputs** by default; the inspector exposes an **Output states (comma-separated)** field that promotes any listed state to an output pin. On DSL load the adapter auto-picks at most one (priority: mandatory RAMSES output → state referenced by the fewest peers; reserved names like `if` are never promoted), stores the choice in `args.output_states`, and creates the corresponding wires. Editing the expression in the inspector rebuilds the node's connectors live.

### RAMSES I/O pseudo-nodes
`ramses_in` / `ramses_out` are visual-only block types (skipped by the emitter) that surface model-type inputs/outputs on the canvas. They are auto-seeded on "New" and on DSL load, and auto-wired to every block that references the corresponding state.

## Design Document

Full architecture design at `docs/DESIGN.md` — covers all design decisions, phase plan, and detailed specifications.
