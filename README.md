[![PyPI version](https://img.shields.io/pypi/v/stepss-cg-studio)](https://pypi.org/project/stepss-cg-studio/)
[![CI](https://img.shields.io/github/actions/workflow/status/SPS-L/stepss-cg-studio/ci.yml?branch=main&label=tests)](https://github.com/SPS-L/stepss-cg-studio/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0%20%2B%20bundled%20CODEGEN-green.svg)](#license)
[![Docs](https://img.shields.io/github/actions/workflow/status/SPS-L/stepss-docs/deploy.yml?branch=main&label=docs)](https://stepss.sps-lab.org/developer/cg-studio/)

# CODEGEN Studio

CODEGEN Studio is a browser-based, drag-and-drop visual editor for building [STEPSS CODEGEN](https://stepss.sps-lab.org/developer/user-models/) User-Defined Models, part of the [STEPSS](https://stepss.sps-lab.org/) power system simulation platform. It lets you create device models by wiring blocks on a canvas instead of manually writing DSL files.

STEPSS has been developed by [Dr. Petros Aristidou](https://sps-lab.org/) (Cyprus University of Technology) and Dr. Thierry Van Cutsem (Emeritus, University of Liège).

## Overview

CODEGEN Studio replaces the manual editing of CODEGEN DSL `.txt` files with a graphical workflow. You drag blocks from a categorised palette, connect input/output ports to define signal flow, fill in metadata tables, and export ready-to-compile DSL files, or run the bundled CODEGEN directly from the editor to generate Fortran `.f90` source.

The tool supports all four CODEGEN model types:

| Type | Purpose | Mandatory Outputs |
|------|---------|-------------------|
| **EXC** | Excitation controller | `vf` |
| **TOR** | Torque controller | `tm` |
| **INJ** | Current injector | `ix`, `iy` |
| **TWOP** | Two-port device | `ix1`, `iy1`, `ix2`, `iy2` |

## Features

- **Drag-and-drop block diagram editor**: assemble models visually on a canvas with 54 built-in blocks
- **Live DSL preview**: syntax-highlighted code updates in real time as you edit
- **Lossless round-trip**: import existing `.txt` DSL files with automatic canvas layout, edit, and re-export
- **One-click Fortran generation**: the CODEGEN executables ship in the wheel, so this works on a fresh install
- **Project save/load**: JSON project files preserve full editor state including block positions
- **Mandatory output validation**: warns when required outputs for the model type are missing
- **Undo/redo**: 60-step history with keyboard shortcuts
- **Extensible block catalogue**: add new blocks via a single JSON entry, no code changes required
- **No build step**: vanilla JavaScript frontend served by a Python backend

## Installation

### Requirements

- Python ≥ 3.10
- A modern browser (Chrome, Firefox, or Edge)

### Install from PyPI

```bash
pip install stepss-cg-studio
```

The CODEGEN executables are bundled in the wheel, for Linux x86-64, Windows x86-64 and macOS Apple Silicon. **Run Codegen works on a fresh install**: there is nothing to obtain, install or configure, and no setting to point anywhere.

macOS is the one platform that needs anything else:

```bash
brew install gcc
```

Apple does not support fully static executables, so that CODEGEN build links against `libgfortran`. The Linux and Windows builds are statically linked and need nothing at all.

The bundled CODEGEN is named in Settings (gear icon), and in the two leading components of this package's own version: `stepss-cg-studio` 5.3.0 and 5.3.1 both run CODEGEN 5.3. See [Versioning](#versioning).

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

1. **Select model type and name**: choose EXC, TOR, INJ, or TWOP from the toolbar dropdown
2. **Add blocks**: drag blocks from the left-hand palette onto the canvas
3. **Connect blocks**: wire output ports to input ports to define signal flow
4. **Edit block properties**: select a block to configure output names and arguments in the inspector
5. **Populate metadata**: fill in Data, Parameters, States, and Observables in the tabs below the canvas
6. **Export**: click "Export DSL" for the `.txt` file, or "Run Codegen" to generate Fortran directly

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl/Cmd + S | Save project |
| Ctrl/Cmd + Z | Undo |
| Ctrl/Cmd + Shift + Z (or Ctrl/Cmd + Y) | Redo |
| Delete / Backspace | Delete selected block |
| Escape | Close modal |

## Project Structure

```
stepss-cg-studio/
├── pyproject.toml              # Package config, dependencies, entry point
├── src/cg_studio/
│   ├── __init__.py             # Package version (<bundled CODEGEN X.Y>.<counter>)
│   ├── _bundled.py             # Which CODEGEN release bin/ holds
│   ├── __main__.py             # python -m cg_studio support
│   ├── cli.py                  # CLI entry point (cg-studio command)
│   ├── config.py               # Platform-aware config & codegen resolution
│   ├── app.py                  # FastAPI server & API endpoints
│   ├── dsl_parser.py           # DSL .txt → ModelProject dict
│   ├── dsl_emitter.py          # ModelProject dict → DSL .txt
│   ├── bin/                    # Bundled CODEGEN: lin/, win/, mac/ + LICENSE-CODEGEN
│   └── frontend/               # Static web assets (no build step)
│       ├── index.html
│       ├── css/style.css
│       ├── js/                 # Vanilla JS modules
│       └── blocks.json         # Block catalogue (54 blocks, extend here)
├── tests/                      # Pytest test suite (~150 tests)
├── tools/                      # Release automation: update_codegen.sh, bump_version.sh
├── examples/                   # Example DSL models (.txt) and projects (.json)
├── docs/                       # Design documents
├── run.bat                     # Windows dev launcher
└── run.sh                      # Linux/macOS dev launcher
```

## Adding New Blocks

Edit `src/cg_studio/frontend/blocks.json`: add a single JSON entry with the block name, ports, argument schema, DSL line templates, and category. No JavaScript or Python changes required.

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

- **Bundled CODEGEN**: which CODEGEN release this install runs. Read-only, and not a setting: the package version is derived from it, so running a different CODEGEN means installing a different `stepss-cg-studio`.
- **Server host**: change to `0.0.0.0` for network access (default: `127.0.0.1`)
- **Server port**: HTTP port (default: `8765`)

Settings are stored in a platform-specific config directory:
- **Windows:** `%LOCALAPPDATA%\cg-studio\config.json`
- **Linux/macOS:** `~/.config/cg-studio/config.json`

Also editable via the REST API at `http://localhost:8765/docs`.

## Documentation

Full documentation is available at [https://stepss.sps-lab.org/developer/cg-studio/](https://stepss.sps-lab.org/developer/cg-studio/).

- [User-Defined Models](https://stepss.sps-lab.org/developer/user-models/): DSL format specification
- [CODEGEN Blocks Library](https://stepss.sps-lab.org/developer/codegen-library/): complete block reference
- [CODEGEN Model Examples](https://stepss.sps-lab.org/developer/codegen-examples/): annotated example files

## Versioning

The version is `<bundled CODEGEN X.Y>.<counter>`, so the leading pair always names the generator in the wheel:

| Event | Version |
|---|---|
| CODEGEN v5.3 published | `5.3.0` |
| a change on the Python side | `5.3.1` |
| another change on the Python side | `5.3.2` |
| CODEGEN v5.4 published | `5.4.0` |

Publishing a CODEGEN release is what starts a sequence: `stepss-Codegen` tells this repository, `.github/workflows/sync-codegen-release.yml` refreshes the executables, proves the rebuilt wheel generates Fortran on all three platforms, and only then releases and publishes to PyPI. Nothing here is bumped by hand.

## License

This package is **mixed-licence**, and the badge above says so on purpose.

- The Python and JavaScript in this repository are **Apache License 2.0**. See [LICENSE](LICENSE). Copyright © Petros Aristidou.
- The **CODEGEN executables bundled in the wheel are not**. CODEGEN is the property of **Dr. Thierry Van Cutsem** and is distributed as a compiled executable under an **Academic Public License**: free of charge for non-commercial use (teaching, and research at universities and non-profit institutions); commercial use requires a separate licence from the authors. Its source is in none of the public STEPSS repositories. The licence text ships beside the executables as `cg_studio/bin/LICENSE-CODEGEN`.

[STEPSS licensing](https://stepss.sps-lab.org/getting-started/license/) is the single owner of these facts; everything above is a summary of that page.

## Authors

Developed and maintained by the [Sustainable Power Systems Laboratory (SPS-L)](https://sps-lab.org/) at the Cyprus University of Technology, under the direction of Dr. Petros Aristidou.

- [Dr. Petros Aristidou](https://sps-lab.org/): Cyprus University of Technology
- Dr. Thierry Van Cutsem: Emeritus, University of Liège

## Support

- Documentation: [https://stepss.sps-lab.org/developer/cg-studio/](https://stepss.sps-lab.org/developer/cg-studio/)
- Issues: [https://github.com/SPS-L/stepss-cg-studio/issues](https://github.com/SPS-L/stepss-cg-studio/issues)
- Project page: [https://sps-lab.org/](https://sps-lab.org/)
