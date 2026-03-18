# folder2pdf

Convert a folder's contents (and its sub-folders) into a single PDF document.  
Text and source-code files are included as readable content; image files are embedded with captions.  
The output is useful for AI ingestion tools like **NotebookLLM**.

---

## Installation

```bash
pip install folder2pdf
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
| `-b`, `--blacklist PATTERN [PATTERN ...]` | Glob patterns (gitignore-style) for files or directories to exclude, e.g. `tests/ *.log secret.txt`. |
| `--no-gitignore` | Do not read or apply the `.gitignore` file found in the target folder. |

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

Exclude test files and log files:
```bash
folder2pdf ./my-project -o my-project.pdf -b "tests/" "*.log"
```

Ignore `.gitignore` rules:
```bash
folder2pdf ./my-project -o my-project.pdf --no-gitignore
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
- Files matched by the `.gitignore` in the target folder (requires `pathspec`)
- Files matched by the `--blacklist` patterns
- Binary files without a recognised extension

---

## Project Summary (cover page)

The generated PDF cover page includes a **Project Summary** section with:

- **Total Files Processed** – number of files included
- **Total Lines of Code** – combined line count across all text files
- **Image Files** – number of image files embedded
- **Lines by Extension** – per-extension line counts, sorted by descending count

---

## Programmatic API

```python
from folder2pdf.converter import convert

pdf_path = convert(
    folder="./my-project",
    output="my-project.pdf",
    include_images=True,
    extensions=None,       # None = use built-in defaults
    blacklist=["tests/", "*.log"],  # optional exclusion patterns
    use_gitignore=True,    # read & apply .gitignore in the folder
)
print(f"PDF saved to {pdf_path}")
```

---

## Dependencies

- [fpdf2](https://pyfpdf.github.io/fpdf2/) — PDF generation
- [Pillow](https://pillow.readthedocs.io/) — image processing
- [pathspec](https://python-path-specification.readthedocs.io/) — gitignore-style pattern matching
