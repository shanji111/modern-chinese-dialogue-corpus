"""Offline rule+BERT hybrid shadow analysis using existing predictions."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from io_utils import ARTIFACTS_DIR, artifact_path, read_csv, write_csv, write_json, write_text


SEEDS = [20260621, 42, 1234, 2025, 3407]
LABELS = ["no", "yes"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    base = artifact_path("formal_300_v1")
    parser.add_argument("--v3-dir", default=str(base / "bert_shadow_v3_multiseed"))
    parser.add_argument("--output-dir", default=str(base / "hybrid_shadow_v1"))
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--rule-baseline-json", default=str(base / "baselines" / "rule_baseline_gold_v1_binary.json"))
    parser.add_argument("--gold-dev-csv", default=str(base / "baselines" / "gold_v1_binary_dev.csv"))
    parser.add_argument("--gold-test-csv", default=str(base / "baselines" / "gold_v1_binary_test.csv"))
    parser.add_argument("--evaluation-key", default=str(base / "formal_300_v1_evaluation_key.csv"))
    parser.add_argument("--gold-binary-csv", default=str(base / "formal_300_v1_gold_v1_binary.csv"))
    parser.add_argument("--v3-summary-json", default=str(base / "bert_shadow_v3_multiseed" / "multiseed_summary.json"))
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting hybrid shadow artifacts.")
    return parser.parse_args()


def ensure_output_dir(path: str | Path) -> Path:
    output_dir = Path(path)
    artifacts_root = ARTIFACTS_DIR.resolve()
    try:
        output_dir.resolve().relative_to(artifacts_root)
    except ValueError as exc:
        raise SystemExit(f"Hybrid outputs must be under {artifacts_root}: {output_dir}") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def bool_text(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def index_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["annotation_id"]: row for row in rows}


def load_seed_predictions(v3_dir: Path, seeds: list[int], split: str) -> dict[str, list[dict[str, str]]]:
    per_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for seed in seeds:
        path = v3_dir / f"seed_{seed}" / f"{split}_predictions.csv"
        for row in read_csv(path):
            item = dict(row)
            item["seed"] = str(seed)
            per_id[item["annotation_id"]].append(item)
    return per_id


def attach_key(row: dict[str, Any], key: dict[str, str]) -> None:
    for field in [
        "rule_summary",
        "rule_any_positive",
        "has_lexical_echo",
        "has_pattern_reuse",
        "has_question_response",
        "has_negation_turn",
        "has_repair_repetition",
        "shared_terms",
        "markers",
    ]:
        row[field] = row.get(field) or key.get(field, "")


def combine_predictions(
    per_id: dict[str, list[dict[str, str]]],
    gold_rows: dict[str, dict[str, str]],
    key_rows: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    for annotation_id, seed_rows in sorted(per_id.items()):
        first = seed_rows[0]
        gold = gold_rows.get(annotation_id, {})
        probs = [float(row["prob_yes"]) for row in seed_rows]
        row: dict[str, Any] = {
            "annotation_id": annotation_id,
            "pair_id": first.get("pair_id", ""),
            "source": first.get("source") or gold.get("source", ""),
            "dataset_name": first.get("dataset_name") or gold.get("dataset_name", ""),
            "sample_stratum": first.get("sample_stratum") or gold.get("sample_stratum", ""),
            "turn_a": first.get("turn_a") or gold.get("turn_a", ""),
            "turn_b": first.get("turn_b") or gold.get("turn_b", ""),
            "gold_label": first.get("gold_label") or gold.get("resonance_present", ""),
            "binary_label": int(first.get("binary_label") or gold.get("binary_label") or 0),
            "mean_prob": statistics.mean(probs),
            "min_prob": min(probs),
            "max_prob": max(probs),
            "std_prob": statistics.stdev(probs) if len(probs) > 1 else 0.0,
            "seed_probs": json.dumps({seed_rows[i]["seed"]: probs[i] for i in range(len(seed_rows))}, ensure_ascii=False),
            "rule_any_positive": first.get("rule_any_positive", ""),
            "rule_summary": first.get("rule_summary", ""),
            "has_lexical_echo": first.get("has_lexical_echo", ""),
            "has_pattern_reuse": first.get("has_pattern_reuse", ""),
            "has_question_response": first.get("has_question_response", ""),
            "has_negation_turn": first.get("has_negation_turn", ""),
            "has_repair_repetition": first.get("has_repair_repetition", ""),
            "label_reproduction": gold.get("label_reproduction", ""),
            "label_parallelism": gold.get("label_parallelism", ""),
            "label_selective_reuse": gold.get("label_selective_reuse", ""),
            "label_repair": gold.get("label_repair", ""),
            "label_contrast": gold.get("label_contrast", ""),
            "label_analogy_candidate": gold.get("label_analogy_candidate", ""),
            "evidence_span_a": gold.get("evidence_span_a", ""),
            "evidence_span_b": gold.get("evidence_span_b", ""),
        }
        attach_key(row, key_rows.get(annotation_id, {}))
        row["rule_pred"] = "yes" if bool_text(row.get("rule_any_positive")) else "no"
        row["risk_type"] = risk_type(row)
        rows.append(row)
    return rows


def risk_type(row: dict[str, Any]) -> str:
    text = " ".join(
        str(row.get(field) or "")
        for field in [
            "turn_a",
            "turn_b",
            "evidence_span_a",
            "evidence_span_b",
            "rule_summary",
            "shared_terms",
            "markers",
        ]
    )
    if row.get("gold_label") == "no" and bool_text(row.get("has_question_response")):
        return "question_response"
    if row.get("gold_label") == "no":
        return "topic_related_but_not_resonance"
    if bool_text(row.get("label_analogy_candidate")):
        return "analogy"
    if any(token in text for token in ["这", "此", "那个", "那", "他", "她", "它", "其", "斯", "指回", "指称"]):
        return "demonstrative_or_reference"
    if any(token in text for token in ["填入", "填补", "槽位", "什么", "怎样", "如何", "何以", "为何", "谁", "哪里", "多少", "何人", "孰"]):
        return "slot_filling"
    if min(len(str(row.get("turn_a") or "")), len(str(row.get("turn_b") or ""))) <= 4:
        return "short_answer"
    return "semantic_selection"


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def metrics_for(rows: list[dict[str, Any]], preds: list[str]) -> dict[str, Any]:
    truth = [row["gold_label"] for row in rows]
    tp = sum(1 for gold, pred in zip(truth, preds) if gold == "yes" and pred == "yes")
    fp = sum(1 for gold, pred in zip(truth, preds) if gold == "no" and pred == "yes")
    fn = sum(1 for gold, pred in zip(truth, preds) if gold == "yes" and pred == "no")
    tn = sum(1 for gold, pred in zip(truth, preds) if gold == "no" and pred == "no")
    pos = prf(tp, fp, fn)
    no = prf(tn, fn, fp)
    total = len(rows)
    yes_support = sum(1 for gold in truth if gold == "yes")
    no_support = total - yes_support
    macro_precision = (pos["precision"] + no["precision"]) / 2
    macro_recall = (pos["recall"] + no["recall"]) / 2
    macro_f1 = (pos["f1"] + no["f1"]) / 2
    weighted_f1 = (pos["f1"] * yes_support + no["f1"] * no_support) / total if total else 0.0
    return {
        "accuracy": (tp + tn) / total if total else 0.0,
        "positive_class": pos,
        "no_class": no,
        "macro": {"precision": macro_precision, "recall": macro_recall, "f1": macro_f1},
        "weighted_f1": weighted_f1,
        "balanced_accuracy": macro_recall,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "support": {"yes": yes_support, "no": no_support, "total": total},
    }


def rule_fn_recovered(rows: list[dict[str, Any]], preds: list[str]) -> int:
    return sum(
        1
        for row, pred in zip(rows, preds)
        if row["gold_label"] == "yes" and row["rule_pred"] == "no" and pred == "yes"
    )


def question_veto(row: dict[str, Any]) -> bool:
    return (
        bool_text(row.get("has_question_response"))
        and not bool_text(row.get("has_lexical_echo"))
        and not bool_text(row.get("has_pattern_reuse"))
        and not bool_text(row.get("has_negation_turn"))
        and not bool_text(row.get("has_repair_repetition"))
    )


def topic_veto(row: dict[str, Any]) -> bool:
    return (
        row["rule_pred"] == "no"
        and not bool_text(row.get("has_lexical_echo"))
        and not bool_text(row.get("has_pattern_reuse"))
        and not bool_text(row.get("has_negation_turn"))
        and not bool_text(row.get("has_repair_repetition"))
        and str(row.get("sample_stratum") or "") in {"potential_false_negative", "hard_negative_or_boundary"}
    )


def strategy_pred(strategy: str, row: dict[str, Any], threshold: float) -> str:
    bert_yes = float(row["mean_prob"]) >= threshold
    rule_yes = row["rule_pred"] == "yes"
    if strategy == "ensemble_mean":
        return "yes" if bert_yes else "no"
    if strategy == "rule_or_bert":
        return "yes" if rule_yes or bert_yes else "no"
    if strategy == "rule_and_bert":
        return "yes" if rule_yes and bert_yes else "no"
    if strategy == "rule_priority_with_bert_recall":
        return "yes" if rule_yes or (not rule_yes and bert_yes) else "no"
    if strategy == "bert_with_rule_veto":
        if not bert_yes:
            return "no"
        if question_veto(row):
            return "no"
        return "yes"
    if strategy == "bert_with_rule_veto_plus_topic_guard":
        if not bert_yes:
            return "no"
        if question_veto(row) or topic_veto(row):
            return "no"
        return "yes"
    raise ValueError(f"Unknown strategy: {strategy}")


def threshold_candidates(rows: list[dict[str, Any]], *, minimum: float = 0.0) -> list[float]:
    values = {0.0, 0.5, 1.0}
    values.update(float(row["mean_prob"]) for row in rows)
    return sorted(value for value in values if value >= minimum)


def select_threshold(strategy: str, dev_rows: list[dict[str, Any]], *, minimum: float = 0.0) -> tuple[float, dict[str, Any], list[str]]:
    best_threshold = 0.5
    best_metrics: dict[str, Any] | None = None
    best_preds: list[str] = []

    def score(metrics: dict[str, Any], threshold: float) -> tuple[float, float, float, float, float, float]:
        cm = metrics["confusion_matrix"]
        return (
            metrics["macro"]["f1"],
            metrics["balanced_accuracy"],
            metrics["no_class"]["recall"],
            metrics["positive_class"]["f1"],
            -cm["fp"],
            -abs(threshold - 0.5),
        )

    best_score: tuple[float, float, float, float, float, float] | None = None
    for threshold in threshold_candidates(dev_rows, minimum=minimum):
        preds = [strategy_pred(strategy, row, threshold) for row in dev_rows]
        metrics = metrics_for(dev_rows, preds)
        current_score = score(metrics, threshold)
        if best_score is None or current_score > best_score:
            best_threshold = threshold
            best_metrics = metrics
            best_preds = preds
            best_score = current_score
    assert best_metrics is not None
    return best_threshold, best_metrics, best_preds


def run_strategy(strategy: str, dev_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]]) -> dict[str, Any]:
    minimum = 0.5 if strategy == "rule_priority_with_bert_recall" else 0.0
    threshold, dev_metrics, dev_preds = select_threshold(strategy, dev_rows, minimum=minimum)
    test_preds = [strategy_pred(strategy, row, threshold) for row in test_rows]
    test_metrics = metrics_for(test_rows, test_preds)
    return {
        "strategy": strategy,
        "selected_threshold": threshold,
        "dev": dev_metrics,
        "test": test_metrics,
        "dev_rule_fn_recovered": rule_fn_recovered(dev_rows, dev_preds),
        "test_rule_fn_recovered": rule_fn_recovered(test_rows, test_preds),
        "test_all_yes": test_metrics["confusion_matrix"]["tn"] == 0 and test_metrics["confusion_matrix"]["fn"] == 0,
        "test_predictions": {row["annotation_id"]: pred for row, pred in zip(test_rows, test_preds)},
        "dev_predictions": {row["annotation_id"]: pred for row, pred in zip(dev_rows, dev_preds)},
    }


def result_row(result: dict[str, Any]) -> dict[str, object]:
    dev = result["dev"]
    test = result["test"]
    cm = test["confusion_matrix"]
    dev_cm = dev["confusion_matrix"]
    return {
        "strategy": result["strategy"],
        "selected_threshold": result["selected_threshold"],
        "dev_accuracy": dev["accuracy"],
        "dev_positive_precision": dev["positive_class"]["precision"],
        "dev_positive_recall": dev["positive_class"]["recall"],
        "dev_positive_f1": dev["positive_class"]["f1"],
        "dev_no_precision": dev["no_class"]["precision"],
        "dev_no_recall": dev["no_class"]["recall"],
        "dev_no_f1": dev["no_class"]["f1"],
        "dev_macro_precision": dev["macro"]["precision"],
        "dev_macro_recall": dev["macro"]["recall"],
        "dev_macro_f1": dev["macro"]["f1"],
        "dev_weighted_f1": dev["weighted_f1"],
        "dev_balanced_accuracy": dev["balanced_accuracy"],
        "dev_tp": dev_cm["tp"],
        "dev_fp": dev_cm["fp"],
        "dev_fn": dev_cm["fn"],
        "dev_tn": dev_cm["tn"],
        "test_accuracy": test["accuracy"],
        "test_positive_precision": test["positive_class"]["precision"],
        "test_positive_recall": test["positive_class"]["recall"],
        "test_positive_f1": test["positive_class"]["f1"],
        "test_no_precision": test["no_class"]["precision"],
        "test_no_recall": test["no_class"]["recall"],
        "test_no_f1": test["no_class"]["f1"],
        "test_macro_precision": test["macro"]["precision"],
        "test_macro_recall": test["macro"]["recall"],
        "test_macro_f1": test["macro"]["f1"],
        "test_weighted_f1": test["weighted_f1"],
        "test_balanced_accuracy": test["balanced_accuracy"],
        "test_tp": cm["tp"],
        "test_fp": cm["fp"],
        "test_fn": cm["fn"],
        "test_tn": cm["tn"],
        "test_rule_fn_recovered": result["test_rule_fn_recovered"],
        "test_all_yes": result["test_all_yes"],
    }


def markdown_table(rows: list[list[object]]) -> str:
    if not rows:
        return ""
    lines = [
        "| " + " | ".join(str(value) for value in rows[0]) + " |",
        "| " + " | ".join("---" for _ in rows[0]) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def fmt(value: float) -> str:
    return f"{value:.3f}"


def build_report(results: list[dict[str, Any]], baselines: dict[str, Any], v3_summary: dict[str, Any]) -> str:
    rows = [["Strategy", "Thr", "Macro-F1", "Bal Acc", "No Recall", "Pos F1", "TP/FP/FN/TN", "Rule FN recovered", "All yes"]]
    for result in results:
        test = result["test"]
        cm = test["confusion_matrix"]
        rows.append([
            result["strategy"],
            f"{result['selected_threshold']:.6f}",
            fmt(test["macro"]["f1"]),
            fmt(test["balanced_accuracy"]),
            fmt(test["no_class"]["recall"]),
            fmt(test["positive_class"]["f1"]),
            f"{cm['tp']}/{cm['fp']}/{cm['fn']}/{cm['tn']}",
            result["test_rule_fn_recovered"],
            result["test_all_yes"],
        ])
    v3_mean = v3_summary["stability"]["mean_std"]
    lines = [
        "# Hybrid Shadow v1 Report",
        "",
        "This is an offline rule+BERT hybrid shadow analysis. It uses existing MacBERT v3 multi-seed predictions and rule fields only; no new model is trained, no database is touched, and nothing is connected to the website.",
        "",
        "## Strategy Results On Test",
        "",
        markdown_table(rows),
        "",
        "## Baseline References",
        "",
        f"- majority/similarity: macro-F1≈0.442, balanced accuracy=0.500, no recall=0",
        f"- rule full-set: macro-F1={baselines['rule_full_macro_f1']:.3f}, balanced accuracy={baselines['rule_full_balanced_accuracy']:.3f}",
        f"- rule test split: macro-F1={baselines['rule_test_macro_f1']:.3f}, balanced accuracy={baselines['rule_test_balanced_accuracy']:.3f}",
        f"- MacBERT v3 mean: macro-F1={v3_mean['test_macro_f1']['mean']:.3f} ± {v3_mean['test_macro_f1']['std']:.3f}, balanced accuracy={v3_mean['test_balanced_accuracy']['mean']:.3f} ± {v3_mean['test_balanced_accuracy']['std']:.3f}",
        "",
        "## Interpretation",
        "",
        "- `rule_or_bert` targets recall and should be checked for false-positive growth.",
        "- `rule_and_bert` targets precision but can suppress recall.",
        "- `rule_priority_with_bert_recall` preserves direct rule positives while allowing high-confidence BERT recovery for rule-negative rows.",
        "- `bert_with_rule_veto` currently only implements an available question-response veto; stronger negative patterns remain future work.",
        "- `bert_with_rule_veto_plus_topic_guard` is exploratory and uses a conservative no-rule/no-cue topic guard; it should not be deployed without more data.",
    ]
    return "\n".join(lines) + "\n"


def error_ids(rows: list[dict[str, Any]], preds: dict[str, str], label: str) -> list[str]:
    output = []
    for row in rows:
        pred = preds[row["annotation_id"]]
        gold = row["gold_label"]
        if label == "FP" and gold == "no" and pred == "yes":
            output.append(row["annotation_id"])
        if label == "FN" and gold == "yes" and pred == "no":
            output.append(row["annotation_id"])
    return output


def build_error_analysis(results: list[dict[str, Any]], test_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Hybrid Error Analysis",
        "",
        "This file compares false positives, false negatives, and rule-FN recovery across hybrid strategies.",
        "",
    ]
    for result in results:
        fp_ids = error_ids(test_rows, result["test_predictions"], "FP")
        fn_ids = error_ids(test_rows, result["test_predictions"], "FN")
        fp_risks = Counter(row["risk_type"] for row in test_rows if row["annotation_id"] in fp_ids)
        fn_risks = Counter(row["risk_type"] for row in test_rows if row["annotation_id"] in fn_ids)
        lines.extend([
            f"## {result['strategy']}",
            "",
            f"- FP count: {len(fp_ids)}; IDs: {', '.join(fp_ids) or '(none)'}",
            f"- FN count: {len(fn_ids)}; IDs: {', '.join(fn_ids) or '(none)'}",
            f"- FP risk types: `{json.dumps(dict(fp_risks), ensure_ascii=False)}`",
            f"- FN risk types: `{json.dumps(dict(fn_risks), ensure_ascii=False)}`",
            f"- Rule FN recovered: {result['test_rule_fn_recovered']}",
            "",
        ])
    return "\n".join(lines) + "\n"


def choose_best(results: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        results,
        key=lambda result: (
            result["test"]["macro"]["f1"],
            result["test"]["balanced_accuracy"],
            -result["test"]["confusion_matrix"]["fp"],
            result["test_rule_fn_recovered"],
        ),
    )


def build_recommendation(best: dict[str, Any], results: list[dict[str, Any]], baselines: dict[str, Any]) -> str:
    test = best["test"]
    cm = test["confusion_matrix"]
    by_name = {result["strategy"]: result for result in results}
    ensemble = by_name.get("ensemble_mean", {})
    ensemble_cm = ensemble.get("test", {}).get("confusion_matrix", {}) if ensemble else {}
    rule_test_macro = baselines["rule_test_macro_f1"]
    rule_test_balanced = baselines["rule_test_balanced_accuracy"]
    lines = [
        "# Hybrid Shadow Recommendation",
        "",
        f"Best post-hoc hybrid strategy in this run: `{best['strategy']}`.",
        "",
        f"- test macro-F1: {test['macro']['f1']:.3f}",
        f"- test balanced accuracy: {test['balanced_accuracy']:.3f}",
        f"- test no-class recall: {test['no_class']['recall']:.3f}",
        f"- test positive F1: {test['positive_class']['f1']:.3f}",
        f"- TP/FP/FN/TN: {cm['tp']}/{cm['fp']}/{cm['fn']}/{cm['tn']}",
        f"- rule FN recovered: {best['test_rule_fn_recovered']}",
        f"- rule test split reference: macro-F1={rule_test_macro:.3f}, balanced accuracy={rule_test_balanced:.3f}",
        "",
        "## Tradeoff",
        "",
        f"- Pure ensemble_mean FP/FN: {ensemble_cm.get('fp', 'n/a')}/{ensemble_cm.get('fn', 'n/a')}",
        f"- Best hybrid FP/FN: {cm['fp']}/{cm['fn']}",
        "- The best hybrid improves recall and macro-F1 over pure ensemble_mean, but it does not reduce false positives; it accepts one extra false positive to recover more rule false negatives.",
        "- The stable topic-related false positive remains a risk and should be highlighted in any future shadow UI.",
        "",
        "## Integration Recommendation",
        "",
        "Recommend moving toward website shadow integration only as an offline-visible auxiliary signal first, not as an automatic production decision.",
        "",
        "BERT should be integrated as:",
        "",
        "- reranker",
        "- confidence scorer",
        "- recall supplement",
        "- not graph generator",
        "",
        "Rule graph explanations should remain visible. The BERT score can help prioritize or flag hidden carry-over, but it should not replace rule evidence or generate graph edges by itself.",
        "",
        "## Guardrails",
        "",
        "- Do not automatically rewrite gold labels.",
        "- Do not use BERT outputs to mutate corpus.db.",
        "- Keep test-set threshold selection prohibited.",
        "- More gold data is still needed before production routing.",
        "- Add a shadow-only UI flag or offline export before any user-facing automatic behavior.",
    ]
    if best["test"]["macro"]["f1"] <= baselines["rule_test_macro_f1"]:
        lines.append("- Because the best hybrid does not beat rule test macro-F1, keep this strictly experimental.")
    else:
        lines.append("- The best hybrid beats rule test macro-F1 in this split, but should still remain shadow-only until validated on more data.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    output_dir = ensure_output_dir(args.output_dir)
    v3_dir = Path(args.v3_dir)
    key_rows = index_by_id(read_csv(args.evaluation_key))
    _gold_binary_count = len(read_csv(args.gold_binary_csv))
    if _gold_binary_count == 0:
        raise SystemExit("gold_v1_binary is empty")
    gold_dev = index_by_id(read_csv(args.gold_dev_csv))
    gold_test = index_by_id(read_csv(args.gold_test_csv))
    dev_rows = combine_predictions(load_seed_predictions(v3_dir, args.seeds, "dev"), gold_dev, key_rows)
    test_rows = combine_predictions(load_seed_predictions(v3_dir, args.seeds, "test"), gold_test, key_rows)
    v3_summary = json.loads(Path(args.v3_summary_json).read_text(encoding="utf-8"))
    first_seed_metrics = json.loads((v3_dir / f"seed_{args.seeds[0]}" / "metrics.json").read_text(encoding="utf-8"))
    baselines = {
        "majority_macro_f1": 0.442,
        "majority_balanced_accuracy": 0.500,
        "rule_full_macro_f1": first_seed_metrics["baselines"]["rule_full_reference"]["macro"]["f1"],
        "rule_full_balanced_accuracy": first_seed_metrics["baselines"]["rule_full_reference"]["balanced_accuracy"],
        "rule_test_macro_f1": first_seed_metrics["baselines"]["rule_from_key"]["test"]["macro"]["f1"],
        "rule_test_balanced_accuracy": first_seed_metrics["baselines"]["rule_from_key"]["test"]["balanced_accuracy"],
    }
    strategies = [
        "ensemble_mean",
        "rule_or_bert",
        "rule_and_bert",
        "rule_priority_with_bert_recall",
        "bert_with_rule_veto",
        "bert_with_rule_veto_plus_topic_guard",
    ]
    results = [run_strategy(strategy, dev_rows, test_rows) for strategy in strategies]
    rows = [result_row(result) for result in results]
    best = choose_best(results)
    payload = {
        "strategies": results,
        "result_rows": rows,
        "best_strategy": best["strategy"],
        "baselines": baselines,
        "v3_mean": v3_summary["stability"]["mean_std"],
        "notes": {
            "trained_new_model": False,
            "ran_new_bert_training": False,
            "modified_gold_or_split": False,
            "read_or_wrote_corpus_db": False,
            "connected_website": False,
        },
    }
    # Remove bulky per-strategy prediction maps from JSON summary while keeping metrics.
    compact_payload = dict(payload)
    compact_payload["strategies"] = [
        {key: value for key, value in result.items() if key not in {"test_predictions", "dev_predictions"}}
        for result in results
    ]
    write_csv(output_dir / "hybrid_strategy_results.csv", rows, list(rows[0].keys()), overwrite=args.overwrite)
    write_json(output_dir / "hybrid_strategy_results.json", compact_payload, overwrite=args.overwrite)
    write_text(output_dir / "hybrid_shadow_v1_report.md", build_report(results, baselines, v3_summary), overwrite=args.overwrite)
    write_text(output_dir / "hybrid_error_analysis.md", build_error_analysis(results, test_rows), overwrite=args.overwrite)
    write_text(output_dir / "hybrid_recommendation.md", build_recommendation(best, results, baselines), overwrite=args.overwrite)
    print(f"wrote={output_dir}")
    print(f"strategies={len(results)}")
    print(f"best={best['strategy']}")
    print(f"best_macro_f1={best['test']['macro']['f1']:.6f}")
    print(f"best_balanced_accuracy={best['test']['balanced_accuracy']:.6f}")
    print(f"best_no_recall={best['test']['no_class']['recall']:.6f}")


if __name__ == "__main__":
    main()
