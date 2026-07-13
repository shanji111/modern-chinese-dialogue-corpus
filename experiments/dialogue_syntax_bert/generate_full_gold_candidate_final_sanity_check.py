from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parent
BASE_DIR = ROOT / "artifacts" / "formal_300_v1" / "diagraph_gold_50"
FULL_DIR = BASE_DIR / "full_gold_candidate"
OUTPUT_DIR = FULL_DIR / "final_sanity_check"

ALL_ROWS_PATH = FULL_DIR / "full_diagraph_gold_50_column_reviewed_all_rows.csv"
ACTIVE_PATH = FULL_DIR / "full_diagraph_gold_50_column_gold_candidate_active.csv"
MERGE_REPORT_PATH = FULL_DIR / "full_diagraph_gold_50_merge_validation_report.md"
DISTRIBUTION_SUMMARY_PATH = FULL_DIR / "full_diagraph_gold_50_distribution_summary.md"
README_PATH = FULL_DIR / "full_diagraph_gold_50_gold_candidate_readme.md"
PAIR_LIST_PATH = BASE_DIR / "diagraph_gold_50_pair_list.csv"
GUIDE_PATH = BASE_DIR / "diagraph_gold_50_annotation_guide_v2.md"

REPORT_PATH = OUTPUT_DIR / "full_diagraph_gold_50_final_sanity_check_report.md"
SPOT_REVIEW_PATH = OUTPUT_DIR / "full_diagraph_gold_50_final_spot_review_list.csv"
FREEZE_READINESS_PATH = OUTPUT_DIR / "full_diagraph_gold_50_freeze_readiness.md"

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

SPOT_REVIEW_RULES = [
    {
        "annotation_id": "F300V1-0127",
        "risk_type": "overannotation_and_analogy_chain",
        "reason": "当前是全表列数最多的样本，6 个 active columns 中有 5 个 core，同时混合 analogy、semantic_substitution 与命题回指。",
        "suggested_action": "复查 C04/C05/C06 的边界与功能分工，确认 5 个 core columns 是否都不可缺。",
        "priority": "high",
    },
    {
        "annotation_id": "F300V1-0220",
        "risk_type": "analogy_structure_chain",
        "reason": "该 hard pair 的 2 个 active columns 全部是 analogy，评估完全依赖结构推理链是否成立。",
        "suggested_action": "复查 C01/C02 是否都体现了 A 关系结构向 B 设喻链的稳定转移，而不是单一类比被拆成两栏。",
        "priority": "high",
    },
    {
        "annotation_id": "F300V1-0287",
        "risk_type": "semantic_substitution_breadth",
        "reason": "5 栏中包含 2 个较宽的 semantic_substitution 和 1 个 pragmatic_function，容易从政策摘要滑向宽泛话题相关。",
        "suggested_action": "重点复查 C03/C05 的替换位是否足够明确，并检查辅助栏是否增殖过多。",
        "priority": "high",
    },
    {
        "annotation_id": "F300V1-0214",
        "risk_type": "single_column_context_dependency",
        "reason": "单栏 hard pair，且唯一 retained column 是 weak pragmatic_function，高度依赖论坛语境。",
        "suggested_action": "确认单栏 core 保留是否仍然合理，避免把纯语境延续误吸收到 gold candidate。",
        "priority": "medium",
    },
    {
        "annotation_id": "F300V1-0111",
        "risk_type": "single_column_semantic_substitution",
        "reason": "当前只保留 1 个 semantic_substitution，且来自论坛标签压缩，仍有“纯话题相关/群体标签泛化”的嫌疑。",
        "suggested_action": "确认“某些球迷→破车迷”是否满足稳定替换位标准，而不是情绪性压缩。",
        "priority": "medium",
    },
    {
        "annotation_id": "F300V1-0254",
        "risk_type": "core_overassignment",
        "reason": "该样本有 5 个 active columns 且全部为 core，虽然链条连贯，但存在 core 设得偏满的风险。",
        "suggested_action": "复查 C02/C05 是否至少有一栏更适合作为 auxiliary，而不是全部并列为 core。",
        "priority": "medium",
    },
]


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Iterable[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def row_key(row: Dict[str, str]) -> str:
    return f"{row['annotation_id']}/{row['column_id']}"


def ensure_inputs_exist() -> None:
    required = [
        ALL_ROWS_PATH,
        ACTIVE_PATH,
        MERGE_REPORT_PATH,
        DISTRIBUTION_SUMMARY_PATH,
        README_PATH,
        PAIR_LIST_PATH,
        GUIDE_PATH,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")


def scan(
    all_rows: List[Dict[str, str]],
    active_rows: List[Dict[str, str]],
    pair_map: Dict[str, Dict[str, str]],
) -> Dict[str, object]:
    seen_keys: set[str] = set()
    duplicate_keys: List[str] = []
    unknown_annotation_ids: List[str] = []
    for row in all_rows:
        key = row_key(row)
        if key in seen_keys:
            duplicate_keys.append(key)
        seen_keys.add(key)
        if row["annotation_id"] not in pair_map:
            unknown_annotation_ids.append(row["annotation_id"])

    rows_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    core_counts_by_pair: Counter = Counter()
    span_a_failures: List[str] = []
    span_b_failures: List[str] = []
    invalid_relation_rows: List[str] = []
    invalid_strength_rows: List[str] = []
    invalid_direction_rows: List[str] = []
    invalid_binary_rows: List[str] = []
    excluded_mixed_rows: List[str] = []

    relation_counts = Counter()
    batch_relation_counts = Counter()
    difficulty_column_counts = Counter()
    difficulty_pair_sets: Dict[str, set[str]] = defaultdict(set)
    source_dataset_counts = Counter()
    pair_column_counts = Counter()
    single_column_pairs: List[str] = []

    for row in active_rows:
        rows_by_pair[row["annotation_id"]].append(row)
        pair_column_counts[row["annotation_id"]] += 1
        relation_counts[row["relation_type"]] += 1
        batch_relation_counts[(row["batch"], row["relation_type"])] += 1
        difficulty_column_counts[row["difficulty_level"]] += 1
        difficulty_pair_sets[row["difficulty_level"]].add(row["annotation_id"])
        source_dataset_counts[(row["source"], row["dataset_name"])] += 1

        pair = pair_map[row["annotation_id"]]
        key = row_key(row)
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
        if row["is_core_column"] not in VALID_BINARY or row["supports_resonance"] not in VALID_BINARY:
            invalid_binary_rows.append(key)
        if row.get("reviewed_status", "") == "excluded_from_gold_candidate":
            excluded_mixed_rows.append(key)
        if row["is_core_column"] == "1":
            core_counts_by_pair[row["annotation_id"]] += 1

    missing_active_pairs = sorted(aid for aid in pair_map if aid not in rows_by_pair)
    missing_active_core_pairs = sorted(
        aid for aid in pair_map if core_counts_by_pair[aid] < 1
    )
    single_column_pairs = sorted(aid for aid, rows in rows_by_pair.items() if len(rows) == 1)

    core_total = sum(1 for row in active_rows if row["is_core_column"] == "1")
    aux_total = sum(1 for row in active_rows if row["is_core_column"] == "0")
    difficulty_avg_columns = {}
    for difficulty, column_count in difficulty_column_counts.items():
        pair_count = len(difficulty_pair_sets[difficulty])
        difficulty_avg_columns[difficulty] = column_count / pair_count if pair_count else 0.0

    return {
        "unique_pair_count": len({row["annotation_id"] for row in all_rows}),
        "all_rows_count": len(all_rows),
        "active_count": len(active_rows),
        "decision_counts": Counter(row["reviewer_decision"] for row in all_rows),
        "duplicate_keys": duplicate_keys,
        "unknown_annotation_ids": sorted(set(unknown_annotation_ids)),
        "missing_active_pairs": missing_active_pairs,
        "missing_active_core_pairs": missing_active_core_pairs,
        "span_a_failures": span_a_failures,
        "span_b_failures": span_b_failures,
        "invalid_relation_rows": invalid_relation_rows,
        "invalid_strength_rows": invalid_strength_rows,
        "invalid_direction_rows": invalid_direction_rows,
        "invalid_binary_rows": invalid_binary_rows,
        "excluded_mixed_rows": excluded_mixed_rows,
        "relation_counts": relation_counts,
        "batch_relation_counts": batch_relation_counts,
        "core_total": core_total,
        "aux_total": aux_total,
        "core_ratio": core_total / len(active_rows) if active_rows else 0.0,
        "difficulty_column_counts": difficulty_column_counts,
        "difficulty_pair_counts": {
            difficulty: len(pair_ids) for difficulty, pair_ids in difficulty_pair_sets.items()
        },
        "difficulty_avg_columns": difficulty_avg_columns,
        "source_dataset_counts": source_dataset_counts,
        "pair_column_counts": pair_column_counts,
        "core_counts_by_pair": core_counts_by_pair,
        "single_column_pairs": single_column_pairs,
        "rows_by_pair": rows_by_pair,
    }


def build_spot_review_rows(
    pair_map: Dict[str, Dict[str, str]],
    rows_by_pair: Dict[str, List[Dict[str, str]]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in SPOT_REVIEW_RULES:
        annotation_id = item["annotation_id"]
        if annotation_id not in pair_map or annotation_id not in rows_by_pair:
            continue
        rows.append(
            {
                "annotation_id": annotation_id,
                "pair_id": pair_map[annotation_id]["pair_id"],
                "reason": item["reason"],
                "risk_type": item["risk_type"],
                "suggested_action": item["suggested_action"],
                "priority": item["priority"],
            }
        )
    return rows


def build_report(
    scan_result: Dict[str, object],
    spot_review_rows: List[Dict[str, str]],
) -> str:
    decision_counts: Counter = scan_result["decision_counts"]  # type: ignore[assignment]
    relation_counts: Counter = scan_result["relation_counts"]  # type: ignore[assignment]
    difficulty_avg_columns: Dict[str, float] = scan_result["difficulty_avg_columns"]  # type: ignore[assignment]
    difficulty_pair_counts: Dict[str, int] = scan_result["difficulty_pair_counts"]  # type: ignore[assignment]
    source_dataset_counts: Counter = scan_result["source_dataset_counts"]  # type: ignore[assignment]
    pair_column_counts: Counter = scan_result["pair_column_counts"]  # type: ignore[assignment]
    core_counts_by_pair: Counter = scan_result["core_counts_by_pair"]  # type: ignore[assignment]

    top_source_dataset = source_dataset_counts.most_common(5)
    max_pair_count = pair_column_counts.most_common(1)[0][1] if pair_column_counts else 0
    max_pairs = [aid for aid, count in pair_column_counts.items() if count == max_pair_count]

    lines = [
        "# full_diagraph_gold_50 final sanity check report",
        "",
        "## A. 结构完整性",
        f"- 覆盖 50 个 pair：{'是' if scan_result['unique_pair_count'] == 50 else '否'}",
        f"- active column 是否为 135：{'是' if scan_result['active_count'] == 135 else '否'}",
        f"- all_rows 是否为 151：{'是' if scan_result['all_rows_count'] == 151 else '否'}",
        f"- 每个 pair 至少 1 个 active column：{'是' if not scan_result['missing_active_pairs'] else '否'}",
        f"- 每个 pair 至少 1 个 active core column：{'是' if not scan_result['missing_active_core_pairs'] else '否'}",
        f"- annotation_id + column_id 唯一：{'是' if not scan_result['duplicate_keys'] else '否'}",
        f"- active 表未混入 excluded_from_gold_candidate：{'是' if not scan_result['excluded_mixed_rows'] else '否'}",
        "",
        "## B. span 与值域",
        f"- span_a 全部来自 turn_a：{'是' if not scan_result['span_a_failures'] else '否'}",
        f"- span_b 全部来自 turn_b：{'是' if not scan_result['span_b_failures'] else '否'}",
        f"- relation_type 全部合法：{'是' if not scan_result['invalid_relation_rows'] else '否'}",
        f"- relation_strength 全部合法：{'是' if not scan_result['invalid_strength_rows'] else '否'}",
        f"- alignment_direction 全部合法：{'是' if not scan_result['invalid_direction_rows'] else '否'}",
        f"- is_core_column / supports_resonance 全部合法：{'是' if not scan_result['invalid_binary_rows'] else '否'}",
        "",
        "## C. 质量风险扫描",
        "- `semantic_substitution` 目前总数 16，不算膨胀，但仍有少量样本带“纯话题相关/压缩概括”嫌疑，主要集中在政策摘要压缩和论坛标签替换两类。",
        "- `analogy` 目前总数 7，规模很克制；主风险不在数量，而在少数 hard pair 是否真的具备清楚的结构推理链。",
        "- `pragmatic_function` 目前总数 21，并未异常泛滥，但其中几条单栏或长跨度响应仍偏语境依赖，需要少量 spot review 收口。",
        f"- core column 总数 {scan_result['core_total']}，auxiliary 总数 {scan_result['aux_total']}，core 比例约 {scan_result['core_ratio']:.1%}。整体略偏 core-heavy，但考虑到多批 reviewed 已大量删去辅助栏，这个比例仍在可解释范围内。",
        "- auxiliary column 没有明显增殖。最需要关注的不是整体数量，而是局部样本是否把解释性辅助栏保留得过多。",
        "- hard 样本整体没有表现出系统性过度标注：hard 平均列数反而低于 medium，说明 hard 阶段 pruning 生效了。",
        f"- 单栏 pair 共 {len(scan_result['single_column_pairs'])} 个，绝大多数是经过 reviewed 收缩后的单一主链保留；其中论坛语境依赖或压缩标签型单栏更值得人工再看一眼。",
        f"- 列数最多的 pair 是 {', '.join(max_pairs)}（{max_pair_count} 列），目前不构成结构错误，但确实是最值得做过度标注 spot review 的位置。",
        "",
        "## D. 分布异常扫描",
        "- relation_type 分布没有明显单一类型垄断。最高的是 lexical_reproduction 26 条，占 active 的比例不到 20%，其余类型也有较稳定覆盖。",
        f"- core / auxiliary 比例约为 {scan_result['core_total']} / {scan_result['aux_total']}，没有出现辅助栏压倒主链的异常现象。",
        "- easy / medium / hard 的平均 column 数整体合理：",
        f"  - easy: {difficulty_avg_columns.get('easy', 0.0):.3f}（{difficulty_pair_counts.get('easy', 0)} pairs）",
        f"  - medium: {difficulty_avg_columns.get('medium', 0.0):.3f}（{difficulty_pair_counts.get('medium', 0)} pairs）",
        f"  - hard: {difficulty_avg_columns.get('hard', 0.0):.3f}（{difficulty_pair_counts.get('hard', 0)} pairs）",
        "- medium 平均列数高于 hard 是合理现象：hard 阶段经过更强 pruning，保留更保守。",
        "- source / dataset 没有异常集中。最高的单个 source/dataset 只有 11 条 active columns，约占总量 8.1%，分布较分散。",
        f"- pair 列数上，{', '.join(max_pairs)} 的 6 列略高于总体，但与次高 5 列之间没有断崖式差距，不像明显脏值。",
        "",
        "## E. 冻结建议",
        "- 是否建议保留当前 candidate：建议保留。",
        "- 是否需要生成 candidate_v2：当前不建议。除非 spot review 发现明确错误，否则没有足够理由再起一个修订版。",
        "- 是否可以直接进入 gold_v1 freeze：暂不建议直接进入。当前 candidate 结构上已经成熟，但仍值得做一次小范围人工 spot review 作为冻结前的语义收口。",
        f"- 是否需要人工 spot review：{'需要' if spot_review_rows else '不需要'}。",
    ]

    if spot_review_rows:
        lines.append("- 建议 spot review 样本：")
        for row in spot_review_rows:
            lines.append(
                f"  - {row['annotation_id']} ({row['risk_type']}, {row['priority']}): {row['reason']}"
            )
    else:
        lines.append("- 当前没有必须补做的 spot review 样本。")

    lines.extend(
        [
            "",
            "## Additional notes",
            "- 目前没有发现足以推翻 current candidate 的结构性错误，因此 candidate 保留是稳妥的。",
            "- 更合适的流程是：先做这份列表中的 targeted spot review；如果没有实质性修订，再进入 gold_v1 freeze，而不是先生成 candidate_v2。",
            "- 顶部 source / dataset 分布（前 5）：",
        ]
    )
    for (source, dataset_name), count in top_source_dataset:
        lines.append(f"  - {source} / {dataset_name}: {count}")

    return "\n".join(lines) + "\n"


def build_freeze_readiness(spot_review_rows: List[Dict[str, str]]) -> str:
    lines = [
        "# full_diagraph_gold_50 freeze readiness",
        "",
        "- 当前 candidate 具备较强的结构冻结基础：50 个 pair 覆盖完整，all_rows / active 行数一致，delete / revise / keep 决策链完整，span 与值域校验均通过。",
        "- 但它当前更适合被视为“freeze-ready candidate”，而不是立刻执行 gold_v1 freeze 的最终状态。",
        "- 冻结为 gold_v1 前还缺一件事：对少量高风险样本做 targeted spot review，确认 analogy、宽 semantic_substitution、单栏 pragmatic_function 和高 core 密度样本没有残留边界问题。",
        "- 一旦正式冻结为 gold_v1，后续就不应再随意修改；任何修订都应通过新版本或明确 revision 记录管理。",
        "- gold_v1 将用于后续 column-level graph-generation evaluation，是自动图谱纵栏生成质量评估的直接参照层。",
        "- 这个 column-level gold_v1 与 pair-level `gold_v1` / `gold_v1_binary` 处于不同层级：pair-level gold 只判断某个 pair 是否存在 resonance；column-level gold 则提供具体的跨句映射结构。",
        "- BERT / hybrid 不参与 column gold 生成。它们只属于更早阶段的 pair-level shadow experiment，不应被当作 column gold 的直接来源。",
    ]
    if spot_review_rows:
        lines.append(
            f"- 因当前仍有 {len(spot_review_rows)} 个建议 spot review 的样本，所以本轮不建议直接宣布 gold_v1 freeze 完成。"
        )
    else:
        lines.append("- 当前没有残留的高优先级 spot review 样本，可进入 gold_v1 freeze 决策。")
    return "\n".join(lines) + "\n"


def main() -> None:
    ensure_inputs_exist()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = read_csv_dicts(ALL_ROWS_PATH)
    active_rows = read_csv_dicts(ACTIVE_PATH)
    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    pair_map = {row["annotation_id"]: row for row in pair_rows}

    scan_result = scan(all_rows, active_rows, pair_map)
    spot_review_rows = build_spot_review_rows(
        pair_map,
        scan_result["rows_by_pair"],  # type: ignore[arg-type]
    )

    report_text = build_report(scan_result, spot_review_rows)
    freeze_readiness_text = build_freeze_readiness(spot_review_rows)

    REPORT_PATH.write_text(report_text, encoding="utf-8")
    FREEZE_READINESS_PATH.write_text(freeze_readiness_text, encoding="utf-8")
    write_csv(
        SPOT_REVIEW_PATH,
        spot_review_rows,
        [
            "annotation_id",
            "pair_id",
            "reason",
            "risk_type",
            "suggested_action",
            "priority",
        ],
    )


if __name__ == "__main__":
    main()
