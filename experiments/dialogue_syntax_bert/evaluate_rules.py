"""Evaluate current rule labels against a human annotation CSV."""

from __future__ import annotations

import argparse
from pathlib import Path

from io_utils import artifact_path, read_csv, write_json
from labels import ALL_LABEL_KEYS, POSITIVE_LABEL_KEYS, human_labels_from_row, parse_bool, rule_labels_from_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, help="CSV produced by sample_pairs.py and filled by annotators.")
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
    parser.add_argument(
        "--include-unlabeled",
        action="store_true",
        help="Treat rows with no human labels as all-negative instead of skipping them.",
    )
    return parser.parse_args()


def has_any_human_label(row: dict[str, object]) -> bool:
    return any(parse_bool(row.get(f"label_{label_key}")) for label_key in ALL_LABEL_KEYS)


def get_rule_predictions(row: dict[str, object]) -> dict[str, bool]:
    if any(f"rule_{label_key}" in row for label_key in ALL_LABEL_KEYS):
        predictions = {
            label_key: parse_bool(row.get(f"rule_{label_key}"))
            for label_key in POSITIVE_LABEL_KEYS
        }
        predictions["no_relation"] = not any(predictions.values())
        return predictions
    return rule_labels_from_row(row)


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


def evaluate(rows: list[dict[str, str]], include_unlabeled: bool = False) -> dict[str, object]:
    labeled_rows = [
        row for row in rows
        if include_unlabeled or has_any_human_label(row)
    ]
    per_label = {}
    for label_key in ALL_LABEL_KEYS:
        y_true = []
        y_pred = []
        for row in labeled_rows:
            human = human_labels_from_row(row)
            rule = get_rule_predictions(row)
            y_true.append(human[label_key])
            y_pred.append(rule[label_key])
        per_label[label_key] = binary_metrics(y_true, y_pred)

    micro_true = []
    micro_pred = []
    for row in labeled_rows:
        human = human_labels_from_row(row)
        rule = get_rule_predictions(row)
        for label_key in POSITIVE_LABEL_KEYS:
            micro_true.append(human[label_key])
            micro_pred.append(rule[label_key])

    return {
        "row_count": len(rows),
        "labeled_row_count": len(labeled_rows),
        "positive_label_micro": binary_metrics(micro_true, micro_pred),
        "per_label": per_label,
    }


def format_float(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:.3f}"


def build_markdown_report(report: dict[str, object]) -> str:
    lines = [
        "# Rule Baseline Report",
        "",
        f"Rows in CSV: {report['row_count']}",
        f"Rows evaluated: {report['labeled_row_count']}",
        "",
        "## Positive-Label Micro Average",
        "",
        "| precision | recall | f1 | support | tp | fp | fn |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    micro = report["positive_label_micro"]
    lines.append(
        "| {precision} | {recall} | {f1} | {support} | {tp} | {fp} | {fn} |".format(
            **{key: format_float(value) for key, value in micro.items()}
        )
    )
    lines.extend([
        "",
        "## Per Label",
        "",
        "| label | precision | recall | f1 | support | tp | fp | fn |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for label_key, metrics in report["per_label"].items():
        values = {key: format_float(value) for key, value in metrics.items()}
        lines.append(
            f"| {label_key} | {values['precision']} | {values['recall']} | {values['f1']} | "
            f"{values['support']} | {values['tp']} | {values['fp']} | {values['fn']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    rows = read_csv(args.annotations)
    report = evaluate(rows, include_unlabeled=args.include_unlabeled)
    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(build_markdown_report(report), encoding="utf-8")
    output_json = write_json(args.output_json, report)
    print(build_markdown_report(report))
    print(f"wrote_md={output_md}")
    print(f"wrote_json={output_json}")


if __name__ == "__main__":
    main()

