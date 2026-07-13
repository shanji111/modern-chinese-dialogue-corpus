from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from evaluate_diagraph_generation_v1 import (
    DEFAULT_GOLD_ACTIVE,
    PAIR_LIST_PATH,
    PRED_REQUIRED_FIELDS,
    build_pair_map,
    compute_exact_matches,
    compute_relaxed_matches,
    evaluate_predictions,
    pred_key,
    read_csv_dicts,
    validate_gold_rows,
    validate_prediction_rows,
    write_csv,
)


ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = ROOT / "artifacts" / "formal_300_v1"
EVAL_ROOT = ARTIFACT_ROOT / "diagraph_generation_evaluation_v1"

CANDIDATE_POOL_PATH = EVAL_ROOT / "bert_candidate_pool_v0" / "bert_candidate_pool_v0.csv"
OUTPUT_DIR = EVAL_ROOT / "bert_assisted_prototype_v0"
SCORING_INPUT_PATH = OUTPUT_DIR / "bert_candidate_scoring_input_v0.csv"
LABELS_PATH = OUTPUT_DIR / "bert_candidate_offline_eval_labels_v0.csv"
SHADOW_SCORES_PATH = OUTPUT_DIR / "bert_candidate_shadow_scores_v0.csv"
FILTERED_DIR = OUTPUT_DIR / "filtered_predictions"
SIM_SUMMARY_PATH = OUTPUT_DIR / "bert_assisted_filtering_simulation_summary.csv"
REPORT_PATH = OUTPUT_DIR / "bert_assisted_prototype_v0_report.md"
ERROR_NOTES_PATH = OUTPUT_DIR / "bert_assisted_prototype_v0_error_notes.md"
MANIFEST_PATH = OUTPUT_DIR / "bert_assisted_prototype_v0_manifest.md"
SIM_REPORT_PATH = OUTPUT_DIR / "bert_assisted_filtering_simulation_report.md"
STATUS_JSON_PATH = OUTPUT_DIR / "bert_assisted_prototype_v0_status.json"

LOCAL_MACBERT_PATH = Path(r"D:\hf_models\hfl_chinese_macbert_base")
RELAXED_THRESHOLD = 0.5
MACBERT_MAX_LENGTH = 256
MACBERT_BATCH_SIZE = 16
SCORE_METHOD_NAME = "macbert_frozen_mean_pool_cosine_v0"

SCORING_INPUT_FIELDS = [
    "candidate_id",
    "annotation_id",
    "pair_id",
    "turn_a",
    "turn_b",
    "pred_span_a",
    "pred_span_b",
    "pred_relation_type",
    "pred_relation_strength",
    "pred_alignment_direction",
    "pred_is_core_column",
    "pred_supports_resonance",
    "pred_confidence",
    "candidate_tier",
    "from_rule_v1",
    "from_rule_v1_1",
    "source_count",
    "suggested_bert_task",
    "bert_input_text",
]
LABEL_FIELDS = [
    "candidate_id",
    "annotation_id",
    "pair_id",
    "pred_column_id",
    "pred_span_a",
    "pred_span_b",
    "pred_relation_type",
    "gold_exact_match",
    "gold_relaxed_match",
    "gold_matched_column_id",
    "gold_relation_type",
    "relation_type_correct_exact_or_relaxed",
    "gold_is_core_column",
    "candidate_should_keep_relaxed",
]
SHADOW_SCORE_FIELDS = [
    "candidate_id",
    "annotation_id",
    "pair_id",
    "pred_span_a",
    "pred_span_b",
    "pred_relation_type",
    "candidate_tier",
    "pair_context_similarity",
    "span_pair_similarity",
    "candidate_context_fit_score",
    "bert_score_method",
    "bert_model_path",
    "bert_loaded",
    "scoring_notes",
]
SIM_SUMMARY_FIELDS = [
    "strategy_name",
    "candidate_count",
    "covered_pairs",
    "invalid_prediction_count",
    "exact_column_precision",
    "exact_column_recall",
    "exact_column_f1",
    "relaxed_column_precision",
    "relaxed_column_recall",
    "relaxed_column_f1",
    "relation_type_accuracy_on_exact_matches",
    "relation_type_accuracy_on_relaxed_matches",
    "core_column_recall",
    "missing_core_rate",
    "overgeneration_rate",
    "compared_to_candidate_pool_v0",
]

RISKY_RELATION_TYPES = {
    "coreference_or_demonstrative",
    "slot_filling",
    "contrast",
    "repair",
    "short_answer",
}


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_cosine(cosine: float) -> float:
    return clamp01((cosine + 1.0) / 2.0)


def format_score(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}"


def quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if not norm_a or not norm_b:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def build_scoring_input_rows(
    candidate_rows: List[Dict[str, str]],
    pair_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for candidate in candidate_rows:
        pair = pair_map[candidate["annotation_id"]]
        bert_input_text = (
            f"[TURN_A] {pair['turn_a']} "
            f"[TURN_B] {pair['turn_b']} "
            f"[SPAN_A] {candidate['pred_span_a']} "
            f"[SPAN_B] {candidate['pred_span_b']} "
            f"[RELATION] {candidate['pred_relation_type']}"
        )
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "annotation_id": candidate["annotation_id"],
                "pair_id": candidate["pair_id"],
                "turn_a": pair["turn_a"],
                "turn_b": pair["turn_b"],
                "pred_span_a": candidate["pred_span_a"],
                "pred_span_b": candidate["pred_span_b"],
                "pred_relation_type": candidate["pred_relation_type"],
                "pred_relation_strength": candidate["pred_relation_strength"],
                "pred_alignment_direction": candidate["pred_alignment_direction"],
                "pred_is_core_column": candidate["pred_is_core_column"],
                "pred_supports_resonance": candidate["pred_supports_resonance"],
                "pred_confidence": candidate["pred_confidence"],
                "candidate_tier": candidate["candidate_tier"],
                "from_rule_v1": candidate["from_rule_v1"],
                "from_rule_v1_1": candidate["from_rule_v1_1"],
                "source_count": candidate["source_count"],
                "suggested_bert_task": candidate["suggested_bert_task"],
                "bert_input_text": bert_input_text,
            }
        )
    return rows


def build_offline_eval_labels(
    candidate_rows: List[Dict[str, str]],
    gold_rows: List[Dict[str, str]],
    pair_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    gold_annotation_ids = {row["annotation_id"] for row in gold_rows}
    valid_rows, invalid_rows = validate_prediction_rows(
        candidate_rows,
        gold_annotation_ids=gold_annotation_ids,
        pair_map=pair_map,
    )
    if invalid_rows:
        raise ValueError(f"candidate pool unexpectedly produced invalid rows for label build: {len(invalid_rows)}")

    exact_matches, _, _ = compute_exact_matches(gold_rows, valid_rows)
    relaxed_matches = compute_relaxed_matches(gold_rows, valid_rows, RELAXED_THRESHOLD)

    exact_by_pred = {f"{match.annotation_id}/{match.pred_column_id}": match for match in exact_matches}
    relaxed_by_pred = {f"{match.annotation_id}/{match.pred_column_id}": match for match in relaxed_matches}

    labels: List[Dict[str, str]] = []
    for row in valid_rows:
        key = pred_key(row)
        exact_match = exact_by_pred.get(key)
        relaxed_match = relaxed_by_pred.get(key)
        chosen_match = exact_match or relaxed_match
        labels.append(
            {
                "candidate_id": row["candidate_id"],
                "annotation_id": row["annotation_id"],
                "pair_id": row["pair_id"],
                "pred_column_id": row["pred_column_id"],
                "pred_span_a": row["pred_span_a"],
                "pred_span_b": row["pred_span_b"],
                "pred_relation_type": row["pred_relation_type"],
                "gold_exact_match": "1" if exact_match else "0",
                "gold_relaxed_match": "1" if relaxed_match else "0",
                "gold_matched_column_id": chosen_match.gold_column_id if chosen_match else "",
                "gold_relation_type": chosen_match.gold_relation_type if chosen_match else "",
                "relation_type_correct_exact_or_relaxed": (
                    "1"
                    if chosen_match and chosen_match.gold_relation_type == row["pred_relation_type"]
                    else "0"
                ),
                "gold_is_core_column": chosen_match.gold_is_core_column if chosen_match else "",
                "candidate_should_keep_relaxed": "1" if relaxed_match else "0",
            }
        )
    return labels


def load_macbert_or_reason() -> Tuple[object | None, object | None, str]:
    try:
        import torch  # type: ignore
        from transformers import AutoModel, AutoTokenizer  # type: ignore

        torch.set_grad_enabled(False)
        if hasattr(torch, "set_num_threads"):
            try:
                torch.set_num_threads(1)
            except RuntimeError:
                pass

        tokenizer = AutoTokenizer.from_pretrained(str(LOCAL_MACBERT_PATH), local_files_only=True)
        model = AutoModel.from_pretrained(str(LOCAL_MACBERT_PATH), local_files_only=True)
        model.eval()
        return tokenizer, model, ""
    except Exception as exc:  # pragma: no cover - fallback path
        return None, None, f"{type(exc).__name__}: {exc}"


def mean_pool(last_hidden_state, attention_mask):
    import torch  # type: ignore

    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def encode_texts(
    texts: Sequence[str],
    tokenizer,
    model,
    batch_size: int = MACBERT_BATCH_SIZE,
    max_length: int = MACBERT_MAX_LENGTH,
) -> Dict[str, List[float]]:
    import torch  # type: ignore

    unique_texts = list(dict.fromkeys(texts))
    embeddings: Dict[str, List[float]] = {}
    for start in range(0, len(unique_texts), batch_size):
        batch = unique_texts[start : start + batch_size]
        encoded = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = model(**encoded)
            pooled = mean_pool(outputs.last_hidden_state, encoded["attention_mask"])
        for text, vector in zip(batch, pooled.tolist()):
            embeddings[text] = [float(item) for item in vector]
    return embeddings


def build_shadow_scores(
    scoring_rows: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], bool, str, Dict[str, float]]:
    tokenizer, model, failure_reason = load_macbert_or_reason()
    if tokenizer is None or model is None:
        rows = [
            {
                "candidate_id": row["candidate_id"],
                "annotation_id": row["annotation_id"],
                "pair_id": row["pair_id"],
                "pred_span_a": row["pred_span_a"],
                "pred_span_b": row["pred_span_b"],
                "pred_relation_type": row["pred_relation_type"],
                "candidate_tier": row["candidate_tier"],
                "pair_context_similarity": "",
                "span_pair_similarity": "",
                "candidate_context_fit_score": "",
                "bert_score_method": SCORE_METHOD_NAME,
                "bert_model_path": str(LOCAL_MACBERT_PATH),
                "bert_loaded": "0",
                "scoring_notes": f"shadow scoring not executed; {failure_reason}",
            }
            for row in scoring_rows
        ]
        return rows, False, failure_reason, {}

    pair_context_texts = [f"[TURN_A] {row['turn_a']} [TURN_B] {row['turn_b']}" for row in scoring_rows]
    relation_context_texts = [
        f"[SPAN_A] {row['pred_span_a']} [SPAN_B] {row['pred_span_b']} [RELATION] {row['pred_relation_type']}"
        for row in scoring_rows
    ]
    all_texts = []
    for row in scoring_rows:
        all_texts.extend(
            [
                row["turn_a"],
                row["turn_b"],
                row["pred_span_a"],
                row["pred_span_b"],
                f"[TURN_A] {row['turn_a']} [TURN_B] {row['turn_b']}",
                f"[SPAN_A] {row['pred_span_a']} [SPAN_B] {row['pred_span_b']} [RELATION] {row['pred_relation_type']}",
            ]
        )
    embeddings = encode_texts(all_texts, tokenizer=tokenizer, model=model)

    rows: List[Dict[str, str]] = []
    fit_scores: List[float] = []
    span_scores: List[float] = []
    pair_scores: List[float] = []

    for row in scoring_rows:
        turn_a_vec = embeddings[row["turn_a"]]
        turn_b_vec = embeddings[row["turn_b"]]
        span_a_vec = embeddings[row["pred_span_a"]]
        span_b_vec = embeddings[row["pred_span_b"]]
        pair_context_vec = embeddings[f"[TURN_A] {row['turn_a']} [TURN_B] {row['turn_b']}"]
        relation_context_vec = embeddings[
            f"[SPAN_A] {row['pred_span_a']} [SPAN_B] {row['pred_span_b']} [RELATION] {row['pred_relation_type']}"
        ]

        pair_context_similarity = cosine_similarity(turn_a_vec, turn_b_vec)
        span_pair_similarity = cosine_similarity(span_a_vec, span_b_vec)
        pair_relation_similarity = cosine_similarity(pair_context_vec, relation_context_vec)
        candidate_context_fit_score = 0.5 * normalize_cosine(span_pair_similarity) + 0.5 * normalize_cosine(
            pair_relation_similarity
        )

        pair_scores.append(pair_context_similarity)
        span_scores.append(span_pair_similarity)
        fit_scores.append(candidate_context_fit_score)

        rows.append(
            {
                "candidate_id": row["candidate_id"],
                "annotation_id": row["annotation_id"],
                "pair_id": row["pair_id"],
                "pred_span_a": row["pred_span_a"],
                "pred_span_b": row["pred_span_b"],
                "pred_relation_type": row["pred_relation_type"],
                "candidate_tier": row["candidate_tier"],
                "pair_context_similarity": format_score(pair_context_similarity),
                "span_pair_similarity": format_score(span_pair_similarity),
                "candidate_context_fit_score": format_score(candidate_context_fit_score),
                "bert_score_method": SCORE_METHOD_NAME,
                "bert_model_path": str(LOCAL_MACBERT_PATH),
                "bert_loaded": "1",
                "scoring_notes": "shadow_only_frozen_macbert; local_files_only; mean_pooling; score_is_not_probability",
            }
        )

    stats = {
        "pair_context_similarity_mean": statistics.mean(pair_scores) if pair_scores else 0.0,
        "span_pair_similarity_mean": statistics.mean(span_scores) if span_scores else 0.0,
        "candidate_context_fit_score_mean": statistics.mean(fit_scores) if fit_scores else 0.0,
    }
    return rows, True, "", stats


def merge_candidate_views(
    candidate_rows: List[Dict[str, str]],
    scoring_rows: List[Dict[str, str]],
    label_rows: List[Dict[str, str]],
    shadow_rows: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    scoring_by_id = {row["candidate_id"]: row for row in scoring_rows}
    labels_by_id = {row["candidate_id"]: row for row in label_rows}
    shadow_by_id = {row["candidate_id"]: row for row in shadow_rows}
    merged: List[Dict[str, str]] = []
    for candidate in candidate_rows:
        row = dict(candidate)
        row.update(scoring_by_id.get(candidate["candidate_id"], {}))
        row.update(labels_by_id.get(candidate["candidate_id"], {}))
        row.update(shadow_by_id.get(candidate["candidate_id"], {}))
        merged.append(row)
    return merged


def rank_within_pair(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["annotation_id"]].append(row)
    for annotation_id, group in grouped.items():
        group.sort(
            key=lambda item: (
                safe_float(item.get("candidate_context_fit_score"), -1.0),
                safe_float(item.get("span_pair_similarity"), -1.0),
                item["candidate_tier"] == "high_precision_rule",
                item["pred_is_core_column"] == "1",
            ),
            reverse=True,
        )
        for index, row in enumerate(group, start=1):
            row["_pair_rank"] = str(index)
    return grouped


def keep_top_candidate_per_pair(selected: List[Dict[str, str]], all_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    selected_ids = {row["candidate_id"] for row in selected}
    grouped = rank_within_pair([dict(row) for row in all_rows])
    for annotation_id, group in grouped.items():
        if not any(row["candidate_id"] in selected_ids for row in group):
            selected.append(next(row for row in all_rows if row["candidate_id"] == group[0]["candidate_id"]))
            selected_ids.add(group[0]["candidate_id"])
    return sorted(selected, key=lambda row: row["candidate_id"])


def build_filtered_prediction_rows(rows: List[Dict[str, str]], strategy_name: str) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    for row in rows:
        output.append(
            {
                "annotation_id": row["annotation_id"],
                "pair_id": row["pair_id"],
                "pred_column_id": row["pred_column_id"],
                "pred_span_a": row["pred_span_a"],
                "pred_span_b": row["pred_span_b"],
                "pred_relation_type": row["pred_relation_type"],
                "pred_relation_strength": row["pred_relation_strength"],
                "pred_alignment_direction": row["pred_alignment_direction"],
                "pred_is_core_column": row["pred_is_core_column"],
                "pred_supports_resonance": row["pred_supports_resonance"],
                "pred_confidence": row["pred_confidence"],
                "generator_name": "bert_assisted_prototype",
                "generator_version": strategy_name,
                "notes": f"source=bert_candidate_pool_v0; strategy={strategy_name}; candidate_id={row['candidate_id']}",
            }
        )
    return output


def select_strategy_rows(strategy_name: str, merged_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    rows = [dict(row) for row in merged_rows]
    pair_groups = rank_within_pair(rows)
    span_scores = [safe_float(row.get("span_pair_similarity")) for row in rows if row.get("span_pair_similarity") != ""]
    fit_scores = [safe_float(row.get("candidate_context_fit_score")) for row in rows if row.get("candidate_context_fit_score") != ""]
    span_q60 = quantile(span_scores, 0.60)
    span_q45 = quantile(span_scores, 0.45)
    fit_q50 = quantile(fit_scores, 0.50)
    fit_q55 = quantile(fit_scores, 0.55)

    if strategy_name == "rule_pool_no_filter":
        return sorted(rows, key=lambda row: row["candidate_id"])

    selected: List[Dict[str, str]] = []
    if strategy_name == "bert_span_similarity_top":
        for row in rows:
            pair_rank = int(row["_pair_rank"])
            span_sim = safe_float(row.get("span_pair_similarity"))
            if pair_rank == 1 or span_sim >= span_q60:
                selected.append(row)
        return keep_top_candidate_per_pair(selected, rows)

    if strategy_name == "tier_aware_filter":
        for row in rows:
            pair_rank = int(row["_pair_rank"])
            fit_score = safe_float(row.get("candidate_context_fit_score"))
            span_sim = safe_float(row.get("span_pair_similarity"))
            tier = row["candidate_tier"]
            keep = False
            if tier == "high_precision_rule":
                keep = True
            elif tier == "precision_ablation_only":
                keep = fit_score >= fit_q50
            elif tier == "recall_rule_only":
                keep = fit_score >= fit_q55 and span_sim >= span_q45
            if pair_rank == 1 and fit_score >= fit_q50:
                keep = True
            if keep:
                selected.append(row)
        return keep_top_candidate_per_pair(selected, rows)

    if strategy_name == "relation_type_sanity_filter":
        for row in rows:
            pair_rank = int(row["_pair_rank"])
            fit_score = safe_float(row.get("candidate_context_fit_score"))
            span_sim = safe_float(row.get("span_pair_similarity"))
            relation_type = row["pred_relation_type"]
            tier = row["candidate_tier"]
            keep = False
            if tier == "high_precision_rule":
                keep = True
            elif relation_type in RISKY_RELATION_TYPES:
                keep = fit_score >= fit_q50 and span_sim >= span_q45
            elif relation_type == "lexical_reproduction":
                keep = span_sim >= span_q60
            else:
                keep = fit_score >= fit_q50
            if pair_rank == 1 and fit_score >= fit_q50:
                keep = True
            if keep:
                selected.append(row)
        return keep_top_candidate_per_pair(selected, rows)

    raise ValueError(f"Unsupported strategy: {strategy_name}")


def evaluate_filtered_strategies(merged_rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], Dict[str, Dict[str, object]]]:
    FILTERED_DIR.mkdir(parents=True, exist_ok=True)
    strategy_names = [
        "rule_pool_no_filter",
        "bert_span_similarity_top",
        "tier_aware_filter",
        "relation_type_sanity_filter",
    ]
    summaries: List[Dict[str, str]] = []
    raw_results: Dict[str, Dict[str, object]] = {}
    no_filter_summary: Dict[str, object] | None = None

    for strategy_name in strategy_names:
        selected_rows = select_strategy_rows(strategy_name, merged_rows)
        prediction_rows = build_filtered_prediction_rows(selected_rows, strategy_name)
        prediction_path = FILTERED_DIR / f"{strategy_name}.csv"
        evaluation_dir = FILTERED_DIR / f"{strategy_name}_evaluation"
        write_csv(prediction_path, prediction_rows, PRED_REQUIRED_FIELDS)
        result = evaluate_predictions(
            gold_path=DEFAULT_GOLD_ACTIVE,
            pair_list_path=PAIR_LIST_PATH,
            prediction_path=prediction_path,
            output_dir=evaluation_dir,
            relaxed_threshold=RELAXED_THRESHOLD,
            run_name=strategy_name,
        )
        summary = result["summary"]
        raw_results[strategy_name] = {
            "selected_rows": selected_rows,
            "prediction_path": prediction_path,
            "evaluation_dir": evaluation_dir,
            "summary": summary,
        }
        if strategy_name == "rule_pool_no_filter":
            no_filter_summary = summary

    assert no_filter_summary is not None
    for strategy_name in strategy_names:
        summary = raw_results[strategy_name]["summary"]
        compared = (
            f"delta_relaxed_f1={summary['relaxed_column_f1'] - no_filter_summary['relaxed_column_f1']:.6f}; "
            f"delta_relaxed_precision={summary['relaxed_column_precision'] - no_filter_summary['relaxed_column_precision']:.6f}; "
            f"delta_relaxed_recall={summary['relaxed_column_recall'] - no_filter_summary['relaxed_column_recall']:.6f}; "
            f"delta_overgeneration={summary['overgeneration_rate'] - no_filter_summary['overgeneration_rate']:.6f}"
        )
        summaries.append(
            {
                "strategy_name": strategy_name,
                "candidate_count": str(len(raw_results[strategy_name]["selected_rows"])),
                "covered_pairs": str(
                    len({row["annotation_id"] for row in raw_results[strategy_name]["selected_rows"]})
                ),
                "invalid_prediction_count": str(summary["invalid_prediction_count"]),
                "exact_column_precision": str(summary["exact_column_precision"]),
                "exact_column_recall": str(summary["exact_column_recall"]),
                "exact_column_f1": str(summary["exact_column_f1"]),
                "relaxed_column_precision": str(summary["relaxed_column_precision"]),
                "relaxed_column_recall": str(summary["relaxed_column_recall"]),
                "relaxed_column_f1": str(summary["relaxed_column_f1"]),
                "relation_type_accuracy_on_exact_matches": str(
                    summary["relation_type_accuracy_on_exact_matches"]
                ),
                "relation_type_accuracy_on_relaxed_matches": str(
                    summary["relation_type_accuracy_on_relaxed_matches"]
                ),
                "core_column_recall": str(summary["core_column_recall"]),
                "missing_core_rate": str(summary["missing_core_rate"]),
                "overgeneration_rate": str(summary["overgeneration_rate"]),
                "compared_to_candidate_pool_v0": compared,
            }
        )
    return summaries, raw_results


def choose_best_strategy(sim_rows: List[Dict[str, str]]) -> str:
    def sort_key(row: Dict[str, str]) -> Tuple[float, float, float]:
        return (
            safe_float(row["relaxed_column_f1"]),
            safe_float(row["relaxed_column_precision"]),
            safe_float(row["core_column_recall"]),
        )

    return max(sim_rows, key=sort_key)["strategy_name"]


def collect_error_examples(
    best_strategy_rows: List[Dict[str, str]],
    label_rows: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    labels_by_candidate = {row["candidate_id"]: row for row in label_rows}
    selected_ids = {row["candidate_id"] for row in best_strategy_rows}
    filtered_true_positives: List[Dict[str, str]] = []
    retained_false_positives: List[Dict[str, str]] = []
    for candidate_id, label in labels_by_candidate.items():
        if label["candidate_should_keep_relaxed"] == "1" and candidate_id not in selected_ids:
            filtered_true_positives.append(label)
        if label["candidate_should_keep_relaxed"] == "0" and candidate_id in selected_ids:
            retained_false_positives.append(label)
    return filtered_true_positives, retained_false_positives


def write_simulation_report(
    sim_rows: List[Dict[str, str]],
    best_strategy: str,
) -> None:
    lines = [
        "# bert_assisted_filtering_simulation_report",
        "",
        f"- evaluated strategies: {', '.join(row['strategy_name'] for row in sim_rows)}",
        f"- best strategy by relaxed F1: {best_strategy}",
        "",
        "| strategy | candidate_count | relaxed P | relaxed R | relaxed F1 | core recall | overgeneration |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sim_rows:
        lines.append(
            f"| {row['strategy_name']} | {row['candidate_count']} | {row['relaxed_column_precision']} | {row['relaxed_column_recall']} | {row['relaxed_column_f1']} | {row['core_column_recall']} | {row['overgeneration_rate']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- All filtered predictions here are simulations built on top of the candidate pool.",
            "- They are not final deployed systems and do not modify gold or baseline artifacts.",
        ]
    )
    SIM_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_main_report(
    scoring_rows: List[Dict[str, str]],
    label_rows: List[Dict[str, str]],
    shadow_rows: List[Dict[str, str]],
    bert_loaded: bool,
    bert_failure_reason: str,
    shadow_stats: Dict[str, float],
    sim_rows: List[Dict[str, str]],
    sim_results: Dict[str, Dict[str, object]],
    best_strategy: str,
) -> None:
    positive_scores = []
    negative_scores = []
    labels_by_candidate = {row["candidate_id"]: row for row in label_rows}
    for row in shadow_rows:
        score = safe_float(row.get("candidate_context_fit_score"), None) if row.get("candidate_context_fit_score") != "" else None
        if score is None:
            continue
        if labels_by_candidate[row["candidate_id"]]["candidate_should_keep_relaxed"] == "1":
            positive_scores.append(score)
        else:
            negative_scores.append(score)

    tier_positive = Counter()
    tier_total = Counter()
    relation_positive = Counter()
    relation_total = Counter()
    for label in label_rows:
        candidate = next(row for row in shadow_rows if row["candidate_id"] == label["candidate_id"])
        tier = candidate["candidate_tier"]
        relation_type = candidate["pred_relation_type"]
        tier_total[tier] += 1
        relation_total[relation_type] += 1
        if label["candidate_should_keep_relaxed"] == "1":
            tier_positive[tier] += 1
            relation_positive[relation_type] += 1

    benefit_lines = []
    for tier, total in tier_total.items():
        benefit_lines.append(f"- {tier}: {tier_positive[tier]} / {total} relaxed-kept")

    hard_relation_lines = []
    for relation_type, total in sorted(relation_total.items()):
        rate = relation_positive[relation_type] / total if total else 0.0
        hard_relation_lines.append(f"- {relation_type}: keep-label rate {rate:.3f} ({relation_positive[relation_type]}/{total})")

    best_summary = next(row for row in sim_rows if row["strategy_name"] == best_strategy)
    no_filter_summary = next(row for row in sim_rows if row["strategy_name"] == "rule_pool_no_filter")
    better_than_no_filter = safe_float(best_summary["relaxed_column_f1"]) > safe_float(no_filter_summary["relaxed_column_f1"])

    lines = [
        "# bert_assisted_prototype_v0 report",
        "",
        f"- MacBERT loaded successfully: {'yes' if bert_loaded else 'no'}",
        f"- model path: {LOCAL_MACBERT_PATH}",
        f"- model training in this step: no",
        f"- model fine-tuning in this step: no",
        f"- candidate rows scored: {len(shadow_rows)}",
        f"- scoring input rows: {len(scoring_rows)}",
        f"- offline evaluation label rows: {len(label_rows)}",
        f"- best filter strategy: {best_strategy}",
        f"- better than no_filter: {'yes' if better_than_no_filter else 'no'}",
        "",
        "## Shadow score definition",
        "",
        "- `pair_context_similarity`: cosine similarity between frozen MacBERT embeddings of `turn_a` and `turn_b`.",
        "- `span_pair_similarity`: cosine similarity between frozen MacBERT embeddings of `pred_span_a` and `pred_span_b`.",
        "- `candidate_context_fit_score`: normalized heuristic score built from frozen MacBERT span similarity and context-vs-span+relation similarity.",
        "- These are shadow scores only, not trained probabilities.",
        "",
        "## Score vs relaxed-match label",
        "",
        f"- mean candidate_context_fit_score on relaxed-kept candidates: {statistics.mean(positive_scores):.6f}" if positive_scores else "- mean candidate_context_fit_score on relaxed-kept candidates: n/a",
        f"- mean candidate_context_fit_score on relaxed-rejected candidates: {statistics.mean(negative_scores):.6f}" if negative_scores else "- mean candidate_context_fit_score on relaxed-rejected candidates: n/a",
        "",
        "## Tier signals",
        "",
        *benefit_lines,
        "",
        "## Relation-type difficulty",
        "",
        *hard_relation_lines,
        "",
        "## Strategy comparison",
        "",
        f"- no_filter relaxed F1: {no_filter_summary['relaxed_column_f1']}",
        f"- best strategy relaxed F1: {best_summary['relaxed_column_f1']}",
        f"- no_filter overgeneration: {no_filter_summary['overgeneration_rate']}",
        f"- best strategy overgeneration: {best_summary['overgeneration_rate']}",
        "",
        "## Recommendation",
        "",
        f"- move to supervised reranker next: {'yes, cautiously' if bert_loaded else 'not yet'}",
        "- Keep the next stage focused on binary keep/filter plus relation-type sanity check.",
        "- Do not let BERT directly generate spans or new columns at this stage.",
        "- 70 candidates / 50 pairs are still too small and too evaluation-oriented for training a large end-to-end generator.",
        "",
        "## Boundary notes",
        "",
        "- This round used BERT only for offline shadow scoring.",
        "- This round did not train or fine-tune any model.",
        "- This round did not modify gold.",
        "- This round did not touch the website.",
    ]
    if not bert_loaded:
        lines.extend(["", "## BERT loading failure", "", f"- reason: {bert_failure_reason}"])
    if shadow_stats:
        lines.extend(
            [
                "",
                "## Score distribution snapshot",
                "",
                f"- pair_context_similarity mean: {shadow_stats['pair_context_similarity_mean']:.6f}",
                f"- span_pair_similarity mean: {shadow_stats['span_pair_similarity_mean']:.6f}",
                f"- candidate_context_fit_score mean: {shadow_stats['candidate_context_fit_score_mean']:.6f}",
            ]
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_error_notes(
    best_strategy_rows: List[Dict[str, str]],
    label_rows: List[Dict[str, str]],
    shadow_rows: List[Dict[str, str]],
    bert_loaded: bool,
) -> None:
    filtered_true_positives, retained_false_positives = collect_error_examples(best_strategy_rows, label_rows)
    shadow_by_id = {row["candidate_id"]: row for row in shadow_rows}

    tp_lines = []
    for row in filtered_true_positives[:8]:
        score_row = shadow_by_id[row["candidate_id"]]
        tp_lines.append(
            f"- {row['candidate_id']} {row['annotation_id']}/{row['pred_column_id']} "
            f"{row['pred_relation_type']} filtered despite relaxed gold match; "
            f"fit={score_row.get('candidate_context_fit_score', '')} span={score_row.get('span_pair_similarity', '')}"
        )
    fp_lines = []
    for row in retained_false_positives[:8]:
        score_row = shadow_by_id[row["candidate_id"]]
        fp_lines.append(
            f"- {row['candidate_id']} {row['annotation_id']}/{row['pred_column_id']} "
            f"{row['pred_relation_type']} retained without relaxed gold match; "
            f"fit={score_row.get('candidate_context_fit_score', '')} span={score_row.get('span_pair_similarity', '')}"
        )

    lines = [
        "# bert_assisted_prototype_v0 error notes",
        "",
        "## Typical true positives that BERT-style filtering may drop",
        "",
        *(tp_lines or ["- none in sampled summary"]),
        "",
        "## Typical false positives that frozen scoring may still keep",
        "",
        *(fp_lines or ["- none in sampled summary"]),
        "",
        "## Limits of frozen encoder scoring",
        "",
        "- Frozen cosine-style scores do not understand the full dialogue graph objective.",
        "- They are especially weak on pragmatic_function, analogy, and long reasoning chains.",
        "- A similarity score can prefer surface overlap while missing structure-critical but lexically weak columns.",
        "",
        "## Limits of relation_type sanity check",
        "",
        "- It can flag suspicious coreference / slot_filling / contrast / repair candidates.",
        "- It cannot reliably replace column-level annotation decisions on its own.",
        "",
        "## Data requirement note",
        "",
        "- If we later train a supervised binary keep/filter reranker, we will need more column-level gold and cross-validation discipline.",
        f"- BERT loaded in this run: {'yes' if bert_loaded else 'no'}",
    ]
    ERROR_NOTES_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest() -> None:
    lines = [
        "# bert_assisted_prototype_v0 manifest",
        "",
        "| file | purpose |",
        "| --- | --- |",
        "| `bert_candidate_scoring_input_v0.csv/xlsx` | candidate-level BERT scoring input pack |",
        "| `bert_candidate_offline_eval_labels_v0.csv/xlsx` | offline exact/relaxed evaluation labels for analysis only |",
        "| `bert_candidate_shadow_scores_v0.csv/xlsx` | frozen MacBERT shadow scores or placeholder rows |",
        "| `filtered_predictions/*.csv` | simulated filtered predictions per strategy |",
        "| `filtered_predictions/*_evaluation/` | evaluator outputs for each simulation strategy |",
        "| `bert_assisted_filtering_simulation_summary.csv/xlsx` | summary table over filtering strategies |",
        "| `bert_assisted_filtering_simulation_report.md` | filtering simulation report |",
        "| `bert_assisted_prototype_v0_report.md` | main prototype report |",
        "| `bert_assisted_prototype_v0_error_notes.md` | limitations and qualitative error notes |",
        "| `bert_assisted_prototype_v0_manifest.md` | artifact manifest |",
        "",
        "## Scope note",
        "",
        "- This prototype uses BERT only for offline shadow scoring.",
        "- No training or fine-tuning was performed.",
        "- Filtered predictions are simulation outputs, not final production systems.",
    ]
    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    candidate_rows = read_csv_dicts(CANDIDATE_POOL_PATH)
    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    gold_rows = read_csv_dicts(DEFAULT_GOLD_ACTIVE)
    pair_map = build_pair_map(pair_rows)
    validate_gold_rows(gold_rows, pair_map)

    candidate_annotation_ids = {row["annotation_id"] for row in candidate_rows}
    valid_candidate_rows, invalid_candidate_rows = validate_prediction_rows(
        candidate_rows,
        gold_annotation_ids={row["annotation_id"] for row in gold_rows},
        pair_map=pair_map,
    )
    if invalid_candidate_rows:
        raise ValueError(f"candidate pool contains invalid rows: {len(invalid_candidate_rows)}")
    if len(valid_candidate_rows) != len(candidate_rows):
        raise ValueError("candidate pool row count changed after validation unexpectedly.")

    scoring_rows = build_scoring_input_rows(candidate_rows, pair_map)
    label_rows = build_offline_eval_labels(candidate_rows, gold_rows, pair_map)
    shadow_rows, bert_loaded, bert_failure_reason, shadow_stats = build_shadow_scores(scoring_rows)

    merged_rows = merge_candidate_views(candidate_rows, scoring_rows, label_rows, shadow_rows)
    sim_rows, sim_results = evaluate_filtered_strategies(merged_rows)
    best_strategy = choose_best_strategy(sim_rows)

    write_csv(SCORING_INPUT_PATH, scoring_rows, SCORING_INPUT_FIELDS)
    write_csv(LABELS_PATH, label_rows, LABEL_FIELDS)
    write_csv(SHADOW_SCORES_PATH, shadow_rows, SHADOW_SCORE_FIELDS)
    write_csv(SIM_SUMMARY_PATH, sim_rows, SIM_SUMMARY_FIELDS)
    write_simulation_report(sim_rows, best_strategy)
    write_main_report(
        scoring_rows=scoring_rows,
        label_rows=label_rows,
        shadow_rows=shadow_rows,
        bert_loaded=bert_loaded,
        bert_failure_reason=bert_failure_reason,
        shadow_stats=shadow_stats,
        sim_rows=sim_rows,
        sim_results=sim_results,
        best_strategy=best_strategy,
    )
    write_error_notes(
        best_strategy_rows=sim_results[best_strategy]["selected_rows"],
        label_rows=label_rows,
        shadow_rows=shadow_rows,
        bert_loaded=bert_loaded,
    )
    write_manifest()

    status = {
        "candidate_count": len(candidate_rows),
        "scoring_input_rows": len(scoring_rows),
        "label_rows": len(label_rows),
        "shadow_score_rows": len(shadow_rows),
        "bert_loaded": bert_loaded,
        "bert_failure_reason": bert_failure_reason,
        "best_strategy": best_strategy,
        "best_strategy_summary": next(row for row in sim_rows if row["strategy_name"] == best_strategy),
    }
    STATUS_JSON_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
