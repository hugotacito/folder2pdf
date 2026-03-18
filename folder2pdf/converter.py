"""Core logic for converting a folder's contents to a PDF document."""

import os
from collections import defaultdict
from pathlib import Path
from fpdf import FPDF

try:
    import pathspec
    _PATHSPEC_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PATHSPEC_AVAILABLE = False

# File extensions treated as plain text / source code
TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".env", ".log",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".scss",
    ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb", ".php",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".sql", ".r", ".swift", ".kt", ".m", ".lua", ".pl", ".hs",
    ".dockerfile", ".makefile",
}

# File extensions treated as images
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}

# Maximum characters read from a single text file
_MAX_FILE_CHARS = 100_000

# Points per mm (fpdf uses mm by default)
_MARGIN = 15

# Search paths for a Unicode-capable monospace TTF font (checked in order)
_MONO_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Courier New.ttf",
    "C:/Windows/Fonts/cour.ttf",
]

# Resolved at import time; None means fall back to built-in Courier with sanitisation
_MONO_FONT_PATH: str | None = next(
    (p for p in _MONO_FONT_CANDIDATES if os.path.exists(p)), None
)
_MONO_FONT_FAMILY = "UniMono"


def _sanitize_for_builtin_font(text: str) -> str:
    """Replace characters outside Latin-1 with a '?' placeholder."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _is_text_file(path: Path) -> bool:
    """Return True if *path* should be treated as a text/source-code file."""
    return path.suffix.lower() in TEXT_EXTENSIONS


def _is_image_file(path: Path) -> bool:
    """Return True if *path* should be treated as an image."""
    return path.suffix.lower() in IMAGE_EXTENSIONS


def _read_text_safe(path: Path, max_chars: int = _MAX_FILE_CHARS) -> str:
    """Read text from *path*, truncating at *max_chars* if needed."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            content = fh.read(max_chars)
        if len(content) == max_chars:
            content += "\n\n[... file truncated ...]"
        return content
    except OSError as exc:
        return f"[Error reading file: {exc}]"


def _load_gitignore_spec(folder: Path):
    """
    Return a *pathspec* ``PathSpec`` built from all ``.gitignore`` files found
    inside *folder* (and its parents up to *folder* itself).  Returns *None*
    when *pathspec* is not installed or no ``.gitignore`` file exists.
    """
    if not _PATHSPEC_AVAILABLE:
        return None

    patterns: list[str] = []
    gitignore = folder / ".gitignore"
    if gitignore.is_file():
        try:
            patterns.extend(gitignore.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            pass

    if not patterns:
        return None

    return pathspec.PathSpec.from_lines("gitignore", patterns)


def _is_gitignored(path: Path, folder: Path, spec) -> bool:
    """Return True if *path* matches the gitignore *spec* relative to *folder*."""
    if spec is None:
        return False
    try:
        rel = path.relative_to(folder)
    except ValueError:
        return False
    # pathspec expects forward-slash paths
    return spec.match_file(rel.as_posix())


def _compile_blacklist(patterns: list[str]) -> list:
    """
    Return a list of compiled pathspec ``PathSpec`` matchers, one per pattern.
    Falls back to simple fnmatch-based matching when pathspec is unavailable.
    """
    if not patterns:
        return []
    if _PATHSPEC_AVAILABLE:
        return [pathspec.PathSpec.from_lines("gitignore", [p]) for p in patterns]
    import fnmatch
    return patterns  # raw patterns; matched via fnmatch below


def _is_blacklisted(path: Path, folder: Path, compiled_blacklist: list) -> bool:
    """Return True if *path* is matched by any entry in *compiled_blacklist*."""
    if not compiled_blacklist:
        return False
    try:
        rel = path.relative_to(folder)
    except ValueError:
        return False
    rel_posix = rel.as_posix()
    if _PATHSPEC_AVAILABLE:
        return any(spec.match_file(rel_posix) for spec in compiled_blacklist)
    import fnmatch
    name = path.name
    for pattern in compiled_blacklist:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_posix, pattern):
            return True
    return False


def _collect_files(
    folder: Path,
    include_images: bool = True,
    extensions: set[str] | None = None,
    blacklist: list[str] | None = None,
    use_gitignore: bool = True,
) -> list[Path]:
    """
    Walk *folder* recursively and return a sorted list of files to include.

    Parameters
    ----------
    folder:
        Root folder to scan.
    include_images:
        Whether to include image files.
    extensions:
        If provided, only include files whose suffix (lower-cased) is in this
        set.  When *None* the default TEXT_EXTENSIONS (plus IMAGE_EXTENSIONS if
        *include_images* is True) are used.
    blacklist:
        Optional list of glob patterns (gitignore-style) for files/directories
        to exclude, e.g. ``["*.log", "tests/", "secret.txt"]``.
    use_gitignore:
        When *True* (the default) read the ``.gitignore`` in *folder* and skip
        any file it matches.
    """
    allowed: set[str]
    if extensions is not None:
        allowed = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    else:
        allowed = set(TEXT_EXTENSIONS)
        if include_images:
            allowed |= IMAGE_EXTENSIONS

    gitignore_spec = _load_gitignore_spec(folder) if use_gitignore else None
    compiled_bl = _compile_blacklist(blacklist or [])

    results: list[Path] = []
    for root, dirs, files in os.walk(folder):
        # Skip hidden directories (e.g. .git, .venv)
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in files:
            if name.startswith("."):
                continue
            p = Path(root) / name
            if p.suffix.lower() not in allowed:
                continue
            if _is_gitignored(p, folder, gitignore_spec):
                continue
            if _is_blacklisted(p, folder, compiled_bl):
                continue
            results.append(p)

    # Return paths in a stable, globally sorted order
    results.sort(key=lambda p: str(p))
    return results


def _compute_stats(files: list[Path], folder: Path) -> dict:
    """
    Compute statistics for the collected *files*.

    Returns a dict with keys:
      total_files        – total number of files
      total_lines        – total lines across all text files
      image_count        – number of image files
      lines_by_extension – dict mapping extension -> line count (text files only)
    """
    total_lines = 0
    image_count = 0
    lines_by_ext: dict[str, int] = defaultdict(int)

    for f in files:
        if _is_image_file(f):
            image_count += 1
        else:
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    lines = sum(1 for _ in fh)
            except OSError:
                lines = 0
            total_lines += lines
            ext = f.suffix.lower() or "(no ext)"
            lines_by_ext[ext] += lines

    return {
        "total_files": len(files),
        "total_lines": total_lines,
        "image_count": image_count,
        "lines_by_extension": dict(lines_by_ext),
    }


class FolderPDF(FPDF):
    """Custom FPDF subclass that adds a header and footer to every page."""

    def __init__(self, folder_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._folder_name = folder_name
        self._unicode_mono = False

    def setup_fonts(self) -> None:
        """Register fonts.  Call once after construction."""
        if _MONO_FONT_PATH:
            self.add_font(_MONO_FONT_FAMILY, fname=_MONO_FONT_PATH)
            self._unicode_mono = True

    def set_mono_font(self, size: int = 8) -> None:
        """Activate the best available monospace font."""
        if self._unicode_mono:
            self.set_font(_MONO_FONT_FAMILY, size=size)
        else:
            self.set_font("Courier", size=size)

    def header(self):
        self.set_font("Helvetica", style="I", size=8)
        self.set_text_color(150, 150, 150)
        label = self._folder_name
        if not self._unicode_mono:
            label = _sanitize_for_builtin_font(label)
        self.cell(0, 6, label, align="L")
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", style="I", size=8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)


def convert(
    folder: str | Path,
    output: str | Path = "output.pdf",
    include_images: bool = True,
    extensions: list[str] | None = None,
    blacklist: list[str] | None = None,
    use_gitignore: bool = True,
) -> Path:
    """
    Generate a PDF from the contents of *folder*.

    Parameters
    ----------
    folder:
        Path to the directory to scan.
    output:
        Destination PDF path.
    include_images:
        Whether to embed image files in the PDF.
    extensions:
        Optional list of file extensions to include (e.g. ``[".py", ".md"]``).
        When *None* the built-in defaults are used.
    blacklist:
        Optional list of glob patterns (gitignore-style) for files/directories
        to exclude, e.g. ``["*.log", "tests/", "secret.txt"]``.
    use_gitignore:
        When *True* (the default) read the ``.gitignore`` in *folder* and skip
        any file it matches.

    Returns
    -------
    Path
        Absolute path to the generated PDF file.

    Raises
    ------
    ValueError
        If *folder* does not exist or is not a directory.
    """
    folder = Path(folder).resolve()
    if not folder.exists():
        raise ValueError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise ValueError(f"Path is not a directory: {folder}")

    output = Path(output)

    ext_set: set[str] | None = set(extensions) if extensions is not None else None
    files = _collect_files(
        folder,
        include_images=include_images,
        extensions=ext_set,
        blacklist=blacklist,
        use_gitignore=use_gitignore,
    )

    stats = _compute_stats(files, folder)

    pdf = FolderPDF(folder_name=str(folder), orientation="P", unit="mm", format="A4")
    pdf.setup_fonts()
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
    pdf.set_auto_page_break(auto=True, margin=_MARGIN)

    # ------------------------------------------------------------------ #
    # Cover page                                                           #
    # ------------------------------------------------------------------ #
    pdf.add_page()
    pdf.set_font("Helvetica", style="B", size=24)
    pdf.ln(30)
    pdf.cell(0, 12, "Folder Contents", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 8, folder.name, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", style="I", size=10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, str(folder), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # Project summary block
    _add_summary_section(pdf, stats)

    # ------------------------------------------------------------------ #
    # Table of contents                                                    #
    # ------------------------------------------------------------------ #
    if files:
        pdf.add_page()
        pdf.set_font("Helvetica", style="B", size=16)
        pdf.cell(0, 10, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("Helvetica", size=9)
        for f in files:
            rel = f.relative_to(folder)
            entry = str(rel)
            if not pdf._unicode_mono:
                entry = _sanitize_for_builtin_font(entry)
            pdf.cell(0, 5, entry, new_x="LMARGIN", new_y="NEXT")

    # ------------------------------------------------------------------ #
    # File sections                                                        #
    # ------------------------------------------------------------------ #
    for f in files:
        rel = f.relative_to(folder)
        is_image = _is_image_file(f)

        pdf.add_page()

        # Section heading
        pdf.set_font("Helvetica", style="B", size=13)
        pdf.set_fill_color(230, 230, 230)
        heading = str(rel)
        if not pdf._unicode_mono:
            heading = _sanitize_for_builtin_font(heading)
        pdf.cell(0, 8, heading, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        if is_image:
            _add_image_section(pdf, f, rel)
        else:
            _add_text_section(pdf, f)

    output.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output))
    return output.resolve()


def _add_summary_section(pdf: FolderPDF, stats: dict) -> None:
    """Render the Project Summary block on the cover page."""
    col_label = 40   # mm – width of the label column
    col_value = 30   # mm – width of the value column

    def _row(label: str, value: str) -> None:
        pdf.set_font("Helvetica", style="B", size=10)
        lbl = label if pdf._unicode_mono else _sanitize_for_builtin_font(label)
        pdf.cell(col_label, 6, lbl, new_x="RIGHT", new_y="TOP")
        pdf.set_font("Helvetica", size=10)
        val = value if pdf._unicode_mono else _sanitize_for_builtin_font(value)
        pdf.cell(col_value, 6, val, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", style="B", size=12)
    pdf.cell(0, 8, "Project Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 80, pdf.get_y())
    pdf.ln(3)

    _row("Total Files Processed:", str(stats["total_files"]))
    _row("Total Lines of Code:", str(stats["total_lines"]))
    _row("Image Files:", str(stats["image_count"]))

    lines_by_ext: dict[str, int] = stats["lines_by_extension"]
    if lines_by_ext:
        pdf.ln(4)
        pdf.set_font("Helvetica", style="B", size=10)
        pdf.cell(0, 6, "Lines by Extension:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        sorted_exts = sorted(lines_by_ext.items(), key=lambda kv: kv[1], reverse=True)
        for ext, count in sorted_exts:
            ext_lbl = f"  {ext}"
            if not pdf._unicode_mono:
                ext_lbl = _sanitize_for_builtin_font(ext_lbl)
            pdf.cell(col_label, 6, ext_lbl, new_x="RIGHT", new_y="TOP")
            cnt_str = f"{count} lines"
            if not pdf._unicode_mono:
                cnt_str = _sanitize_for_builtin_font(cnt_str)
            pdf.cell(col_value, 6, cnt_str, new_x="LMARGIN", new_y="NEXT")


def _add_text_section(pdf: FolderPDF, path: Path) -> None:
    """Add a text/code file section to *pdf*."""
    content = _read_text_safe(path)
    if not pdf._unicode_mono:
        content = _sanitize_for_builtin_font(content)
    pdf.set_mono_font(size=8)
    # Multi-cell handles long lines and newlines automatically
    pdf.multi_cell(0, 4, content)


def _add_image_section(pdf: FolderPDF, path: Path, rel: Path) -> None:
    """Embed an image in *pdf* with a filename annotation/caption."""
    try:
        from PIL import Image as PILImage

        with PILImage.open(path) as img:
            orig_w, orig_h = img.size
            img_format = img.format or "PNG"

        # Available page width (A4 minus margins)
        page_w = pdf.w - 2 * _MARGIN
        page_h = pdf.h - 2 * _MARGIN - 20  # leave room for caption

        # Scale image to fit within the page
        scale = min(page_w / orig_w, page_h / orig_h, 1.0)
        draw_w = orig_w * scale
        draw_h = orig_h * scale

        x = _MARGIN + (page_w - draw_w) / 2  # center horizontally
        pdf.image(str(path), x=x, w=draw_w, h=draw_h)

        # Caption / annotation
        pdf.ln(3)
        pdf.set_font("Helvetica", style="I", size=9)
        pdf.set_text_color(80, 80, 80)
        caption = f"{rel.name}  ({orig_w} x {orig_h} px, {img_format})"
        if not pdf._unicode_mono:
            caption = _sanitize_for_builtin_font(caption)
        pdf.cell(0, 5, caption, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    except (OSError, ValueError, RuntimeError) as exc:
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(180, 0, 0)
        msg = f"[Could not embed image: {exc}]"
        if not pdf._unicode_mono:
            msg = _sanitize_for_builtin_font(msg)
        pdf.cell(0, 6, msg, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

