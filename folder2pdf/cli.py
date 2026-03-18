"""Command-line interface for folder2pdf."""

import argparse
import sys
from pathlib import Path

from .converter import convert


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="folder2pdf",
        description=(
            "Read a folder's contents (and its sub-folders) and generate a PDF. "
            "Text and source-code files are included as readable content; "
            "image files are embedded with captions."
        ),
    )
    parser.add_argument(
        "folder",
        help="Path to the folder to convert.",
    )
    parser.add_argument(
        "-o", "--output",
        default="output.pdf",
        metavar="OUTPUT",
        help="Destination PDF file path (default: output.pdf).",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        default=False,
        help="Do not embed image files in the PDF.",
    )
    parser.add_argument(
        "-e", "--extensions",
        nargs="+",
        metavar="EXT",
        help=(
            "Whitelist of file extensions to include, e.g. '.py .md .txt'. "
            "When omitted the built-in defaults are used."
        ),
    )
    parser.add_argument(
        "-b", "--blacklist",
        nargs="+",
        metavar="PATTERN",
        help=(
            "Glob patterns (gitignore-style) for files or directories to exclude, "
            "e.g. 'tests/ *.log secret.txt'. Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_true",
        default=False,
        help="Do not read or apply the .gitignore file found in the target folder.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    folder = Path(args.folder)
    output = Path(args.output)

    try:
        result = convert(
            folder=folder,
            output=output,
            include_images=not args.no_images,
            extensions=args.extensions,
            blacklist=args.blacklist,
            use_gitignore=not args.no_gitignore,
        )
        print(f"PDF generated: {result}")
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError) as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
