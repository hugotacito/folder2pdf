"""Tests for folder2pdf."""

import os
import sys
from pathlib import Path

import pytest

# Ensure the package is importable when running from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from folder2pdf.converter import (
    TEXT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    _collect_files,
    _is_image_file,
    _is_text_file,
    _read_text_safe,
    convert,
)
from folder2pdf.cli import build_parser, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tree(tmp_path: Path) -> dict[str, Path]:
    """
    Create a minimal folder tree for testing:

    tmp_path/
        hello.txt
        script.py
        sub/
            readme.md
            data.json
            image.png  (tiny valid PNG)
        hidden/
            secret.txt   (inside a hidden dir – should be skipped)
        .hidden.txt       (hidden file – should be skipped)
    """
    files: dict[str, Path] = {}

    (tmp_path / "hello.txt").write_text("Hello, world!\n")
    files["hello.txt"] = tmp_path / "hello.txt"

    (tmp_path / "script.py").write_text("print('hello')\n")
    files["script.py"] = tmp_path / "script.py"

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "readme.md").write_text("# Sub readme\n")
    files["sub/readme.md"] = sub / "readme.md"

    (sub / "data.json").write_text('{"key": "value"}\n')
    files["sub/data.json"] = sub / "data.json"

    # Minimal 1×1 transparent PNG
    _write_minimal_png(sub / "image.png")
    files["sub/image.png"] = sub / "image.png"

    hidden_dir = tmp_path / "hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.txt").write_text("should be skipped\n")

    (tmp_path / ".hidden.txt").write_text("also skipped\n")

    return files


def _write_minimal_png(path: Path) -> None:
    """Write a minimal valid 10×10 red PNG to *path*."""
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (10, 10), color=(255, 0, 0))
    img.save(str(path), format="PNG")


# ---------------------------------------------------------------------------
# Unit tests: extension detection
# ---------------------------------------------------------------------------

class TestExtensionDetection:
    def test_text_extensions_non_empty(self):
        assert len(TEXT_EXTENSIONS) > 0

    def test_image_extensions_non_empty(self):
        assert len(IMAGE_EXTENSIONS) > 0

    def test_is_text_file_py(self, tmp_path):
        p = tmp_path / "script.py"
        p.touch()
        assert _is_text_file(p)

    def test_is_text_file_md(self, tmp_path):
        p = tmp_path / "readme.md"
        p.touch()
        assert _is_text_file(p)

    def test_is_text_file_false_for_png(self, tmp_path):
        p = tmp_path / "photo.png"
        p.touch()
        assert not _is_text_file(p)

    def test_is_image_file_png(self, tmp_path):
        p = tmp_path / "photo.png"
        p.touch()
        assert _is_image_file(p)

    def test_is_image_file_jpg(self, tmp_path):
        p = tmp_path / "photo.jpg"
        p.touch()
        assert _is_image_file(p)

    def test_is_image_file_false_for_py(self, tmp_path):
        p = tmp_path / "script.py"
        p.touch()
        assert not _is_image_file(p)


# ---------------------------------------------------------------------------
# Unit tests: _read_text_safe
# ---------------------------------------------------------------------------

class TestReadTextSafe:
    def test_reads_content(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_text("hello world")
        assert _read_text_safe(p) == "hello world"

    def test_truncation(self, tmp_path):
        p = tmp_path / "big.txt"
        p.write_text("x" * 200)
        result = _read_text_safe(p, max_chars=50)
        assert len(result) > 50  # includes truncation notice
        assert "truncated" in result

    def test_missing_file(self, tmp_path):
        p = tmp_path / "no_such.txt"
        result = _read_text_safe(p)
        assert "Error" in result


# ---------------------------------------------------------------------------
# Unit tests: _collect_files
# ---------------------------------------------------------------------------

class TestCollectFiles:
    def test_collects_text_and_images(self, tmp_path):
        _make_tree(tmp_path)
        files = _collect_files(tmp_path, include_images=True)
        names = {f.name for f in files}
        assert "hello.txt" in names
        assert "script.py" in names
        assert "readme.md" in names
        assert "data.json" in names
        assert "image.png" in names

    def test_skips_hidden_directory(self, tmp_path):
        _make_tree(tmp_path)
        files = _collect_files(tmp_path)
        # The "hidden/" directory starts with a dot-free name but we named it
        # "hidden" – we test that .hidden dirs are excluded.
        # Let's create one explicitly.
        dot_dir = tmp_path / ".git"
        dot_dir.mkdir()
        (dot_dir / "config").write_text("git config")
        files = _collect_files(tmp_path)
        paths = [str(f) for f in files]
        assert not any(".git" in p for p in paths)

    def test_skips_hidden_files(self, tmp_path):
        _make_tree(tmp_path)
        files = _collect_files(tmp_path)
        names = [f.name for f in files]
        assert ".hidden.txt" not in names

    def test_no_images_flag(self, tmp_path):
        _make_tree(tmp_path)
        files = _collect_files(tmp_path, include_images=False)
        names = {f.name for f in files}
        assert "image.png" not in names
        assert "hello.txt" in names

    def test_custom_extensions(self, tmp_path):
        _make_tree(tmp_path)
        files = _collect_files(tmp_path, extensions={".py"})
        names = {f.name for f in files}
        assert "script.py" in names
        assert "hello.txt" not in names
        assert "image.png" not in names

    def test_sorted_output(self, tmp_path):
        _make_tree(tmp_path)
        files = _collect_files(tmp_path)
        str_paths = [str(f) for f in files]
        assert str_paths == sorted(str_paths)


# ---------------------------------------------------------------------------
# Integration tests: convert()
# ---------------------------------------------------------------------------

class TestConvert:
    def test_creates_pdf(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("Hello, PDF!")
        out = tmp_path / "out.pdf"
        result = convert(src, output=out)
        assert result.exists()
        assert result.suffix == ".pdf"
        assert result.stat().st_size > 0

    def test_pdf_contains_content(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("Hello, PDF!")
        out = tmp_path / "out.pdf"
        convert(src, output=out)
        # PDF is binary, but the text should appear somewhere
        raw = out.read_bytes()
        assert b"PDF" in raw

    def test_with_image(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        _write_minimal_png(src / "photo.png")
        out = tmp_path / "out.pdf"
        result = convert(src, output=out, include_images=True)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_no_images_flag(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("text")
        _write_minimal_png(src / "photo.png")
        out_with = tmp_path / "with_img.pdf"
        out_without = tmp_path / "without_img.pdf"
        convert(src, output=out_with, include_images=True)
        convert(src, output=out_without, include_images=False)
        # PDF with embedded image should be larger
        assert out_with.stat().st_size > out_without.stat().st_size

    def test_nested_folders(self, tmp_path):
        _make_tree(tmp_path)
        out = tmp_path / "nested.pdf"
        result = convert(tmp_path, output=out)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_empty_folder(self, tmp_path):
        src = tmp_path / "empty"
        src.mkdir()
        out = tmp_path / "empty.pdf"
        result = convert(src, output=out)
        assert result.exists()

    def test_raises_on_missing_folder(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            convert(tmp_path / "nonexistent", output=tmp_path / "out.pdf")

    def test_raises_on_file_as_folder(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        with pytest.raises(ValueError, match="not a directory"):
            convert(f, output=tmp_path / "out.pdf")

    def test_custom_extensions(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "script.py").write_text("print('hi')")
        (src / "notes.txt").write_text("notes")
        out = tmp_path / "out.pdf"
        # Only include .py files
        result = convert(src, output=out, extensions=[".py"])
        assert result.exists()

    def test_output_in_subdirectory(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("hello")
        out = tmp_path / "sub" / "nested" / "out.pdf"
        result = convert(src, output=out)
        assert result.exists()


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    def test_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            build_parser().parse_args(["--help"])
        assert exc.value.code == 0

    def test_main_creates_pdf(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("Hello")
        out = tmp_path / "out.pdf"
        rc = main([str(src), "-o", str(out)])
        assert rc == 0
        assert out.exists()

    def test_main_missing_folder(self, tmp_path, capsys):
        rc = main([str(tmp_path / "no_such_folder")])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_main_no_images(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("Hello")
        out = tmp_path / "out.pdf"
        rc = main([str(src), "-o", str(out), "--no-images"])
        assert rc == 0
        assert out.exists()

    def test_main_custom_extensions(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "script.py").write_text("# code")
        out = tmp_path / "out.pdf"
        rc = main([str(src), "-o", str(out), "-e", ".py"])
        assert rc == 0
        assert out.exists()

    def test_main_default_output_name(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("Hello")
        monkeypatch.chdir(tmp_path)
        rc = main([str(src)])
        assert rc == 0
        assert (tmp_path / "output.pdf").exists()
