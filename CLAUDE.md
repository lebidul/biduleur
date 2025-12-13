# CLAUDE.md - Bidul Project Guide

## Project Overview

**Bidul** is a Python-based event management and document generation system that transforms event data (Excel/CSV) into professionally formatted PDF documents and SVG graphics for "Le Bidul" - a monthly cultural agenda publication.

## Architecture

Three-module pipeline:
```
Input (CSV/XLS) → [BIDULEUR] → HTML → [MISENPAGEUR] → PDF/SVG/PNG
                                            ↑
                                      [leTruc GUI]
```

- **biduleur/**: Data parsing & HTML generation
- **misenpageur/**: Layout & PDF/SVG rendering (ReportLab)
- **leTruc/**: Tkinter GUI application

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
| `leTruc/app.py` | Main GUI application class |

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

- **Data**: pandas, openpyxl, beautifulsoup4
- **Rendering**: reportlab, Pillow, PyYAML, lxml, svglib
- **GUI**: tkinterdnd2
- **External**: pdf2svg (for SVG export)

## Testing

No formal test framework. Manual testing via CLI/GUI. GitHub Actions validates builds.

## Key Features

- Auto-fitting typography (font size scales to content)
- Intelligent logo packing (rectpack algorithm)
- SVG logos and "ours" (legal mentions) support
- Icon replacement (chapeau, free icons)
- INACTIF column for event filtering
- Instagram Stories export (1080x1920 PNG)
- Debug mode with timestamped artifacts

## Python Version

Requires Python 3.10+ (uses `match` statement, modern type hints)
