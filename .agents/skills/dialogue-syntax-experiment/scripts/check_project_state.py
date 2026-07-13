from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_pair_hash_for_check(text_a: str, text_b: str) -> str:
    def normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value or "").lower()
        return re.sub(r"\s+", " ", normalized).strip()

    payload = normalize(text_a) + "\n<PAIR>\n" + normalize(text_b)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        current = current[key]
    return current


def close_enough(actual: float, expected: float, tolerance: float = 1e-12) -> bool:
    return abs(float(actual) - float(expected)) <= tolerance


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify frozen dialogue-syntax experiment state.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--skip-git", action="store_true")
    args = parser.parse_args()

    root = args.repo_root.resolve()
    registry_path = root / "experiments" / "dialogue_syntax_bert" / "EXPERIMENT_REGISTRY.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    snapshot = root / registry["reproducibility_snapshot"]["root"]
    manifest_path = root / registry["reproducibility_snapshot"]["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    for item in manifest["files"]:
        path = snapshot / item["path"]
        passed = path.is_file() and path.stat().st_size == item["size_bytes"] and sha256(path) == item["sha256"]
        record(f"sha256:{item['path']}", passed, item["sha256"])
    record("manifest_file_count", len(manifest["files"]) == manifest["file_count"], manifest["file_count"])

    pair_gold = read_csv(snapshot / "formal_300_v1_gold_v1.csv")
    labels = Counter(row["resonance_present"] for row in pair_gold)
    expected_pair = registry["pair_gold"]
    record("pair_gold_rows", len(pair_gold) == expected_pair["rows"], len(pair_gold))
    record("pair_gold_labels", dict(labels) == expected_pair["labels"], dict(labels))

    binary = read_csv(snapshot / "formal_300_v1_gold_v1_binary.csv")
    record("pair_binary_rows", len(binary) == expected_pair["binary_rows"], len(binary))
    split_rows: dict[str, list[dict[str, str]]] = {}
    for split, expected_count in expected_pair["splits"].items():
        rows = read_csv(snapshot / "baselines" / f"gold_v1_binary_{split}.csv")
        split_rows[split] = rows
        record(f"split_count:{split}", len(rows) == expected_count, len(rows))

    for field in ("pair_id", "normalized_pair_hash", "conversation_group_key"):
        sets = {name: {row[field] for row in rows} for name, rows in split_rows.items()}
        overlap = sorted((sets["train"] & sets["dev"]) | (sets["train"] & sets["test"]) | (sets["dev"] & sets["test"]))
        record(f"split_disjoint:{field}", not overlap, overlap[:10])
    split_ids = {row["annotation_id"] for rows in split_rows.values() for row in rows}
    binary_ids = {row["annotation_id"] for row in binary}
    record("split_union_matches_binary_gold", split_ids == binary_ids, {"split": len(split_ids), "binary": len(binary_ids)})

    column_root = snapshot / "diagraph_gold_50" / "gold_v1"
    active = read_csv(column_root / "diagraph_gold_50_column_gold_v1_active.csv")
    all_rows = read_csv(column_root / "diagraph_gold_50_column_gold_v1_all_rows.csv")
    expected_column = registry["column_gold"]
    record("column_active_rows", len(active) == expected_column["active_rows"], len(active))
    record("column_all_rows", len(all_rows) == expected_column["all_rows"], len(all_rows))
    active_pair_ids = {row["annotation_id"] for row in active}
    record("column_positive_pairs", len(active_pair_ids) == expected_column["positive_pairs"], len(active_pair_ids))
    core_by_pair = Counter(row["annotation_id"] for row in active if row["is_core_column"] == "1")
    missing_core = sorted(active_pair_ids - set(core_by_pair))
    record("column_core_coverage", not missing_core, missing_core)

    pair_lookup = {row["annotation_id"]: row for row in pair_gold}
    span_errors: list[str] = []
    for row in active:
        pair = pair_lookup.get(row["annotation_id"])
        if pair is None or row["span_a"] not in pair["turn_a"] or row["span_b"] not in pair["turn_b"]:
            span_errors.append(f"{row['annotation_id']}:{row['column_id']}")
    record("column_spans_are_substrings", not span_errors, span_errors[:20])

    multiseed = json.loads((snapshot / "bert_shadow_v3_multiseed" / "multiseed_summary.json").read_text(encoding="utf-8"))
    historical = registry["historical_metrics"]
    record(
        "metric:macbert_multiseed_macro_f1",
        close_enough(nested(multiseed, "stability", "mean_std", "test_macro_f1", "mean"), historical["macbert_multiseed_test_macro_f1_mean"]),
        nested(multiseed, "stability", "mean_std", "test_macro_f1", "mean"),
    )

    hybrid = json.loads((snapshot / "hybrid_shadow_v1" / "hybrid_strategy_results.json").read_text(encoding="utf-8"))
    selected = next(row for row in hybrid["strategies"] if row["strategy"] == historical["recommended_hybrid"])
    record(
        "metric:recommended_hybrid_macro_f1",
        close_enough(nested(selected, "test", "macro", "f1"), historical["recommended_hybrid_test_macro_f1"]),
        nested(selected, "test", "macro", "f1"),
    )
    record(
        "metric:recommended_hybrid_balanced_accuracy",
        close_enough(nested(selected, "test", "balanced_accuracy"), historical["recommended_hybrid_test_balanced_accuracy"]),
        nested(selected, "test", "balanced_accuracy"),
    )

    external = registry.get("external_validation_selection")
    ai_route = registry.get("ai_exploration")
    if ai_route:
        for field in ("protocol", "prompt_path", "validator"):
            path = root / ai_route[field]
            record(f"ai_route_artifact:{field}", path.is_file(), str(path))
        record("ai_route_not_gold", ai_route.get("labels_are_gold") is False, ai_route.get("labels_are_gold"))
        record("ai_route_not_confirmatory", ai_route.get("confirmatory_use_authorized") is False, ai_route.get("confirmatory_use_authorized"))
    if external:
        external_root = root / external["root"]
        external_manifest = json.loads((root / external["manifest"]).read_text(encoding="utf-8"))
        record("external_selection_version", external_manifest.get("selection_version") == external["version"], external_manifest.get("selection_version"))
        for filename, expected in external_manifest["public_files"].items():
            path = external_root / filename
            passed = path.is_file() and path.stat().st_size == expected["size_bytes"] and sha256(path) == expected["sha256"]
            record(f"external_sha256:{filename}", passed, expected["sha256"])

        selection = read_csv(external_root / "selection_key.csv")
        record("external_selection_rows", len(selection) == external["sample_size"], len(selection))
        for field in ("annotation_id", "pair_id", "normalized_pair_hash", "conversation_group_key"):
            values = [row[field] for row in selection]
            record(f"external_unique:{field}", len(values) == len(set(values)), len(set(values)))
        strata = Counter(row["sample_stratum"] for row in selection)
        partitions = Counter(row["confirmatory_partition"] for row in selection)
        record("external_stratum_counts", dict(strata) == external["stratum_counts"], dict(strata))
        record("external_partition_counts", dict(partitions) == external["partition_counts"], dict(partitions))

        development_datasets = {row["dataset_name"] for row in selection if row["confirmatory_partition"] == "development"}
        holdout_datasets = {row["dataset_name"] for row in selection if row["confirmatory_partition"] == "external_holdout"}
        record("external_dataset_disjoint", not (development_datasets & holdout_datasets), sorted(development_datasets & holdout_datasets))
        all_sources = {row["source"] for row in selection}
        holdout_sources = {row["source"] for row in selection if row["confirmatory_partition"] == "external_holdout"}
        record("external_holdout_source_coverage", holdout_sources == all_sources, sorted(all_sources - holdout_sources))
        excluded_source_substrings = external.get("excluded_source_substrings", [])
        excluded_hits = [row["source"] for row in selection if any(pattern and pattern in row["source"] for pattern in excluded_source_substrings)]
        record("external_excluded_source_substrings", not excluded_hits, excluded_hits[:10])
        record(
            "external_manifest_excluded_source_substrings",
            set(external_manifest.get("sampling", {}).get("excluded_source_substrings", [])) >= set(excluded_source_substrings),
            external_manifest.get("sampling", {}).get("excluded_source_substrings", []),
        )

        old_pair_ids = {row["pair_id"] for row in pair_gold}
        old_pair_hashes = {normalized_pair_hash_for_check(row["turn_a"], row["turn_b"]) for row in pair_gold}
        old_binary_groups = {row["conversation_group_key"] for row in binary}
        record("external_excludes_old_pair_ids", not ({row["pair_id"] for row in selection} & old_pair_ids), "")
        record("external_excludes_old_pair_hashes", not ({row["normalized_pair_hash"] for row in selection} & old_pair_hashes), "")
        record("external_excludes_old_binary_groups", not ({row["conversation_group_key"] for row in selection} & old_binary_groups), "")

        primary_files = {
            "development": external_root / "development_annotation_blind.csv",
            "external_holdout": external_root / "external_holdout_annotation_blind.csv",
        }
        primary_ids: dict[str, set[str]] = {}
        for name, path in primary_files.items():
            rows = read_csv(path)
            primary_ids[name] = {row["annotation_id"] for row in rows}
            labels_blank = all(not row.get(field, "").strip() for row in rows for field in external["annotation_fields"])
            record(f"external_labels_blank:{name}", labels_blank, len(rows))
        key_ids = {row["annotation_id"] for row in selection}
        record("external_primary_packets_match_key", primary_ids["development"] | primary_ids["external_holdout"] == key_ids, "")
        audit_files = external.get(
            "audit_subset_files",
            {
                "development": "development_overlap_annotator_b_blind.csv",
                "external_holdout": "external_holdout_overlap_annotator_b_blind.csv",
            },
        )
        for name, filename, expected_count in (
            ("development", audit_files["development"], external["development_overlap_rows"]),
            ("external_holdout", audit_files["external_holdout"], external["holdout_overlap_rows"]),
        ):
            rows = read_csv(external_root / filename)
            ids = {row["annotation_id"] for row in rows}
            labels_blank = all(not row.get(field, "").strip() for row in rows for field in external["annotation_fields"])
            record(f"external_overlap_count:{name}", len(rows) == expected_count, len(rows))
            record(f"external_overlap_subset:{name}", ids <= primary_ids[name], sorted(ids - primary_ids[name])[:10])
            record(f"external_overlap_labels_blank:{name}", labels_blank, len(rows))

    network = registry.get("network_async_stress")
    if network:
        network_root = root / network["root"]
        network_manifest = json.loads((root / network["manifest"]).read_text(encoding="utf-8"))
        record("network_stress_exploratory_only", network_manifest.get("exploratory_only") is True, network_manifest.get("exploratory_only"))
        record("network_stress_not_confirmatory", network_manifest.get("not_a_confirmatory_holdout") is True, network_manifest.get("not_a_confirmatory_holdout"))
        packet_path = network_root / network_manifest["public_file"]["path"]
        packet_hash = network_manifest["public_file"]["sha256"]
        record("network_stress_packet_hash", packet_path.is_file() and sha256(packet_path) == packet_hash, packet_hash)
        stress_rows = read_csv(packet_path)
        record("network_stress_row_count", len(stress_rows) == network["rows"], len(stress_rows))
        record("network_stress_source_profile", all("网络" in row.get("source", "") for row in stress_rows), sorted({row.get("source", "") for row in stress_rows}))
        record(
            "network_stress_labels_blank",
            all(not row.get(field, "").strip() for row in stress_rows for field in external["annotation_fields"]),
            len(stress_rows),
        )

    if not args.skip_git:
        untracked = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", "experiments/dialogue_syntax_bert", ".agents", "AGENTS.md", "PROJECT_STATE.md"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
        relevant_untracked = [line for line in untracked if line.startswith("?? ")]
        record("git_no_untracked_experiment_files", not relevant_untracked, relevant_untracked[:20])

    failed = [check for check in checks if not check["passed"]]
    report = {
        "status": "pass" if not failed else "fail",
        "checks_total": len(checks),
        "checks_failed": len(failed),
        "failed": failed,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
