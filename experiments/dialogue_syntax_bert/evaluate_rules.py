"""Evaluate heuristic rule behavior against filled blind annotations.

This report treats the current rule system as a resonance detector and trigger
set. It does not treat individual `has_*` columns as supervised classifiers for
human mechanism labels.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from io_utils import artifact_path, read_csv, write_csv, write_json, write_text
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
REVIEW_QUEUE_COLUMNS = [
    "review_priority",
    "annotation_id",
    "pair_id",
    "source",
    "dataset_name",
    "turn_a",
    "turn_b",
    "resonance_present",
    *CORE_LABEL_COLUMNS,
    ANALOGY_COLUMN,
    "rule_summary",
    "rule_any_positive",
    *FLAG_COLUMNS,
    "shared_terms",
    "markers",
    "review_reason",
    "annotator_note",
    "uncertainty_reason",
]


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
    parser.add_argument(
        "--review-queue-csv",
        default="",
        help="Optional review queue CSV path.",
    )
    parser.add_argument(
        "--report-note",
        default="",
        help="Optional note printed near the top of the Markdown report.",
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


def yes_no_distribution(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "yes": sum(1 for row in rows if resonance_value(row) == "yes"),
        "no": sum(1 for row in rows if resonance_value(row) == "no"),
        "uncertain": sum(1 for row in rows if resonance_value(row) == "uncertain"),
        "invalid_or_blank": sum(1 for row in rows if resonance_value(row) == ""),
    }


def core_positive_labels(row: dict[str, str]) -> list[str]:
    return [label for label in CORE_LABEL_COLUMNS if parse_label(row.get(label)) == "1"]


def has_core_positive(row: dict[str, str]) -> bool:
    return bool(core_positive_labels(row))


def is_false_positive(row: dict[str, str]) -> bool:
    return rule_any_positive(row) and resonance_value(row) == "no"


def is_false_negative(row: dict[str, str]) -> bool:
    return (not rule_any_positive(row)) and resonance_value(row) == "yes"


def is_question_boundary(row: dict[str, str]) -> bool:
    return parse_bool(row.get("has_question_response")) and not has_core_positive(row)


def row_ref(row: dict[str, str]) -> dict[str, str]:
    return {
        "annotation_id": row.get("annotation_id", ""),
        "pair_id": row.get("pair_id", ""),
        "source": row.get("source", ""),
        "dataset_name": row.get("dataset_name", "") or row.get("dataset", ""),
        "resonance_present": row.get("resonance_present", ""),
        "rule_summary": row.get("rule_summary", ""),
        "rule_any_positive": row.get("rule_any_positive", ""),
        "core_positive_labels": ", ".join(core_positive_labels(row)),
        "analogy_candidate": row.get(ANALOGY_COLUMN, ""),
        "annotator_note": row.get("annotator_note", ""),
        "uncertainty_reason": row.get("uncertainty_reason", ""),
    }


def list_refs(rows: list[dict[str, str]], predicate, limit: int | None = None) -> list[dict[str, str]]:
    refs = [row_ref(row) for row in rows if predicate(row)]
    return refs if limit is None else refs[:limit]


def review_reasons(row: dict[str, str]) -> tuple[int | None, list[str]]:
    reasons = []
    priorities = []
    if resonance_value(row) == "uncertain":
        priorities.append(1)
        reasons.append("P1 resonance_present=uncertain")
    if is_false_positive(row):
        priorities.append(2)
        reasons.append("P2 rule_any_positive=1 but resonance_present=no")
    if is_false_negative(row):
        priorities.append(2)
        reasons.append("P2 rule_any_positive=0 but resonance_present=yes")
    if parse_label(row.get(ANALOGY_COLUMN)) == "1":
        priorities.append(3)
        reasons.append("P3 label_analogy_candidate=1")
    if is_question_boundary(row):
        priorities.append(4)
        reasons.append("P4 has_question_response=1 but no core mechanism label=1")
    if (row.get("annotator_note") or "").strip() or (row.get("uncertainty_reason") or "").strip():
        priorities.append(5)
        reasons.append("P5 annotator_note or uncertainty_reason is non-empty")
    if not reasons:
        return None, []
    return min(priorities), reasons


def build_review_queue(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    queue = []
    for row in rows:
        priority, reasons = review_reasons(row)
        if priority is None:
            continue
        queue.append({
            "review_priority": priority,
            "annotation_id": row.get("annotation_id", ""),
            "pair_id": row.get("pair_id", ""),
            "source": row.get("source", ""),
            "dataset_name": row.get("dataset_name", "") or row.get("dataset", ""),
            "turn_a": row.get("turn_a", ""),
            "turn_b": row.get("turn_b", ""),
            "resonance_present": row.get("resonance_present", ""),
            **{label: row.get(label, "") for label in CORE_LABEL_COLUMNS},
            ANALOGY_COLUMN: row.get(ANALOGY_COLUMN, ""),
            "rule_summary": row.get("rule_summary", ""),
            "rule_any_positive": row.get("rule_any_positive", ""),
            **{flag: row.get(flag, "") for flag in FLAG_COLUMNS},
            "shared_terms": row.get("shared_terms", ""),
            "markers": row.get("markers", ""),
            "review_reason": " | ".join(reasons),
            "annotator_note": row.get("annotator_note", ""),
            "uncertainty_reason": row.get("uncertainty_reason", ""),
        })
    queue.sort(key=lambda row: (int(row["review_priority"]), row["annotation_id"], row["pair_id"]))
    return queue


def evaluate(rows: list[dict[str, str]]) -> dict[str, object]:
    yes_no_rows = [row for row in rows if resonance_value(row) in {"yes", "no"}]
    y_true = [resonance_value(row) == "yes" for row in yes_no_rows]
    y_pred = [rule_any_positive(row) for row in yes_no_rows]
    false_positive_refs = list_refs(rows, is_false_positive)
    false_negative_refs = list_refs(rows, is_false_negative)
    uncertain_refs = list_refs(rows, lambda row: resonance_value(row) == "uncertain")
    analogy_refs = list_refs(rows, lambda row: parse_label(row.get(ANALOGY_COLUMN)) == "1")
    question_boundary_refs = list_refs(rows, is_question_boundary)
    review_queue = build_review_queue(rows)
    top_review_suggestions = [
        {
            "annotation_id": item.get("annotation_id", ""),
            "pair_id": item.get("pair_id", ""),
            "source": item.get("source", ""),
            "dataset_name": item.get("dataset_name", ""),
            "resonance_present": item.get("resonance_present", ""),
            "rule_summary": item.get("rule_summary", ""),
            "core_positive_labels": ", ".join(label for label in CORE_LABEL_COLUMNS if item.get(label) == "1"),
            "analogy_candidate": item.get(ANALOGY_COLUMN, ""),
            "review_reason": item.get("review_reason", ""),
        }
        for item in review_queue[:10]
    ]
    return {
        "row_count": len(rows),
        "resonance_distribution": yes_no_distribution(rows),
        "yes_no_row_count": len(yes_no_rows),
        "uncertain_row_count": sum(1 for row in rows if resonance_value(row) == "uncertain"),
        "invalid_or_blank_resonance_count": sum(1 for row in rows if resonance_value(row) == ""),
        "overall_rule_any_positive_vs_resonance": binary_metrics(y_true, y_pred),
        "trigger_analysis": trigger_analysis(rows),
        "uncertain_summary": uncertain_summary(rows),
        "analogy_candidate_summary": analogy_summary(rows),
        "false_positive_count": len(false_positive_refs),
        "false_negative_count": len(false_negative_refs),
        "false_positive_samples": false_positive_refs,
        "false_negative_samples": false_negative_refs,
        "uncertain_samples": uncertain_refs,
        "analogy_candidate_samples": analogy_refs,
        "question_boundary_samples": question_boundary_refs,
        "review_queue_count": len(review_queue),
        "top_review_suggestions": top_review_suggestions,
        "review_queue": review_queue,
        "core_labels": list(CORE_LABEL_COLUMNS),
        "excluded_from_core_f1": [ANALOGY_COLUMN, "resonance_present=uncertain"],
    }


def format_float(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:.3f}"


def format_sample_table(rows: list[dict[str, str]], *, title: str, empty_text: str = "None") -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        lines.extend([empty_text, ""])
        return lines
    lines.extend([
        "| annotation_id | pair_id | source | dataset | resonance | rule | core labels | analogy | note |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for row in rows:
        lines.append(
            f"| {row.get('annotation_id', '')} | {row.get('pair_id', '')} | {row.get('source', '')} | "
            f"{row.get('dataset_name', '')} | {row.get('resonance_present', '')} | {row.get('rule_summary', '')} | "
            f"{row.get('core_positive_labels', '')} | {row.get('analogy_candidate', '')} | "
            f"{(row.get('uncertainty_reason') or row.get('annotator_note') or '').replace('|', '/')} |"
        )
    lines.append("")
    return lines


def build_markdown_report(report: dict[str, object], report_note: str = "") -> str:
    overall = report["overall_rule_any_positive_vs_resonance"]
    distribution = report["resonance_distribution"]
    lines = [
        "# Rule Calibration Report",
        "",
        "This report evaluates rules as heuristic triggers, not as direct supervised mechanism classifiers.",
        report_note,
        "",
        f"Rows in CSV: {report['row_count']}",
        f"Resonance distribution: yes={distribution['yes']} no={distribution['no']} uncertain={distribution['uncertain']} invalid_or_blank={distribution['invalid_or_blank']}",
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
    lines.extend(format_sample_table(report["false_positive_samples"], title="Rule False Positive Candidates"))
    lines.extend(format_sample_table(report["false_negative_samples"], title="Rule False Negative Candidates"))
    lines.extend(format_sample_table(report["uncertain_samples"], title="Uncertain Samples"))
    lines.extend(format_sample_table(report["analogy_candidate_samples"], title="Analogy Candidate Samples"))
    lines.extend(format_sample_table(report["question_boundary_samples"], title="Question-Response Boundary Samples"))
    top_suggestions = []
    for item in report["review_queue"][:10]:
        top_suggestions.append({
            "annotation_id": item.get("annotation_id", ""),
            "pair_id": item.get("pair_id", ""),
            "source": item.get("source", ""),
            "dataset_name": item.get("dataset_name", ""),
            "resonance_present": item.get("resonance_present", ""),
            "rule_summary": item.get("rule_summary", ""),
            "core_positive_labels": ", ".join(label for label in CORE_LABEL_COLUMNS if item.get(label) == "1"),
            "analogy_candidate": item.get(ANALOGY_COLUMN, ""),
            "uncertainty_reason": item.get("review_reason", ""),
        })
    lines.extend(format_sample_table(top_suggestions, title="Top 10 Human Review Suggestions"))
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    rows = load_rows(args.annotations, args.key)
    report = evaluate(rows)
    output_md = write_text(Path(args.output_md), build_markdown_report(report, args.report_note), overwrite=args.overwrite)
    output_json = write_json(args.output_json, report, overwrite=args.overwrite)
    if args.review_queue_csv:
        review_queue_path = write_csv(
            args.review_queue_csv,
            report["review_queue"],
            REVIEW_QUEUE_COLUMNS,
            overwrite=args.overwrite,
            force_overwrite_labels=False,
        )
        print(f"wrote_review_queue={review_queue_path}")
    print(build_markdown_report(report, args.report_note))
    print(f"wrote_md={output_md}")
    print(f"wrote_json={output_json}")


if __name__ == "__main__":
    main()
