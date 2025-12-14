# CLAUDE.md - Bidul Project Guide

## Project Overview

**Bidul** is a Python-based event management and document generation system that transforms event data (Excel/CSV) into professionally formatted PDF documents and SVG graphics for "Le Bidul" - a monthly cultural agenda publication for the Sarthe region in France.

## Architecture

### Core Pipeline
```
Input (CSV/XLS) → [BIDULEUR] → HTML → [MISENPAGEUR] → PDF/SVG/PNG
                                            ↑
                                      [leTruc GUI]
```

### Modules

| Module | Purpose |
|--------|---------|
| **biduleur/** | Data parsing & HTML generation from Excel/CSV |
| **misenpageur/** | Layout engine & PDF/SVG rendering (ReportLab) |
| **leTruc/** | Tkinter GUI application |
| **publisher/** | Social media automation (Instagram, Facebook) |
| **indexer/** | OCR pipeline for PDF archive extraction |
| **indexer_ia/** | AI-enhanced OCR with Google Drive integration |
| **tapageur/** | Additional processing utilities |
| **outils-bidul/** | Utility scripts (gallery, flyers, covers) |

## Quick Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Launch GUI
python run_gui.py

# CLI - Full pipeline
python cli.py -i input.xlsx --out output.pdf

# CLI - Data only (XLS → HTML)
python -m biduleur.main input.xlsx --out-bidul output.html

# CLI - Render only (HTML → PDF)
python -m misenpageur.main --html input.html --out output.pdf

# Build Windows executable
pip install pyinstaller==6.6.0
pyinstaller bidul.spec --clean --noconfirm
```

## Key Files

| File | Purpose |
|------|---------|
| `misenpageur/config.yml` | Styling, typography, layout parameters |
| `misenpageur/layout.yml` | Geometric coordinates (points) |
| `biduleur/constants.py` | Column names, HTML constants |
| `misenpageur/misenpageur/draw_logic.py` | Core rendering algorithm |
| `misenpageur/misenpageur/drawing.py` | ReportLab drawing primitives |
| `misenpageur/misenpageur/textflow.py` | Text wrapping and icon handling |
| `misenpageur/misenpageur/config.py` | Config dataclass with YAML loading |
| `leTruc/app.py` | Main GUI application class |
| `leTruc/callbacks.py` | GUI event handlers |
| `leTruc/widgets.py` | Custom Tkinter widgets |
| `cli.py` | Main CLI entry point |
| `run_gui.py` | GUI launcher script |

## Code Conventions

- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: Prefix with `_`
- **Type hints**: Python 3.10+ syntax throughout
- **Logging**: Use `logging.getLogger(__name__)`

## Configuration-Driven Design

All styling via YAML config files:
```python
@dataclass
class Config:
    input_html: str = "input.html"
    font_name: str = "Arial Narrow"
    # ...

@classmethod
def from_yaml(cls, path: str) -> "Config":
    with open(path, "r", encoding="utf-8") as f:
        return cls(**yaml.safe_load(f))
```

## Dependencies

### Core
- **Data**: pandas, openpyxl, beautifulsoup4
- **Rendering**: reportlab, Pillow, PyYAML, lxml, svglib
- **GUI**: tkinterdnd2
- **External**: pdf2svg (for SVG export)

### Optional (for extended modules)
- **OCR/Indexer**: pytesseract, pdf2image, PyPDF2, opencv-python, langdetect
- **Publisher**: instagrapi, google-api-python-client
- **AI**: transformers, torch (for indexer_ia)

## Testing

Limited test coverage in `misenpageur/tests/`. Manual testing via CLI/GUI. GitHub Actions validates builds.

```bash
# Run existing tests
python -m pytest misenpageur/tests/
```

## Key Features

- Auto-fitting typography (font size scales to content)
- Intelligent logo packing (rectpack algorithm)
- SVG logos and "ours" (legal mentions) support
- Icon replacement (chapeau, free icons)
- INACTIF column for event filtering
- Instagram Stories export (1080x1920 PNG)
- Debug mode with timestamped artifacts
- Config import/export via JSON
- Drag-and-drop file support in GUI

## Python Version

Requires Python 3.10+ (uses `match` statement, modern type hints)

## Project Structure

```
bidul.biduleur/
├── biduleur/          # Data parsing module
├── misenpageur/       # Rendering engine
│   ├── misenpageur/   # Core rendering logic
│   ├── assets/        # Logos, icons, ours
│   └── tests/         # Unit tests
├── leTruc/            # GUI application
├── publisher/         # Social media automation
├── indexer/           # OCR pipeline
├── indexer_ia/        # AI-enhanced OCR
├── outils-bidul/      # Utility scripts
├── cli.py             # CLI entry point
├── run_gui.py         # GUI launcher
└── bidul.spec         # PyInstaller spec
```

## Common Workflows

### Generate PDF from Excel
```bash
python cli.py -i events.xlsx --out bidul.pdf
```

### Debug mode (timestamped outputs)
Set `debug_mode: true` in config.yml or use GUI checkbox.

### Import config in GUI
Use "Importer Config" button to load a previously exported config.json.
