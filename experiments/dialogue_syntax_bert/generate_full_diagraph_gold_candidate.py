from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parent
BASE_DIR = ROOT / "artifacts" / "formal_300_v1" / "diagraph_gold_50"
OUTPUT_DIR = BASE_DIR / "full_gold_candidate"

PILOT_PATH = BASE_DIR / "pilot10_review" / "pilot10_column_annotation_reviewed_v1.csv"
EASY_MEDIUM_PATH = (
    BASE_DIR
    / "remaining_easy_medium21"
    / "reviewed_v1"
    / "remaining_easy_medium21_column_reviewed_v1.csv"
)
HARD_PATH = (
    BASE_DIR
    / "remaining_hard19"
    / "reviewed_v1"
    / "remaining_hard19_column_reviewed_v1.csv"
)
PAIR_LIST_PATH = BASE_DIR / "diagraph_gold_50_pair_list.csv"
PRIORITY_PATH = BASE_DIR / "diagraph_gold_50_annotation_priority.csv"
GUIDE_PATH = BASE_DIR / "diagraph_gold_50_annotation_guide_v2.md"

ALL_ROWS_PATH = OUTPUT_DIR / "full_diagraph_gold_50_column_reviewed_all_rows.csv"
ACTIVE_PATH = OUTPUT_DIR / "full_diagraph_gold_50_column_gold_candidate_active.csv"
VALIDATION_REPORT_PATH = OUTPUT_DIR / "full_diagraph_gold_50_merge_validation_report.md"
SUMMARY_PATH = OUTPUT_DIR / "full_diagraph_gold_50_distribution_summary.md"
RELATION_DIST_PATH = OUTPUT_DIR / "full_diagraph_gold_50_relation_type_distribution.csv"
CORE_AUX_DIST_PATH = OUTPUT_DIR / "full_diagraph_gold_50_core_aux_distribution.csv"
README_PATH = OUTPUT_DIR / "full_diagraph_gold_50_gold_candidate_readme.md"
NEXT_STEP_PLAN_PATH = OUTPUT_DIR / "full_diagraph_gold_50_next_step_plan.md"

ALL_ROWS_FIELDNAMES = [
    "annotation_id",
    "pair_id",
    "column_id",
    "span_a",
    "span_b",
    "relation_type",
    "relation_strength",
    "alignment_direction",
    "is_core_column",
    "supports_resonance",
    "notes",
    "draft_confidence",
    "needs_human_review",
    "review_reason",
    "reviewer_decision",
    "reviewer_note",
    "reviewed_relation_type",
    "reviewed_relation_strength",
    "reviewed_is_core_column",
    "reviewed_supports_resonance",
    "reviewed_status",
    "batch",
]

ACTIVE_FIELDNAMES = [
    "annotation_id",
    "pair_id",
    "column_id",
    "span_a",
    "span_b",
    "relation_type",
    "relation_strength",
    "alignment_direction",
    "is_core_column",
    "supports_resonance",
    "notes",
    "reviewer_decision",
    "reviewer_note",
    "batch",
    "source",
    "dataset_name",
    "difficulty_level",
    "sample_stratum",
]

VALID_RELATION_TYPES = {
    "lexical_reproduction",
    "syntactic_parallelism",
    "semantic_substitution",
    "coreference_or_demonstrative",
    "slot_filling",
    "short_answer",
    "contrast",
    "repair",
    "analogy",
    "pragmatic_function",
    "punctuation_or_modal",
    "other",
}
VALID_STRENGTHS = {"strong", "medium", "weak"}
VALID_DIRECTIONS = {"A_to_B", "B_to_A", "mutual"}
VALID_BINARY = {"0", "1"}


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Iterable[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_reviewed_status(row: Dict[str, str]) -> str:
    existing = row.get("reviewed_status", "").strip()
    if existing:
        return existing
    decision = row.get("reviewer_decision", "").strip()
    if decision == "delete":
        return "excluded_from_gold_candidate"
    if decision == "revise":
        return "revised_in_gold_candidate"
    return "kept_in_gold_candidate"


def normalize_batch_rows(rows: List[Dict[str, str]], batch: str) -> List[Dict[str, str]]:
    normalized_rows: List[Dict[str, str]] = []
    for row in rows:
        normalized = {field: row.get(field, "") for field in ALL_ROWS_FIELDNAMES}
        normalized["reviewed_status"] = normalize_reviewed_status(row)
        normalized["batch"] = batch
        normalized_rows.append(normalized)
    return normalized_rows


def row_key(row: Dict[str, str]) -> str:
    return f"{row['annotation_id']}/{row['column_id']}"


def build_active_rows(
    all_rows: List[Dict[str, str]],
    pair_map: Dict[str, Dict[str, str]],
    priority_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    active_rows: List[Dict[str, str]] = []
    for row in all_rows:
        if row["reviewer_decision"] == "delete":
            continue
        if row["reviewed_status"] == "excluded_from_gold_candidate":
            continue
        pair = pair_map[row["annotation_id"]]
        priority = priority_map[row["annotation_id"]]
        active_rows.append(
            {
                "annotation_id": row["annotation_id"],
                "pair_id": row["pair_id"],
                "column_id": row["column_id"],
                "span_a": row["span_a"],
                "span_b": row["span_b"],
                "relation_type": row["reviewed_relation_type"],
                "relation_strength": row["reviewed_relation_strength"],
                "alignment_direction": row["alignment_direction"],
                "is_core_column": row["reviewed_is_core_column"],
                "supports_resonance": row["reviewed_supports_resonance"],
                "notes": row["notes"],
                "reviewer_decision": row["reviewer_decision"],
                "reviewer_note": row["reviewer_note"],
                "batch": row["batch"],
                "source": pair["source"],
                "dataset_name": pair["dataset_name"],
                "difficulty_level": priority["difficulty_level"],
                "sample_stratum": pair["sample_stratum"],
            }
        )
    return active_rows


def count_unique_pairs(rows: List[Dict[str, str]]) -> Dict[str, int]:
    by_batch: Dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_batch[row["batch"]].add(row["annotation_id"])
    return {batch: len(ids) for batch, ids in by_batch.items()}


def validate(
    all_rows: List[Dict[str, str]],
    active_rows: List[Dict[str, str]],
    pair_map: Dict[str, Dict[str, str]],
    priority_map: Dict[str, Dict[str, str]],
) -> Dict[str, object]:
    errors: List[str] = []
    duplicate_keys_all: List[str] = []
    unknown_annotation_ids: List[str] = []
    span_a_failures: List[str] = []
    span_b_failures: List[str] = []
    invalid_relation_rows: List[str] = []
    invalid_strength_rows: List[str] = []
    invalid_direction_rows: List[str] = []
    invalid_binary_rows: List[str] = []
    mixed_excluded_rows: List[str] = []

    seen_keys: set[str] = set()
    decision_counts = Counter(row["reviewer_decision"] for row in all_rows)
    revise_counts_by_batch = Counter()
    for row in all_rows:
        key = row_key(row)
        if key in seen_keys:
            duplicate_keys_all.append(key)
        seen_keys.add(key)
        if row["annotation_id"] not in pair_map:
            unknown_annotation_ids.append(row["annotation_id"])
            continue
        if row["reviewer_decision"] == "revise":
            revise_counts_by_batch[row["batch"]] += 1

    rows_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    core_counts_by_pair: Counter = Counter()
    relation_counts = Counter()
    relation_counts_by_batch = Counter()
    difficulty_counts = Counter()
    pair_column_counts = Counter()
    source_dataset_counts = Counter()
    for row in active_rows:
        key = row_key(row)
        pair = pair_map.get(row["annotation_id"])
        if pair is None:
            errors.append(f"Unexpected active annotation_id: {row['annotation_id']}")
            continue
        priority = priority_map[row["annotation_id"]]
        rows_by_pair[row["annotation_id"]].append(row)
        pair_column_counts[row["annotation_id"]] += 1
        relation_counts[row["relation_type"]] += 1
        relation_counts_by_batch[(row["batch"], row["relation_type"])] += 1
        difficulty_counts[priority["difficulty_level"]] += 1
        source_dataset_counts[(row["source"], row["dataset_name"])] += 1
        if row["is_core_column"] == "1":
            core_counts_by_pair[row["annotation_id"]] += 1
        if row["span_a"] not in pair["turn_a"]:
            span_a_failures.append(key)
        if row["span_b"] not in pair["turn_b"]:
            span_b_failures.append(key)
        if row["relation_type"] not in VALID_RELATION_TYPES:
            invalid_relation_rows.append(key)
        if row["relation_strength"] not in VALID_STRENGTHS:
            invalid_strength_rows.append(key)
        if row["alignment_direction"] not in VALID_DIRECTIONS:
            invalid_direction_rows.append(key)
        if (
            row["is_core_column"] not in VALID_BINARY
            or row["supports_resonance"] not in VALID_BINARY
        ):
            invalid_binary_rows.append(key)
        if row.get("reviewed_status", "") == "excluded_from_gold_candidate":
            mixed_excluded_rows.append(key)

    unique_pair_ids = sorted({row["annotation_id"] for row in all_rows})
    batch_pair_counts = count_unique_pairs(all_rows)
    missing_pairs_active = sorted(
        annotation_id for annotation_id in pair_map if annotation_id not in rows_by_pair
    )
    missing_core_pairs_active = sorted(
        annotation_id for annotation_id in pair_map if core_counts_by_pair[annotation_id] < 1
    )

    if len(unique_pair_ids) != 50:
        errors.append(f"Expected 50 unique annotation_id, got {len(unique_pair_ids)}")
    if len(all_rows) != 151:
        errors.append(f"Expected 151 all_rows, got {len(all_rows)}")
    if len(active_rows) != 135:
        errors.append(f"Expected 135 active rows, got {len(active_rows)}")
    if decision_counts["delete"] != 16:
        errors.append(f"Expected 16 delete rows, got {decision_counts['delete']}")
    if decision_counts["revise"] != 14:
        errors.append(f"Expected 14 revise rows, got {decision_counts['revise']}")
    expected_pair_counts = {"pilot10": 10, "easy_medium21": 21, "hard19": 19}
    for batch, expected in expected_pair_counts.items():
        actual = batch_pair_counts.get(batch, 0)
        if actual != expected:
            errors.append(f"Expected {expected} pairs in {batch}, got {actual}")
    expected_revise_counts = {"pilot10": 6, "easy_medium21": 4, "hard19": 4}
    for batch, expected in expected_revise_counts.items():
        actual = revise_counts_by_batch.get(batch, 0)
        if actual != expected:
            errors.append(f"Expected {expected} revise rows in {batch}, got {actual}")
    if duplicate_keys_all:
        errors.append(f"Duplicate annotation_id+column_id: {duplicate_keys_all}")
    if unknown_annotation_ids:
        errors.append(f"Unknown annotation_id outside pair_list: {sorted(set(unknown_annotation_ids))}")
    if missing_pairs_active:
        errors.append(f"Pairs with no active column: {missing_pairs_active}")
    if missing_core_pairs_active:
        errors.append(f"Pairs with no active core column: {missing_core_pairs_active}")
    if span_a_failures:
        errors.append(f"span_a failures: {span_a_failures}")
    if span_b_failures:
        errors.append(f"span_b failures: {span_b_failures}")
    if invalid_relation_rows:
        errors.append(f"Invalid relation_type rows: {invalid_relation_rows}")
    if invalid_strength_rows:
        errors.append(f"Invalid relation_strength rows: {invalid_strength_rows}")
    if invalid_direction_rows:
        errors.append(f"Invalid alignment_direction rows: {invalid_direction_rows}")
    if invalid_binary_rows:
        errors.append(f"Invalid binary rows: {invalid_binary_rows}")
    if mixed_excluded_rows:
        errors.append(
            f"Excluded rows mixed into active candidate: {mixed_excluded_rows}"
        )

    return {
        "errors": errors,
        "unique_pair_count": len(unique_pair_ids),
        "all_rows_count": len(all_rows),
        "active_count": len(active_rows),
        "decision_counts": decision_counts,
        "batch_pair_counts": batch_pair_counts,
        "revise_counts_by_batch": revise_counts_by_batch,
        "missing_pairs_active": missing_pairs_active,
        "missing_core_pairs_active": missing_core_pairs_active,
        "span_a_failures": span_a_failures,
        "span_b_failures": span_b_failures,
        "relation_counts": relation_counts,
        "relation_counts_by_batch": relation_counts_by_batch,
        "difficulty_counts": difficulty_counts,
        "pair_column_counts": pair_column_counts,
        "core_counts_by_pair": core_counts_by_pair,
        "source_dataset_counts": source_dataset_counts,
    }


def build_relation_distribution_rows(
    validation: Dict[str, object]
) -> List[Dict[str, str]]:
    relation_counts: Counter = validation["relation_counts"]  # type: ignore[assignment]
    relation_counts_by_batch: Counter = validation["relation_counts_by_batch"]  # type: ignore[assignment]
    rows: List[Dict[str, str]] = []
    for relation_type in sorted(relation_counts):
        rows.append(
            {
                "scope": "all",
                "scope_value": "ALL",
                "relation_type": relation_type,
                "count": str(relation_counts[relation_type]),
            }
        )
        for batch in ("pilot10", "easy_medium21", "hard19"):
            rows.append(
                {
                    "scope": "batch",
                    "scope_value": batch,
                    "relation_type": relation_type,
                    "count": str(relation_counts_by_batch[(batch, relation_type)]),
                }
            )
    return rows


def build_core_aux_distribution_rows(
    active_rows: List[Dict[str, str]],
    priority_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    counter: Counter = Counter()
    for row in active_rows:
        role = "core" if row["is_core_column"] == "1" else "auxiliary"
        difficulty = priority_map[row["annotation_id"]]["difficulty_level"]
        counter[("all", "ALL", role)] += 1
        counter[("batch", row["batch"], role)] += 1
        counter[("difficulty", difficulty, role)] += 1
    rows: List[Dict[str, str]] = []
    for (scope, scope_value, role), count in sorted(counter.items()):
        rows.append(
            {
                "scope": scope,
                "scope_value": scope_value,
                "column_role": role,
                "count": str(count),
            }
        )
    return rows


def build_validation_report(validation: Dict[str, object]) -> str:
    decision_counts: Counter = validation["decision_counts"]  # type: ignore[assignment]
    batch_pair_counts: Dict[str, int] = validation["batch_pair_counts"]  # type: ignore[assignment]
    revise_counts_by_batch: Counter = validation["revise_counts_by_batch"]  # type: ignore[assignment]
    lines = [
        "# full_diagraph_gold_50 merge validation report",
        "",
        "## Coverage",
        f"- unique annotation_id 数量: {validation['unique_pair_count']}",
        f"- all_rows 总行数: {validation['all_rows_count']}",
        f"- active 有效 column 数量: {validation['active_count']}",
        "",
        "## Batch sizes",
        f"- pilot10 pair 数: {batch_pair_counts.get('pilot10', 0)}",
        f"- easy_medium21 pair 数: {batch_pair_counts.get('easy_medium21', 0)}",
        f"- hard19 pair 数: {batch_pair_counts.get('hard19', 0)}",
        "",
        "## Decision totals",
        f"- keep: {decision_counts['keep']}",
        f"- revise: {decision_counts['revise']}",
        f"- delete: {decision_counts['delete']}",
        f"- revise by batch: pilot10={revise_counts_by_batch.get('pilot10', 0)}, easy_medium21={revise_counts_by_batch.get('easy_medium21', 0)}, hard19={revise_counts_by_batch.get('hard19', 0)}",
        "",
        "## Checks",
        f"- 覆盖全部 50 个 pair: {'通过' if validation['unique_pair_count'] == 50 else '未通过'}",
        f"- all_rows=151: {'通过' if validation['all_rows_count'] == 151 else '未通过'}",
        f"- active=135: {'通过' if validation['active_count'] == 135 else '未通过'}",
        f"- delete=16: {'通过' if decision_counts['delete'] == 16 else '未通过'}",
        f"- revise=14: {'通过' if decision_counts['revise'] == 14 else '未通过'}",
        f"- 每个 pair 至少 1 个 active column: {'通过' if not validation['missing_pairs_active'] else '未通过'}",
        f"- 每个 pair 至少 1 个 active core column: {'通过' if not validation['missing_core_pairs_active'] else '未通过'}",
        f"- span_a 全部命中 turn_a: {'通过' if not validation['span_a_failures'] else '未通过'}",
        f"- span_b 全部命中 turn_b: {'通过' if not validation['span_b_failures'] else '未通过'}",
        f"- active 中无 excluded_from_gold_candidate: {'通过' if not any('Excluded rows mixed' in err for err in validation['errors']) else '未通过'}",
        "",
        "## Errors",
    ]
    if validation["errors"]:
        for err in validation["errors"]:
            lines.append(f"- {err}")
    else:
        lines.append("- 无结构性错误。")
    return "\n".join(lines) + "\n"


def build_distribution_summary(
    active_rows: List[Dict[str, str]],
    pair_map: Dict[str, Dict[str, str]],
    priority_map: Dict[str, Dict[str, str]],
    validation: Dict[str, object],
) -> str:
    relation_counts: Counter = validation["relation_counts"]  # type: ignore[assignment]
    relation_counts_by_batch: Counter = validation["relation_counts_by_batch"]  # type: ignore[assignment]
    difficulty_counts: Counter = validation["difficulty_counts"]  # type: ignore[assignment]
    pair_column_counts: Counter = validation["pair_column_counts"]  # type: ignore[assignment]
    core_counts_by_pair: Counter = validation["core_counts_by_pair"]  # type: ignore[assignment]
    source_dataset_counts: Counter = validation["source_dataset_counts"]  # type: ignore[assignment]

    core_total = sum(1 for row in active_rows if row["is_core_column"] == "1")
    aux_total = sum(1 for row in active_rows if row["is_core_column"] == "0")

    top_pairs = pair_column_counts.most_common(10)
    top_sources = source_dataset_counts.most_common(10)

    concentration_rows: List[tuple[str, str, int, int, float]] = []
    rows_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in active_rows:
        rows_by_pair[row["annotation_id"]].append(row)
    for annotation_id, rows in rows_by_pair.items():
        counts = Counter(row["relation_type"] for row in rows)
        relation_type, count = counts.most_common(1)[0]
        concentration_rows.append(
            (annotation_id, relation_type, count, len(rows), count / len(rows))
        )
    concentration_rows.sort(key=lambda item: (-item[4], -item[2], item[0]))

    lines = [
        "# full_diagraph_gold_50 distribution summary",
        "",
        "## Overall",
        f"- active column 总数: {len(active_rows)}",
        f"- core / auxiliary: {core_total} / {aux_total}",
        f"- easy / medium / hard 有效 column: {difficulty_counts['easy']} / {difficulty_counts['medium']} / {difficulty_counts['hard']}",
        "",
        "## relation_type total distribution",
    ]
    for relation_type, count in relation_counts.most_common():
        lines.append(f"- {relation_type}: {count}")

    lines.extend(["", "## relation_type by batch"])
    for relation_type in sorted(relation_counts):
        lines.append(
            f"- {relation_type}: pilot10={relation_counts_by_batch[('pilot10', relation_type)]}, "
            f"easy_medium21={relation_counts_by_batch[('easy_medium21', relation_type)]}, "
            f"hard19={relation_counts_by_batch[('hard19', relation_type)]}"
        )

    lines.extend(["", "## Column count per pair (top 10)"])
    for annotation_id, count in top_pairs:
        lines.append(
            f"- {annotation_id}: columns={count}, core={core_counts_by_pair[annotation_id]}, difficulty={priority_map[annotation_id]['difficulty_level']}"
        )

    lines.extend(["", "## source / dataset column counts (top 10)"])
    for (source, dataset_name), count in top_sources:
        lines.append(f"- {source} / {dataset_name}: {count}")

    lines.extend(["", "## Samples with strongest relation-type concentration"])
    for annotation_id, relation_type, count, total, share in concentration_rows[:10]:
        lines.append(
            f"- {annotation_id}: dominant={relation_type}, {count}/{total} ({share:.2%})"
        )

    lines.extend(["", "## Core column count per pair (top 10)"])
    for annotation_id, count in core_counts_by_pair.most_common(10):
        lines.append(f"- {annotation_id}: core={count}, total={pair_column_counts[annotation_id]}")

    max_count = top_pairs[0][1] if top_pairs else 0
    max_pairs = [annotation_id for annotation_id, count in top_pairs if count == max_count]
    lines.extend(
        [
            "",
            "## Notes",
            f"- column 数最多的样本: {', '.join(max_pairs)} (各 {max_count} 行)" if max_pairs else "- column 数最多的样本: 无",
            "- relation_type 最容易集中的样本并不一定最稳定；它们常常只是单一承接机制占主导，仍需结合 pair 结构理解。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_readme() -> str:
    lines = [
        "# full_diagraph_gold_50 gold candidate README",
        "",
        "- 这不是 final gold，而是 `gold_candidate`。",
        "- 它来自三批 reviewed_v1 的合并：`pilot10 reviewed_v1` + `remaining_easy_medium21 reviewed_v1` + `remaining_hard19 reviewed_v1`。",
        "- BERT 没有参与 column 生成。",
        "- BERT / hybrid 只属于前一阶段的 pair-level shadow experiment，用于 pair 置信度、rerank 或 recall supplement，而不是直接生成 column-level diagraph。",
        "- 本目录用于后续评估跨句图谱纵栏生成质量。",
        "- `full_diagraph_gold_50_column_gold_candidate_active.csv/xlsx` 是后续评估的主要输入。",
        "- `full_diagraph_gold_50_column_reviewed_all_rows.csv/xlsx` 用于审计 delete / revise / keep 决策。",
        "- 如果后续要冻结为真正的 gold_v1，还需要再做一次 final sanity check。",
    ]
    return "\n".join(lines) + "\n"


def build_next_step_plan() -> str:
    lines = [
        "# full_diagraph_gold_50 next step plan",
        "",
        "下一步不是继续标注，而是进入合并后的质量收口与评估设计阶段：",
        "",
        "1. final sanity check",
        "- 对 active candidate 做一次全量一致性复核，重点检查 relation_type 边界、core 划分、长跨度 pragmatic_function 和 analogy。",
        "",
        "2. optional spot review",
        "- 对列数较多、relation_type 高度集中的样本做抽查式 spot review，确认合并后没有批次间标准漂移。",
        "",
        "3. column-level graph-generation evaluation design",
        "- 以 active candidate 作为 gold candidate 输入，开始设计自动跨句图谱纵栏生成的评估流程。",
        "",
        "4. 评估指标设计",
        "- column precision",
        "- column recall",
        "- relation_type accuracy",
        "- core column recall",
        "- overgeneration rate",
        "- missing-core rate",
        "- resonance-degree error",
        "",
        "5. 建议顺序",
        "- 先完成 final sanity check，再进入自动图谱生成评估方案；不要在此阶段重新训练模型或扩展 pair-level BERT。 ",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    required_inputs = [
        PILOT_PATH,
        EASY_MEDIUM_PATH,
        HARD_PATH,
        PAIR_LIST_PATH,
        PRIORITY_PATH,
        GUIDE_PATH,
    ]
    missing_inputs = [str(path) for path in required_inputs if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"Missing required inputs: {missing_inputs}")

    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    pair_map = {row["annotation_id"]: row for row in pair_rows}
    priority_rows = read_csv_dicts(PRIORITY_PATH)
    priority_map = {row["annotation_id"]: row for row in priority_rows}

    all_rows = []
    all_rows.extend(normalize_batch_rows(read_csv_dicts(PILOT_PATH), "pilot10"))
    all_rows.extend(normalize_batch_rows(read_csv_dicts(EASY_MEDIUM_PATH), "easy_medium21"))
    all_rows.extend(normalize_batch_rows(read_csv_dicts(HARD_PATH), "hard19"))

    active_rows = build_active_rows(all_rows, pair_map, priority_map)
    validation = validate(all_rows, active_rows, pair_map, priority_map)

    write_csv(ALL_ROWS_PATH, all_rows, ALL_ROWS_FIELDNAMES)
    write_csv(ACTIVE_PATH, active_rows, ACTIVE_FIELDNAMES)
    write_csv(
        RELATION_DIST_PATH,
        build_relation_distribution_rows(validation),
        ["scope", "scope_value", "relation_type", "count"],
    )
    write_csv(
        CORE_AUX_DIST_PATH,
        build_core_aux_distribution_rows(active_rows, priority_map),
        ["scope", "scope_value", "column_role", "count"],
    )

    VALIDATION_REPORT_PATH.write_text(
        build_validation_report(validation),
        encoding="utf-8",
    )
    SUMMARY_PATH.write_text(
        build_distribution_summary(active_rows, pair_map, priority_map, validation),
        encoding="utf-8",
    )
    README_PATH.write_text(build_readme(), encoding="utf-8")
    NEXT_STEP_PLAN_PATH.write_text(build_next_step_plan(), encoding="utf-8")


if __name__ == "__main__":
    main()
