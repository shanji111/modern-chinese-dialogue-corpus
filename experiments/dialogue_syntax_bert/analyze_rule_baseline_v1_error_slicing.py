from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from evaluate_diagraph_generation_v1 import read_csv_dicts, write_csv


ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = ROOT / "artifacts" / "formal_300_v1"
GOLD_ACTIVE_PATH = (
    ARTIFACT_ROOT / "diagraph_gold_50" / "gold_v1" / "diagraph_gold_50_column_gold_v1_active.csv"
)
PAIR_LIST_PATH = ARTIFACT_ROOT / "diagraph_gold_50" / "diagraph_gold_50_pair_list.csv"
BASELINE_DIR = ARTIFACT_ROOT / "diagraph_generation_evaluation_v1" / "rule_baseline_v1"
PREDICTION_PATH = BASELINE_DIR / "rule_baseline_prediction_v1.csv"
EVALUATION_DIR = BASELINE_DIR / "evaluation_run"
ERROR_SLICING_DIR = BASELINE_DIR / "error_slicing"

SUMMARY_JSON_PATH = EVALUATION_DIR / "evaluation_summary.json"
PER_PAIR_METRICS_PATH = EVALUATION_DIR / "per_pair_metrics.csv"
UNMATCHED_GOLD_PATH = EVALUATION_DIR / "unmatched_gold_columns.csv"
OVERGENERATED_PATH = EVALUATION_DIR / "overgenerated_prediction_columns.csv"
CONFUSION_PATH = EVALUATION_DIR / "relation_type_confusion_matrix.csv"
CORE_ERROR_PATH = EVALUATION_DIR / "core_column_error_report.csv"

REPORT_PATH = ERROR_SLICING_DIR / "rule_baseline_v1_error_slicing_report.md"
UNMATCHED_BY_RELATION_PATH = ERROR_SLICING_DIR / "rule_baseline_v1_unmatched_by_relation_type.csv"
MISSING_CORE_PATH = ERROR_SLICING_DIR / "rule_baseline_v1_missing_core_columns.csv"
EMPTY_PAIR_PATH = ERROR_SLICING_DIR / "rule_baseline_v1_empty_prediction_pairs.csv"
OVERGEN_ANALYSIS_PATH = ERROR_SLICING_DIR / "rule_baseline_v1_overgeneration_analysis.csv"
NEXT_STEP_PATH = ERROR_SLICING_DIR / "rule_baseline_v1_next_step_recommendations.md"

RELATION_FOCUS_ORDER = [
    "analogy",
    "semantic_substitution",
    "pragmatic_function",
    "contrast",
    "repair",
    "coreference_or_demonstrative",
    "slot_filling",
    "short_answer",
    "syntactic_parallelism",
    "lexical_reproduction",
]


def span_overlap_ratio(a: str, b: str) -> float:
    a = a or ""
    b = b or ""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return min(len(a), len(b)) / max(len(a), len(b))
    shorter = min(len(a), len(b))
    best = 0
    for start in range(len(a)):
        for end in range(start + 1, len(a) + 1):
            piece = a[start:end]
            if piece in b and len(piece) > best:
                best = len(piece)
    return best / shorter if shorter else 0.0


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def load_inputs() -> Dict[str, object]:
    gold_rows = read_csv_dicts(GOLD_ACTIVE_PATH)
    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    prediction_rows = read_csv_dicts(PREDICTION_PATH)
    per_pair_rows = read_csv_dicts(PER_PAIR_METRICS_PATH)
    unmatched_rows = read_csv_dicts(UNMATCHED_GOLD_PATH)
    overgenerated_rows = read_csv_dicts(OVERGENERATED_PATH)
    confusion_rows = read_csv_dicts(CONFUSION_PATH)
    core_error_rows = read_csv_dicts(CORE_ERROR_PATH)
    summary = json.loads(SUMMARY_JSON_PATH.read_text(encoding="utf-8"))

    pair_map = {row["annotation_id"]: row for row in pair_rows}
    per_pair_map = {row["annotation_id"]: row for row in per_pair_rows}
    gold_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    pred_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    unmatched_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in gold_rows:
        gold_by_pair[row["annotation_id"]].append(row)
    for row in prediction_rows:
        pred_by_pair[row["annotation_id"]].append(row)
    for row in unmatched_rows:
        unmatched_by_pair[row["annotation_id"]].append(row)

    return {
        "gold_rows": gold_rows,
        "pair_rows": pair_rows,
        "prediction_rows": prediction_rows,
        "per_pair_rows": per_pair_rows,
        "unmatched_rows": unmatched_rows,
        "overgenerated_rows": overgenerated_rows,
        "confusion_rows": confusion_rows,
        "core_error_rows": core_error_rows,
        "summary": summary["summary"],
        "pair_map": pair_map,
        "per_pair_map": per_pair_map,
        "gold_by_pair": gold_by_pair,
        "pred_by_pair": pred_by_pair,
        "unmatched_by_pair": unmatched_by_pair,
    }


def dominant_relation_types(rows: Sequence[Dict[str, str]]) -> str:
    counts = Counter(row["relation_type"] for row in rows)
    ordered = [relation for relation, _count in counts.most_common()]
    return ", ".join(ordered)


def difficulty_level_for_pair(gold_rows_for_pair: Sequence[Dict[str, str]]) -> str:
    if not gold_rows_for_pair:
        return "unknown"
    values = Counter(row.get("difficulty_level", "") for row in gold_rows_for_pair if row.get("difficulty_level"))
    return values.most_common(1)[0][0] if values else "unknown"


def classify_missing_reason(
    core_error_row: Dict[str, str],
    predicted_columns_for_pair: int,
) -> str:
    relation_type = core_error_row["gold_relation_type"]
    error_type = core_error_row["error_type"]
    if error_type == "gold_core_predicted_noncore":
        return "predicted_noncore_core_demotion"
    if predicted_columns_for_pair == 0:
        return "pair_empty_prediction"
    if relation_type == "analogy":
        return "analogy_main_chain_missing"
    if relation_type == "semantic_substitution":
        return "semantic_substitution_main_chain_missing"
    if relation_type == "pragmatic_function":
        return "pragmatic_function_main_chain_missing"
    if relation_type in {"repair", "contrast"}:
        return "repair_or_contrast_main_chain_missing"
    return "span_boundary_or_trigger_miss"


def suspected_empty_reason(gold_rows_for_pair: Sequence[Dict[str, str]], pair_row: Dict[str, str]) -> str:
    relation_types = {row["relation_type"] for row in gold_rows_for_pair}
    turn_a = pair_row["turn_a"]
    turn_b = pair_row["turn_b"]
    if "analogy" in relation_types:
        return "analogy chain unsupported by intentional conservative baseline"
    if "pragmatic_function" in relation_types:
        return "implicit discourse-function mapping lacks explicit surface trigger"
    if "semantic_substitution" in relation_types:
        return "replacement relation not recoverable from high-precision surface rules"
    if "syntactic_parallelism" in relation_types:
        return "structural parallelism not implemented in v1 lexical-only matcher"
    if "slot_filling" in relation_types and ("？" in turn_a or "?" in turn_a):
        return "question present but answer pattern falls outside simple slot/short-answer templates"
    if "repair" in relation_types and turn_b.strip() in {"不是", "不对", "没有", "别", "不要"}:
        return "bare negation answer too short for current repair trigger"
    if "lexical_reproduction" in relation_types:
        return "surface overlap likely filtered by conservative lexical span pruning"
    return "no high-confidence rule fired without forcing low-quality columns"


def build_unmatched_by_relation(data: Dict[str, object]) -> List[Dict[str, object]]:
    gold_rows = data["gold_rows"]
    unmatched_rows = data["unmatched_rows"]
    gold_counts = Counter(row["relation_type"] for row in gold_rows)
    unmatched_counts = Counter(row["relation_type"] for row in unmatched_rows)
    gold_core_counts = Counter(row["relation_type"] for row in gold_rows if row["is_core_column"] == "1")
    unmatched_core_counts = Counter(
        row["relation_type"] for row in unmatched_rows if row["is_core_column"] == "1"
    )

    rows: List[Dict[str, object]] = []
    for relation_type in RELATION_FOCUS_ORDER:
        gold_count = gold_counts.get(relation_type, 0)
        unmatched_count = unmatched_counts.get(relation_type, 0)
        core_gold_count = gold_core_counts.get(relation_type, 0)
        core_unmatched_count = unmatched_core_counts.get(relation_type, 0)
        rows.append(
            {
                "relation_type": relation_type,
                "gold_count": gold_count,
                "unmatched_count": unmatched_count,
                "unmatched_rate": round(unmatched_count / gold_count, 6) if gold_count else 0.0,
                "core_gold_count": core_gold_count,
                "core_unmatched_count": core_unmatched_count,
                "core_unmatched_rate": round(core_unmatched_count / core_gold_count, 6)
                if core_gold_count
                else 0.0,
            }
        )
    return rows


def build_missing_core_rows(data: Dict[str, object]) -> List[Dict[str, object]]:
    pair_map = data["pair_map"]
    gold_by_pair = data["gold_by_pair"]
    pred_by_pair = data["pred_by_pair"]
    rows: List[Dict[str, object]] = []

    for error_row in data["core_error_rows"]:
        if error_row["error_type"] not in {"missing_gold_core", "gold_core_predicted_noncore"}:
            continue
        pair_gold = gold_by_pair[error_row["annotation_id"]]
        pair_meta = pair_map[error_row["annotation_id"]]
        predicted_columns = len(pred_by_pair.get(error_row["annotation_id"], []))
        gold_row = next(
            row
            for row in pair_gold
            if row["column_id"] == error_row["gold_column_id"]
        )
        rows.append(
            {
                "annotation_id": error_row["annotation_id"],
                "pair_id": error_row["pair_id"],
                "source": pair_meta["source"],
                "dataset_name": pair_meta["dataset_name"],
                "difficulty_level": difficulty_level_for_pair(pair_gold),
                "column_id": gold_row["column_id"],
                "span_a": gold_row["span_a"],
                "span_b": gold_row["span_b"],
                "relation_type": gold_row["relation_type"],
                "relation_strength": gold_row["relation_strength"],
                "predicted_columns_for_pair": predicted_columns,
                "suspected_missing_reason": classify_missing_reason(error_row, predicted_columns),
            }
        )
    return rows


def build_empty_prediction_rows(data: Dict[str, object]) -> List[Dict[str, object]]:
    pair_map = data["pair_map"]
    gold_by_pair = data["gold_by_pair"]
    per_pair_rows = data["per_pair_rows"]
    rows: List[Dict[str, object]] = []
    for pair_metric in per_pair_rows:
        if int(pair_metric["valid_pred_column_count"]) != 0:
            continue
        annotation_id = pair_metric["annotation_id"]
        pair_gold = gold_by_pair[annotation_id]
        pair_meta = pair_map[annotation_id]
        rows.append(
            {
                "annotation_id": annotation_id,
                "pair_id": pair_metric["pair_id"],
                "source": pair_meta["source"],
                "dataset_name": pair_meta["dataset_name"],
                "difficulty_level": difficulty_level_for_pair(pair_gold),
                "gold_active_columns": len(pair_gold),
                "gold_core_columns": sum(1 for row in pair_gold if row["is_core_column"] == "1"),
                "gold_relation_types": dominant_relation_types(pair_gold),
                "suspected_reason": suspected_empty_reason(pair_gold, pair_meta),
            }
        )
    return rows


def classify_overgeneration(row: Dict[str, str], pair_gold: Sequence[Dict[str, str]]) -> Tuple[str, str]:
    same_type_gold = [gold for gold in pair_gold if gold["relation_type"] == row["pred_relation_type"]]
    max_a = 0.0
    max_b = 0.0
    for gold in pair_gold:
        max_a = max(max_a, span_overlap_ratio(row["pred_span_a"], gold["span_a"]))
        max_b = max(max_b, span_overlap_ratio(row["pred_span_b"], gold["span_b"]))

    if same_type_gold and (max_a >= 0.5 or max_b >= 0.5):
        return (
            "acceptable_relaxed_boundary_drift",
            "tighten span boundary normalization / duplicate suppression within same pair",
        )
    if row["pred_relation_type"] == "coreference_or_demonstrative":
        return (
            "demonstrative_overreach",
            "require stronger antecedent length and restrict bare 这/那 proposition linking",
        )
    if row["pred_relation_type"] == "short_answer":
        return (
            "question_answer_template_overreach",
            "tighten question detection and require clearer B-side answer form",
        )
    if row["pred_relation_type"] == "slot_filling":
        return (
            "slot_detection_overreach",
            "require explicit wh-slot and stronger answer-like clause shape",
        )
    if row["pred_relation_type"] == "contrast":
        return (
            "contrast_marker_overreach",
            "require a more stable comparison axis before emitting contrast",
        )
    if row["pred_relation_type"] == "lexical_reproduction":
        return (
            "low_information_lexical_false_positive",
            "raise lexical span informativeness threshold and demote repeated short spans",
        )
    return ("true_false_positive", "tighten trigger rule and add a confidence filter")


def build_overgeneration_rows(data: Dict[str, object]) -> List[Dict[str, object]]:
    gold_by_pair = data["gold_by_pair"]
    rows: List[Dict[str, object]] = []
    for row in data["overgenerated_rows"]:
        error_type, suggested_fix = classify_overgeneration(row, gold_by_pair[row["annotation_id"]])
        rows.append(
            {
                "annotation_id": row["annotation_id"],
                "pair_id": row["pair_id"],
                "pred_column_id": row["pred_column_id"],
                "pred_span_a": row["pred_span_a"],
                "pred_span_b": row["pred_span_b"],
                "pred_relation_type": row["pred_relation_type"],
                "pred_confidence": row["pred_confidence"],
                "suspected_error_type": error_type,
                "suggested_fix": suggested_fix,
            }
        )
    return rows


def top_confusions(confusion_rows: Sequence[Dict[str, str]]) -> List[Tuple[str, str, int]]:
    rows: List[Tuple[str, str, int]] = []
    for row in confusion_rows:
        gold_type = row["gold_relation_type"]
        for pred_type, value in row.items():
            if pred_type in {"gold_relation_type", "row_total"}:
                continue
            count = int(value)
            if count > 0 and pred_type != gold_type:
                rows.append((gold_type, pred_type, count))
    rows.sort(key=lambda item: (-item[2], item[0], item[1]))
    return rows


def write_report(
    data: Dict[str, object],
    unmatched_by_relation_rows: Sequence[Dict[str, object]],
    missing_core_rows: Sequence[Dict[str, object]],
    empty_prediction_rows: Sequence[Dict[str, object]],
    overgeneration_rows: Sequence[Dict[str, object]],
) -> None:
    summary = data["summary"]
    core_reason_counts = Counter(row["suspected_missing_reason"] for row in missing_core_rows)
    confusion_top = top_confusions(data["confusion_rows"])[:8]

    unmatched_table_rows = [
        (
            row["relation_type"],
            row["gold_count"],
            row["unmatched_count"],
            row["unmatched_rate"],
            row["core_unmatched_count"],
            row["core_unmatched_rate"],
        )
        for row in unmatched_by_relation_rows
    ]

    empty_preview_rows = [
        (
            row["annotation_id"],
            row["dataset_name"],
            row["difficulty_level"],
            row["gold_relation_types"],
            row["suspected_reason"],
        )
        for row in empty_prediction_rows[:10]
    ]
    overgen_preview_rows = [
        (
            row["annotation_id"],
            row["pred_relation_type"],
            row["pred_span_a"],
            row["pred_span_b"],
            row["suspected_error_type"],
        )
        for row in overgeneration_rows[:10]
    ]

    lines = [
        "# rule_baseline_v1 error slicing report",
        "",
        "## A. 总体诊断",
        "",
        f"- baseline 明显是高 precision / 低 recall 倾向：exact precision = {summary['exact_column_precision']}，但 exact recall = {summary['exact_column_recall']}；relaxed precision 仍有 {summary['relaxed_column_precision']}，说明保守触发总体没有失控。",
        f"- exact 与 relaxed 的差距很大（exact match {summary['exact_match_count']}，relaxed match {summary['relaxed_match_count']}），核心含义是：不少预测已经碰到正确结构附近，但 span 粒度、命题回指边界、问答子句切分还不够稳。",
        f"- core recall 偏低（{summary['core_column_recall']}），主要不是因为预测全错，而是因为 missing gold core 58 条、gold core predicted non-core 13 条；也就是“主链没抓到”和“抓到了但没升 core”同时存在。",
        f"- overgeneration rate = {summary['overgeneration_rate']}，在保守 baseline 里属于中等可接受但需要收紧的水平：还没到失控，但 demonstrative / short-answer / 低信息 lexical 明显在拉噪声。",
        "",
        "## B. unmatched gold 分析",
        "",
        markdown_table(
            [
                "relation_type",
                "gold",
                "unmatched",
                "unmatched_rate",
                "core_unmatched",
                "core_unmatched_rate",
            ],
            unmatched_table_rows,
        ),
        "",
        "- `analogy` 高 unmatched 是预期内结果：v1 baseline 故意不自动生成 analogy。",
        "- `pragmatic_function`、`semantic_substitution`、`contrast` 的 unmatched 高，说明这些类型对纯 surface rule 很不友好。",
        "- `lexical_reproduction` unmatched rate 最低，说明 lexical rule 是当前 baseline 最稳的部分。",
        "",
        "## C. missing core 分析",
        "",
        f"- missing core 总量：{len(missing_core_rows)}",
        f"- 其中 `pair_empty_prediction`：{core_reason_counts.get('pair_empty_prediction', 0)}",
        f"- 其中 `analogy_main_chain_missing`：{core_reason_counts.get('analogy_main_chain_missing', 0)}",
        f"- 其中 `semantic_substitution_main_chain_missing`：{core_reason_counts.get('semantic_substitution_main_chain_missing', 0)}",
        f"- 其中 `pragmatic_function_main_chain_missing`：{core_reason_counts.get('pragmatic_function_main_chain_missing', 0)}",
        f"- 其中 `repair_or_contrast_main_chain_missing`：{core_reason_counts.get('repair_or_contrast_main_chain_missing', 0)}",
        f"- 其中 `span_boundary_or_trigger_miss`：{core_reason_counts.get('span_boundary_or_trigger_miss', 0)}",
        f"- 其中 `predicted_noncore_core_demotion`：{core_reason_counts.get('predicted_noncore_core_demotion', 0)}",
        "",
        "- 风险上最值得盯的是 analogy / pragmatic_function / semantic_substitution 主链缺失，因为这些不是简单 span 边界问题，而是 generator 能力边界。",
        "- `predicted_noncore_core_demotion` 说明当前 baseline 已经碰到对的列，但 core promotion 规则过于保守；这是 v1.1 最容易修的一类问题。",
        "",
        "## D. empty prediction pair 分析",
        "",
        f"- empty prediction pair 数量：{len(empty_prediction_rows)}",
        "",
        markdown_table(
            ["annotation_id", "dataset_name", "difficulty", "gold_relation_types", "suspected_reason"],
            empty_preview_rows,
        ),
        "",
        "- 这些空 pair 里，常见原因是：pragmatic_function 没有显式 surface cue、analogy 完全未覆盖、以及古汉语/论坛语境下的 slot/repair 结构超出简单模板。",
        "",
        "## E. overgenerated prediction 分析",
        "",
        f"- overgenerated columns 数量：{len(overgeneration_rows)}",
        "",
        markdown_table(
            ["annotation_id", "pred_relation_type", "pred_span_a", "pred_span_b", "suspected_error_type"],
            overgen_preview_rows,
        ),
        "",
        "- 当前 overgeneration 里最典型的是 bare `这/那` proposition recall 过度链接、question template 误判、以及低信息 lexical span。",
        "- 其中一部分可视为 relaxed boundary drift 或 duplicate candidate，但另一部分已经是真误报，尤其是 low-confidence demonstrative 和过宽 short_answer。",
        "",
        "## F. relation_type confusion 分析",
        "",
        markdown_table(
            ["gold_relation_type", "pred_relation_type", "count"],
            confusion_top,
        ),
        "",
        "- relaxed relation accuracy 从 exact 的高位下降到 0.591837，核心原因不是 lexical 本身崩掉，而是：一旦进入 relaxed match，slot_filling / short_answer / coreference / pragmatic_function 的边界开始互相挤压。",
        "- 可通过规则修复的混淆：`slot_filling <-> short_answer`、`repair <-> contrast`、`syntactic_parallelism -> lexical_reproduction` 的一部分。",
        "- 更适合 BERT-assisted classifier 的混淆：`pragmatic_function` 与 `short_answer/coreference`，以及 `semantic_substitution` 与 `contrast/repair/lexical`。",
        "",
        "## G. 下一步建议",
        "",
        "1. rule baseline v1.1 应先修：span 边界规范化、lexical pruning、slot_filling/short_answer 切分、repair/contrast 触发、core promotion。",
        "2. 不建议继续用纯规则硬攻：analogy、真正的 semantic_substitution、pragmatic_function、论坛语境标签压缩、长论证链回指。",
        "3. BERT-assisted 最合适的第一步不是端到端生成，而是 candidate reranker / false-positive filter；relation_type classifier 可作为第二步。",
        "",
    ]

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_next_step_recommendations() -> None:
    lines = [
        "# rule_baseline_v1 next step recommendations",
        "",
        "## Decision",
        "",
        "- 是否应该先做 rule_baseline_v1_1：应该。",
        "- 是否现在就直接进入 BERT-assisted 作为主线替代：不建议直接跳过 v1.1。",
        "- 是否应该在 v1.1 之后立刻接 BERT-assisted prototype：建议。",
        "",
        "## rule_baseline_v1_1 只修 3-5 个点",
        "",
        "1. span 边界规范化：减少 exact / relaxed 差距，尤其是问答子句与命题回指片段。",
        "2. lexical reproduction pruning：提高短 span 的信息量阈值，压掉低信息重复项。",
        "3. slot_filling / short_answer 切分：收紧疑问句识别，避免把一般追问或引语开头误当短回答。",
        "4. repair / contrast 触发：补 bare negation 和更稳定的对照轴，减少误判与漏判。",
        "5. core promotion 规则：对于已命中的高置信列，避免过度保守地停留在 non-core。",
        "",
        "## 不建议继续纯规则硬修的部分",
        "",
        "- analogy：需要结构推理链，不适合用当前 50-pair gold 硬堆 surface rule。",
        "- 真正的 semantic_substitution：需要判断可解释替换位，纯规则容易退化成 topic-relatedness。",
        "- pragmatic_function：需要读出确认请求、解释性回应、追问转写等语用功能。",
        "- 论坛语境标签压缩：例如群体标签、站队昵称、语境化绰号，纯规则很容易误触发。",
        "- 长跨度论证链：特别是命题级 demonstrative / discourse recall。",
        "",
        "## BERT-assisted 第一优先级",
        "",
        "- 第一优先级：candidate reranker / false-positive filter。",
        "- 第二优先级：relation_type classifier。",
        "- 第三优先级：missing-core detector。",
        "- 暂不建议先做 recall supplement；当前 50-pair gold 太小，直接补召回容易把噪声一并放大。",
        "",
        "## 为什么不能靠当前 50-pair gold 训练端到端模型",
        "",
        "- 样本太小，无法稳定学习 column 数、span 边界、relation_type、core flag 的联合分布。",
        "- relation_type 严重长尾，analogy / short_answer / syntactic_parallelism 等样本过少。",
        "- 一个 pair 对多个 column 的结构是多对多映射，不适合直接用极小数据端到端硬学。",
        "- 当前最现实的路径仍然是：规则候选生成 + BERT-assisted rerank/filter/classify。",
        "",
    ]
    NEXT_STEP_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ERROR_SLICING_DIR.mkdir(parents=True, exist_ok=True)
    data = load_inputs()

    unmatched_by_relation_rows = build_unmatched_by_relation(data)
    missing_core_rows = build_missing_core_rows(data)
    empty_prediction_rows = build_empty_prediction_rows(data)
    overgeneration_rows = build_overgeneration_rows(data)

    write_csv(
        UNMATCHED_BY_RELATION_PATH,
        unmatched_by_relation_rows,
        [
            "relation_type",
            "gold_count",
            "unmatched_count",
            "unmatched_rate",
            "core_gold_count",
            "core_unmatched_count",
            "core_unmatched_rate",
        ],
    )
    write_csv(
        MISSING_CORE_PATH,
        missing_core_rows,
        [
            "annotation_id",
            "pair_id",
            "source",
            "dataset_name",
            "difficulty_level",
            "column_id",
            "span_a",
            "span_b",
            "relation_type",
            "relation_strength",
            "predicted_columns_for_pair",
            "suspected_missing_reason",
        ],
    )
    write_csv(
        EMPTY_PAIR_PATH,
        empty_prediction_rows,
        [
            "annotation_id",
            "pair_id",
            "source",
            "dataset_name",
            "difficulty_level",
            "gold_active_columns",
            "gold_core_columns",
            "gold_relation_types",
            "suspected_reason",
        ],
    )
    write_csv(
        OVERGEN_ANALYSIS_PATH,
        overgeneration_rows,
        [
            "annotation_id",
            "pair_id",
            "pred_column_id",
            "pred_span_a",
            "pred_span_b",
            "pred_relation_type",
            "pred_confidence",
            "suspected_error_type",
            "suggested_fix",
        ],
    )

    write_report(
        data=data,
        unmatched_by_relation_rows=unmatched_by_relation_rows,
        missing_core_rows=missing_core_rows,
        empty_prediction_rows=empty_prediction_rows,
        overgeneration_rows=overgeneration_rows,
    )
    write_next_step_recommendations()

    print(
        json.dumps(
            {
                "output_dir": str(ERROR_SLICING_DIR),
                "missing_core_count": len(missing_core_rows),
                "empty_prediction_pairs": len(empty_prediction_rows),
                "overgenerated_predictions": len(overgeneration_rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
