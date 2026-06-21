"""Post-hoc error audit for BERT shadow v2 predictions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from io_utils import ARTIFACTS_DIR, artifact_path, read_csv, write_csv, write_json, write_text


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
    parser.add_argument("--test-predictions", default=str(base / "bert_shadow_v2" / "test_predictions.csv"))
    parser.add_argument("--dev-predictions", default=str(base / "bert_shadow_v2" / "dev_predictions.csv"))
    parser.add_argument("--metrics-json", default=str(base / "bert_shadow_v2" / "bert_shadow_v2_metrics.json"))
    parser.add_argument("--rule-baseline-json", default=str(base / "baselines" / "rule_baseline_gold_v1_binary.json"))
    parser.add_argument("--gold-test-csv", default=str(base / "baselines" / "gold_v1_binary_test.csv"))
    parser.add_argument("--evaluation-key", default=str(base / "formal_300_v1_evaluation_key.csv"))
    parser.add_argument("--gold-binary-csv", default=str(base / "formal_300_v1_gold_v1_binary.csv"))
    parser.add_argument("--gold-master-csv", default=str(base / "formal_300_v1_gold_v1.csv"))
    parser.add_argument("--output-dir", default=str(base / "bert_shadow_v2" / "audit"))
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting v2 audit artifacts.")
    return parser.parse_args()


def ensure_output_dir(path: str | Path) -> Path:
    output_dir = Path(path)
    artifacts_root = ARTIFACTS_DIR.resolve()
    try:
        output_dir.resolve().relative_to(artifacts_root)
    except ValueError as exc:
        raise SystemExit(f"Audit outputs must be under {artifacts_root}: {output_dir}") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def index_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["annotation_id"]: row for row in rows}


def bool_text(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def prediction_label(row: dict[str, str], key: str = "pred_dev_threshold") -> str:
    return (row.get(key) or "").strip()


def rule_label(row: dict[str, str]) -> str:
    return "yes" if bool_text(row.get("rule_any_positive")) else "no"


def error_type(gold: str, pred: str) -> str:
    if gold == "yes" and pred == "yes":
        return "TP"
    if gold == "no" and pred == "yes":
        return "FP"
    if gold == "yes" and pred == "no":
        return "FN"
    return "TN"


def rule_vs_bert_type(gold: str, bert_pred: str, rule_pred: str) -> str:
    bert_correct = bert_pred == gold
    rule_correct = rule_pred == gold
    if bert_correct and rule_correct:
        return "both_correct"
    if bert_correct and not rule_correct:
        return "bert_only_correct"
    if rule_correct and not bert_correct:
        return "rule_only_correct"
    return "both_wrong"


def joined_text(row: dict[str, str]) -> str:
    return " ".join(
        str(row.get(column) or "")
        for column in [
            "turn_a",
            "turn_b",
            "evidence_span_a",
            "evidence_span_b",
            "annotator_note",
            "rule_summary",
        ]
    )


def risk_type(row: dict[str, str]) -> str:
    text = joined_text(row)
    if (row.get("gold_label") == "no" or row.get("resonance_present") == "no") and bool_text(row.get("has_question_response")):
        return "question_response"
    if row.get("gold_label") == "no" or row.get("resonance_present") == "no":
        return "topic_related_but_not_resonance"
    if bool_text(row.get("label_analogy_candidate")):
        return "analogy"
    if any(token in text for token in ["这", "此", "那个", "那", "他", "她", "它", "其", "斯", "指回", "指称"]):
        return "demonstrative_or_reference"
    if any(token in text for token in ["填入", "填补", "槽位", "什么", "怎样", "如何", "何以", "为何", "谁", "哪里", "多少", "何人", "孰"]):
        return "slot_filling"
    short_turn = min(len(row.get("turn_a", "")), len(row.get("turn_b", ""))) <= 4
    short_evidence = min(len(row.get("evidence_span_a", "")), len(row.get("evidence_span_b", ""))) <= 3
    if short_turn or short_evidence:
        return "short_answer"
    return "semantic_selection"


def likely_reason(row: dict[str, str]) -> str:
    kind = row["case_type"]
    risk = row["risk_type"]
    if kind == "BERT FP":
        if risk == "question_response":
            return "BERT appears to over-trust the question-answer adjacency even though the gold label treats it as ordinary factual/topic response without stable resonance."
        return "BERT likely captured topical relatedness or discourse adjacency, but the gold label requires a more stable reusable resource."
    if kind == "BERT FN":
        if risk == "demonstrative_or_reference":
            return "The cue is mostly referential or demonstrative, so surface lexical overlap is weak and the classifier may miss the implicit carry-over."
        if risk == "slot_filling":
            return "The resonance is expressed as filling an open slot; the answer may be semantically right without repeating many words."
        if risk == "short_answer":
            return "The response is short and context-dependent, making the positive evidence sparse."
        if risk == "analogy":
            return "The link relies on analogy or structural mapping rather than direct lexical echo."
        return "The positive relation is semantic selection rather than explicit form reuse, which remains difficult for the classifier."
    if kind == "BERT recovered rule FN":
        return "Rule features did not fire, but MacBERT assigned enough probability to recover a hidden semantic carry-over."
    if kind == "Rule-only correct":
        return "The rule cue aligned with gold, while BERT was too conservative or over-sensitive to topical similarity."
    return "Review model/rule disagreement."


def v3_hint(row: dict[str, str]) -> str:
    risk = row["risk_type"]
    if risk in {"demonstrative_or_reference", "slot_filling", "short_answer"}:
        return "For v3, keep targeted analysis for implicit carry-over; consider multi-seed stability before adding new data or changing gold."
    if risk == "question_response":
        return "For v3, preserve hard-negative pressure around ordinary question-answer pairs."
    if risk == "topic_related_but_not_resonance":
        return "For v3, separate topic relatedness from resonance with harder negative diagnostics."
    if risk == "analogy":
        return "For v3, keep analogy as a separate analysis label rather than optimizing binary F1 around it."
    return "For v3, inspect whether calibration or more stable thresholding helps this type."


def build_error_table(
    test_predictions: list[dict[str, str]],
    gold_test: dict[str, dict[str, str]],
    full_gold: dict[str, dict[str, str]],
    key_rows: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows = []
    for pred in test_predictions:
        annotation_id = pred["annotation_id"]
        gold = gold_test.get(annotation_id, {})
        master = full_gold.get(annotation_id, {})
        key = key_rows.get(annotation_id, {})
        gold_label = pred.get("gold_label") or gold.get("resonance_present", "")
        bert_pred = prediction_label(pred)
        r_pred = rule_label(pred)
        enriched = {
            "annotation_id": annotation_id,
            "pair_id": pred.get("pair_id", ""),
            "turn_a": pred.get("turn_a", ""),
            "turn_b": pred.get("turn_b", ""),
            "gold_label": gold_label,
            "bert_prob": pred.get("prob_yes", ""),
            "bert_pred": bert_pred,
            "rule_pred": r_pred,
            "error_type": error_type(gold_label, bert_pred),
            "rule_vs_bert_type": rule_vs_bert_type(gold_label, bert_pred, r_pred),
            "sample_stratum": pred.get("sample_stratum") or gold.get("sample_stratum", ""),
            "source": pred.get("source") or gold.get("source", ""),
            "dataset_name": pred.get("dataset_name") or gold.get("dataset_name", ""),
            "label_reproduction": gold.get("label_reproduction", ""),
            "label_parallelism": gold.get("label_parallelism", ""),
            "label_selective_reuse": gold.get("label_selective_reuse", ""),
            "label_repair": gold.get("label_repair", ""),
            "label_contrast": gold.get("label_contrast", ""),
            "label_analogy_candidate": gold.get("label_analogy_candidate", ""),
            "evidence_span_a": gold.get("evidence_span_a") or pred.get("evidence_span_a", ""),
            "evidence_span_b": gold.get("evidence_span_b") or pred.get("evidence_span_b", ""),
            "annotator_note": master.get("annotator_note", ""),
            "rule_summary": pred.get("rule_summary") or key.get("rule_summary", ""),
            "has_question_response": pred.get("has_question_response") or key.get("has_question_response", ""),
            "has_lexical_echo": pred.get("has_lexical_echo") or key.get("has_lexical_echo", ""),
            "has_pattern_reuse": pred.get("has_pattern_reuse") or key.get("has_pattern_reuse", ""),
            "has_negation_turn": pred.get("has_negation_turn") or key.get("has_negation_turn", ""),
            "has_repair_repetition": pred.get("has_repair_repetition") or key.get("has_repair_repetition", ""),
        }
        enriched["risk_type"] = risk_type(enriched)
        rows.append(enriched)
    return rows


def table_fieldnames() -> list[str]:
    return [
        "annotation_id",
        "pair_id",
        "turn_a",
        "turn_b",
        "gold_label",
        "bert_prob",
        "bert_pred",
        "rule_pred",
        "error_type",
        "rule_vs_bert_type",
        "sample_stratum",
        "source",
        "dataset_name",
        *LABEL_COLUMNS,
        "evidence_span_a",
        "evidence_span_b",
        "annotator_note",
        "risk_type",
        "rule_summary",
        "has_question_response",
        "has_lexical_echo",
        "has_pattern_reuse",
        "has_negation_turn",
        "has_repair_repetition",
    ]


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row.get(field, "") for row in rows).items()))


def label_distribution(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    output = {}
    for column in LABEL_COLUMNS:
        output[column] = count_by(rows, column)
    return output


def risk_distribution(rows: list[dict[str, str]]) -> dict[str, int]:
    return count_by(rows, "risk_type")


def split_cases(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    return {
        "fp": [row for row in rows if row["error_type"] == "FP"],
        "fn": [row for row in rows if row["error_type"] == "FN"],
        "bert_recovered_rule_fn": [
            row for row in rows
            if row["gold_label"] == "yes" and row["rule_pred"] == "no" and row["bert_pred"] == "yes"
        ],
        "missed_rule_fn": [
            row for row in rows
            if row["gold_label"] == "yes" and row["rule_pred"] == "no" and row["bert_pred"] == "no"
        ],
        "rule_only_correct": [row for row in rows if row["rule_vs_bert_type"] == "rule_only_correct"],
        "bert_only_correct": [row for row in rows if row["rule_vs_bert_type"] == "bert_only_correct"],
    }


def build_summary_json(rows: list[dict[str, str]]) -> dict[str, Any]:
    cases = split_cases(rows)
    fp_fn = cases["fp"] + cases["fn"]
    fn_rows = cases["fn"]
    return {
        "row_count": len(rows),
        "error_counts": count_by(rows, "error_type"),
        "rule_vs_bert_counts": count_by(rows, "rule_vs_bert_type"),
        "fp_fn_by_source": {
            "fp": count_by(cases["fp"], "source"),
            "fn": count_by(cases["fn"], "source"),
        },
        "fp_fn_by_sample_stratum": {
            "fp": count_by(cases["fp"], "sample_stratum"),
            "fn": count_by(cases["fn"], "sample_stratum"),
        },
        "fp_fn_by_core_label": {
            "fp": label_distribution(cases["fp"]),
            "fn": label_distribution(cases["fn"]),
        },
        "fn_selective_reuse_count": sum(1 for row in fn_rows if row.get("label_selective_reuse") == "1"),
        "fn_analogy_candidate_count": sum(1 for row in fn_rows if row.get("label_analogy_candidate") == "1"),
        "fn_risk_counts": risk_distribution(fn_rows),
        "fn_short_answer_count": sum(1 for row in fn_rows if row["risk_type"] == "short_answer"),
        "fn_demonstrative_or_reference_count": sum(1 for row in fn_rows if row["risk_type"] == "demonstrative_or_reference"),
        "fn_slot_filling_count": sum(1 for row in fn_rows if row["risk_type"] == "slot_filling"),
        "fp_fn_risk_counts": risk_distribution(fp_fn),
        "bert_only_correct_type_counts": risk_distribution(cases["bert_only_correct"]),
        "rule_only_correct_type_counts": risk_distribution(cases["rule_only_correct"]),
        "bert_recovered_rule_fn_type_counts": risk_distribution(cases["bert_recovered_rule_fn"]),
        "missed_rule_fn_type_counts": risk_distribution(cases["missed_rule_fn"]),
        "bert_recovered_rule_fn_ids": [row["annotation_id"] for row in cases["bert_recovered_rule_fn"]],
        "missed_rule_fn_ids": [row["annotation_id"] for row in cases["missed_rule_fn"]],
        "bert_fp_ids": [row["annotation_id"] for row in cases["fp"]],
        "bert_fn_ids": [row["annotation_id"] for row in cases["fn"]],
    }


def case_block(row: dict[str, str], case_type: str) -> list[str]:
    enriched = dict(row)
    enriched["case_type"] = case_type
    return [
        f"### {row['annotation_id']} - {case_type} - {row['risk_type']}",
        "",
        f"- A: {row['turn_a']}",
        f"- B: {row['turn_b']}",
        f"- Gold: {row['gold_label']}; Rule: {row['rule_pred']}; BERT: {row['bert_pred']} (prob={float(row['bert_prob']):.4f})",
        f"- Labels: reproduction={row['label_reproduction']}, parallelism={row['label_parallelism']}, selective_reuse={row['label_selective_reuse']}, repair={row['label_repair']}, contrast={row['label_contrast']}, analogy={row['label_analogy_candidate']}",
        f"- Evidence A/B: {row['evidence_span_a']} / {row['evidence_span_b']}",
        f"- Rule evidence: {row['rule_summary']}",
        f"- Possible reason: {likely_reason(enriched)}",
        f"- v3 hint: {v3_hint(enriched)}",
        "",
    ]


def build_case_study(rows: list[dict[str, str]], metrics: dict[str, Any]) -> str:
    cases = split_cases(rows)
    lines = [
        "# BERT Shadow v2 FP/FN Case Study",
        "",
        "This audit is post-hoc only. No new model was trained, no threshold was selected from test, and no gold/split files were modified.",
        "",
        f"- Dev-selected threshold: {metrics['thresholds']['dev_selected_threshold']:.6f}",
        f"- BERT FP: {len(cases['fp'])}",
        f"- BERT FN: {len(cases['fn'])}",
        f"- Rule FN recovered by BERT: {len(cases['bert_recovered_rule_fn'])}",
        f"- Rule FN still missed by BERT: {len(cases['missed_rule_fn'])}",
        f"- Rule correct but BERT wrong: {len(cases['rule_only_correct'])}",
        "",
        "## BERT False Positive",
        "",
    ]
    for row in cases["fp"]:
        lines.extend(case_block(row, "BERT FP"))
    lines.extend(["## BERT False Negatives", ""])
    for row in cases["fn"]:
        lines.extend(case_block(row, "BERT FN"))
    lines.extend(["## BERT Recovered Rule False Negatives", ""])
    for row in cases["bert_recovered_rule_fn"]:
        lines.extend(case_block(row, "BERT recovered rule FN"))
    lines.extend(["## Rule False Negatives Not Recovered By BERT", ""])
    for row in cases["missed_rule_fn"]:
        lines.extend(case_block(row, "BERT missed rule FN"))
    lines.extend(["## Rule Correct But BERT Wrong", ""])
    for row in cases["rule_only_correct"]:
        lines.extend(case_block(row, "Rule-only correct"))
    return "\n".join(lines)


def build_threshold_sensitivity(metrics: dict[str, Any]) -> str:
    dev_threshold = metrics["thresholds"]["dev_selected_threshold"]
    test_05 = metrics["test"]["threshold_0_5"]
    test_sel = metrics["test"]["dev_selected_threshold"]
    dev_05 = metrics["dev"]["threshold_0_5"]
    dev_sel = metrics["dev"]["dev_selected_threshold"]
    lines = [
        "# BERT Shadow v2 Threshold Sensitivity",
        "",
        "This is a post-hoc audit. It does not use test results to choose a new threshold.",
        "",
        f"- Default threshold: 0.5",
        f"- Dev-selected threshold: {dev_threshold:.6f}",
        "",
        "## Dev",
        "",
        f"- 0.5: macro-F1={dev_05['macro']['f1']:.3f}, balanced accuracy={dev_05['balanced_accuracy']:.3f}, no recall={dev_05['no_class']['recall']:.3f}, TP/FP/FN/TN={dev_05['confusion_matrix']['tp']}/{dev_05['confusion_matrix']['fp']}/{dev_05['confusion_matrix']['fn']}/{dev_05['confusion_matrix']['tn']}",
        f"- selected: macro-F1={dev_sel['macro']['f1']:.3f}, balanced accuracy={dev_sel['balanced_accuracy']:.3f}, no recall={dev_sel['no_class']['recall']:.3f}, TP/FP/FN/TN={dev_sel['confusion_matrix']['tp']}/{dev_sel['confusion_matrix']['fp']}/{dev_sel['confusion_matrix']['fn']}/{dev_sel['confusion_matrix']['tn']}",
        "",
        "## Test",
        "",
        f"- 0.5: macro-F1={test_05['macro']['f1']:.3f}, balanced accuracy={test_05['balanced_accuracy']:.3f}, no recall={test_05['no_class']['recall']:.3f}, TP/FP/FN/TN={test_05['confusion_matrix']['tp']}/{test_05['confusion_matrix']['fp']}/{test_05['confusion_matrix']['fn']}/{test_05['confusion_matrix']['tn']}",
        f"- selected: macro-F1={test_sel['macro']['f1']:.3f}, balanced accuracy={test_sel['balanced_accuracy']:.3f}, no recall={test_sel['no_class']['recall']:.3f}, TP/FP/FN/TN={test_sel['confusion_matrix']['tp']}/{test_sel['confusion_matrix']['fp']}/{test_sel['confusion_matrix']['fn']}/{test_sel['confusion_matrix']['tn']}",
        "",
        "## Interpretation",
        "",
        "The dev-selected threshold improves dev macro-F1 and removes all dev false positives, but on test the default 0.5 threshold is slightly better for macro-F1 and balanced accuracy.",
        "This does not license choosing 0.5 because it looked better on test after the fact. Test must remain final evaluation only.",
        "The discrepancy suggests threshold selection is unstable with only 43 dev rows and 43 test rows.",
        "For v3, prefer multi-seed runs and, if possible, cross-validation or a calibration-only protocol selected entirely on dev folds.",
        "",
        "Do not retroactively tune the threshold on test.",
    ]
    return "\n".join(lines) + "\n"


def build_next_steps(summary: dict[str, Any], metrics: dict[str, Any]) -> str:
    test_sel = metrics["test"]["dev_selected_threshold"]
    lines = [
        "# BERT Shadow v2 Next-Step Recommendation",
        "",
        "BERT shadow v2 is an effective shadow result: it beats majority/similarity and the rule test split on macro-F1 and balanced accuracy, while keeping no-class recall above zero.",
        "",
        f"- Test macro-F1: {test_sel['macro']['f1']:.3f}",
        f"- Test balanced accuracy: {test_sel['balanced_accuracy']:.3f}",
        f"- Test no-class recall: {test_sel['no_class']['recall']:.3f}",
        f"- Test false positives: {summary['error_counts'].get('FP', 0)}",
        f"- Test false negatives: {summary['error_counts'].get('FN', 0)}",
        "",
        "## Recommendation",
        "",
        "- Continue to v3, but do not blindly chase higher positive F1.",
        "- Prioritize multi-seed stability because the dev/test splits are small.",
        "- Add threshold calibration experiments selected only on dev or cross-validation folds.",
        "- Keep hard-negative analysis around ordinary question-response and topic-related non-resonance cases.",
        "- Do not alter gold labels just to fit the model.",
        "- It is worth downloading `hfl/chinese-roberta-wwm-ext` for a controlled model-family comparison, but only after v2 multi-seed stability is measured.",
        "",
        "## Guardrails",
        "",
        "- Keep BERT as a shadow classifier/reranker, not a replacement for the rule graph.",
        "- Compare against majority, similarity, rule full-set, rule test split, and v1.",
        "- Report macro-F1, balanced accuracy, and no-class recall every time.",
        "- If a future run collapses to all-yes, treat it as ineffective regardless of positive F1.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    output_dir = ensure_output_dir(args.output_dir)
    test_predictions = read_csv(args.test_predictions)
    dev_predictions = read_csv(args.dev_predictions)
    if not dev_predictions:
        raise SystemExit("dev predictions are empty")
    metrics = json.loads(Path(args.metrics_json).read_text(encoding="utf-8"))
    rule_baseline = json.loads(Path(args.rule_baseline_json).read_text(encoding="utf-8"))
    gold_test = index_by_id(read_csv(args.gold_test_csv))
    key_rows = index_by_id(read_csv(args.evaluation_key))
    full_gold = index_by_id(read_csv(args.gold_master_csv)) if Path(args.gold_master_csv).exists() else {}
    # Read full binary gold to ensure the user-specified frozen binary input is present and stable.
    _gold_binary_count = len(read_csv(args.gold_binary_csv))
    if _gold_binary_count == 0:
        raise SystemExit("gold_v1_binary is empty")

    table_rows = build_error_table(test_predictions, gold_test, full_gold, key_rows)
    summary = build_summary_json(table_rows)
    summary["rule_baseline_overall"] = rule_baseline.get("overall", {})
    summary["thresholds"] = metrics.get("thresholds", {})
    summary["test_metrics"] = metrics.get("test", {})
    summary["notes"] = {
        "trained_new_model": False,
        "modified_gold_or_split": False,
        "read_or_wrote_corpus_db": False,
        "connected_website": False,
    }

    write_csv(
        output_dir / "v2_test_error_table.csv",
        table_rows,
        table_fieldnames(),
        overwrite=args.overwrite,
        force_overwrite_labels=True,
    )
    write_text(
        output_dir / "v2_fp_fn_case_study.md",
        build_case_study(table_rows, metrics),
        overwrite=args.overwrite,
    )
    write_json(output_dir / "v2_error_type_summary.json", summary, overwrite=args.overwrite)
    write_text(
        output_dir / "v2_threshold_sensitivity.md",
        build_threshold_sensitivity(metrics),
        overwrite=args.overwrite,
    )
    write_text(
        output_dir / "v2_next_step_recommendation.md",
        build_next_steps(summary, metrics),
        overwrite=args.overwrite,
    )
    print(f"wrote={output_dir}")
    print(f"rows={len(table_rows)}")
    print(f"errors={summary['error_counts']}")
    print(f"fn_risks={summary['fn_risk_counts']}")
    print(f"fp_ids={summary['bert_fp_ids']}")


if __name__ == "__main__":
    main()
