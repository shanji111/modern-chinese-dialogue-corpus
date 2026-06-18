"""Evaluate heuristic rule behavior against filled blind annotations.

This report treats the current rule system as a resonance detector and trigger
set. It does not treat individual `has_*` columns as supervised classifiers for
human mechanism labels.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from io_utils import artifact_path, read_csv, write_json, write_text
from sample_pairs import FLAG_COLUMNS


CORE_LABEL_COLUMNS = (
    "label_reproduction",
    "label_parallelism",
    "label_selective_reuse",
    "label_repair",
    "label_contrast",
)
ANALOGY_COLUMN = "label_analogy_candidate"
RESONANCE_VALUES = {"yes", "no", "uncertain"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, help="Filled blind annotation CSV or merged CSV.")
    parser.add_argument("--key", default="", help="Optional evaluation key CSV produced by split_blind_annotation.py.")
    parser.add_argument(
        "--output-md",
        default=str(artifact_path("reports", "rule_baseline_report.md")),
        help="Markdown report path.",
    )
    parser.add_argument(
        "--output-json",
        default=str(artifact_path("reports", "rule_baseline_report.json")),
        help="JSON report path.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing report artifacts.")
    return parser.parse_args()


def parse_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def parse_label(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"1", "0", "?"} else ""


def resonance_value(row: dict[str, str]) -> str:
    value = str(row.get("resonance_present") or "").strip().lower()
    return value if value in RESONANCE_VALUES else ""


def merge_with_key(annotation_rows: list[dict[str, str]], key_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    key_by_annotation = {row.get("annotation_id", ""): row for row in key_rows if row.get("annotation_id")}
    key_by_pair = {row.get("pair_id", ""): row for row in key_rows if row.get("pair_id")}
    merged = []
    for row in annotation_rows:
        key = key_by_annotation.get(row.get("annotation_id", "")) or key_by_pair.get(row.get("pair_id", "")) or {}
        merged.append({**key, **row})
    return merged


def load_rows(annotations_path: str, key_path: str = "") -> list[dict[str, str]]:
    annotation_rows = read_csv(annotations_path)
    if not key_path:
        return annotation_rows
    return merge_with_key(annotation_rows, read_csv(key_path))


def rule_any_positive(row: dict[str, str]) -> bool:
    if "rule_any_positive" in row and str(row.get("rule_any_positive", "")).strip() != "":
        return parse_bool(row.get("rule_any_positive"))
    return any(parse_bool(row.get(flag)) for flag in FLAG_COLUMNS)


def binary_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, float | int]:
    tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth and pred)
    fp = sum(1 for truth, pred in zip(y_true, y_pred) if not truth and pred)
    fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth and not pred)
    tn = sum(1 for truth, pred in zip(y_true, y_pred) if not truth and not pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "support": tp + fn,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def proportion(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def label_rate(rows: list[dict[str, str]], label_column: str) -> dict[str, float | int]:
    labeled = [row for row in rows if parse_label(row.get(label_column)) in {"1", "0"}]
    positives = sum(1 for row in labeled if parse_label(row.get(label_column)) == "1")
    return {
        "positive": positives,
        "denominator": len(labeled),
        "rate": proportion(positives, len(labeled)),
        "unknown": sum(1 for row in rows if parse_label(row.get(label_column)) == "?"),
    }


def trigger_analysis(rows: list[dict[str, str]]) -> dict[str, object]:
    analysis = {}
    for flag in FLAG_COLUMNS:
        triggered = [row for row in rows if parse_bool(row.get(flag))]
        yes = sum(1 for row in triggered if resonance_value(row) == "yes")
        no = sum(1 for row in triggered if resonance_value(row) == "no")
        uncertain = sum(1 for row in triggered if resonance_value(row) == "uncertain")
        mechanism_rates = {
            label: label_rate(triggered, label)
            for label in CORE_LABEL_COLUMNS
        }
        mechanism_rates[ANALOGY_COLUMN] = label_rate(triggered, ANALOGY_COLUMN)
        analysis[flag] = {
            "triggered_count": len(triggered),
            "resonance_yes": yes,
            "resonance_no": no,
            "resonance_uncertain": uncertain,
            "resonance_yes_rate_excluding_uncertain": proportion(yes, yes + no),
            "mechanism_label_rates": mechanism_rates,
        }
    return analysis


def uncertain_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    uncertain = [row for row in rows if resonance_value(row) == "uncertain"]
    return {
        "count": len(uncertain),
        "rule_positive": sum(1 for row in uncertain if rule_any_positive(row)),
        "by_flag": {
            flag: sum(1 for row in uncertain if parse_bool(row.get(flag)))
            for flag in FLAG_COLUMNS
        },
    }


def analogy_summary(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "positive": sum(1 for row in rows if parse_label(row.get(ANALOGY_COLUMN)) == "1"),
        "negative": sum(1 for row in rows if parse_label(row.get(ANALOGY_COLUMN)) == "0"),
        "uncertain": sum(1 for row in rows if parse_label(row.get(ANALOGY_COLUMN)) == "?"),
    }


def evaluate(rows: list[dict[str, str]]) -> dict[str, object]:
    yes_no_rows = [row for row in rows if resonance_value(row) in {"yes", "no"}]
    y_true = [resonance_value(row) == "yes" for row in yes_no_rows]
    y_pred = [rule_any_positive(row) for row in yes_no_rows]
    return {
        "row_count": len(rows),
        "yes_no_row_count": len(yes_no_rows),
        "uncertain_row_count": sum(1 for row in rows if resonance_value(row) == "uncertain"),
        "invalid_or_blank_resonance_count": sum(1 for row in rows if resonance_value(row) == ""),
        "overall_rule_any_positive_vs_resonance": binary_metrics(y_true, y_pred),
        "trigger_analysis": trigger_analysis(rows),
        "uncertain_summary": uncertain_summary(rows),
        "analogy_candidate_summary": analogy_summary(rows),
        "core_labels": list(CORE_LABEL_COLUMNS),
        "excluded_from_core_f1": [ANALOGY_COLUMN, "resonance_present=uncertain"],
    }


def format_float(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:.3f}"


def build_markdown_report(report: dict[str, object]) -> str:
    overall = report["overall_rule_any_positive_vs_resonance"]
    lines = [
        "# Rule Calibration Report",
        "",
        "This report evaluates rules as heuristic triggers, not as direct supervised mechanism classifiers.",
        "",
        f"Rows in CSV: {report['row_count']}",
        f"Rows used for main yes/no binary metrics: {report['yes_no_row_count']}",
        f"Uncertain rows excluded from main binary metrics: {report['uncertain_row_count']}",
        f"Invalid or blank `resonance_present` rows: {report['invalid_or_blank_resonance_count']}",
        "",
        "## Overall Rule Detection",
        "",
        "`rule_any_positive` is compared with `resonance_present=yes/no`. `uncertain` rows are excluded.",
        "",
        "| precision | recall | f1 | support | tp | fp | fn | tn |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| {precision} | {recall} | {f1} | {support} | {tp} | {fp} | {fn} | {tn} |".format(
            **{key: format_float(value) for key, value in overall.items()}
        ),
        "",
        "## Single Rule Trigger Analysis",
        "",
        "Rows are grouped by each `has_*` trigger. Mechanism rates are conditional descriptive rates, not per-label F1.",
        "",
        "| trigger | count | resonance yes | resonance no | uncertain | yes rate excl. uncertain | reproduction | parallelism | selective reuse | repair | contrast | analogy candidate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for flag, data in report["trigger_analysis"].items():
        rates = data["mechanism_label_rates"]
        lines.append(
            f"| {flag} | {data['triggered_count']} | {data['resonance_yes']} | {data['resonance_no']} | "
            f"{data['resonance_uncertain']} | {data['resonance_yes_rate_excluding_uncertain']:.3f} | "
            f"{rates['label_reproduction']['rate']:.3f} | {rates['label_parallelism']['rate']:.3f} | "
            f"{rates['label_selective_reuse']['rate']:.3f} | {rates['label_repair']['rate']:.3f} | "
            f"{rates['label_contrast']['rate']:.3f} | {rates['label_analogy_candidate']['rate']:.3f} |"
        )
    uncertain = report["uncertain_summary"]
    analogy = report["analogy_candidate_summary"]
    lines.extend([
        "",
        "## Uncertain Rows",
        "",
        f"- Count: {uncertain['count']}",
        f"- Rule-positive among uncertain: {uncertain['rule_positive']}",
        f"- Trigger distribution: {uncertain['by_flag']}",
        "",
        "## Analogy Candidate",
        "",
        "`label_analogy_candidate` is reported separately and excluded from core rule F1.",
        "",
        f"- Positive: {analogy['positive']}",
        f"- Negative: {analogy['negative']}",
        f"- Uncertain: {analogy['uncertain']}",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    rows = load_rows(args.annotations, args.key)
    report = evaluate(rows)
    output_md = write_text(Path(args.output_md), build_markdown_report(report), overwrite=args.overwrite)
    output_json = write_json(args.output_json, report, overwrite=args.overwrite)
    print(build_markdown_report(report))
    print(f"wrote_md={output_md}")
    print(f"wrote_json={output_json}")


if __name__ == "__main__":
    main()
