from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_paths(path: Path) -> list[Path]:
    result: list[Path] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"Unsafe artifact path: {value}")
        result.append(candidate)
    if not result:
        raise ValueError(f"No artifacts listed in {path}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy an allowlisted compact artifact snapshot without overwriting changed files."
    )
    parser.add_argument("--source-formal-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--version", default="frozen_v1")
    parser.add_argument("--list-file", type=Path)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    list_file = args.list_file or script_dir.parent / "references" / "critical-artifacts-v1.txt"
    source_root = args.source_formal_root.resolve()
    repo_root = args.repo_root.resolve()
    destination_root = (
        repo_root
        / "experiments"
        / "dialogue_syntax_bert"
        / "reproducibility"
        / args.version
    )
    destination_root.mkdir(parents=True, exist_ok=True)

    manifest_files: list[dict[str, object]] = []
    copied = 0
    reused = 0
    for relative in load_paths(list_file):
        source = source_root / relative
        destination = destination_root / relative
        if not source.is_file():
            raise FileNotFoundError(f"Missing source artifact: {source}")
        source_hash = sha256(source)
        if destination.exists():
            if not destination.is_file() or sha256(destination) != source_hash:
                raise FileExistsError(
                    f"Frozen destination differs; create a new version instead of overwriting: {destination}"
                )
            reused += 1
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied += 1
        manifest_files.append(
            {
                "path": relative.as_posix(),
                "size_bytes": destination.stat().st_size,
                "sha256": source_hash,
            }
        )

    manifest = {
        "schema_version": 1,
        "snapshot_version": args.version,
        "source_artifact_set": source_root.name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(manifest_files),
        "files": manifest_files,
    }
    manifest_path = destination_root / "MANIFEST.sha256.json"
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != encoded:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous_files = previous.get("files")
        if previous_files != manifest_files:
            raise FileExistsError(
                f"Frozen manifest contents changed; create a new version: {manifest_path}"
            )
        manifest = previous
        encoded = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if not manifest_path.exists():
        manifest_path.write_text(encoded, encoding="utf-8")
    print(
        json.dumps(
            {
                "snapshot": str(destination_root),
                "file_count": len(manifest_files),
                "copied": copied,
                "reused_identical": reused,
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
