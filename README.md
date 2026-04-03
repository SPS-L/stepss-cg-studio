# CODEGEN Visual Block Editor — `cg-studio`

A browser-based, drag-and-drop block diagram editor for building [STEPSS CODEGEN](https://stepss.sps-lab.org/developer/user-models/) DSL models.

## What it does

- Drag, drop and connect CODEGEN blocks on a canvas to assemble device models
- Supports all 4 model types: **EXC**, **TOR**, **INJ**, **TWOP**
- Live DSL preview updates as you edit
- Save/load `.cgproj` project files (canvas + model data)
- Export DSL `.txt` files
- Run `codegen` binary in one click to generate `.f90`
- Import existing `.txt` DSL files → canvas auto-layout

## Requirements

- Python ≥ 3.10
- `pip install fastapi uvicorn aiofiles`
- A browser (Chrome/Firefox/Edge)
- (Optional) CODEGEN binary for `.f90` generation

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure codegen binary path (optional)
# Edit server/config.json

# Start the server
python server/app.py

# Open in browser
# http://localhost:8765
```

On Windows, double-click `run.bat`. On Linux/macOS, run `./run.sh`.

## Project Structure

```
stepss-cg-studio/
├── server/
│   ├── app.py              # FastAPI server
│   ├── dsl_parser.py       # DSL .txt → ModelProject dict
│   ├── dsl_emitter.py      # ModelProject dict → DSL .txt
│   └── config.json         # codegen binary path, workspace
├── frontend/
│   ├── index.html          # Single-page app
│   ├── css/style.css
│   ├── js/
│   │   ├── main.js
│   │   ├── canvas.js
│   │   ├── sidebar.js
│   │   ├── forms.js
│   │   ├── dsl_preview.js
│   │   ├── store.js
│   │   └── api.js
│   └── blocks.json         # Block catalogue (extend here for new blocks)
├── examples/               # Example .cgproj project files
├── tests/
│   ├── test_parser.py
│   └── test_emitter.py
├── docs/
│   └── DESIGN.md           # Full architecture design document
├── requirements.txt
├── run.bat
└── run.sh
```

## Adding New Blocks

Edit `frontend/blocks.json` — add one JSON entry with the block name, ports, argument schema, and DSL line template. No JavaScript changes required.

## License

MIT — see [LICENSE](LICENSE)

## Authors

Developed by the [Sustainable Power Systems Lab (SPS-L)](https://sps-lab.org), Cyprus University of Technology.
