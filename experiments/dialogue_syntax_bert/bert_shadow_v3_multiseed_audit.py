"""Summarize BERT shadow v3 multi-seed stability runs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from io_utils import ARTIFACTS_DIR, artifact_path, read_csv, write_csv, write_json, write_text


SEEDS = [20260621, 42, 1234, 2025, 3407]
LABEL_COLUMNS = [
    "label_reproduction",
    "label_parallelism",
    "label_selective_reuse",
    "label_repair",
    "label_contrast",
    "label_analogy_candidate",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    base = artifact_path("formal_300_v1")
    parser.add_argument("--run-dir", default=str(base / "bert_shadow_v3_multiseed"))
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--v1-metrics", default=str(base / "bert_shadow_v1" / "bert_shadow_v1_metrics.json"))
    parser.add_argument("--v2-metrics", default=str(base / "bert_shadow_v2" / "bert_shadow_v2_metrics.json"))
    parser.add_argument("--gold-test-csv", default=str(base / "baselines" / "gold_v1_binary_test.csv"))
    parser.add_argument("--evaluation-key", default=str(base / "formal_300_v1_evaluation_key.csv"))
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting v3 multiseed summary artifacts.")
    return parser.parse_args()


def ensure_run_dir(path: str | Path) -> Path:
    run_dir = Path(path)
    artifacts_root = ARTIFACTS_DIR.resolve()
    try:
        run_dir.resolve().relative_to(artifacts_root)
    except ValueError as exc:
        raise SystemExit(f"Run directory must be under {artifacts_root}: {run_dir}") from exc
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def metric(metrics: dict[str, Any], split: str = "test", threshold: str = "dev_selected_threshold") -> dict[str, Any]:
    return metrics[split][threshold]


def confusion(metrics: dict[str, Any], split: str = "test", threshold: str = "dev_selected_threshold") -> dict[str, int]:
    return metric(metrics, split, threshold)["confusion_matrix"]


def mean_std(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values) if values else 0.0,
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def bool_text(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def prediction_label(row: dict[str, str]) -> str:
    return (row.get("pred_dev_threshold") or "").strip()


def risk_type(row: dict[str, str]) -> str:
    text = " ".join(
        str(row.get(column) or "")
        for column in [
            "turn_a",
            "turn_b",
            "evidence_span_a",
            "evidence_span_b",
            "rule_summary",
        ]
    )
    gold = row.get("gold_label") or row.get("resonance_present")
    if gold == "no" and bool_text(row.get("has_question_response")):
        return "question_response"
    if gold == "no":
        return "topic_related_but_not_resonance"
    if bool_text(row.get("label_analogy_candidate")):
        return "analogy"
    if any(token in text for token in ["这", "此", "那个", "那", "他", "她", "它", "其", "斯", "指回", "指称"]):
        return "demonstrative_or_reference"
    if any(token in text for token in ["填入", "填补", "槽位", "什么", "怎样", "如何", "何以", "为何", "谁", "哪里", "多少", "何人", "孰"]):
        return "slot_filling"
    if min(len(row.get("turn_a", "")), len(row.get("turn_b", ""))) <= 4 or min(
        len(row.get("evidence_span_a", "")),
        len(row.get("evidence_span_b", "")),
    ) <= 3:
        return "short_answer"
    return "semantic_selection"


def index_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["annotation_id"]: row for row in rows}


def rule_pred(row: dict[str, str]) -> str:
    return "yes" if bool_text(row.get("rule_any_positive")) else "no"


def error_type(gold: str, pred: str) -> str:
    if gold == "yes" and pred == "yes":
        return "TP"
    if gold == "no" and pred == "yes":
        return "FP"
    if gold == "yes" and pred == "no":
        return "FN"
    return "TN"


def attach_gold_labels(pred_rows: list[dict[str, str]], gold_rows: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    output = []
    for row in pred_rows:
        gold = gold_rows.get(row["annotation_id"], {})
        enriched = dict(row)
        for column in LABEL_COLUMNS:
            enriched[column] = gold.get(column, "")
        enriched["risk_type"] = risk_type(enriched)
        output.append(enriched)
    return output


def seed_summary_row(seed: int, metrics: dict[str, Any]) -> dict[str, object]:
    dev = metric(metrics, "dev")
    test = metric(metrics, "test")
    cm = test["confusion_matrix"]
    rule_compare = metrics["rule_vs_bert"]["test_dev_selected_threshold"]
    return {
        "seed": seed,
        "selected_threshold": metrics["thresholds"]["dev_selected_threshold"],
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
        "dev_tp": dev["confusion_matrix"]["tp"],
        "dev_fp": dev["confusion_matrix"]["fp"],
        "dev_fn": dev["confusion_matrix"]["fn"],
        "dev_tn": dev["confusion_matrix"]["tn"],
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
        "test_all_yes": metrics["all_yes_check"]["test_dev_selected_all_yes"],
        "rule_fn_recovered": rule_compare["rule_false_negative_recovered_by_bert"],
        "bert_false_positive_total": rule_compare["bert_false_positive_total"],
    }


def summary_fieldnames() -> list[str]:
    return list(seed_summary_row(0, {
        "thresholds": {"dev_selected_threshold": 0.0},
        "dev": {"dev_selected_threshold": {
            "accuracy": 0.0,
            "positive_class": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "no_class": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "macro": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "weighted_f1": 0.0,
            "balanced_accuracy": 0.0,
            "confusion_matrix": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        }},
        "test": {"dev_selected_threshold": {
            "accuracy": 0.0,
            "positive_class": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "no_class": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "macro": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "weighted_f1": 0.0,
            "balanced_accuracy": 0.0,
            "confusion_matrix": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        }},
        "all_yes_check": {"test_dev_selected_all_yes": False},
        "rule_vs_bert": {"test_dev_selected_threshold": {
            "rule_false_negative_recovered_by_bert": 0,
            "bert_false_positive_total": 0,
        }},
    }).keys())


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


def fmt_mean_std(stats: dict[str, float]) -> str:
    return f"{stats['mean']:.3f} ± {stats['std']:.3f}"


def build_stability(
    summaries: list[dict[str, object]],
    per_sample: dict[str, list[dict[str, str]]],
    baselines: dict[str, float],
) -> dict[str, Any]:
    vectors = {
        "test_macro_f1": [float(row["test_macro_f1"]) for row in summaries],
        "test_balanced_accuracy": [float(row["test_balanced_accuracy"]) for row in summaries],
        "test_no_recall": [float(row["test_no_recall"]) for row in summaries],
        "test_positive_f1": [float(row["test_positive_f1"]) for row in summaries],
        "test_fp": [float(row["test_fp"]) for row in summaries],
        "test_fn": [float(row["test_fn"]) for row in summaries],
        "rule_fn_recovered": [float(row["rule_fn_recovered"]) for row in summaries],
    }
    stats = {key: mean_std(values) for key, values in vectors.items()}
    all_yes_seeds = [int(row["seed"]) for row in summaries if str(row["test_all_yes"]).lower() == "true"]
    stable_fn = []
    stable_fp = []
    sensitive = []
    error_frequency = {}
    risk_counts_stable_fn: Counter[str] = Counter()
    risk_counts_stable_fp: Counter[str] = Counter()
    for annotation_id, rows in per_sample.items():
        preds = [prediction_label(row) for row in rows]
        errors = [error_type(row["gold_label"], prediction_label(row)) for row in rows]
        error_frequency[annotation_id] = dict(Counter(errors))
        if len(set(preds)) > 1 or len(set(errors)) > 1:
            sensitive.append(annotation_id)
        if all(error == "FN" for error in errors):
            stable_fn.append(annotation_id)
            risk_counts_stable_fn[risk_type(rows[0])] += 1
        if all(error == "FP" for error in errors):
            stable_fp.append(annotation_id)
            risk_counts_stable_fp[risk_type(rows[0])] += 1
    return {
        "mean_std": stats,
        "exceed_counts": {
            "majority_similarity": sum(
                1
                for row in summaries
                if float(row["test_macro_f1"]) > baselines["majority_macro_f1"]
                and float(row["test_balanced_accuracy"]) > baselines["majority_balanced_accuracy"]
            ),
            "rule_full_set": sum(
                1
                for row in summaries
                if float(row["test_macro_f1"]) > baselines["rule_full_macro_f1"]
                and float(row["test_balanced_accuracy"]) > baselines["rule_full_balanced_accuracy"]
            ),
            "rule_test_split": sum(
                1
                for row in summaries
                if float(row["test_macro_f1"]) > baselines["rule_test_macro_f1"]
                and float(row["test_balanced_accuracy"]) > baselines["rule_test_balanced_accuracy"]
            ),
            "no_recall_gt_zero": sum(1 for row in summaries if float(row["test_no_recall"]) > 0),
        },
        "all_yes_seeds": all_yes_seeds,
        "stable_fn_ids": stable_fn,
        "stable_fp_ids": stable_fp,
        "seed_sensitive_ids": sensitive,
        "stable_fn_risk_counts": dict(risk_counts_stable_fn),
        "stable_fp_risk_counts": dict(risk_counts_stable_fp),
        "error_frequency_by_annotation_id": error_frequency,
    }


def collect_runs(run_dir: Path, seeds: list[int], gold_rows: dict[str, dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, list[dict[str, str]]], dict[int, dict[str, Any]]]:
    summaries = []
    per_sample: dict[str, list[dict[str, str]]] = defaultdict(list)
    metrics_by_seed = {}
    for seed in seeds:
        seed_dir = run_dir / f"seed_{seed}"
        metrics_path = seed_dir / "metrics.json"
        predictions_path = seed_dir / "test_predictions.csv"
        if not metrics_path.exists():
            metrics_path = next(seed_dir.glob("*_metrics.json"))
        metrics = load_json(metrics_path)
        metrics_by_seed[seed] = metrics
        summaries.append(seed_summary_row(seed, metrics))
        pred_rows = attach_gold_labels(read_csv(predictions_path), gold_rows)
        for row in pred_rows:
            row["seed"] = str(seed)
            per_sample[row["annotation_id"]].append(row)
    return summaries, per_sample, metrics_by_seed


def build_report(summaries: list[dict[str, object]], stability: dict[str, Any], baselines: dict[str, float]) -> str:
    rows = [["Seed", "Thr", "Macro-F1", "Bal Acc", "No Recall", "Pos F1", "TP/FP/FN/TN", "Rule FN recovered", "All yes"]]
    for item in summaries:
        rows.append([
            item["seed"],
            f"{float(item['selected_threshold']):.6f}",
            f"{float(item['test_macro_f1']):.3f}",
            f"{float(item['test_balanced_accuracy']):.3f}",
            f"{float(item['test_no_recall']):.3f}",
            f"{float(item['test_positive_f1']):.3f}",
            f"{item['test_tp']}/{item['test_fp']}/{item['test_fn']}/{item['test_tn']}",
            item["rule_fn_recovered"],
            item["test_all_yes"],
        ])
    stats = stability["mean_std"]
    lines = [
        "# BERT Shadow v3 Multi-Seed Report",
        "",
        "This is an offline shadow experiment. It does not connect to the website, does not deploy, does not read or write the formal database, and does not modify gold or split files.",
        "",
        "## Per-Seed Test Results",
        "",
        markdown_table(rows),
        "",
        "## Mean +/- Std",
        "",
        f"- test macro-F1: {fmt_mean_std(stats['test_macro_f1'])}",
        f"- test balanced accuracy: {fmt_mean_std(stats['test_balanced_accuracy'])}",
        f"- test no-class recall: {fmt_mean_std(stats['test_no_recall'])}",
        f"- test positive F1: {fmt_mean_std(stats['test_positive_f1'])}",
        f"- test FP count: {fmt_mean_std(stats['test_fp'])}",
        f"- test FN count: {fmt_mean_std(stats['test_fn'])}",
        f"- rule FN recovery count: {fmt_mean_std(stats['rule_fn_recovered'])}",
        "",
        "## Baseline Comparison",
        "",
        f"- majority/similarity: macro-F1≈{baselines['majority_macro_f1']:.3f}, balanced accuracy={baselines['majority_balanced_accuracy']:.3f}, no recall=0",
        f"- rule full-set: macro-F1={baselines['rule_full_macro_f1']:.3f}, balanced accuracy={baselines['rule_full_balanced_accuracy']:.3f}",
        f"- rule test split: macro-F1={baselines['rule_test_macro_f1']:.3f}, balanced accuracy={baselines['rule_test_balanced_accuracy']:.3f}",
        f"- seeds exceeding majority/similarity: {stability['exceed_counts']['majority_similarity']} / {len(summaries)}",
        f"- seeds exceeding rule full-set: {stability['exceed_counts']['rule_full_set']} / {len(summaries)}",
        f"- seeds exceeding rule test split: {stability['exceed_counts']['rule_test_split']} / {len(summaries)}",
        f"- seeds with no-class recall > 0: {stability['exceed_counts']['no_recall_gt_zero']} / {len(summaries)}",
        f"- all-yes seeds: {', '.join(str(seed) for seed in stability['all_yes_seeds']) or 'none'}",
    ]
    return "\n".join(lines) + "\n"


def build_stability_analysis(stability: dict[str, Any]) -> str:
    lines = [
        "# BERT Shadow v3 Stability Analysis",
        "",
        "## Error Consistency",
        "",
        f"- Stable FN count: {len(stability['stable_fn_ids'])}",
        f"- Stable FP count: {len(stability['stable_fp_ids'])}",
        f"- Seed-sensitive sample count: {len(stability['seed_sensitive_ids'])}",
        f"- Stable FN risk counts: `{json.dumps(stability['stable_fn_risk_counts'], ensure_ascii=False)}`",
        f"- Stable FP risk counts: `{json.dumps(stability['stable_fp_risk_counts'], ensure_ascii=False)}`",
        "",
        "## Stable FNs",
        "",
        ", ".join(stability["stable_fn_ids"]) or "(none)",
        "",
        "## Stable FPs",
        "",
        ", ".join(stability["stable_fp_ids"]) or "(none)",
        "",
        "## Seed-Sensitive Samples",
        "",
        ", ".join(stability["seed_sensitive_ids"]) or "(none)",
        "",
        "## Interpretation",
        "",
        "Stable FNs should be read as persistent blind spots. If they are concentrated in demonstrative/reference, short-answer, or selective-reuse cases, future work should analyze implicit carry-over rather than simply increasing epochs.",
    ]
    return "\n".join(lines) + "\n"


def build_v2_comparison(stability: dict[str, Any], v1: dict[str, Any], v2: dict[str, Any]) -> str:
    stats = stability["mean_std"]
    v1_test = metric(v1, "test")
    v2_test = metric(v2, "test")
    rows = [
        ["System", "Macro-F1", "Bal Acc", "No Recall", "Pos F1", "TP/FP/FN/TN"],
        [
            "BERT shadow v1",
            f"{v1_test['macro']['f1']:.3f}",
            f"{v1_test['balanced_accuracy']:.3f}",
            f"{v1_test['no_class']['recall']:.3f}",
            f"{v1_test['positive_class']['f1']:.3f}",
            "/".join(str(v1_test["confusion_matrix"][key]) for key in ["tp", "fp", "fn", "tn"]),
        ],
        [
            "BERT shadow v2",
            f"{v2_test['macro']['f1']:.3f}",
            f"{v2_test['balanced_accuracy']:.3f}",
            f"{v2_test['no_class']['recall']:.3f}",
            f"{v2_test['positive_class']['f1']:.3f}",
            "/".join(str(v2_test["confusion_matrix"][key]) for key in ["tp", "fp", "fn", "tn"]),
        ],
        [
            "BERT shadow v3 mean",
            fmt_mean_std(stats["test_macro_f1"]),
            fmt_mean_std(stats["test_balanced_accuracy"]),
            fmt_mean_std(stats["test_no_recall"]),
            fmt_mean_std(stats["test_positive_f1"]),
            f"FP {fmt_mean_std(stats['test_fp'])}; FN {fmt_mean_std(stats['test_fn'])}",
        ],
    ]
    lines = [
        "# BERT Shadow v2 vs v3 Multi-Seed",
        "",
        markdown_table(rows),
        "",
        "## Conclusion Template",
        "",
    ]
    if stats["test_macro_f1"]["mean"] > 0.642 and stats["test_balanced_accuracy"]["mean"] > 0.753:
        lines.append("MacBERT shadow experiment shows robust improvement under the current split, because the multi-seed mean exceeds the rule test split on macro-F1 and balanced accuracy.")
    elif stats["test_macro_f1"]["mean"] > 0.442 and stats["test_balanced_accuracy"]["mean"] > 0.5:
        lines.append("MacBERT has potential but the result should remain preliminary until the sample size is expanded or cross-validation confirms the pattern.")
    else:
        lines.append("Current seed variance or low mean performance suggests this should be treated only as a preliminary shadow experiment.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    run_dir = ensure_run_dir(args.run_dir)
    gold_rows = index_by_id(read_csv(args.gold_test_csv))
    summaries, per_sample, metrics_by_seed = collect_runs(run_dir, args.seeds, gold_rows)
    v1 = load_json(args.v1_metrics)
    v2 = load_json(args.v2_metrics)
    rule_test = metric(next(iter(metrics_by_seed.values())), "test")  # placeholder for shape only
    del rule_test
    first_metrics = next(iter(metrics_by_seed.values()))
    baselines = {
        "majority_macro_f1": 0.442,
        "majority_balanced_accuracy": 0.500,
        "rule_full_macro_f1": first_metrics["baselines"]["rule_full_reference"]["macro"]["f1"],
        "rule_full_balanced_accuracy": first_metrics["baselines"]["rule_full_reference"]["balanced_accuracy"],
        "rule_test_macro_f1": first_metrics["baselines"]["rule_from_key"]["test"]["macro"]["f1"],
        "rule_test_balanced_accuracy": first_metrics["baselines"]["rule_from_key"]["test"]["balanced_accuracy"],
    }
    stability = build_stability(summaries, per_sample, baselines)
    payload = {
        "seeds": args.seeds,
        "summaries": summaries,
        "baselines": baselines,
        "stability": stability,
        "notes": {
            "trained_new_model_in_this_script": False,
            "modified_gold_or_split": False,
            "read_or_wrote_corpus_db": False,
            "connected_website": False,
        },
    }
    write_csv(run_dir / "multiseed_summary.csv", summaries, summary_fieldnames(), overwrite=args.overwrite)
    write_json(run_dir / "multiseed_summary.json", payload, overwrite=args.overwrite)
    write_text(run_dir / "bert_shadow_v3_multiseed_report.md", build_report(summaries, stability, baselines), overwrite=args.overwrite)
    write_text(run_dir / "bert_shadow_v3_stability_analysis.md", build_stability_analysis(stability), overwrite=args.overwrite)
    write_text(run_dir / "bert_shadow_v2_vs_v3_multiseed.md", build_v2_comparison(stability, v1, v2), overwrite=args.overwrite)
    print(f"wrote={run_dir}")
    print(f"seeds={len(summaries)}")
    print(f"mean_macro_f1={stability['mean_std']['test_macro_f1']['mean']:.6f}")
    print(f"mean_balanced_accuracy={stability['mean_std']['test_balanced_accuracy']['mean']:.6f}")
    print(f"all_yes_seeds={stability['all_yes_seeds']}")
    print(f"stable_fn={len(stability['stable_fn_ids'])}")
    print(f"stable_fp={len(stability['stable_fp_ids'])}")


if __name__ == "__main__":
    main()
