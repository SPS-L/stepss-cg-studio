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

CI runs pytest on Python 3.10–3.12 via GitHub Actions (`.github/workflows/ci.yml`). That workflow **only tests**; building, gating and publishing the wheel belong to `sync-codegen-release.yml`.

## CODEGEN is bundled, and that decides the version number

The wheel carries the CODEGEN executables for all three platforms under
`src/cg_studio/bin/{lin,win,mac}/`, committed to this repository. `Run Codegen`
therefore works on a fresh `pip install stepss-cg-studio`, which is the whole
point: CODEGEN is distributed as a compiled executable and there was previously
nowhere for a user to obtain one, so the editor's headline action failed on
every fresh install.

Three things follow, and none of them is optional:

- **There is no "Codegen binary path" setting, and it must not come back.**
  `resolve_codegen()` takes no argument, reads no config key and does not search
  `PATH`. `load_config()` deletes a `codegen_path` left behind by an older
  install rather than ignoring it in place, because a setting still sitting in
  `config.json` reads as though it decides something. If you find yourself
  adding a parameter to `resolve_codegen()`, that is the regression.

- **The version is `<bundled CODEGEN X.Y>.<counter>`**, computed by
  `tools/bump_version.sh` from the tags that already exist: CODEGEN v5.3 makes
  the next release 5.3.0, a python-only change after it 5.3.1, and CODEGEN v5.4
  restarts at 5.4.0. `tests/test_config.py` asserts `__version__` and
  `_bundled.py` agree, so bumping one by hand fails the suite. The counter is
  derived rather than stored, so a re-run recomputes the same value and a tag
  created by hand is taken into account for free.

  CODEGEN versions are two components from v5.3 onwards precisely so this works;
  its release workflow rejects a three-component tag. `bump_version.sh` still
  takes only the first two components, which keeps the older v5.1.0/v5.2.0
  releases usable as a base instead of producing a four-component wheel.

- **The wheel is mixed-licence.** The Python is Apache 2.0; the bundled
  executables are Dr. Thierry Van Cutsem's property under an Academic Public
  License. `pyproject.toml` says so, the classifier claiming OSI Apache 2.0 for
  the whole distribution is gone, and `bin/LICENSE-CODEGEN` ships beside the
  binaries. `getting-started/license.md` in stepss-docs is the single owner of
  these facts; everything here is a summary pointing at it. Never re-add
  `License :: OSI Approved :: Apache Software License`.

`tools/update_codegen.sh <tag>` is what refreshes the binaries. It unpacks each
archive into its own directory: the Linux and macOS tarballs both contain a
member named `CODEGEN`, and a flat extraction leaves one platform holding the
other's executable, which is not distinguishable by name, size or `file` output.

## Releases

`.github/workflows/sync-codegen-release.yml` is the only thing that releases
this package, and it is the registered **PyPI trusted publisher**. A trusted
publisher binds to the workflow *filename*, so renaming that file or moving the
publish step elsewhere breaks the upload with a 403 no re-run can fix.

It fires on a `repository_dispatch` (`codegen-release`) from stepss-Codegen, and
on `workflow_dispatch` for a python-only release (`source: manual`) or a
rehearsal. A dispatch is fire-and-forget and nothing polls: if the sender's
`notify-cg-studio` job goes red, this repository silently keeps shipping the
previous CODEGEN until someone runs the workflow by hand.

Shape, and the reasons behind it — this mirrors stepss-python-ui's
`sync-upstream-release.yml`, which is the reference if anything here needs
extending:

- `workflow_dispatch` **rehearses by default**. Only `publish: true` (or a real
  dispatch) can reach `main` or PyPI; an unset input fails closed.
- A **duplicate dispatch** is detected by comparing `_bundled.py` against the
  incoming tag, not by the computed version, which is a fresh counter and so can
  never pre-exist. 'Re-run all jobs' on the sender replays its release event and
  fires the dispatch again; republishing byte-identical executables would spend
  a second PyPI version, and a PyPI version can never be reclaimed.
- The `gate` job installs the **built wheel** on Linux, Windows and macOS and
  makes it generate Fortran on each. It also reads the version back out of the
  executable with `CODEGEN -v`: a wheel whose `_bundled.py` and whose `bin/`
  disagree passes every other check.
- `main` is fast-forwarded **before** the release is cut and the release
  **before** the PyPI upload, so the least reversible step is last. If only the
  upload fails, the gated wheel is attached to the release and can be uploaded
  by hand — never a rebuild.
- `report-failure` fires on `cancelled()` as well as `failure()`: a timeout
  during the PyPI upload produces no failed job at all, and that is the most
  dangerous moment in the pipeline.

## Architecture

### Backend (`src/cg_studio/`)

- **`app.py`** — FastAPI server. API routes registered before static file mount (SPA fallback). Key endpoints: `POST /parse`, `POST /emit`, `POST /run_codegen`, `GET /blocks`, `GET /mandatory_outputs`, `GET /ramses_inputs`, `GET /ramses_reserved`, `GET /codegen_version`, `GET/PUT /config`.
- **`dsl_parser.py`** — Converts DSL `.txt` → `ModelProject` dict. The critical `_parse_blocks()` method counts argument lines by looking up block name in `blocks.json` to determine `len(dsl_lines)`. Maps positional lines to template tokens (`{{input}}`, `{{output}}`, `{{K}}`, etc.). Exposes three name dicts: `RAMSES_INPUT_STATES` (palette-visible inputs), `MANDATORY_OUTPUTS`, and `RAMSES_INPUTS` (full reserved-name list incl. `if` for exc).
- **`dsl_emitter.py`** — Inverse of parser: `ModelProject` dict → DSL `.txt`. Expects blocks in topologically-sorted order (frontend must sort before calling `/emit`). Normalises block comments to start with `!`.
- **`config.py`** — Platform-aware config store. Reads/writes `config.json` under `%LOCALAPPDATA%\cg-studio\` (Windows) or `~/.config/cg-studio/` (Linux/macOS). Keys: workspace dir, host, port. Also owns `resolve_codegen()`, which finds the bundled executable, and `codegen_version()`.
- **`_bundled.py`** — one constant, `CODEGEN_VERSION`, naming the CODEGEN release in `bin/`. Written by `tools/update_codegen.sh`; never edit by hand.
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
