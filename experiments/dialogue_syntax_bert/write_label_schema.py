"""Write the annotation label schema as a Markdown artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

from labels import label_schema_markdown
from io_utils import artifact_path, ensure_parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(artifact_path("annotation", "label_schema.md")),
        help="Markdown output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = ensure_parent(Path(args.output))
    output_path.write_text(label_schema_markdown(), encoding="utf-8")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()

