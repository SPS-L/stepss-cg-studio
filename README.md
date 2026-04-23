[![PyPI version](https://img.shields.io/pypi/v/stepss-cg-studio)](https://pypi.org/project/stepss-cg-studio/)
[![CI](https://img.shields.io/github/actions/workflow/status/SPS-L/stepss-cg-studio/ci.yml?branch=main&label=tests)](https://github.com/SPS-L/stepss-cg-studio/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docs](https://img.shields.io/github/actions/workflow/status/SPS-L/stepss-docs/deploy.yml?branch=main&label=docs)](https://stepss.sps-lab.org/developer/cg-studio/)

# CODEGEN Studio

CODEGEN Studio is a browser-based, drag-and-drop visual editor for building [STEPSS CODEGEN](https://stepss.sps-lab.org/developer/user-models/) User-Defined Models — part of the [STEPSS](https://stepss.sps-lab.org/) power system simulation suite. It lets you create device models by wiring blocks on a canvas instead of manually writing DSL files.

STEPSS has been developed by [Dr. Petros Aristidou](https://sps-lab.org/) (Cyprus University of Technology) and Dr. Thierry Van Cutsem (Emeritus, University of Liège).

## Overview

CODEGEN Studio replaces the manual editing of CODEGEN DSL `.txt` files with a graphical workflow. You drag blocks from a categorised palette, connect input/output ports to define signal flow, fill in metadata tables, and export ready-to-compile DSL files — or run the `codegen` binary directly from the editor to generate Fortran `.f90` source.

The tool supports all four CODEGEN model types:

| Type | Purpose | Mandatory Outputs |
|------|---------|-------------------|
| **EXC** | Excitation controller | `vf` |
| **TOR** | Torque controller | `tm` |
| **INJ** | Current injector | `ix`, `iy` |
| **TWOP** | Two-port device | `ix1`, `iy1`, `ix2`, `iy2` |

## Key Features

- **Drag-and-drop block diagram editor** — assemble models visually on a canvas with 54 built-in blocks
- **Live DSL preview** — syntax-highlighted code updates in real time as you edit
- **Lossless round-trip** — import existing `.txt` DSL files with automatic canvas layout, edit, and re-export
- **One-click Fortran generation** — run the `codegen` binary directly from the browser
- **Project save/load** — `.cgproj` files preserve full editor state including block positions
- **Mandatory output validation** — warns when required outputs for the model type are missing
- **Undo/redo** — 60-step history with keyboard shortcuts
- **Extensible block catalogue** — add new blocks via a single JSON entry, no code changes required
- **No build step** — vanilla JavaScript frontend served by a Python backend

## Installation

### Requirements

- Python ≥ 3.10
- A modern browser (Chrome, Firefox, or Edge)

### Install from PyPI

```bash
pip install stepss-cg-studio
```

The CODEGEN binary is bundled in the package for Windows and Linux — no separate download needed. On macOS, the binary is not yet available; you can provide your own via Settings.

### Install from source (for development)

```bash
git clone https://github.com/SPS-L/stepss-cg-studio.git
cd stepss-cg-studio
pip install -e ".[dev]"
```

## Quick Start

```bash
cg-studio
```

This starts the local server and opens your browser to the editor at `http://localhost:8765`. That's it.

You can also run it as a Python module:

```bash
python -m cg_studio
```

### CLI options

```bash
cg-studio --port 9000        # use a different port
cg-studio --host 0.0.0.0     # allow network access
cg-studio --no-browser        # start server without opening browser
```

### Building a model

1. **Select model type and name** — choose EXC, TOR, INJ, or TWOP from the toolbar dropdown
2. **Add blocks** — drag blocks from the left-hand palette onto the canvas
3. **Connect blocks** — wire output ports to input ports to define signal flow
4. **Edit block properties** — select a block to configure output names and arguments in the inspector
5. **Populate metadata** — fill in Data, Parameters, States, and Observables in the tabs below the canvas
6. **Export** — click "Export DSL" for the `.txt` file, or "Run Codegen" to generate Fortran directly

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl/Cmd + S | Save project |
| Ctrl/Cmd + Z | Undo |
| Ctrl/Cmd + Shift + Z | Redo |
| Delete / Backspace | Delete selected block |
| Escape | Close modal |

## Project Structure

```
stepss-cg-studio/
├── pyproject.toml              # Package config, dependencies, entry point
├── src/cg_studio/
│   ├── __init__.py             # Package version
│   ├── __main__.py             # python -m cg_studio support
│   ├── cli.py                  # CLI entry point (cg-studio command)
│   ├── config.py               # Platform-aware config & codegen resolution
│   ├── app.py                  # FastAPI server & API endpoints
│   ├── dsl_parser.py           # DSL .txt → ModelProject dict
│   ├── dsl_emitter.py          # ModelProject dict → DSL .txt
│   ├── bin/                    # Bundled CODEGEN binaries
│   └── frontend/               # Static web assets (no build step)
│       ├── index.html
│       ├── css/style.css
│       ├── js/                 # Vanilla JS modules
│       └── blocks.json         # Block catalogue (54 blocks, extend here)
├── tests/                      # Pytest test suite (~140 tests)
├── examples/                   # Example .cgproj project files
├── docs/                       # Design documents
├── run.bat                     # Windows dev launcher
└── run.sh                      # Linux/macOS dev launcher
```

## Adding New Blocks

Edit `src/cg_studio/frontend/blocks.json` — add a single JSON entry with the block name, ports, argument schema, DSL line templates, and category. No JavaScript or Python changes required.

## Running Tests

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_parser.py -v

# Run a single test
pytest tests/test_parser.py::test_function_name -v
```

CI runs pytest on Python 3.10–3.12 via GitHub Actions.

## Settings

Access via the gear icon in the toolbar:

- **Codegen binary path** — path to the `codegen` executable (default: bundled binary)
- **Server host** — change to `0.0.0.0` for network access (default: `127.0.0.1`)
- **Server port** — HTTP port (default: `8765`)

Settings are stored in a platform-specific config directory:
- **Windows:** `%LOCALAPPDATA%\cg-studio\config.json`
- **Linux/macOS:** `~/.config/cg-studio/config.json`

Also editable via the REST API at `http://localhost:8765/docs`.

## Documentation

Full documentation is available at [https://stepss.sps-lab.org/developer/cg-studio/](https://stepss.sps-lab.org/developer/cg-studio/).

- [User-Defined Models](https://stepss.sps-lab.org/developer/user-models/) — DSL format specification
- [CODEGEN Blocks Library](https://stepss.sps-lab.org/developer/codegen-library/) — complete block reference
- [CODEGEN Model Examples](https://stepss.sps-lab.org/developer/codegen-examples/) — annotated example files

## License

MIT — see [LICENSE](LICENSE).

## Authors

Developed by the [Sustainable Power Systems Lab (SPS-L)](https://sps-lab.org), Cyprus University of Technology.

- [Dr. Petros Aristidou](https://sps-lab.org/) — Cyprus University of Technology
- Dr. Thierry Van Cutsem — Emeritus, University of Liège

## Support

- Documentation: [https://stepss.sps-lab.org/developer/cg-studio/](https://stepss.sps-lab.org/developer/cg-studio/)
- Issues: [https://github.com/SPS-L/stepss-cg-studio/issues](https://github.com/SPS-L/stepss-cg-studio/issues)
- Project page: [https://sps-lab.org/](https://sps-lab.org/)
