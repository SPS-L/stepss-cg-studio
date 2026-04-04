# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

STEPSS CG Studio is a browser-based drag-and-drop block diagram editor for building CODEGEN DSL models for RAMSES power system device modeling. Full-stack app: Python FastAPI backend + vanilla JS frontend (no build step).

Four model types: `exc` (excitation), `tor` (torque), `inj` (injector), `twop` (two-port). Each has specific RAMSES input variables and mandatory output states defined in `dsl_parser.py` (`RAMSES_INPUTS`, `MANDATORY_OUTPUTS`).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests (~75 tests)
pytest tests/ -v

# Run specific test files
pytest tests/test_parser.py -v
pytest tests/test_api.py -v

# Run a single test
pytest tests/test_parser.py::test_function_name -v

# Start server (http://localhost:8765)
python server/app.py
```

CI runs pytest on Python 3.10–3.12 via GitHub Actions (`.github/workflows/ci.yml`).

## Architecture

### Backend (`server/`)

- **`app.py`** — FastAPI server. API routes registered before static file mount (SPA fallback). Key endpoints: `POST /parse`, `POST /emit`, `POST /run_codegen`, `GET /blocks`, `GET/PUT /config`.
- **`dsl_parser.py`** — Converts DSL `.txt` → `ModelProject` dict. The critical `_parse_blocks()` method counts argument lines by looking up block name in `blocks.json` to determine `len(dsl_lines)`. Maps positional lines to template tokens (`{{input}}`, `{{output}}`, `{{K}}`, etc.).
- **`dsl_emitter.py`** — Inverse of parser: `ModelProject` dict → DSL `.txt`. Expects blocks in topologically-sorted order (frontend must sort before calling `/emit`).
- **`config.json`** — Runtime config (codegen binary path, workspace dir, host, port).

### Frontend (`frontend/`)

Vanilla JS SPA, no build step. Drawflow (canvas) and CodeMirror 6 (DSL preview) loaded from CDN.

- **`store.js`** — Canonical `ModelProject` state, Kahn's topological sort, undo/redo (60-step ring buffer), event bus.
- **`canvas.js`** — Drawflow integration, drag-from-sidebar, port connections → signal assignment, Sugiyama auto-layout algorithm.
- **`main.js`** — App bootstrap, toolbar handlers, keyboard shortcuts (Ctrl+Z/Y/S), file I/O, Settings modal.
- **`forms.js`** — Right-panel tabs: model metadata, data/params/states/observables tables, block properties form.
- **`palette.js`** — Block palette UI grouped by category with search filter.
- **`dsl_preview.js`** — Debounced (600ms) live DSL preview using CodeMirror.
- **`api.js`** — `fetch()` wrappers for backend endpoints.

### Key Data Flow

1. User connects blocks on canvas → `store.js` updates `ModelProject.blocks[].inputStates`/`outputState`
2. Topological sort (Kahn's algorithm in `store.js`) orders blocks before emit
3. `POST /emit` converts ordered `ModelProject` → DSL text
4. DSL preview updates live via debounced store listener

### Block Catalogue (`frontend/blocks.json`)

51 blocks across categories (Transfer Functions, Limiters, Controllers, etc.). Each entry defines `dsl_lines` templates, `args` schema, `inputs`/`outputs`, and `category`. **Extending: add a JSON entry here — no code changes needed.**

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

| Type | Input Variables | Mandatory Outputs |
|------|----------------|-------------------|
| `exc` | `v`, `p`, `q`, `omega`, `if`, `vf` | `vf` |
| `tor` | `p`, `omega`, `tm` | `tm` |
| `inj` | `vx`, `vy`, `omega`, `ix`, `iy` | `ix`, `iy` |
| `twop` | `vx1`, `vy1`, `vx2`, `vy2`, `omega1`, `omega2`, `ix1`, `iy1`, `ix2`, `iy2` | `ix1`, `iy1`, `ix2`, `iy2` |

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

## Design Document

Full architecture design at `docs/DESIGN.md` — covers all design decisions, phase plan, and detailed specifications.
