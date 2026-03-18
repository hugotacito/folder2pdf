# folder2pdf

Convert a folder's contents (and its sub-folders) into a single PDF document.  
Text and source-code files are included as readable content; image files are embedded with captions.  
The output is useful for AI ingestion tools like **NotebookLLM**.

---

## Installation

```bash
pip install .
```

Or install from the requirements file:

```bash
pip install -r requirements.txt
python -m folder2pdf.cli <folder> [options]
```

---

## Usage

```
folder2pdf <folder> [options]
```

### Arguments

| Argument | Description |
|---|---|
| `folder` | Path to the folder to convert. |

### Options

| Option | Description |
|---|---|
| `-o`, `--output OUTPUT` | Destination PDF file path (default: `output.pdf`). |
| `--no-images` | Do not embed image files in the PDF. |
| `-e`, `--extensions EXT [EXT ...]` | Whitelist of file extensions to include, e.g. `.py .md .txt`. When omitted, built-in defaults are used. |

### Examples

Convert a folder to PDF:
```bash
folder2pdf ./my-project -o my-project.pdf
```

Convert without images:
```bash
folder2pdf ./my-project -o my-project.pdf --no-images
```

Only include Python and Markdown files:
```bash
folder2pdf ./my-project -o my-project.pdf -e .py .md
```

---

## What gets included

**Text / source-code files** (default extensions):

`.txt` `.md` `.rst` `.csv` `.tsv` `.json` `.xml` `.yaml` `.yml` `.toml`  
`.ini` `.cfg` `.conf` `.env` `.log` `.py` `.js` `.ts` `.jsx` `.tsx`  
`.html` `.htm` `.css` `.scss` `.java` `.c` `.cpp` `.h` `.hpp` `.cs`  
`.go` `.rs` `.rb` `.php` `.sh` `.bash` `.zsh` `.ps1` `.bat` `.sql` and more.

**Image files** (embedded with captions):

`.png` `.jpg` `.jpeg` `.gif` `.bmp` `.webp` `.tiff`

**Skipped automatically:**

- Hidden files and directories (names starting with `.`)
- Binary files without a recognised extension

---

## Programmatic API

```python
from folder2pdf.converter import convert

pdf_path = convert(
    folder="./my-project",
    output="my-project.pdf",
    include_images=True,
    extensions=None,   # None = use built-in defaults
)
print(f"PDF saved to {pdf_path}")
```

---

## Dependencies

- [fpdf2](https://pyfpdf.github.io/fpdf2/) — PDF generation
- [Pillow](https://pillow.readthedocs.io/) — image processing
