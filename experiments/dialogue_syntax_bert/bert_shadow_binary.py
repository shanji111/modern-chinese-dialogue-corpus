"""Offline BERT shadow experiment for binary dialogue-resonance detection."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import platform
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ARTIFACTS_DIR, artifact_path, ensure_can_write, read_csv, write_csv, write_json, write_text


DEFAULT_OUTPUT_DIR = artifact_path("formal_300_v1", "bert_shadow_v1")
LABEL_TO_INT = {"no": 0, "yes": 1}
INT_TO_LABEL = {0: "no", 1: "yes"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-name-or-path", required=True, help="Local Hugging Face model path. No downloads are used.")
    parser.add_argument(
        "--train-csv",
        default=str(artifact_path("formal_300_v1", "baselines", "gold_v1_binary_train.csv")),
    )
    parser.add_argument(
        "--dev-csv",
        default=str(artifact_path("formal_300_v1", "baselines", "gold_v1_binary_dev.csv")),
    )
    parser.add_argument(
        "--test-csv",
        default=str(artifact_path("formal_300_v1", "baselines", "gold_v1_binary_test.csv")),
    )
    parser.add_argument(
        "--evaluation-key",
        default=str(artifact_path("formal_300_v1", "formal_300_v1_evaluation_key.csv")),
    )
    parser.add_argument(
        "--metrics-audit-json",
        default=str(artifact_path("formal_300_v1", "baselines", "baseline_metrics_audit.json")),
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--experiment-name", default="bert_shadow_v1", help="Prefix for metrics/report artifact names.")
    parser.add_argument(
        "--comparison-metrics-json",
        default="",
        help="Optional previous shadow metrics JSON for v1/v2 comparison report.",
    )
    parser.add_argument(
        "--write-canonical-aliases",
        action="store_true",
        help="Also write metrics.json and report.md aliases in the output directory.",
    )
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=20260621)
    parser.add_argument("--early-stopping-patience", type=int, default=2)
    parser.add_argument("--use-class-weight", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting shadow experiment artifacts.")
    return parser.parse_args()


def artifact_output_dir(path: str | Path) -> Path:
    output_dir = Path(path)
    artifacts_root = ARTIFACTS_DIR.resolve()
    try:
        output_dir.resolve().relative_to(artifacts_root)
    except ValueError as exc:
        raise SystemExit(f"Output directory must be under {artifacts_root}: {output_dir}") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def parse_bool(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def load_split(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_csv(path):
        label_text = (row.get("resonance_present") or "").strip()
        if label_text not in LABEL_TO_INT:
            raise SystemExit(f"Binary split contains non-binary label {label_text!r}: {path}")
        enriched: dict[str, Any] = dict(row)
        enriched["label"] = LABEL_TO_INT[label_text]
        rows.append(enriched)
    if not rows:
        raise SystemExit(f"Split is empty: {path}")
    return rows


def load_evaluation_key(path: str | Path) -> dict[str, dict[str, str]]:
    key_path = Path(path)
    if not key_path.exists():
        return {}
    return {row["annotation_id"]: row for row in read_csv(key_path)}


def safe_float(value: float) -> float:
    return value if math.isfinite(value) else 0.0


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def binary_metrics(truth: list[int], pred: list[int]) -> dict[str, Any]:
    if len(truth) != len(pred):
        raise ValueError("truth and prediction lengths differ")
    tp = sum(1 for y, p in zip(truth, pred) if y == 1 and p == 1)
    fp = sum(1 for y, p in zip(truth, pred) if y == 0 and p == 1)
    fn = sum(1 for y, p in zip(truth, pred) if y == 1 and p == 0)
    tn = sum(1 for y, p in zip(truth, pred) if y == 0 and p == 0)
    positive = prf(tp, fp, fn)
    no_class = prf(tn, fn, fp)
    support_yes = sum(1 for y in truth if y == 1)
    support_no = sum(1 for y in truth if y == 0)
    total = len(truth)
    macro_precision = (positive["precision"] + no_class["precision"]) / 2
    macro_recall = (positive["recall"] + no_class["recall"]) / 2
    macro_f1 = (positive["f1"] + no_class["f1"]) / 2
    weighted_f1 = (
        (positive["f1"] * support_yes + no_class["f1"] * support_no) / total
        if total
        else 0.0
    )
    return {
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "support": {"yes": support_yes, "no": support_no, "total": total},
        "accuracy": (tp + tn) / total if total else 0.0,
        "positive_class": positive,
        "no_class": no_class,
        "macro": {"precision": macro_precision, "recall": macro_recall, "f1": macro_f1},
        "weighted_f1": weighted_f1,
        "balanced_accuracy": macro_recall,
    }


def metrics_from_threshold(rows: list[dict[str, Any]], threshold: float, score_key: str = "prob_yes") -> dict[str, Any]:
    truth = [int(row["label"]) for row in rows]
    pred = [1 if float(row[score_key]) >= threshold else 0 for row in rows]
    metrics = binary_metrics(truth, pred)
    metrics["threshold"] = threshold
    return metrics


def threshold_candidates(rows: list[dict[str, Any]]) -> list[float]:
    values = {0.0, 0.5, 1.0}
    for row in rows:
        score = float(row["prob_yes"])
        values.add(max(0.0, min(1.0, score)))
    return sorted(values)


def select_threshold(dev_rows: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    best_threshold = 0.5
    best_metrics = metrics_from_threshold(dev_rows, best_threshold)

    def sort_key(item: tuple[float, dict[str, Any]]) -> tuple[float, float, float, float, float]:
        threshold, metrics = item
        return (
            metrics["macro"]["f1"],
            metrics["balanced_accuracy"],
            metrics["no_class"]["recall"],
            metrics["positive_class"]["f1"],
            -abs(threshold - 0.5),
        )

    best_threshold, best_metrics = max(
        ((threshold, metrics_from_threshold(dev_rows, threshold)) for threshold in threshold_candidates(dev_rows)),
        key=sort_key,
    )
    return best_threshold, best_metrics


def pr_curve(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    truth = [int(row["label"]) for row in rows]
    curve = []
    for threshold in threshold_candidates(rows):
        pred = [1 if float(row["prob_yes"]) >= threshold else 0 for row in rows]
        metrics = binary_metrics(truth, pred)
        curve.append(
            {
                "threshold": threshold,
                "precision": metrics["positive_class"]["precision"],
                "recall": metrics["positive_class"]["recall"],
                "f1": metrics["positive_class"]["f1"],
            }
        )
    return curve


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[str(row.get(field) or "")] += 1
    return dict(sorted(counts.items()))


def attach_rule_fields(rows: list[dict[str, Any]], evaluation_key: dict[str, dict[str, str]]) -> None:
    for row in rows:
        key = evaluation_key.get(str(row.get("annotation_id")))
        if not key:
            row["rule_any_positive"] = ""
            row["rule_summary"] = ""
            continue
        row["rule_any_positive"] = key.get("rule_any_positive", "")
        row["rule_summary"] = key.get("rule_summary", "")
        for name in [
            "has_lexical_echo",
            "has_pattern_reuse",
            "has_question_response",
            "has_negation_turn",
            "has_repair_repetition",
            "shared_terms",
            "markers",
        ]:
            row[name] = key.get(name, "")


def rule_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keyed = [row for row in rows if str(row.get("rule_any_positive", "")).strip() != ""]
    if not keyed:
        return {"available": False}
    truth = [int(row["label"]) for row in keyed]
    pred = [1 if parse_bool(row.get("rule_any_positive")) else 0 for row in keyed]
    metrics = binary_metrics(truth, pred)
    metrics["available"] = True
    return metrics


def false_negative_type(row: dict[str, Any]) -> str:
    note = " ".join(
        str(row.get(column) or "")
        for column in [
            "evidence_span_a",
            "evidence_span_b",
            "annotator_note",
            "uncertainty_reason",
            "turn_a",
            "turn_b",
        ]
    )
    if parse_bool(row.get("label_analogy_candidate")):
        return "analogy"
    if any(token in note for token in ["这", "此", "那个", "他", "她", "它", "指回", "指称"]):
        return "demonstrative_or_reference"
    if any(token in note for token in ["填入", "填补", "槽位", "什么", "怎样", "如何", "何以", "为何", "谁", "哪里", "多少"]):
        return "slot_filling"
    if any(token in note for token in ["短答", "没事", "对", "是的", "不是", "可以", "愿闻"]):
        return "short_answer"
    return "semantic_selection"


def compare_with_rule(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    rule_fn_rows = [
        row
        for row in rows
        if int(row["label"]) == 1 and str(row.get("rule_any_positive", "")).strip() != "" and not parse_bool(row.get("rule_any_positive"))
    ]
    bert_recovered = [
        row
        for row in rule_fn_rows
        if float(row["prob_yes"]) >= threshold
    ]
    bert_fp_rows = [
        row
        for row in rows
        if int(row["label"]) == 0 and float(row["prob_yes"]) >= threshold
    ]
    new_fp_rows = [
        row
        for row in bert_fp_rows
        if str(row.get("rule_any_positive", "")).strip() != "" and not parse_bool(row.get("rule_any_positive"))
    ]
    return {
        "threshold": threshold,
        "rule_false_negative_total": len(rule_fn_rows),
        "rule_false_negative_recovered_by_bert": len(bert_recovered),
        "bert_false_positive_total": len(bert_fp_rows),
        "bert_false_positive_not_rule_positive": len(new_fp_rows),
        "recovered_annotation_ids": [row.get("annotation_id") for row in bert_recovered],
        "new_false_positive_annotation_ids": [row.get("annotation_id") for row in new_fp_rows],
        "rule_fn_type_counts": dict(Counter(false_negative_type(row) for row in rule_fn_rows)),
        "recovered_type_counts": dict(Counter(false_negative_type(row) for row in bert_recovered)),
    }


def add_predictions(rows: list[dict[str, Any]], probabilities: list[float], threshold_05: float, selected_threshold: float) -> None:
    for row, prob in zip(rows, probabilities):
        row["prob_yes"] = safe_float(float(prob))
        row["pred_0_5"] = "yes" if float(prob) >= threshold_05 else "no"
        row["pred_dev_threshold"] = "yes" if float(prob) >= selected_threshold else "no"


def prediction_rows(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        output.append(
            {
                "annotation_id": row.get("annotation_id", ""),
                "pair_id": row.get("pair_id", ""),
                "source": row.get("source", ""),
                "dataset_name": row.get("dataset_name", ""),
                "sample_stratum": row.get("sample_stratum", ""),
                "turn_a": row.get("turn_a", ""),
                "turn_b": row.get("turn_b", ""),
                "gold_label": row.get("resonance_present", ""),
                "binary_label": row.get("binary_label", ""),
                "prob_yes": row.get("prob_yes", ""),
                "pred_0_5": row.get("pred_0_5", ""),
                "pred_dev_threshold": row.get("pred_dev_threshold", ""),
                "rule_any_positive": row.get("rule_any_positive", ""),
                "rule_summary": row.get("rule_summary", ""),
                "has_lexical_echo": row.get("has_lexical_echo", ""),
                "has_pattern_reuse": row.get("has_pattern_reuse", ""),
                "has_question_response": row.get("has_question_response", ""),
                "has_negation_turn": row.get("has_negation_turn", ""),
                "has_repair_repetition": row.get("has_repair_repetition", ""),
                "evidence_span_a": row.get("evidence_span_a", ""),
                "evidence_span_b": row.get("evidence_span_b", ""),
                "error_0_5": int(row["label"]) != (1 if row.get("pred_0_5") == "yes" else 0),
                "error_dev_threshold": int(row["label"]) != (1 if row.get("pred_dev_threshold") == "yes" else 0),
            }
        )
    return output


class PairDataset:
    def __init__(self, rows: list[dict[str, Any]], tokenizer: Any, max_length: int):
        self.rows = rows
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = self.rows[index]
        encoded = self.tokenizer(
            str(row.get("turn_a") or ""),
            str(row.get("turn_b") or ""),
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["labels"] = int(row["label"])
        return item


def collate_batch(batch: list[dict[str, Any]]) -> dict[str, Any]:
    import torch

    output: dict[str, Any] = {}
    for key in batch[0]:
        if key == "labels":
            output[key] = torch.tensor([item[key] for item in batch], dtype=torch.long)
        else:
            output[key] = torch.stack([item[key] for item in batch])
    return output


def predict_probabilities(model: Any, loader: Any, device: Any) -> list[float]:
    import torch

    model.eval()
    probabilities: list[float] = []
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels")
            del labels
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(**batch)
            probs = torch.softmax(outputs.logits, dim=-1)[:, 1]
            probabilities.extend(float(value) for value in probs.cpu().tolist())
    return probabilities


def write_env_report(
    output_dir: Path,
    *,
    args: argparse.Namespace,
    status: str,
    message: str,
    model_loaded: bool,
    torch_version: str = "",
    transformers_version: str = "",
    device: str = "",
    overwrite: bool | None = None,
) -> None:
    lines = [
        "# BERT Shadow v1 Environment Report",
        "",
        "This is an offline shadow experiment report. It does not connect to the website, does not deploy, and does not read or write the formal corpus database.",
        "",
        f"- Status: {status}",
        f"- Message: {message}",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Python: {platform.python_version()}",
        f"- Platform: {platform.platform()}",
        f"- Torch: {torch_version or 'not loaded'}",
        f"- Transformers: {transformers_version or 'not loaded'}",
        f"- Device: {device or 'not selected'}",
        f"- Model path: `{args.model_name_or_path}`",
        f"- Model loaded: {model_loaded}",
        f"- Train CSV: `{args.train_csv}`",
        f"- Dev CSV: `{args.dev_csv}`",
        f"- Test CSV: `{args.test_csv}`",
        f"- Output dir: `{args.output_dir}`",
        "",
        "Safety notes:",
        "",
        "- No internet download is attempted; `local_files_only=True` and offline environment variables are used.",
        "- Frozen gold files and split CSVs are read only.",
        "- Test split is used only after training/threshold selection.",
    ]
    write_text(
        output_dir / "env_report.md",
        "\n".join(lines) + "\n",
        overwrite=args.overwrite if overwrite is None else overwrite,
    )


def format_metrics(metrics: dict[str, Any]) -> str:
    matrix = metrics["confusion_matrix"]
    return (
        f"accuracy={metrics['accuracy']:.3f}, "
        f"positive_f1={metrics['positive_class']['f1']:.3f}, "
        f"macro_f1={metrics['macro']['f1']:.3f}, "
        f"balanced_accuracy={metrics['balanced_accuracy']:.3f}, "
        f"no_recall={metrics['no_class']['recall']:.3f}, "
        f"TP={matrix['tp']}, FP={matrix['fp']}, FN={matrix['fn']}, TN={matrix['tn']}"
    )


def markdown_table(rows: list[list[object]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    sep = ["---"] * len(header)
    lines = [
        "| " + " | ".join(str(value) for value in header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def build_report(
    *,
    args: argparse.Namespace,
    train_rows: list[dict[str, Any]],
    dev_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    history: list[dict[str, Any]],
    metrics_payload: dict[str, Any],
    baselines: dict[str, Any],
) -> str:
    selected_threshold = metrics_payload["thresholds"]["dev_selected_threshold"]
    dev_selected = metrics_payload["dev"]["dev_selected_threshold"]
    test_selected = metrics_payload["test"]["dev_selected_threshold"]
    test_05 = metrics_payload["test"]["threshold_0_5"]
    lines = [
        f"# {args.experiment_name} Report",
        "",
        "本报告是离线 shadow experiment：未接入网站，未部署，未修改正式数据库，未修改 frozen gold 文件，也未修改 train/dev/test split。Test split 只用于最终评估。",
        "",
        "BERT 结果不能只看 positive F1；本报告同步报告 macro-F1、balanced accuracy 和 no-class recall。如果模型全预测 yes，则视为失败或无效改进。",
        "",
        "## Configuration",
        "",
        f"- Model path: `{args.model_name_or_path}`",
        f"- Train/dev/test rows: {len(train_rows)} / {len(dev_rows)} / {len(test_rows)}",
        f"- max_length: {args.max_length}",
        f"- batch_size: {args.batch_size}",
        f"- epochs requested: {args.epochs}",
        f"- learning_rate: {args.learning_rate}",
        f"- weight_decay: {args.weight_decay}",
        f"- seed: {args.seed}",
        f"- class_weight: {args.use_class_weight}",
        f"- selected threshold from dev: {selected_threshold:.6f}",
        "",
        "## Results",
        "",
        "### Dev",
        "",
        f"- threshold 0.5: {format_metrics(metrics_payload['dev']['threshold_0_5'])}",
        f"- dev-selected threshold: {format_metrics(dev_selected)}",
        "",
        "### Test",
        "",
        f"- threshold 0.5: {format_metrics(test_05)}",
        f"- dev-selected threshold: {format_metrics(test_selected)}",
        "",
        "## Baseline Comparison",
        "",
    ]

    comparison_rows = [["System", "Split", "Macro-F1", "Balanced Acc.", "No Recall", "Positive F1"]]
    for name in ["majority", "similarity", "rule_from_key"]:
        baseline = baselines.get(name, {})
        split_metrics = baseline.get("test")
        if split_metrics:
            comparison_rows.append(
                [
                    name,
                    "test",
                    f"{split_metrics['macro']['f1']:.3f}",
                    f"{split_metrics['balanced_accuracy']:.3f}",
                    f"{split_metrics['no_class']['recall']:.3f}",
                    f"{split_metrics['positive_class']['f1']:.3f}",
                ]
            )
    comparison_rows.append(
        [
            args.experiment_name,
            "test",
            f"{test_selected['macro']['f1']:.3f}",
            f"{test_selected['balanced_accuracy']:.3f}",
            f"{test_selected['no_class']['recall']:.3f}",
            f"{test_selected['positive_class']['f1']:.3f}",
        ]
    )
    lines.extend([markdown_table(comparison_rows), ""])

    full_rule = baselines.get("rule_full_reference")
    if full_rule:
        lines.extend(
            [
                "Full-set rule baseline reference:",
                "",
                f"- macro-F1={full_rule['macro']['f1']:.3f}, balanced_accuracy={full_rule['balanced_accuracy']:.3f}, no-class recall={full_rule['no_class']['recall']:.3f}, positive F1={full_rule['positive_class']['f1']:.3f}",
                "",
            ]
        )

    rule_compare = metrics_payload["rule_vs_bert"]["test_dev_selected_threshold"]
    lines.extend(
        [
            "## Rule False Negative Recovery",
            "",
            f"- Rule false negatives on test: {rule_compare['rule_false_negative_total']}",
            f"- Recovered by BERT at dev-selected threshold: {rule_compare['rule_false_negative_recovered_by_bert']}",
            f"- BERT false positives on test: {rule_compare['bert_false_positive_total']}",
            f"- BERT false positives not already rule-positive: {rule_compare['bert_false_positive_not_rule_positive']}",
            f"- Rule FN type counts: `{json.dumps(rule_compare['rule_fn_type_counts'], ensure_ascii=False)}`",
            f"- Recovered type counts: `{json.dumps(rule_compare['recovered_type_counts'], ensure_ascii=False)}`",
            "",
            "## Training History",
            "",
        ]
    )
    history_rows = [["Epoch", "Train Loss", "Dev Macro-F1@0.5", "Dev Balanced Acc.@0.5", "Dev No Recall@0.5"]]
    for item in history:
        dev = item["dev_threshold_0_5"]
        history_rows.append(
            [
                item["epoch"],
                f"{item['train_loss']:.4f}",
                f"{dev['macro']['f1']:.3f}",
                f"{dev['balanced_accuracy']:.3f}",
                f"{dev['no_class']['recall']:.3f}",
            ]
        )
    lines.append(markdown_table(history_rows))
    lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "- Majority/similarity baselines are all-yes style references; beating them on positive F1 alone is not meaningful.",
            "- A useful BERT shadow result should improve macro-F1 and balanced accuracy while keeping no-class recall above zero.",
            "- This run should remain offline and should not be routed into the production website without a separate design and safety review.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_error_analysis(rows: list[dict[str, Any]], threshold: float, title: str) -> str:
    false_negatives = [
        row for row in rows if int(row["label"]) == 1 and float(row["prob_yes"]) < threshold
    ]
    false_positives = [
        row for row in rows if int(row["label"]) == 0 and float(row["prob_yes"]) >= threshold
    ]
    lines = [
        f"# {title}",
        "",
        f"- Threshold: {threshold:.6f}",
        f"- False negatives: {len(false_negatives)}",
        f"- False positives: {len(false_positives)}",
        "",
        "## False Negatives",
        "",
    ]
    for row in false_negatives[:50]:
        lines.extend(
            [
                f"### {row.get('annotation_id')} prob_yes={float(row['prob_yes']):.4f} risk={false_negative_type(row)}",
                "",
                f"- A: {row.get('turn_a', '')}",
                f"- B: {row.get('turn_b', '')}",
                f"- Evidence A/B: {row.get('evidence_span_a', '')} / {row.get('evidence_span_b', '')}",
                f"- Rule: {row.get('rule_summary', '')}",
                "",
            ]
        )
    lines.extend(["## False Positives", ""])
    for row in false_positives[:50]:
        lines.extend(
            [
                f"### {row.get('annotation_id')} prob_yes={float(row['prob_yes']):.4f}",
                "",
                f"- A: {row.get('turn_a', '')}",
                f"- B: {row.get('turn_b', '')}",
                f"- Rule: {row.get('rule_summary', '')}",
                "",
            ]
        )
    return "\n".join(lines)


def build_rule_comparison(metrics_payload: dict[str, Any], baselines: dict[str, Any]) -> str:
    test = metrics_payload["test"]["dev_selected_threshold"]
    rule_compare = metrics_payload["rule_vs_bert"]["test_dev_selected_threshold"]
    rule_test = baselines.get("rule_from_key", {}).get("test")
    lines = [
        "# Rule vs BERT Comparison",
        "",
        "This is a shadow comparison only. It does not replace the rule graph or connect BERT to the website.",
        "",
        "## Test Metrics",
        "",
        f"- BERT dev-selected threshold: {metrics_payload['thresholds']['dev_selected_threshold']:.6f}",
        f"- BERT: {format_metrics(test)}",
    ]
    if rule_test:
        lines.append(f"- Rule on the same test split: {format_metrics(rule_test)}")
    lines.extend(
        [
            "",
            "## Recovery And New Errors",
            "",
            f"- Rule false negatives on test: {rule_compare['rule_false_negative_total']}",
            f"- BERT recovered rule false negatives: {rule_compare['rule_false_negative_recovered_by_bert']}",
            f"- BERT false positives: {rule_compare['bert_false_positive_total']}",
            f"- BERT false positives not already rule-positive: {rule_compare['bert_false_positive_not_rule_positive']}",
            f"- Recovered IDs: {', '.join(str(item) for item in rule_compare['recovered_annotation_ids']) or '(none)'}",
            f"- New FP IDs: {', '.join(str(item) for item in rule_compare['new_false_positive_annotation_ids']) or '(none)'}",
            "",
            "## Notes",
            "",
            "- Rule precision is interpretable and remains valuable even if recall is limited.",
            "- BERT is useful only if it recovers hidden resonance without collapsing into all-yes predictions.",
        ]
    )
    return "\n".join(lines) + "\n"


def metric_cell(metrics: dict[str, Any], path: list[str], default: object = "") -> object:
    current: object = metrics
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def build_shadow_comparison(current: dict[str, Any], previous: dict[str, Any], previous_name: str = "bert_shadow_v1") -> str:
    current_name = str(current.get("experiment") or "current")
    current_test = current["test"]["dev_selected_threshold"]
    previous_test = previous.get("test", {}).get("dev_selected_threshold", {})
    current_rule = current["rule_vs_bert"]["test_dev_selected_threshold"]
    previous_rule = previous.get("rule_vs_bert", {}).get("test_dev_selected_threshold", {})

    rows = [
        ["Metric", previous_name, current_name],
        ["dev-selected threshold", f"{metric_cell(previous, ['thresholds', 'dev_selected_threshold'], 0):.6f}", f"{metric_cell(current, ['thresholds', 'dev_selected_threshold'], 0):.6f}"],
        ["test macro-F1", f"{metric_cell(previous_test, ['macro', 'f1'], 0):.3f}", f"{current_test['macro']['f1']:.3f}"],
        ["test balanced accuracy", f"{metric_cell(previous_test, ['balanced_accuracy'], 0):.3f}", f"{current_test['balanced_accuracy']:.3f}"],
        ["test no-class recall", f"{metric_cell(previous_test, ['no_class', 'recall'], 0):.3f}", f"{current_test['no_class']['recall']:.3f}"],
        ["test positive F1", f"{metric_cell(previous_test, ['positive_class', 'f1'], 0):.3f}", f"{current_test['positive_class']['f1']:.3f}"],
        ["TP/FP/FN/TN", "/".join(str(metric_cell(previous_test, ['confusion_matrix', key], 0)) for key in ["tp", "fp", "fn", "tn"]), "/".join(str(current_test["confusion_matrix"][key]) for key in ["tp", "fp", "fn", "tn"])],
        ["rule FN recovered", str(metric_cell(previous_rule, ["rule_false_negative_recovered_by_bert"], 0)), str(current_rule["rule_false_negative_recovered_by_bert"])],
        ["BERT false positives", str(metric_cell(previous_rule, ["bert_false_positive_total"], 0)), str(current_rule["bert_false_positive_total"])],
        ["all-yes at dev threshold", str(metric_cell(previous, ["all_yes_check", "test_dev_selected_all_yes"], "")), str(current["all_yes_check"]["test_dev_selected_all_yes"])],
    ]
    lines = [
        "# BERT Shadow v1 vs v2 Comparison",
        "",
        "This comparison uses the dev-selected threshold for each shadow experiment. It is still a shadow-only analysis and is not connected to the website.",
        "",
        markdown_table(rows),
        "",
        "## Interpretation Checklist",
        "",
        "- Prefer macro-F1, balanced accuracy, and no-class recall over positive F1 alone.",
        "- A lower false-positive count is useful only if hidden rule false negatives are still recovered.",
        "- If the current run does not beat the rule baseline on macro-F1 or balanced accuracy, do not describe it as a successful replacement.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    output_dir = artifact_output_dir(args.output_dir)
    model_path = Path(args.model_name_or_path)
    if not model_path.exists():
        write_env_report(
            output_dir,
            args=args,
            status="stopped",
            message="Local model path was not found; no network download attempted.",
            model_loaded=False,
        )
        raise SystemExit(f"Local model path not found: {model_path}")

    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    try:
        import numpy as np
        import torch
        import transformers
        from torch.utils.data import DataLoader
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup
    except ModuleNotFoundError as exc:
        write_env_report(
            output_dir,
            args=args,
            status="stopped",
            message=f"Missing optional dependency: {exc.name}",
            model_loaded=False,
        )
        raise SystemExit(f"Missing optional dependency: {exc.name}") from exc

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_rows = load_split(args.train_csv)
    dev_rows = load_split(args.dev_csv)
    test_rows = load_split(args.test_csv)
    evaluation_key = load_evaluation_key(args.evaluation_key)
    for split_rows in [train_rows, dev_rows, test_rows]:
        attach_rule_fields(split_rows, evaluation_key)

    try:
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            str(model_path),
            num_labels=2,
            local_files_only=True,
        )
    except Exception as exc:  # noqa: BLE001 - write an environment report before stopping.
        write_env_report(
            output_dir,
            args=args,
            status="stopped",
            message=f"Model could not be loaded offline: {exc}",
            model_loaded=False,
            torch_version=torch.__version__,
            transformers_version=transformers.__version__,
            device=str(device),
        )
        raise

    write_env_report(
        output_dir,
        args=args,
        status="running",
        message="Local model loaded offline; training started.",
        model_loaded=True,
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        device=str(device),
    )

    train_dataset = PairDataset(train_rows, tokenizer, args.max_length)
    dev_dataset = PairDataset(dev_rows, tokenizer, args.max_length)
    test_dataset = PairDataset(test_rows, tokenizer, args.max_length)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, collate_fn=collate_batch)
    dev_loader = DataLoader(dev_dataset, batch_size=args.batch_size, shuffle=False, collate_fn=collate_batch)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False, collate_fn=collate_batch)

    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = max(1, len(train_loader) * args.epochs)
    warmup_steps = max(1, int(total_steps * 0.1))
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)
    label_counts = Counter(row["label"] for row in train_rows)
    class_weights = None
    if args.use_class_weight:
        total = len(train_rows)
        class_weights = torch.tensor(
            [
                total / (2 * max(1, label_counts.get(0, 0))),
                total / (2 * max(1, label_counts.get(1, 0))),
            ],
            dtype=torch.float,
            device=device,
        )
    loss_fn = torch.nn.CrossEntropyLoss(weight=class_weights)

    history: list[dict[str, Any]] = []
    best_state: dict[str, Any] | None = None
    best_score: tuple[float, float] = (-1.0, -1.0)
    stale_epochs = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total_batches = 0
        for batch in train_loader:
            labels = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            outputs = model(**batch)
            loss = loss_fn(outputs.logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += float(loss.item())
            total_batches += 1

        dev_probs = predict_probabilities(model, dev_loader, device)
        add_predictions(dev_rows, dev_probs, 0.5, 0.5)
        dev_metrics_05 = metrics_from_threshold(dev_rows, 0.5)
        score = (dev_metrics_05["macro"]["f1"], dev_metrics_05["balanced_accuracy"])
        history_item = {
            "epoch": epoch,
            "train_loss": total_loss / total_batches if total_batches else 0.0,
            "dev_threshold_0_5": dev_metrics_05,
        }
        history.append(history_item)
        print(json.dumps(history_item, ensure_ascii=False))
        if score > best_score:
            best_score = score
            best_state = copy.deepcopy(model.state_dict())
            stale_epochs = 0
        else:
            stale_epochs += 1
        if stale_epochs >= args.early_stopping_patience:
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    dev_probs = predict_probabilities(model, dev_loader, device)
    test_probs = predict_probabilities(model, test_loader, device)
    add_predictions(dev_rows, dev_probs, 0.5, 0.5)
    selected_threshold, dev_selected_metrics = select_threshold(dev_rows)
    add_predictions(dev_rows, dev_probs, 0.5, selected_threshold)
    add_predictions(test_rows, test_probs, 0.5, selected_threshold)

    dev_metrics_05 = metrics_from_threshold(dev_rows, 0.5)
    test_metrics_05 = metrics_from_threshold(test_rows, 0.5)
    test_selected_metrics = metrics_from_threshold(test_rows, selected_threshold)

    metrics_audit = {}
    audit_path = Path(args.metrics_audit_json)
    if audit_path.exists():
        metrics_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_baselines = metrics_audit.get("baselines", {}) if isinstance(metrics_audit, dict) else {}
    baselines = {
        "majority": audit_baselines.get("majority", {}).get("metrics", {}),
        "similarity": audit_baselines.get("similarity", {}).get("metrics", {}),
        "rule_audit": audit_baselines.get("rule", {}).get("metrics", {}),
        "rule_from_key": {
            "train": rule_metrics(train_rows),
            "dev": rule_metrics(dev_rows),
            "test": rule_metrics(test_rows),
        },
    }
    if audit_baselines.get("rule", {}).get("metrics", {}).get("full"):
        baselines["rule_full_reference"] = audit_baselines["rule"]["metrics"]["full"]

    metrics_payload = {
        "experiment": args.experiment_name,
        "shadow_experiment": True,
        "runs_bert": True,
        "trained_model": True,
        "model_path": str(model_path),
        "seed": args.seed,
        "thresholds": {
            "default_threshold": 0.5,
            "dev_selected_threshold": selected_threshold,
            "selection_metric": "dev macro-F1, then balanced accuracy, no-class recall, positive F1, closeness to 0.5",
        },
        "splits": {
            "train": distribution(train_rows, "resonance_present"),
            "dev": distribution(dev_rows, "resonance_present"),
            "test": distribution(test_rows, "resonance_present"),
        },
        "dev": {
            "threshold_0_5": dev_metrics_05,
            "dev_selected_threshold": dev_selected_metrics,
            "pr_curve": pr_curve(dev_rows),
        },
        "test": {
            "threshold_0_5": test_metrics_05,
            "dev_selected_threshold": test_selected_metrics,
            "pr_curve": pr_curve(test_rows),
        },
        "baselines": baselines,
        "rule_vs_bert": {
            "test_threshold_0_5": compare_with_rule(test_rows, 0.5),
            "test_dev_selected_threshold": compare_with_rule(test_rows, selected_threshold),
        },
        "all_yes_check": {
            "test_threshold_0_5_all_yes": test_metrics_05["confusion_matrix"]["tn"] == 0 and test_metrics_05["confusion_matrix"]["fn"] == 0,
            "test_dev_selected_all_yes": test_selected_metrics["confusion_matrix"]["tn"] == 0 and test_selected_metrics["confusion_matrix"]["fn"] == 0,
        },
        "history": history,
    }

    config = {
        "experiment_name": args.experiment_name,
        "model_name_or_path": str(model_path),
        "train_csv": args.train_csv,
        "dev_csv": args.dev_csv,
        "test_csv": args.test_csv,
        "evaluation_key": args.evaluation_key,
        "output_dir": args.output_dir,
        "max_length": args.max_length,
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "seed": args.seed,
        "early_stopping_patience": args.early_stopping_patience,
        "use_class_weight": args.use_class_weight,
        "class_counts_train": dict(label_counts),
        "device": str(device),
        "notes": [
            "Offline shadow experiment.",
            "No website route integration.",
            "No corpus.db access.",
            "Frozen gold and split files are read-only inputs.",
        ],
    }

    fieldnames = list(prediction_rows(dev_rows)[0].keys())
    write_json(output_dir / "train_config.json", config, overwrite=args.overwrite)
    write_csv(
        output_dir / "dev_predictions.csv",
        prediction_rows(dev_rows),
        fieldnames,
        overwrite=args.overwrite,
        force_overwrite_labels=True,
    )
    write_csv(
        output_dir / "test_predictions.csv",
        prediction_rows(test_rows),
        fieldnames,
        overwrite=args.overwrite,
        force_overwrite_labels=True,
    )
    write_json(output_dir / f"{args.experiment_name}_metrics.json", metrics_payload, overwrite=args.overwrite)
    if args.write_canonical_aliases:
        write_json(output_dir / "metrics.json", metrics_payload, overwrite=args.overwrite)
    report_text = build_report(
        args=args,
        train_rows=train_rows,
        dev_rows=dev_rows,
        test_rows=test_rows,
        history=history,
        metrics_payload=metrics_payload,
        baselines=baselines,
    )
    write_text(
        output_dir / f"{args.experiment_name}_report.md",
        report_text,
        overwrite=args.overwrite,
    )
    if args.write_canonical_aliases:
        write_text(output_dir / "report.md", report_text, overwrite=args.overwrite)
    write_text(
        output_dir / "error_analysis_fn_fp.md",
        build_error_analysis(test_rows, selected_threshold, f"{args.experiment_name} Error Analysis"),
        overwrite=args.overwrite,
    )
    write_text(
        output_dir / "rule_vs_bert_comparison.md",
        build_rule_comparison(metrics_payload, baselines),
        overwrite=args.overwrite,
    )
    if args.comparison_metrics_json:
        comparison_path = Path(args.comparison_metrics_json)
        if comparison_path.exists():
            previous_metrics = json.loads(comparison_path.read_text(encoding="utf-8"))
            write_text(
                output_dir / "v1_vs_v2_comparison.md",
                build_shadow_comparison(
                    metrics_payload,
                    previous_metrics,
                    str(previous_metrics.get("experiment") or comparison_path.stem),
                ),
                overwrite=args.overwrite,
            )
    write_env_report(
        output_dir,
        args=args,
        status="completed",
        message="Local offline BERT shadow training completed.",
        model_loaded=True,
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        device=str(device),
        overwrite=True,
    )
    print(f"wrote_output_dir={output_dir}")
    print(f"dev_selected_threshold={selected_threshold:.6f}")
    print(f"test_dev_threshold_macro_f1={test_selected_metrics['macro']['f1']:.6f}")
    print(f"test_dev_threshold_balanced_accuracy={test_selected_metrics['balanced_accuracy']:.6f}")
    print(f"test_dev_threshold_no_recall={test_selected_metrics['no_class']['recall']:.6f}")


if __name__ == "__main__":
    main()
