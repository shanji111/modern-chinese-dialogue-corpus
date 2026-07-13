from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from evaluate_diagraph_generation_v1 import (
    DEFAULT_GOLD_ACTIVE,
    PRED_REQUIRED_FIELDS,
    VALID_ALIGNMENT_DIRECTIONS,
    VALID_BINARY_OR_UNKNOWN,
    VALID_RELATION_STRENGTHS,
    VALID_RELATION_TYPES,
    evaluate_predictions,
    read_csv_dicts,
    write_csv,
)


ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = ROOT / "artifacts" / "formal_300_v1"
PAIR_LIST_PATH = ARTIFACT_ROOT / "diagraph_gold_50" / "diagraph_gold_50_pair_list.csv"
OUTPUT_DIR = ARTIFACT_ROOT / "diagraph_generation_evaluation_v1" / "rule_baseline_v1"
PREDICTION_CSV_PATH = OUTPUT_DIR / "rule_baseline_prediction_v1.csv"
EVALUATION_RUN_DIR = OUTPUT_DIR / "evaluation_run"
GENERATION_REPORT_PATH = OUTPUT_DIR / "rule_baseline_v1_generation_report.md"
EVALUATION_SUMMARY_PATH = OUTPUT_DIR / "rule_baseline_v1_evaluation_summary.md"
ERROR_ANALYSIS_PATH = OUTPUT_DIR / "rule_baseline_v1_error_analysis.md"
MANIFEST_PATH = OUTPUT_DIR / "rule_baseline_v1_manifest.md"

GENERATOR_NAME = "rule_baseline"
GENERATOR_VERSION = "v1"
RELAXED_THRESHOLD = 0.5
MAX_COLUMNS_PER_PAIR = 5
MAX_LEXICAL_COLUMNS_PER_PAIR = 3

QUESTION_TERMS = [
    "什么",
    "甚么",
    "谁",
    "哪",
    "哪里",
    "哪儿",
    "怎么",
    "如何",
    "为什么",
    "为何",
    "何以",
    "多少",
    "几",
    "吗",
    "么",
    "呢",
    "是不是",
    "有没有",
    "能不能",
    "可不可以",
    "行不行",
    "对不对",
]
QUESTION_MARKS = {"?", "？"}
SHORT_ANSWER_TOKENS = {
    "是",
    "不是",
    "有",
    "没有",
    "能",
    "不能",
    "可以",
    "不可以",
    "行",
    "不行",
    "对",
    "不对",
    "嗯",
    "哦",
    "好",
    "好的",
    "当然",
    "当然有",
    "当然有喽",
}
DEMONSTRATIVES = [
    "是这样吗",
    "这样吗",
    "这样",
    "那样",
    "这般",
    "如此",
    "这么",
    "那么",
    "这",
    "那",
]
NEGATION_STARTS = [
    "不是",
    "不对",
    "别",
    "不要",
    "不能",
    "不可",
    "不许",
    "不准",
    "没有",
    "没",
    "莫",
]
CONTRAST_MARKERS = [
    "还是",
    "一样",
    "而是",
    "却",
    "反而",
    "不过",
    "但是",
    "但",
]
FUNCTION_WORD_STOPS = {
    "这个",
    "那个",
    "这样",
    "那样",
    "这个人",
    "那个人",
    "不是",
    "没有",
    "可以",
    "一下",
    "一个",
    "我们",
    "你们",
    "他们",
    "她们",
    "它们",
    "自己",
    "什么",
    "怎么",
    "为什么",
    "因为",
    "如果",
    "但是",
    "不过",
    "还是",
    "就是",
    "然后",
}
PUNCTUATION_CHARS = set("，,。！？!?；;：:、（）()“”‘’\"'《》【】[]<>-—…· \t\r\n")
CLAUSE_BOUNDARY_RE = re.compile(r"[，,。！？!?；;：:\n\r]+")


@dataclass(frozen=True)
class CandidateColumn:
    annotation_id: str
    pair_id: str
    pred_span_a: str
    pred_span_b: str
    pred_relation_type: str
    pred_relation_strength: str
    pred_alignment_direction: str
    pred_is_core_column: str
    pred_supports_resonance: str
    pred_confidence: str
    notes: str
    score: float
    rule_name: str


def ensure_prediction_rows_valid(rows: Sequence[Dict[str, str]], pair_map: Dict[str, Dict[str, str]]) -> None:
    for row in rows:
        missing = [field for field in PRED_REQUIRED_FIELDS if field not in row]
        if missing:
            raise ValueError(f"prediction row missing fields: {missing}")
        pair = pair_map[row["annotation_id"]]
        if row["pair_id"] != pair["pair_id"]:
            raise ValueError(f"pair_id mismatch for {row['annotation_id']}")
        if row["pred_span_a"] not in pair["turn_a"]:
            raise ValueError(f"pred_span_a not found in turn_a: {row['annotation_id']}::{row['pred_span_a']}")
        if row["pred_span_b"] not in pair["turn_b"]:
            raise ValueError(f"pred_span_b not found in turn_b: {row['annotation_id']}::{row['pred_span_b']}")
        if row["pred_relation_type"] not in VALID_RELATION_TYPES:
            raise ValueError(f"invalid pred_relation_type: {row['pred_relation_type']}")
        if row["pred_relation_strength"] not in VALID_RELATION_STRENGTHS:
            raise ValueError(f"invalid pred_relation_strength: {row['pred_relation_strength']}")
        if row["pred_alignment_direction"] not in VALID_ALIGNMENT_DIRECTIONS:
            raise ValueError(f"invalid pred_alignment_direction: {row['pred_alignment_direction']}")
        if row["pred_is_core_column"] not in VALID_BINARY_OR_UNKNOWN:
            raise ValueError(f"invalid pred_is_core_column: {row['pred_is_core_column']}")
        if row["pred_supports_resonance"] not in VALID_BINARY_OR_UNKNOWN:
            raise ValueError(f"invalid pred_supports_resonance: {row['pred_supports_resonance']}")


def split_clauses(text: str) -> List[str]:
    parts = [part.strip() for part in CLAUSE_BOUNDARY_RE.split(text) if part.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def normalize_for_length(text: str) -> str:
    return "".join(ch for ch in text if ch not in PUNCTUATION_CHARS)


def is_meaningful_span(span: str, min_len: int = 1) -> bool:
    stripped = (span or "").strip()
    if not stripped:
        return False
    normalized = normalize_for_length(stripped)
    if len(normalized) < min_len:
        return False
    if all(ch in PUNCTUATION_CHARS for ch in stripped):
        return False
    if stripped in FUNCTION_WORD_STOPS:
        return False
    if len(normalized) == 1 and normalized not in {"我", "你", "他", "她", "它", "这", "那"}:
        return False
    return True


def is_question(turn_a: str) -> bool:
    stripped = turn_a.strip()
    if any(marker in stripped for marker in QUESTION_MARKS):
        return True
    return any(term in stripped for term in QUESTION_TERMS)


def contains_question_word(text: str) -> bool:
    return any(term in text for term in QUESTION_TERMS)


def find_clause_with_term(text: str, terms: Sequence[str]) -> str:
    for clause in split_clauses(text):
        if any(term in clause for term in terms):
            return clause
    return text.strip()


def select_question_span(turn_a: str) -> str:
    clause = find_clause_with_term(turn_a, QUESTION_TERMS)
    return clause if is_meaningful_span(clause, min_len=2) else turn_a.strip()


def select_reference_span(turn_a: str) -> str:
    clauses = split_clauses(turn_a)
    if not clauses:
        return turn_a.strip()
    for clause in reversed(clauses):
        if is_meaningful_span(clause, min_len=2) and len(normalize_for_length(clause)) <= 24:
            return clause
    if len(normalize_for_length(turn_a)) <= 24:
        return turn_a.strip()
    return clauses[-1]


def select_first_answer_clause(turn_b: str) -> str:
    clauses = split_clauses(turn_b)
    return clauses[0] if clauses else turn_b.strip()


def select_contrast_clause(turn_b: str) -> str:
    for clause in split_clauses(turn_b):
        if any(marker in clause for marker in CONTRAST_MARKERS):
            return clause
    return select_first_answer_clause(turn_b)


def relation_score(relation_type: str, strength: str, confidence: str, span_a: str, span_b: str) -> float:
    relation_base = {
        "repair": 95.0,
        "slot_filling": 92.0,
        "short_answer": 88.0,
        "lexical_reproduction": 85.0,
        "contrast": 80.0,
        "coreference_or_demonstrative": 74.0,
        "semantic_substitution": 72.0,
    }.get(relation_type, 60.0)
    strength_bonus = {"strong": 8.0, "medium": 4.0, "weak": 1.0}[strength]
    confidence_bonus = {"high": 5.0, "medium": 2.5, "low": 0.5}[confidence]
    info_bonus = min(len(normalize_for_length(span_a)) + len(normalize_for_length(span_b)), 18) / 10.0
    return relation_base + strength_bonus + confidence_bonus + info_bonus


def make_candidate(
    row: Dict[str, str],
    span_a: str,
    span_b: str,
    relation_type: str,
    relation_strength: str,
    alignment_direction: str,
    is_core: str,
    supports_resonance: str,
    confidence: str,
    note: str,
    rule_name: str,
) -> CandidateColumn | None:
    span_a = (span_a or "").strip()
    span_b = (span_b or "").strip()
    if not is_meaningful_span(span_a, min_len=1) or not is_meaningful_span(span_b, min_len=1):
        return None
    if span_a not in row["turn_a"] or span_b not in row["turn_b"]:
        return None
    if relation_type not in VALID_RELATION_TYPES:
        return None
    if relation_strength not in VALID_RELATION_STRENGTHS:
        return None
    if alignment_direction not in VALID_ALIGNMENT_DIRECTIONS:
        return None
    if is_core not in VALID_BINARY_OR_UNKNOWN:
        return None
    if supports_resonance not in VALID_BINARY_OR_UNKNOWN:
        return None
    return CandidateColumn(
        annotation_id=row["annotation_id"],
        pair_id=row["pair_id"],
        pred_span_a=span_a,
        pred_span_b=span_b,
        pred_relation_type=relation_type,
        pred_relation_strength=relation_strength,
        pred_alignment_direction=alignment_direction,
        pred_is_core_column=is_core,
        pred_supports_resonance=supports_resonance,
        pred_confidence=confidence,
        notes=note,
        score=relation_score(relation_type, relation_strength, confidence, span_a, span_b),
        rule_name=rule_name,
    )


def extract_common_substrings(turn_a: str, turn_b: str, min_len: int = 2, max_len: int = 12) -> List[str]:
    max_len = min(max_len, len(turn_a), len(turn_b))
    candidates: set[str] = set()
    for span_len in range(max_len, min_len - 1, -1):
        seen_at_len: set[str] = set()
        for start in range(0, len(turn_a) - span_len + 1):
            span = turn_a[start : start + span_len]
            if span in seen_at_len:
                continue
            seen_at_len.add(span)
            if span in turn_b and is_meaningful_span(span, min_len=min_len):
                if len(normalize_for_length(span)) == 2 and span in FUNCTION_WORD_STOPS:
                    continue
                candidates.add(span)
    selected: List[str] = []
    for span in sorted(candidates, key=lambda item: (-len(normalize_for_length(item)), item)):
        if any(span in existing for existing in selected if len(existing) >= len(span)):
            continue
        selected.append(span)
        if len(selected) >= MAX_LEXICAL_COLUMNS_PER_PAIR:
            break
    return selected


def build_lexical_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    candidates: List[CandidateColumn] = []
    for span in extract_common_substrings(row["turn_a"], row["turn_b"]):
        normalized_len = len(normalize_for_length(span))
        strength = "strong" if normalized_len >= 4 else "medium"
        confidence = "high" if normalized_len >= 4 else "medium"
        is_core = "1" if normalized_len >= 3 else "0"
        candidate = make_candidate(
            row=row,
            span_a=span,
            span_b=span,
            relation_type="lexical_reproduction",
            relation_strength=strength,
            alignment_direction="mutual",
            is_core=is_core,
            supports_resonance="1",
            confidence=confidence,
            note="rule=lexical_reproduction; exact common substring",
            rule_name="lexical_reproduction",
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def build_coreference_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    candidates: List[CandidateColumn] = []
    a_text = row["turn_a"]
    b_text = row["turn_b"]

    speaker_pairs = [
        ("你", "我"),
        ("我", "你"),
        ("你们", "我们"),
        ("我们", "你们"),
    ]
    for span_a, span_b in speaker_pairs:
        if span_a in a_text and span_b in b_text:
            candidate = make_candidate(
                row=row,
                span_a=span_a,
                span_b=span_b,
                relation_type="coreference_or_demonstrative",
                relation_strength="strong",
                alignment_direction="A_to_B",
                is_core="0",
                supports_resonance="1",
                confidence="medium",
                note="rule=coreference; speaker-role / deictic shift",
                rule_name="coreference_or_demonstrative",
            )
            if candidate is not None:
                candidates.append(candidate)
            break

    for marker in DEMONSTRATIVES:
        if marker in b_text:
            span_a = select_reference_span(a_text)
            strength = "medium" if len(normalize_for_length(span_a)) <= 18 else "weak"
            confidence = "medium" if marker in {"这样", "那样", "这般", "如此", "是这样吗", "这样吗"} else "low"
            candidate = make_candidate(
                row=row,
                span_a=span_a,
                span_b=marker,
                relation_type="coreference_or_demonstrative",
                relation_strength=strength,
                alignment_direction="A_to_B",
                is_core="0",
                supports_resonance="1",
                confidence=confidence,
                note=f"rule=demonstrative; proposition recall via {marker}",
                rule_name="coreference_or_demonstrative",
            )
            if candidate is not None:
                candidates.append(candidate)
            break

    return candidates


def build_slot_or_short_answer_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    if not is_question(row["turn_a"]):
        return []
    span_a = select_question_span(row["turn_a"])
    span_b = select_first_answer_clause(row["turn_b"])
    normalized_b_len = len(normalize_for_length(span_b))
    a_text = row["turn_a"]

    definition_patterns = [
        re.compile(r"^什么是.+"),
        re.compile(r"^.+是什么[？?]?$"),
    ]
    if any(pattern.match(a_text.strip()) for pattern in definition_patterns):
        candidate = make_candidate(
            row=row,
            span_a=span_a,
            span_b=span_b,
            relation_type="slot_filling",
            relation_strength="strong",
            alignment_direction="A_to_B",
            is_core="1",
            supports_resonance="1",
            confidence="high",
            note="rule=slot_filling; definition-style question answering",
            rule_name="slot_filling",
        )
        return [candidate] if candidate is not None else []

    if span_b in SHORT_ANSWER_TOKENS or normalized_b_len <= 4:
        candidate = make_candidate(
            row=row,
            span_a=span_a,
            span_b=span_b,
            relation_type="short_answer",
            relation_strength="medium" if normalized_b_len > 1 else "weak",
            alignment_direction="A_to_B",
            is_core="1",
            supports_resonance="1",
            confidence="medium",
            note="rule=short_answer; explicit question with short B-side answer",
            rule_name="short_answer",
        )
        return [candidate] if candidate is not None else []

    if contains_question_word(span_a) and 2 <= normalized_b_len <= 20:
        candidate = make_candidate(
            row=row,
            span_a=span_a,
            span_b=span_b,
            relation_type="slot_filling",
            relation_strength="medium",
            alignment_direction="A_to_B",
            is_core="1",
            supports_resonance="1",
            confidence="medium",
            note="rule=slot_filling; wh-question answered by B-side clause",
            rule_name="slot_filling",
        )
        return [candidate] if candidate is not None else []

    return []


def build_repair_or_contrast_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    candidates: List[CandidateColumn] = []
    span_a = select_reference_span(row["turn_a"])
    first_b_clause = select_first_answer_clause(row["turn_b"])
    stripped_b = first_b_clause.strip()

    if any(stripped_b.startswith(prefix) for prefix in NEGATION_STARTS):
        candidate = make_candidate(
            row=row,
            span_a=span_a,
            span_b=first_b_clause,
            relation_type="repair",
            relation_strength="strong" if len(normalize_for_length(first_b_clause)) <= 6 else "medium",
            alignment_direction="A_to_B",
            is_core="1",
            supports_resonance="1",
            confidence="high" if stripped_b in NEGATION_STARTS else "medium",
            note="rule=repair; B-side negation / correction opener",
            rule_name="repair",
        )
        if candidate is not None:
            candidates.append(candidate)
            return candidates

    contrast_clause = select_contrast_clause(row["turn_b"])
    if any(marker in contrast_clause for marker in CONTRAST_MARKERS):
        candidate = make_candidate(
            row=row,
            span_a=span_a,
            span_b=contrast_clause,
            relation_type="contrast",
            relation_strength="medium",
            alignment_direction="A_to_B",
            is_core="0",
            supports_resonance="1",
            confidence="low" if len(normalize_for_length(contrast_clause)) > 14 else "medium",
            note="rule=contrast; explicit contrast/evaluation marker in B",
            rule_name="contrast",
        )
        if candidate is not None:
            candidates.append(candidate)

    return candidates


def build_semantic_substitution_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    # Intentional v1 choice: keep this effectively dormant unless a very explicit rename pattern appears.
    a_text = row["turn_a"]
    b_text = row["turn_b"]
    patterns = [
        re.compile(r"(.{2,8})不是(.{1,6})，?是(.{1,8})"),
        re.compile(r"(.{2,8})也叫(.{2,8})"),
    ]
    for pattern in patterns:
        match = pattern.search(b_text)
        if not match:
            continue
        left = match.group(1).strip()
        right = match.group(match.lastindex).strip()
        if left in a_text and right in b_text and is_meaningful_span(left, 2) and is_meaningful_span(right, 2):
            candidate = make_candidate(
                row=row,
                span_a=left,
                span_b=right,
                relation_type="semantic_substitution",
                relation_strength="strong",
                alignment_direction="A_to_B",
                is_core="0",
                supports_resonance="1",
                confidence="low",
                note="rule=semantic_substitution; explicit rename / rewrite pattern",
                rule_name="semantic_substitution",
            )
            return [candidate] if candidate is not None else []
    return []


def deduplicate_candidates(candidates: Iterable[CandidateColumn]) -> List[CandidateColumn]:
    best_by_key: Dict[Tuple[str, str, str], CandidateColumn] = {}
    for candidate in candidates:
        key = (candidate.pred_span_a, candidate.pred_span_b, candidate.pred_relation_type)
        existing = best_by_key.get(key)
        if existing is None or candidate.score > existing.score:
            best_by_key[key] = candidate
    return list(best_by_key.values())


def select_pair_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    candidates: List[CandidateColumn] = []
    candidates.extend(build_slot_or_short_answer_candidates(row))
    candidates.extend(build_repair_or_contrast_candidates(row))
    candidates.extend(build_lexical_candidates(row))
    candidates.extend(build_coreference_candidates(row))
    candidates.extend(build_semantic_substitution_candidates(row))

    deduped = deduplicate_candidates(candidates)
    relation_priority = {
        "repair": 0,
        "slot_filling": 1,
        "short_answer": 2,
        "lexical_reproduction": 3,
        "contrast": 4,
        "coreference_or_demonstrative": 5,
        "semantic_substitution": 6,
    }
    ranked = sorted(
        deduped,
        key=lambda item: (
            -item.score,
            relation_priority.get(item.pred_relation_type, 99),
            item.pred_span_a,
            item.pred_span_b,
        ),
    )[:MAX_COLUMNS_PER_PAIR]
    if ranked and not any(candidate.pred_is_core_column == "1" for candidate in ranked):
        ranked[0] = replace(ranked[0], pred_is_core_column="1")
    return ranked


def candidate_to_prediction_row(candidate: CandidateColumn, pred_column_id: str) -> Dict[str, str]:
    return {
        "annotation_id": candidate.annotation_id,
        "pair_id": candidate.pair_id,
        "pred_column_id": pred_column_id,
        "pred_span_a": candidate.pred_span_a,
        "pred_span_b": candidate.pred_span_b,
        "pred_relation_type": candidate.pred_relation_type,
        "pred_relation_strength": candidate.pred_relation_strength,
        "pred_alignment_direction": candidate.pred_alignment_direction,
        "pred_is_core_column": candidate.pred_is_core_column,
        "pred_supports_resonance": candidate.pred_supports_resonance,
        "pred_confidence": candidate.pred_confidence,
        "generator_name": GENERATOR_NAME,
        "generator_version": GENERATOR_VERSION,
        "notes": candidate.notes,
    }


def load_pair_rows() -> List[Dict[str, str]]:
    rows = read_csv_dicts(PAIR_LIST_PATH)
    required = {"annotation_id", "pair_id", "turn_a", "turn_b"}
    missing = required - set(rows[0].keys())
    if missing:
        raise ValueError(f"pair_list missing required fields: {sorted(missing)}")
    return rows


def generate_prediction_rows(pair_rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], Dict[str, List[CandidateColumn]]]:
    pair_candidates: Dict[str, List[CandidateColumn]] = {}
    prediction_rows: List[Dict[str, str]] = []

    for row in pair_rows:
        selected = select_pair_candidates(row)
        pair_candidates[row["annotation_id"]] = selected
        for index, candidate in enumerate(selected, start=1):
            prediction_rows.append(candidate_to_prediction_row(candidate, pred_column_id=f"P{index:02d}"))

    return prediction_rows, pair_candidates


def write_generation_report(
    pair_rows: List[Dict[str, str]],
    prediction_rows: List[Dict[str, str]],
    pair_candidates: Dict[str, List[CandidateColumn]],
) -> None:
    pair_count = len(pair_rows)
    covered_pairs = sorted(annotation_id for annotation_id, items in pair_candidates.items() if items)
    uncovered_pairs = [row["annotation_id"] for row in pair_rows if not pair_candidates[row["annotation_id"]]]
    relation_counter = Counter(row["pred_relation_type"] for row in prediction_rows)
    confidence_counter = Counter(row["pred_confidence"] for row in prediction_rows)
    rule_counter = Counter(candidate.rule_name for items in pair_candidates.values() for candidate in items)
    per_pair_counts = Counter(len(items) for items in pair_candidates.values())

    lines = [
        "# rule_baseline_v1 generation report",
        "",
        "## Overview",
        "",
        f"- total pairs scanned: {pair_count}",
        f"- predicted columns generated: {len(prediction_rows)}",
        f"- covered pairs: {len(covered_pairs)}",
        f"- empty-prediction pairs: {len(uncovered_pairs)}",
        f"- max candidates per pair: {MAX_COLUMNS_PER_PAIR}",
        "",
        "## Conservative design choices",
        "",
        "- baseline v1 only reads `diagraph_gold_50_pair_list.csv` turn text and does not read the formal database.",
        "- baseline v1 prioritizes high-precision rules for lexical reproduction, demonstrative/coreference, slot filling, short answer, contrast, and repair.",
        "- `semantic_substitution` is effectively near-dormant and only fires on explicit rename-style surface patterns.",
        "- `analogy` is intentionally not auto-generated in v1; this is a deliberate conservative baseline choice.",
        "- some pairs are allowed to stay empty rather than forcing low-quality columns.",
        "",
        "## Relation type distribution",
        "",
    ]
    for relation_type, count in relation_counter.most_common():
        lines.append(f"- {relation_type}: {count}")
    if not relation_counter:
        lines.append("- no predictions generated")
    lines.extend(
        [
            "",
            "## Confidence distribution",
            "",
        ]
    )
    for confidence, count in confidence_counter.most_common():
        lines.append(f"- {confidence}: {count}")
    lines.extend(
        [
            "",
            "## Triggered rule distribution",
            "",
        ]
    )
    for rule_name, count in rule_counter.most_common():
        lines.append(f"- {rule_name}: {count}")
    lines.extend(
        [
            "",
            "## Per-pair candidate count distribution",
            "",
        ]
    )
    for candidate_count in sorted(per_pair_counts):
        lines.append(f"- {candidate_count} columns: {per_pair_counts[candidate_count]} pairs")
    lines.extend(
        [
            "",
            "## Pairs with no prediction",
            "",
            ", ".join(uncovered_pairs) if uncovered_pairs else "none",
            "",
        ]
    )
    GENERATION_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_evaluation_summary() -> None:
    summary_data = json.loads((EVALUATION_RUN_DIR / "evaluation_summary.json").read_text(encoding="utf-8"))
    summary = summary_data["summary"]
    invalid_rows = read_csv_dicts(EVALUATION_RUN_DIR / "invalid_predictions.csv")
    invalid_reasons = Counter(row["invalid_reason"] for row in invalid_rows)

    lines = [
        "# rule_baseline_v1 evaluation summary",
        "",
        "## Counts",
        "",
        f"- gold columns: {summary['gold_column_count']}",
        f"- valid predictions: {summary['valid_prediction_count']}",
        f"- invalid predictions: {summary['invalid_prediction_count']}",
        f"- exact matches: {summary['exact_match_count']}",
        f"- relaxed matches: {summary['relaxed_match_count']}",
        "",
        "## Column metrics",
        "",
        f"- exact precision / recall / F1: {summary['exact_column_precision']} / {summary['exact_column_recall']} / {summary['exact_column_f1']}",
        f"- relaxed precision / recall / F1: {summary['relaxed_column_precision']} / {summary['relaxed_column_recall']} / {summary['relaxed_column_f1']}",
        "",
        "## Label/core metrics",
        "",
        f"- relation_type accuracy on exact matches: {summary['relation_type_accuracy_on_exact_matches']}",
        f"- relation_type accuracy on relaxed matches: {summary['relation_type_accuracy_on_relaxed_matches']}",
        f"- core column precision: {summary['core_column_precision']}",
        f"- core column recall: {summary['core_column_recall']}",
        f"- missing-core rate: {summary['missing_core_rate']}",
        f"- false-core rate: {summary['false_core_rate']}",
        "",
        "## Generation balance",
        "",
        f"- overgeneration rate: {summary['overgeneration_rate']}",
        f"- missing-column rate: {summary['missing_column_rate']}",
        f"- mean abs column count error by pair: {summary['mean_abs_column_count_error_by_pair']}",
        "",
        "## Pair-level diagnostics",
        "",
        f"- pairs with zero matched columns: {summary['pairs_with_zero_matched_columns']}",
        f"- pairs with missing core columns: {summary['pairs_with_missing_core_columns']}",
        f"- pairs with high overgeneration: {summary['pairs_with_high_overgeneration']}",
        "",
        "## Invalid prediction audit",
        "",
    ]
    if invalid_rows:
        for reason, count in invalid_reasons.most_common():
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- no invalid predictions")
    EVALUATION_SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_error_analysis() -> None:
    gold_rows = read_csv_dicts(DEFAULT_GOLD_ACTIVE)
    matched_relaxed = read_csv_dicts(EVALUATION_RUN_DIR / "matched_columns_relaxed.csv")
    per_pair_metrics = read_csv_dicts(EVALUATION_RUN_DIR / "per_pair_metrics.csv")
    overgenerated_rows = read_csv_dicts(EVALUATION_RUN_DIR / "overgenerated_prediction_columns.csv")
    unmatched_gold_rows = read_csv_dicts(EVALUATION_RUN_DIR / "unmatched_gold_columns.csv")

    gold_relation_counts = Counter(row["relation_type"] for row in gold_rows)
    matched_relation_counts = Counter(row["gold_relation_type"] for row in matched_relaxed)
    missing_relation_rows = []
    for relation_type in sorted(gold_relation_counts):
        gold_count = gold_relation_counts[relation_type]
        matched_count = matched_relation_counts.get(relation_type, 0)
        missing_relation_rows.append((relation_type, gold_count - matched_count, gold_count, matched_count))
    missing_relation_rows.sort(key=lambda item: (-item[1], item[0]))

    zero_match_pairs = [
        f"{row['annotation_id']}({row['pair_id']})"
        for row in per_pair_metrics
        if int(row["relaxed_match_count"]) == 0
    ]
    overgenerated_examples = overgenerated_rows[:10]
    unmatched_examples = unmatched_gold_rows[:10]

    lines = [
        "# rule_baseline_v1 error analysis",
        "",
        "## Why this baseline is conservative",
        "",
        "- v1 only trusts explicit surface triggers from `turn_a` / `turn_b` and allows many pairs to stay empty.",
        "- v1 does not auto-generate `analogy` and barely touches `semantic_substitution` unless the wording is extremely explicit.",
        "- high-risk long-range pragmatic mapping is intentionally left for later reranking / richer generation stages.",
        "",
        "## Relation types missed most",
        "",
    ]
    for relation_type, missing_count, gold_count, matched_count in missing_relation_rows:
        lines.append(
            f"- {relation_type}: missed {missing_count} / gold {gold_count} (matched {matched_count})"
        )
    lines.extend(
        [
            "",
            "## Pairs with zero relaxed match",
            "",
            ", ".join(zero_match_pairs) if zero_match_pairs else "none",
            "",
            "## Typical unmatched gold columns",
            "",
        ]
    )
    if unmatched_examples:
        for row in unmatched_examples:
            lines.append(
                f"- {row['annotation_id']}/{row['column_id']}: {row['relation_type']} | A=`{row['span_a']}` | B=`{row['span_b']}`"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Typical overgenerated prediction columns",
            "",
        ]
    )
    if overgenerated_examples:
        for row in overgenerated_examples:
            lines.append(
                f"- {row['annotation_id']}/{row['pred_column_id']}: {row['pred_relation_type']} | A=`{row['pred_span_a']}` | B=`{row['pred_span_b']}` | note={row['notes']}"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Why analogy is not auto-generated",
            "",
            "- analogy needs a stable structure-transfer chain from A to B, and baseline v1 intentionally avoids pretending that surface similarity is enough.",
            "- keeping analogy out of v1 makes the baseline easier to audit and prevents false positives from ironic or evaluative dialogue.",
            "",
            "## What a future BERT-assisted reranker/filter should prioritize",
            "",
            "- pragmatic_function columns that depend on discourse force rather than lexical overlap",
            "- semantic_substitution cases with real replacement slots instead of topic-level relatedness",
            "- long-range coreference / demonstrative mapping",
            "- analogy candidates with structural transfer",
            "- filtering weak lexical overlaps that create overgeneration noise",
            "",
        ]
    )
    ERROR_ANALYSIS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest() -> None:
    files_and_uses = [
        ("rule_baseline_prediction_v1.csv", "rule-based baseline prediction in schema-compliant CSV form"),
        ("rule_baseline_prediction_v1.xlsx", "spreadsheet view of the baseline prediction file"),
        ("rule_baseline_v1_generation_report.md", "generation-side summary of coverage, rule triggers, and conservative design choices"),
        ("rule_baseline_v1_evaluation_summary.md", "compact summary of evaluator metrics for the baseline run"),
        ("rule_baseline_v1_error_analysis.md", "error analysis focused on missed relation types, zero-match pairs, and overgeneration"),
        ("rule_baseline_v1_manifest.md", "artifact manifest for the whole baseline package"),
        ("evaluation_run/evaluation_summary.json", "machine-readable evaluator summary"),
        ("evaluation_run/evaluation_summary.md", "default evaluator summary report"),
        ("evaluation_run/per_pair_metrics.csv", "per-pair metric table from evaluator"),
        ("evaluation_run/per_pair_metrics.xlsx", "spreadsheet version of per-pair metrics"),
        ("evaluation_run/matched_columns_exact.csv", "exact-match alignment table"),
        ("evaluation_run/matched_columns_relaxed.csv", "relaxed-match alignment table"),
        ("evaluation_run/unmatched_gold_columns.csv", "gold columns not recovered after relaxed matching"),
        ("evaluation_run/overgenerated_prediction_columns.csv", "prediction columns with no relaxed gold match"),
        ("evaluation_run/invalid_predictions.csv", "invalid prediction rows excluded from scoring"),
        ("evaluation_run/relation_type_confusion_matrix.csv", "relation-type confusion matrix on relaxed matches"),
        ("evaluation_run/core_column_error_report.csv", "core-column specific mismatch audit"),
    ]
    lines = ["# rule_baseline_v1 manifest", "", "| file | purpose |", "| --- | --- |"]
    for file_name, purpose in files_and_uses:
        lines.append(f"| `{file_name}` | {purpose} |")
    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    pair_rows = load_pair_rows()
    pair_map = {row["annotation_id"]: row for row in pair_rows}
    prediction_rows, pair_candidates = generate_prediction_rows(pair_rows)
    ensure_prediction_rows_valid(prediction_rows, pair_map)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(PREDICTION_CSV_PATH, prediction_rows, PRED_REQUIRED_FIELDS)
    write_generation_report(pair_rows, prediction_rows, pair_candidates)

    evaluate_predictions(
        gold_path=DEFAULT_GOLD_ACTIVE,
        pair_list_path=PAIR_LIST_PATH,
        prediction_path=PREDICTION_CSV_PATH,
        output_dir=EVALUATION_RUN_DIR,
        relaxed_threshold=RELAXED_THRESHOLD,
        run_name="rule_baseline_prediction_v1",
    )

    write_evaluation_summary()
    write_error_analysis()
    write_manifest()

    stats = {
        "prediction_csv": str(PREDICTION_CSV_PATH),
        "predicted_columns": len(prediction_rows),
        "covered_pairs": sum(1 for items in pair_candidates.values() if items),
        "empty_prediction_pairs": sum(1 for items in pair_candidates.values() if not items),
        "evaluation_run_dir": str(EVALUATION_RUN_DIR),
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
