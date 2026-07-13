from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from evaluate_diagraph_generation_v1 import (
    DEFAULT_GOLD_ACTIVE,
    PAIR_LIST_PATH,
    PRED_REQUIRED_FIELDS,
    VALID_ALIGNMENT_DIRECTIONS,
    VALID_BINARY_OR_UNKNOWN,
    VALID_RELATION_STRENGTHS,
    VALID_RELATION_TYPES,
    evaluate_predictions,
    read_csv_dicts,
    write_csv,
)


ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = ROOT / "artifacts" / "formal_300_v1"
EVAL_ROOT = ARTIFACT_ROOT / "diagraph_generation_evaluation_v1"

V1_PREDICTION_PATH = EVAL_ROOT / "rule_baseline_v1" / "rule_baseline_prediction_v1.csv"
V1_SUMMARY_PATH = EVAL_ROOT / "rule_baseline_v1" / "evaluation_run" / "evaluation_summary.json"
V11_PREDICTION_PATH = EVAL_ROOT / "rule_baseline_v1_1" / "rule_baseline_prediction_v1_1.csv"
V11_SUMMARY_PATH = EVAL_ROOT / "rule_baseline_v1_1" / "evaluation_run" / "evaluation_summary.json"

OUTPUT_DIR = EVAL_ROOT / "bert_candidate_pool_v0"
POOL_CSV_PATH = OUTPUT_DIR / "bert_candidate_pool_v0.csv"
POOL_XLSX_PATH = OUTPUT_DIR / "bert_candidate_pool_v0.xlsx"
POOL_EVAL_DIR = OUTPUT_DIR / "evaluation_run"
EVAL_SUMMARY_MD_PATH = OUTPUT_DIR / "bert_candidate_pool_v0_evaluation_summary.md"
COMPARISON_MD_PATH = OUTPUT_DIR / "bert_candidate_pool_v0_comparison_with_v1_and_v1_1.md"
TIER_DIST_PATH = OUTPUT_DIR / "bert_candidate_pool_v0_tier_distribution.csv"
RELATION_DIST_PATH = OUTPUT_DIR / "bert_candidate_pool_v0_relation_type_distribution.csv"
PAIR_COVERAGE_PATH = OUTPUT_DIR / "bert_candidate_pool_v0_pair_coverage.csv"
DIAGNOSTIC_MD_PATH = OUTPUT_DIR / "bert_candidate_pool_v0_diagnostic_report.md"
PROTOTYPE_PLAN_PATH = OUTPUT_DIR / "bert_assisted_prototype_v0_plan.md"
MANIFEST_MD_PATH = OUTPUT_DIR / "bert_candidate_pool_v0_manifest.md"

CANDIDATE_FIELDNAMES = [
    "candidate_id",
    *PRED_REQUIRED_FIELDS,
    "from_rule_v1",
    "from_rule_v1_1",
    "source_count",
    "candidate_tier",
    "candidate_pool_note",
    "needs_bert_score",
    "suggested_bert_task",
]

HIGH_RISK_RELATION_TYPES = {
    "coreference_or_demonstrative",
    "slot_filling",
    "short_answer",
    "contrast",
    "repair",
    "semantic_substitution",
    "analogy",
}
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
STRENGTH_ORDER = {"weak": 0, "medium": 1, "strong": 2}
TIER_ORDER = {
    "high_precision_rule": 0,
    "precision_ablation_only": 1,
    "recall_rule_only": 2,
    "low_confidence_rule": 3,
}


def approx_key(row: Dict[str, str]) -> Tuple[str, str, str, str, str]:
    return (
        row["annotation_id"],
        row["pair_id"],
        row["pred_span_a"],
        row["pred_span_b"],
        row["pred_relation_type"],
    )


def ensure_prediction_rows_valid(rows: List[Dict[str, str]], pair_map: Dict[str, Dict[str, str]], name: str) -> None:
    if not rows:
        raise ValueError(f"{name} is empty.")
    missing = [field for field in PRED_REQUIRED_FIELDS if field not in rows[0]]
    if missing:
        raise ValueError(f"{name} missing required fields: {missing}")

    problems: List[str] = []
    for row in rows:
        annotation_id = row["annotation_id"]
        pair = pair_map.get(annotation_id)
        if pair is None:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} annotation_id_missing_from_pair_list")
            continue
        if row["pair_id"] != pair["pair_id"]:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} pair_id_mismatch")
        if row["pred_span_a"] not in pair["turn_a"]:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} pred_span_a_not_found_in_turn_a")
        if row["pred_span_b"] not in pair["turn_b"]:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} pred_span_b_not_found_in_turn_b")
        if row["pred_relation_type"] not in VALID_RELATION_TYPES:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} invalid_pred_relation_type")
        if row["pred_relation_strength"] not in VALID_RELATION_STRENGTHS:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} invalid_pred_relation_strength")
        if row["pred_alignment_direction"] not in VALID_ALIGNMENT_DIRECTIONS:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} invalid_pred_alignment_direction")
        if row["pred_is_core_column"] not in VALID_BINARY_OR_UNKNOWN:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} invalid_pred_is_core_column")
        if row["pred_supports_resonance"] not in VALID_BINARY_OR_UNKNOWN:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} invalid_pred_supports_resonance")
        if row["pred_confidence"] not in CONFIDENCE_ORDER:
            problems.append(f"{name}:{annotation_id}/{row['pred_column_id']} invalid_pred_confidence")
    if problems:
        raise ValueError("Input prediction validation failed:\n" + "\n".join(problems[:30]))


def choose_primary_row(group: List[Dict[str, str]]) -> Dict[str, str]:
    by_version = {row["generator_version"]: row for row in group}
    return by_version.get("v1.1") or by_version.get("v1") or group[0]


def choose_best_confidence(group: List[Dict[str, str]]) -> str:
    return max(group, key=lambda row: CONFIDENCE_ORDER.get(row["pred_confidence"], -1))["pred_confidence"]


def choose_best_strength(group: List[Dict[str, str]]) -> str:
    return max(group, key=lambda row: STRENGTH_ORDER.get(row["pred_relation_strength"], -1))["pred_relation_strength"]


def choose_alignment_direction(group: List[Dict[str, str]]) -> str:
    directions = {row["pred_alignment_direction"] for row in group}
    if len(directions) == 1:
        return next(iter(directions))
    primary = choose_primary_row(group)
    return primary["pred_alignment_direction"]


def build_suggested_bert_task(candidate_tier: str, relation_type: str) -> str:
    tasks: List[str] = []
    if candidate_tier in {"high_precision_rule", "precision_ablation_only"}:
        tasks.append("rerank_or_keep")
    if candidate_tier in {"recall_rule_only", "low_confidence_rule"}:
        tasks.append("false_positive_filter")
    if relation_type in {
        "contrast",
        "repair",
        "slot_filling",
        "coreference_or_demonstrative",
    }:
        tasks.append("relation_type_check")
    if relation_type == "semantic_substitution":
        tasks.append("semantic_score_needed")
    if relation_type == "analogy":
        tasks.append("not_for_bert_generation_yet")
    return ";".join(dict.fromkeys(tasks))


def determine_candidate_tier(
    from_rule_v1: bool,
    from_rule_v11: bool,
    pred_confidence: str,
    relation_type: str,
) -> str:
    low_conflict = pred_confidence == "low" or relation_type in HIGH_RISK_RELATION_TYPES
    if from_rule_v1 and from_rule_v11:
        return "high_precision_rule"
    if from_rule_v11 and not from_rule_v1:
        return "precision_ablation_only"
    if from_rule_v1 and not from_rule_v11:
        return "recall_rule_only"
    if low_conflict:
        return "low_confidence_rule"
    return "low_confidence_rule"


def merge_prediction_rows(
    v1_rows: List[Dict[str, str]],
    v11_rows: List[Dict[str, str]],
    pair_rows: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    grouped: Dict[Tuple[str, str, str, str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in v1_rows + v11_rows:
        grouped[approx_key(row)].append(row)

    pair_order = {row["annotation_id"]: index for index, row in enumerate(pair_rows)}
    merged_rows: List[Dict[str, str]] = []
    grouped_items = sorted(
        grouped.items(),
        key=lambda item: (
            pair_order.get(item[0][0], 9999),
            item[0][1],
            item[0][2],
            item[0][3],
            item[0][4],
        ),
    )

    global_counter = 1
    pair_counter: Dict[str, int] = defaultdict(int)
    for _, group in grouped_items:
        primary = choose_primary_row(group)
        from_rule_v1 = any(row["generator_version"] == "v1" for row in group)
        from_rule_v11 = any(row["generator_version"] == "v1.1" for row in group)
        pred_confidence = choose_best_confidence(group)
        candidate_tier = determine_candidate_tier(
            from_rule_v1=from_rule_v1,
            from_rule_v11=from_rule_v11,
            pred_confidence=pred_confidence,
            relation_type=primary["pred_relation_type"],
        )
        annotation_id = primary["annotation_id"]
        pair_counter[annotation_id] += 1
        pred_column_id = f"CP{pair_counter[annotation_id]:02d}"
        candidate_id = f"BCPV0-{global_counter:04d}"
        global_counter += 1

        source_labels = []
        source_pred_ids = []
        source_notes = []
        for row in sorted(group, key=lambda item: item["generator_version"]):
            label = f"rule_{row['generator_version']}"
            source_labels.append(label)
            source_pred_ids.append(f"{label}:{row['pred_column_id']}")
            source_notes.append(f"{label}:{row['notes']}")

        risk_reasons: List[str] = []
        if pred_confidence == "low":
            risk_reasons.append("low_source_confidence")
        if primary["pred_relation_type"] in HIGH_RISK_RELATION_TYPES:
            risk_reasons.append(f"high_risk_relation={primary['pred_relation_type']}")

        merged_rows.append(
            {
                "candidate_id": candidate_id,
                "annotation_id": annotation_id,
                "pair_id": primary["pair_id"],
                "pred_column_id": pred_column_id,
                "pred_span_a": primary["pred_span_a"],
                "pred_span_b": primary["pred_span_b"],
                "pred_relation_type": primary["pred_relation_type"],
                "pred_relation_strength": choose_best_strength(group),
                "pred_alignment_direction": choose_alignment_direction(group),
                "pred_is_core_column": "1"
                if any(row["pred_is_core_column"] == "1" for row in group)
                else "0",
                "pred_supports_resonance": "1"
                if any(row["pred_supports_resonance"] == "1" for row in group)
                else "0",
                "pred_confidence": pred_confidence,
                "generator_name": "bert_candidate_pool",
                "generator_version": "v0",
                "notes": " | ".join(source_notes),
                "from_rule_v1": "1" if from_rule_v1 else "0",
                "from_rule_v1_1": "1" if from_rule_v11 else "0",
                "source_count": str(len(group)),
                "candidate_tier": candidate_tier,
                "candidate_pool_note": (
                    f"merged_from={'+'.join(source_labels)}; "
                    f"source_pred_ids={'|'.join(source_pred_ids)}; "
                    f"core_policy=source_or; "
                    f"risk_flags={'|'.join(risk_reasons) if risk_reasons else 'none'}"
                ),
                "needs_bert_score": "0"
                if primary["pred_relation_type"] == "analogy"
                else "1",
                "suggested_bert_task": build_suggested_bert_task(
                    candidate_tier=candidate_tier,
                    relation_type=primary["pred_relation_type"],
                ),
            }
        )

    merged_rows.sort(
        key=lambda row: (
            pair_order.get(row["annotation_id"], 9999),
            TIER_ORDER[row["candidate_tier"]],
            -int(row["source_count"]),
            row["pred_relation_type"],
            row["pred_span_a"],
            row["pred_span_b"],
        )
    )

    final_rows: List[Dict[str, str]] = []
    pair_counter.clear()
    for index, row in enumerate(merged_rows, start=1):
        row = dict(row)
        row["candidate_id"] = f"BCPV0-{index:04d}"
        pair_counter[row["annotation_id"]] += 1
        row["pred_column_id"] = f"CP{pair_counter[row['annotation_id']]:02d}"
        final_rows.append(row)
    return final_rows


def ensure_candidate_pool_valid(rows: List[Dict[str, str]], pair_map: Dict[str, Dict[str, str]]) -> None:
    if not rows:
        raise ValueError("candidate pool is empty.")
    missing = [field for field in CANDIDATE_FIELDNAMES if field not in rows[0]]
    if missing:
        raise ValueError(f"candidate pool missing fields: {missing}")
    ensure_prediction_rows_valid(rows, pair_map, "bert_candidate_pool_v0")


def load_summary(path: Path) -> Dict[str, float]:
    return json.loads(path.read_text(encoding="utf-8"))["summary"]


def build_tier_distribution(rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    tier_counts = Counter(row["candidate_tier"] for row in rows)
    tier_pairs: Dict[str, set[str]] = defaultdict(set)
    tier_cores = Counter()
    tier_needs = Counter()
    for row in rows:
        tier_pairs[row["candidate_tier"]].add(row["annotation_id"])
        if row["pred_is_core_column"] == "1":
            tier_cores[row["candidate_tier"]] += 1
        if row["needs_bert_score"] == "1":
            tier_needs[row["candidate_tier"]] += 1
    output = []
    for tier in sorted(tier_counts, key=lambda item: TIER_ORDER[item]):
        output.append(
            {
                "candidate_tier": tier,
                "candidate_count": tier_counts[tier],
                "pair_count": len(tier_pairs[tier]),
                "core_candidate_count": tier_cores[tier],
                "needs_bert_score_count": tier_needs[tier],
            }
        )
    return output


def build_relation_distribution(rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    relation_stats: Dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        stats = relation_stats[row["pred_relation_type"]]
        stats["candidate_count"] += 1
        stats[row["candidate_tier"]] += 1
        if row["pred_is_core_column"] == "1":
            stats["core_candidate_count"] += 1
        if row["needs_bert_score"] == "1":
            stats["needs_bert_score_count"] += 1
    output = []
    for relation_type in sorted(relation_stats):
        stats = relation_stats[relation_type]
        output.append(
            {
                "pred_relation_type": relation_type,
                "candidate_count": stats["candidate_count"],
                "high_precision_rule_count": stats["high_precision_rule"],
                "precision_ablation_only_count": stats["precision_ablation_only"],
                "recall_rule_only_count": stats["recall_rule_only"],
                "low_confidence_rule_count": stats["low_confidence_rule"],
                "core_candidate_count": stats["core_candidate_count"],
                "needs_bert_score_count": stats["needs_bert_score_count"],
            }
        )
    return output


def build_pair_coverage(rows: List[Dict[str, str]], pair_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    by_annotation: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_annotation[row["annotation_id"]].append(row)

    output = []
    for pair in pair_rows:
        pair_rows_here = by_annotation.get(pair["annotation_id"], [])
        tier_counts = Counter(row["candidate_tier"] for row in pair_rows_here)
        output.append(
            {
                "annotation_id": pair["annotation_id"],
                "pair_id": pair["pair_id"],
                "source": pair["source"],
                "dataset_name": pair["dataset_name"],
                "candidate_count": len(pair_rows_here),
                "high_precision_rule_count": tier_counts["high_precision_rule"],
                "precision_ablation_only_count": tier_counts["precision_ablation_only"],
                "recall_rule_only_count": tier_counts["recall_rule_only"],
                "low_confidence_rule_count": tier_counts["low_confidence_rule"],
                "core_candidate_count": sum(1 for row in pair_rows_here if row["pred_is_core_column"] == "1"),
                "needs_bert_score_count": sum(
                    1 for row in pair_rows_here if row["needs_bert_score"] == "1"
                ),
                "has_candidate": "1" if pair_rows_here else "0",
            }
        )
    return output


def write_evaluation_summary(summary: Dict[str, object], candidate_rows: List[Dict[str, str]]) -> None:
    lines = [
        "# bert_candidate_pool_v0 evaluation summary",
        "",
        f"- candidate columns: {len(candidate_rows)}",
        f"- covered pairs: {len({row['annotation_id'] for row in candidate_rows})}",
        f"- invalid predictions: {summary['invalid_prediction_count']}",
        f"- exact P/R/F1: {summary['exact_column_precision']} / {summary['exact_column_recall']} / {summary['exact_column_f1']}",
        f"- relaxed P/R/F1: {summary['relaxed_column_precision']} / {summary['relaxed_column_recall']} / {summary['relaxed_column_f1']}",
        f"- relation_type accuracy: exact={summary['relation_type_accuracy_on_exact_matches']}, relaxed={summary['relation_type_accuracy_on_relaxed_matches']}",
        f"- core column recall: {summary['core_column_recall']}",
        f"- missing_core_rate: {summary['missing_core_rate']}",
        f"- overgeneration_rate: {summary['overgeneration_rate']}",
        f"- missing_column_rate: {summary['missing_column_rate']}",
        "",
        "## Interpretation",
        "",
        "- This evaluation is for candidate-pool coverage/noise tradeoff, not a final end-to-end generator score.",
        "- A useful pool should keep invalid predictions at 0, preserve or improve recall over the recall-oriented base when possible, and remain easier for a later BERT filter to prune than generating columns from scratch.",
    ]
    EVAL_SUMMARY_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_comparison(
    v1_rows: List[Dict[str, str]],
    v11_rows: List[Dict[str, str]],
    pool_rows: List[Dict[str, str]],
    v1_summary: Dict[str, object],
    v11_summary: Dict[str, object],
    pool_summary: Dict[str, object],
) -> bool:
    metrics = [
        ("candidate_columns", len(v1_rows), len(v11_rows), len(pool_rows)),
        (
            "covered_pairs",
            len({row["annotation_id"] for row in v1_rows}),
            len({row["annotation_id"] for row in v11_rows}),
            len({row["annotation_id"] for row in pool_rows}),
        ),
        (
            "invalid_predictions",
            v1_summary["invalid_prediction_count"],
            v11_summary["invalid_prediction_count"],
            pool_summary["invalid_prediction_count"],
        ),
        ("exact_precision", v1_summary["exact_column_precision"], v11_summary["exact_column_precision"], pool_summary["exact_column_precision"]),
        ("exact_recall", v1_summary["exact_column_recall"], v11_summary["exact_column_recall"], pool_summary["exact_column_recall"]),
        ("exact_f1", v1_summary["exact_column_f1"], v11_summary["exact_column_f1"], pool_summary["exact_column_f1"]),
        ("relaxed_precision", v1_summary["relaxed_column_precision"], v11_summary["relaxed_column_precision"], pool_summary["relaxed_column_precision"]),
        ("relaxed_recall", v1_summary["relaxed_column_recall"], v11_summary["relaxed_column_recall"], pool_summary["relaxed_column_recall"]),
        ("relaxed_f1", v1_summary["relaxed_column_f1"], v11_summary["relaxed_column_f1"], pool_summary["relaxed_column_f1"]),
        (
            "relation_type_accuracy_relaxed",
            v1_summary["relation_type_accuracy_on_relaxed_matches"],
            v11_summary["relation_type_accuracy_on_relaxed_matches"],
            pool_summary["relation_type_accuracy_on_relaxed_matches"],
        ),
        ("core_column_recall", v1_summary["core_column_recall"], v11_summary["core_column_recall"], pool_summary["core_column_recall"]),
        ("missing_core_rate", v1_summary["missing_core_rate"], v11_summary["missing_core_rate"], pool_summary["missing_core_rate"]),
        ("overgeneration_rate", v1_summary["overgeneration_rate"], v11_summary["overgeneration_rate"], pool_summary["overgeneration_rate"]),
    ]

    suitable = (
        pool_summary["invalid_prediction_count"] == 0
        and pool_summary["relaxed_column_recall"] >= v1_summary["relaxed_column_recall"]
        and len(pool_rows) >= len(v1_rows)
        and len({row["annotation_id"] for row in pool_rows}) >= len({row["annotation_id"] for row in v1_rows})
    )

    lines = [
        "# bert_candidate_pool_v0 comparison with v1 and v1.1",
        "",
        "| metric | v1 | v1.1 | candidate_pool_v0 | delta vs v1 | delta vs v1.1 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, v1_value, v11_value, pool_value in metrics:
        delta_v1 = round(float(pool_value) - float(v1_value), 6)
        delta_v11 = round(float(pool_value) - float(v11_value), 6)
        lines.append(
            f"| {name} | {v1_value} | {v11_value} | {pool_value} | {delta_v1} | {delta_v11} |"
        )

    lines.extend(
        [
            "",
            "## Judgment",
            "",
            f"- relative to v1, the pool {'adds' if len(pool_rows) > len(v1_rows) else 'does not add'} extra candidates without dropping the recall base.",
            f"- relative to v1.1, the pool {'restores' if len(pool_rows) > len(v11_rows) else 'does not restore'} candidate coverage lost by the precision-oriented ablation.",
            f"- suitable as BERT candidate pool: {'yes' if suitable else 'no'}",
            "",
            "## Why this is not just v1.1",
            "",
            "- v1 remains the recall-oriented base.",
            "- v1.1 contributes auxiliary precision evidence where it overlaps or introduces a small number of extra candidates.",
            "- the pool keeps v1 candidates even when v1.1 declines to generate them.",
        ]
    )
    COMPARISON_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return suitable


def write_diagnostic_report(
    candidate_rows: List[Dict[str, str]],
    tier_rows: List[Dict[str, object]],
    relation_rows: List[Dict[str, object]],
    pair_coverage_rows: List[Dict[str, object]],
    pool_summary: Dict[str, object],
    gold_rows: List[Dict[str, str]],
) -> None:
    unmatched_gold = read_csv_dicts(POOL_EVAL_DIR / "unmatched_gold_columns.csv")
    overgenerated_rows = read_csv_dicts(POOL_EVAL_DIR / "overgenerated_prediction_columns.csv")
    zero_candidate_pairs = [row["annotation_id"] for row in pair_coverage_rows if row["has_candidate"] == "0"]
    unmatched_gold_core = [row for row in unmatched_gold if row.get("is_core_column") == "1"]
    unmatched_core_pairs = Counter(row["annotation_id"] for row in unmatched_gold_core)
    top_unmatched_core = ", ".join(
        f"{annotation_id} ({count})"
        for annotation_id, count in unmatched_core_pairs.most_common(8)
    ) or "none"

    overgenerated_preview = []
    for row in overgenerated_rows[:10]:
        overgenerated_preview.append(
            f"{row['annotation_id']}/{row['pred_column_id']} {row['pred_relation_type']} [{row.get('candidate_tier', '')}]"
        )

    lines = [
        "# bert_candidate_pool_v0 diagnostic report",
        "",
        f"- candidate pool total columns: {len(candidate_rows)}",
        f"- covered pairs: {len({row['annotation_id'] for row in candidate_rows})} / 50",
        f"- exact P/R/F1: {pool_summary['exact_column_precision']} / {pool_summary['exact_column_recall']} / {pool_summary['exact_column_f1']}",
        f"- relaxed P/R/F1: {pool_summary['relaxed_column_precision']} / {pool_summary['relaxed_column_recall']} / {pool_summary['relaxed_column_f1']}",
        f"- core recall: {pool_summary['core_column_recall']}",
        f"- overgeneration_rate: {pool_summary['overgeneration_rate']}",
        "",
        "## candidate_tier counts",
        "",
    ]
    for row in tier_rows:
        lines.append(
            f"- {row['candidate_tier']}: {row['candidate_count']} candidates across {row['pair_count']} pairs"
        )
    lines.extend(
        [
            "",
            "## relation_type counts",
            "",
        ]
    )
    for row in relation_rows:
        lines.append(f"- {row['pred_relation_type']}: {row['candidate_count']}")
    lines.extend(
        [
            "",
            "## Remaining blind spots",
            "",
            f"- pairs with zero candidates: {', '.join(zero_candidate_pairs) if zero_candidate_pairs else 'none'}",
            f"- unmatched gold core columns after relaxed matching: {len(unmatched_gold_core)}",
            f"- top pairs with uncovered core columns: {top_unmatched_core}",
            "",
            "## Overgenerated candidates that most need BERT filter",
            "",
            f"- overgenerated preview: {', '.join(overgenerated_preview) if overgenerated_preview else 'none'}",
            "",
            "## Interpretation",
            "",
            "- v1.1 is not suitable as a standalone pool because it improves cleanliness by shrinking coverage too aggressively.",
            "- v1 is still the better recall base because it keeps more candidates and more matched columns alive for downstream filtering.",
            "- the first BERT stage should be reranker/filter, not end-to-end generator, because the current 50-pair / 135-column gold_v1 is strong enough for evaluation and diagnostic slicing but too small for direct span-generation training.",
            "- gold_v1 is used here only for offline evaluation and diagnosis, not for candidate creation logic.",
            "",
            "## Gold reference note",
            "",
            f"- gold active columns for offline diagnosis: {len(gold_rows)}",
        ]
    )
    DIAGNOSTIC_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_prototype_plan() -> None:
    lines = [
        "# bert_assisted_prototype_v0 plan",
        "",
        "## Prototype goal",
        "",
        "- Use `bert_candidate_pool_v0` for BERT rerank / false-positive filtering.",
        "- Do not let BERT generate spans directly.",
        "",
        "## Input fields",
        "",
        "- turn_a",
        "- turn_b",
        "- pred_span_a",
        "- pred_span_b",
        "- pred_relation_type",
        "- rule confidence",
        "- candidate_tier",
        "",
        "## Output fields",
        "",
        "- bert_column_score",
        "- bert_keep_probability",
        "- bert_relation_type_score (optional)",
        "",
        "## First-version recommended tasks",
        "",
        "- binary keep/filter",
        "- relation_type sanity check",
        "",
        "## Not recommended yet",
        "",
        "- end-to-end span extraction",
        "- analogy generation",
        "- training a large generator directly on 50 pairs",
        "",
        "## MacBERT scope note",
        "",
        "- If MacBERT is used later, keep it in shadow scoring mode only.",
        "- Do not write BERT output back into gold.",
        "- Do not attach the prototype to the website.",
    ]
    PROTOTYPE_PLAN_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest() -> None:
    lines = [
        "# bert_candidate_pool_v0 manifest",
        "",
        "| file | purpose |",
        "| --- | --- |",
        "| `bert_candidate_pool_v0.csv` | merged candidate pool from v1 recall base plus v1.1 precision hints |",
        "| `bert_candidate_pool_v0.xlsx` | spreadsheet view of the merged candidate pool |",
        "| `bert_candidate_pool_v0_evaluation_summary.md` | compact metric summary for pool evaluation |",
        "| `bert_candidate_pool_v0_comparison_with_v1_and_v1_1.md` | comparison of pool vs v1 and v1.1 |",
        "| `bert_candidate_pool_v0_tier_distribution.csv` | candidate tier counts and coverage |",
        "| `bert_candidate_pool_v0_relation_type_distribution.csv` | relation-type distribution for the pool |",
        "| `bert_candidate_pool_v0_pair_coverage.csv` | per-pair candidate coverage table |",
        "| `bert_candidate_pool_v0_diagnostic_report.md` | diagnostic notes on remaining gaps and noise |",
        "| `bert_assisted_prototype_v0_plan.md` | next-step plan for BERT rerank/filter prototype |",
        "| `bert_candidate_pool_v0_manifest.md` | artifact manifest |",
        "| `evaluation_run/*` | evaluator outputs for the candidate pool |",
        "",
        "## Scope note",
        "",
        "- No BERT training or inference was run in this step.",
        "- No baseline artifacts were overwritten.",
        "- `diagraph_gold_50_column_gold_v1` was used only for offline evaluation.",
    ]
    MANIFEST_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    pair_map = {row["annotation_id"]: row for row in pair_rows}
    gold_rows = read_csv_dicts(DEFAULT_GOLD_ACTIVE)
    v1_rows = read_csv_dicts(V1_PREDICTION_PATH)
    v11_rows = read_csv_dicts(V11_PREDICTION_PATH)

    ensure_prediction_rows_valid(v1_rows, pair_map, "rule_baseline_v1")
    ensure_prediction_rows_valid(v11_rows, pair_map, "rule_baseline_v1_1")

    candidate_rows = merge_prediction_rows(v1_rows, v11_rows, pair_rows)
    ensure_candidate_pool_valid(candidate_rows, pair_map)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(POOL_CSV_PATH, candidate_rows, CANDIDATE_FIELDNAMES)

    eval_result = evaluate_predictions(
        gold_path=DEFAULT_GOLD_ACTIVE,
        pair_list_path=PAIR_LIST_PATH,
        prediction_path=POOL_CSV_PATH,
        output_dir=POOL_EVAL_DIR,
        relaxed_threshold=0.5,
        run_name="bert_candidate_pool_v0",
    )

    tier_rows = build_tier_distribution(candidate_rows)
    relation_rows = build_relation_distribution(candidate_rows)
    pair_coverage_rows = build_pair_coverage(candidate_rows, pair_rows)
    write_csv(TIER_DIST_PATH, tier_rows, list(tier_rows[0].keys()))
    write_csv(RELATION_DIST_PATH, relation_rows, list(relation_rows[0].keys()))
    write_csv(PAIR_COVERAGE_PATH, pair_coverage_rows, list(pair_coverage_rows[0].keys()))

    v1_summary = load_summary(V1_SUMMARY_PATH)
    v11_summary = load_summary(V11_SUMMARY_PATH)
    pool_summary = eval_result["summary"]
    write_evaluation_summary(pool_summary, candidate_rows)
    suitable_for_pool = write_comparison(v1_rows, v11_rows, candidate_rows, v1_summary, v11_summary, pool_summary)
    write_diagnostic_report(candidate_rows, tier_rows, relation_rows, pair_coverage_rows, pool_summary, gold_rows)
    write_prototype_plan()
    write_manifest()

    stats = {
        "candidate_csv": str(POOL_CSV_PATH),
        "candidate_xlsx": str(POOL_XLSX_PATH),
        "candidate_count": len(candidate_rows),
        "covered_pairs": len({row["annotation_id"] for row in candidate_rows}),
        "invalid_prediction_count": pool_summary["invalid_prediction_count"],
        "relaxed_recall": pool_summary["relaxed_column_recall"],
        "overgeneration_rate": pool_summary["overgeneration_rate"],
        "suitable_for_bert_candidate_pool": suitable_for_pool,
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
