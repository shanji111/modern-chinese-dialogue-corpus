"""Write the annotation label schema as a Markdown artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

from labels import label_schema_markdown
from io_utils import artifact_path, write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(artifact_path("annotation", "label_schema.md")),
        help="Markdown output path.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing schema artifact.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = write_text(Path(args.output), label_schema_markdown(), overwrite=args.overwrite)
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
