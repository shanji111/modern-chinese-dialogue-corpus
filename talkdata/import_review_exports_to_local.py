from __future__ import annotations

r"""
Import completed text dialogue exports into the local corpus database.

This script is intentionally a thin manifest over import_bulk_csv.py so the
application stays out of app.py and the import policy is explicit.

Usage:
    python .\talkdata\import_review_exports_to_local.py --dry-run
    python .\talkdata\import_review_exports_to_local.py
    python .\talkdata\import_review_exports_to_local.py --only mengzi --only lunyu
"""

import argparse
import csv
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from import_bulk_csv import import_csv
from text_dialogue_taxonomy import TEXT_DIALOGUE_SOURCE, text_dialogue_category_for_dataset


DB_FILE = PROJECT_ROOT / "corpus.db"
EXPORT_BASE = PROJECT_ROOT / "talkdata" / "review_exports"
BACKUP_DIR = PROJECT_ROOT / "db_backup"
DEFAULT_BATCH = "review_exports_text_20260528"
STAGING_DIR = EXPORT_BASE / "_local_import_staging"


@dataclass(frozen=True)
class ReviewExportSource:
    key: str
    dataset_name: str
    path: Path
    note: str


SOURCES: tuple[ReviewExportSource, ...] = (
    ReviewExportSource(
        key="shuihuzhuan",
        dataset_name="水浒传",
        path=EXPORT_BASE / "shuihuzhuan_llm_first_full_zhipu_retry_glm-4.5-air" / "kept_units.csv",
        note="LLM-first retry full units",
    ),
    ReviewExportSource(
        key="xiyouji",
        dataset_name="西游记",
        path=EXPORT_BASE / "xiyouji_llm_first_full_zhipu" / "kept_units.csv",
        note="LLM-first full units",
    ),
    ReviewExportSource(
        key="pingfandeshijie",
        dataset_name="平凡的世界",
        path=EXPORT_BASE / "merged_dialogues_all_current" / "pingfandeshijie_merged_dialogues.csv",
        note="LLM-first units merged into larger dialogues",
    ),
    ReviewExportSource(
        key="luotuoxiangzi",
        dataset_name="骆驼祥子",
        path=EXPORT_BASE / "merged_dialogues_all_current" / "luotuoxiangzi_merged_dialogues.csv",
        note="LLM-first units merged into larger dialogues",
    ),
    ReviewExportSource(
        key="tangchuanqi",
        dataset_name="唐传奇",
        path=EXPORT_BASE / "tangchuanqi_llm_first_full_zhipu_retry_glm-4.5-air" / "kept_units.csv",
        note="LLM-first retry full units",
    ),
    ReviewExportSource(
        key="qingpingshantang",
        dataset_name="清平山堂话本",
        path=EXPORT_BASE / "qingpingshantang_llm_first_full_zhipu_retry_glm-4.5-air" / "kept_units.csv",
        note="LLM-first retry full units",
    ),
    ReviewExportSource(
        key="shishuoxinyu",
        dataset_name="世说新语",
        path=EXPORT_BASE / "shishuoxinyu_retry_final_no_proxy" / "kept_units.csv",
        note="LLM-first final units, failed chunks retried without proxy",
    ),
    ReviewExportSource(
        key="zhuziyulei",
        dataset_name="朱子语类",
        path=EXPORT_BASE / "zhuziyulei_rule_full" / "zhuziyulei_rule_units.csv",
        note="rule full units",
    ),
    ReviewExportSource(
        key="mengzi",
        dataset_name="孟子",
        path=EXPORT_BASE / "mengzi_rule_full" / "mengzi_rule_units.csv",
        note="rule full units",
    ),
    ReviewExportSource(
        key="lunyu",
        dataset_name="论语",
        path=EXPORT_BASE / "lunyu_rule_full" / "lunyu_rule_units.csv",
        note="rule full units",
    ),
    ReviewExportSource(
        key="zhanguoce",
        dataset_name="战国策",
        path=EXPORT_BASE / "zhanguoce_rule_full" / "zhanguoce_rule_units_import_format.csv",
        note="rule full units",
    ),
    ReviewExportSource(
        key="laoqida",
        dataset_name="老乞大",
        path=EXPORT_BASE / "laoqida_rule_full" / "laoqida_rule_units.csv",
        note="rule full units",
    ),
    ReviewExportSource(
        key="putongshi",
        dataset_name="朴通事",
        path=EXPORT_BASE / "putongshi_rule_full" / "putongshi_rule_units.csv",
        note="rule full units",
    ),
    ReviewExportSource(
        key="xixiangji",
        dataset_name="西厢记",
        path=EXPORT_BASE / "xixiangji_rule_full_speaker_fixed" / "kept_units.csv",
        note="rule full units, speaker labels normalized from role names",
    ),
)


def select_sources(only: list[str]) -> list[ReviewExportSource]:
    if not only:
        return list(SOURCES)
    wanted = set(only)
    known = {source.key for source in SOURCES}
    unknown = sorted(wanted - known)
    if unknown:
        raise SystemExit(f"Unknown source key(s): {', '.join(unknown)}. Known: {', '.join(sorted(known))}")
    return [source for source in SOURCES if source.key in wanted]


def backup_database(db_path: Path, batch: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{db_path.name}.before_{batch}.bak"
    if backup_path.exists():
        return backup_path
    shutil.copy2(db_path, backup_path)
    return backup_path


def prepare_import_csv(source: ReviewExportSource) -> Path:
    """Normalize review/export metadata for the local corpus UI."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    staged_path = STAGING_DIR / f"{source.key}_for_local_import.csv"

    with source.path.open("r", encoding="utf-8-sig", newline="") as input_handle:
        reader = csv.DictReader(input_handle)
        if reader.fieldnames is None:
            raise RuntimeError(f"CSV 文件为空或缺少表头: {source.path}")

        fieldnames = list(reader.fieldnames)
        for field in ("category", "dataset_name", "crawl_source", "license_note"):
            if field not in fieldnames:
                fieldnames.append(field)

        with staged_path.open("w", encoding="utf-8-sig", newline="") as output_handle:
            writer = csv.DictWriter(output_handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                original_source = (row.get("source") or "").strip()
                dataset_name = (row.get("dataset_name") or source.dataset_name).strip()
                title = (row.get("title") or "").strip()
                row["source"] = TEXT_DIALOGUE_SOURCE
                row["title"] = (
                    title.replace("LLM分块抽取单元", "对话单元")
                    .replace("LLM全文抽取", "对话单元")
                    .replace("规则会话单元", "对话单元")
                )
                row["dataset_name"] = dataset_name
                row["category"] = text_dialogue_category_for_dataset(
                    dataset_name,
                    fallback="",
                )
                row["crawl_source"] = (row.get("crawl_source") or original_source or source.note).strip()
                if not (row.get("license_note") or "").strip():
                    row["license_note"] = source.note
                writer.writerow(row)

    return staged_path


def run(args: argparse.Namespace) -> dict[str, Any]:
    selected = select_sources(args.only)
    missing = [source for source in selected if not source.path.exists()]
    if missing:
        details = "\n".join(f"- {source.key}: {source.path}" for source in missing)
        raise FileNotFoundError(f"Missing export CSV(s):\n{details}")

    backup_path = ""
    if not args.dry_run and not args.no_backup:
        backup_path = str(backup_database(args.db, args.batch))

    results: list[dict[str, Any]] = []
    for source in selected:
        import_path = prepare_import_csv(source)
        success, failed, duplicate = import_csv(
            import_path,
            args.db,
            f"{args.batch}_{source.key}",
            dry_run=args.dry_run,
            no_rollback_journal=args.no_rollback_journal,
            insert_batch_size=args.insert_batch_size,
        )
        results.append(
            {
                "key": source.key,
                "dataset_name": source.dataset_name,
                "path": str(source.path),
                "import_path": str(import_path),
                "success": success,
                "failed": failed,
                "duplicate": duplicate,
                "note": source.note,
            }
        )

    return {
        "dry_run": args.dry_run,
        "db": str(args.db),
        "batch": args.batch,
        "backup": backup_path,
        "results": results,
        "success_total": sum(item["success"] for item in results),
        "failed_total": sum(item["failed"] for item in results),
        "duplicate_total": sum(item["duplicate"] for item in results),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import completed review_exports CSVs into local corpus.db.")
    parser.add_argument("--db", type=Path, default=DB_FILE, help="Target SQLite corpus database.")
    parser.add_argument("--batch", default=DEFAULT_BATCH, help="Import batch prefix.")
    parser.add_argument("--only", action="append", default=[], help="Import only one source key; repeatable.")
    parser.add_argument("--dry-run", action="store_true", help="Count rows without writing.")
    parser.add_argument("--no-backup", action="store_true", help="Skip corpus.db backup before writing.")
    parser.add_argument(
        "--no-rollback-journal",
        action="store_true",
        help="SQLite only: disable rollback journal for import_bulk_csv.",
    )
    parser.add_argument("--insert-batch-size", type=int, default=1000, help="PostgreSQL batch size passthrough.")
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    action = "DRY RUN" if summary["dry_run"] else "IMPORT"
    print(f"{action} review_exports -> {summary['db']}")
    print(f"batch: {summary['batch']}")
    if summary["backup"]:
        print(f"backup: {summary['backup']}")
    for item in summary["results"]:
        print(
            f"{item['key']}: insert={item['success']} duplicate={item['duplicate']} "
            f"failed={item['failed']} ({item['dataset_name']})"
        )
    print(f"total insert: {summary['success_total']}")
    print(f"total duplicate: {summary['duplicate_total']}")
    print(f"total failed: {summary['failed_total']}")


if __name__ == "__main__":
    main()
