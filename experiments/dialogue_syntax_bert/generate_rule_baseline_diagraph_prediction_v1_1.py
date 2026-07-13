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

V1_DIR = ARTIFACT_ROOT / "diagraph_generation_evaluation_v1" / "rule_baseline_v1"
V1_PREDICTION_CSV_PATH = V1_DIR / "rule_baseline_prediction_v1.csv"
V1_SUMMARY_JSON_PATH = V1_DIR / "evaluation_run" / "evaluation_summary.json"

OUTPUT_DIR = ARTIFACT_ROOT / "diagraph_generation_evaluation_v1" / "rule_baseline_v1_1"
PREDICTION_CSV_PATH = OUTPUT_DIR / "rule_baseline_prediction_v1_1.csv"
EVALUATION_RUN_DIR = OUTPUT_DIR / "evaluation_run"
GENERATION_REPORT_PATH = OUTPUT_DIR / "rule_baseline_v1_1_generation_report.md"
EVALUATION_SUMMARY_PATH = OUTPUT_DIR / "rule_baseline_v1_1_evaluation_summary.md"
ERROR_ANALYSIS_PATH = OUTPUT_DIR / "rule_baseline_v1_1_error_analysis.md"
COMPARISON_REPORT_PATH = OUTPUT_DIR / "rule_baseline_v1_1_comparison_with_v1.md"
MANIFEST_PATH = OUTPUT_DIR / "rule_baseline_v1_1_manifest.md"

GENERATOR_NAME = "rule_baseline"
GENERATOR_VERSION = "v1.1"
RELAXED_THRESHOLD = 0.5
MAX_COLUMNS_PER_PAIR = 5
MAX_LEXICAL_COLUMNS_PER_PAIR = 2

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
ANSWER_SHORT_TOKENS = {
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
}
SAFE_DEMONSTRATIVES = {"这样", "那样", "这般", "如此", "这么", "那么", "是这样吗", "这样吗"}
NEGATION_STARTS = ["不是", "不对", "别", "不要", "不能", "不可", "不许", "不准", "没有", "没", "莫"]
BARE_NEGATION_TOKENS = {"不是", "不对", "没有", "没", "别", "不要", "不许", "不准", "莫"}
CONTRAST_MARKERS = ["还是", "一样", "而是", "却", "反而", "不过", "但是", "但"]
ALTERNATIVE_PLAN_MARKERS = {"由我", "我来", "我去", "还是一样", "而是", "不过", "却", "反而"}
ACTION_HINTS = {"想", "要", "会", "去", "来", "打", "捶", "动手", "做", "看", "说", "申请", "出面", "告诉"}
RESPONSE_ACTION_MARKERS = {"不要", "别", "不许", "不准", "由我", "我来", "我去", "还是", "打了", "动手"}
QUESTION_INTRO_B_SPANS = {"书云", "有人说", "比如", "例如", "你说", "我说"}
LOW_INFO_LEXICAL_SPANS = {
    "是",
    "在",
    "我",
    "你",
    "他",
    "她",
    "它",
    "这",
    "那",
    "此",
    "其",
    "也",
    "而",
    "的",
    "了",
    "之",
    "者",
    "们",
    "什么",
    "怎么",
    "一个",
    "一些",
    "一下",
    "一起",
    "一样",
    "这个",
    "那个",
    "这样",
    "那样",
    "不是",
    "没有",
    "可以",
    "我们",
    "你们",
    "他们",
    "她们",
    "它们",
}
FUNCTION_WORD_STOPS = {
    "这个",
    "那个",
    "这样",
    "那样",
    "不是",
    "没有",
    "可以",
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


def load_pair_rows() -> List[Dict[str, str]]:
    rows = read_csv_dicts(PAIR_LIST_PATH)
    required = {"annotation_id", "pair_id", "turn_a", "turn_b"}
    missing = required - set(rows[0].keys())
    if missing:
        raise ValueError(f"pair_list missing required fields: {sorted(missing)}")
    return rows


def split_clauses(text: str) -> List[str]:
    parts = [part.strip() for part in CLAUSE_BOUNDARY_RE.split(text or "") if part.strip()]
    return parts or ([text.strip()] if (text or "").strip() else [])


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


def is_low_information_lexical_span(span: str) -> bool:
    normalized = normalize_for_length(span)
    if not normalized:
        return True
    if normalized in LOW_INFO_LEXICAL_SPANS:
        return True
    if len(normalized) <= 2 and normalized in FUNCTION_WORD_STOPS:
        return True
    if len(normalized) == 2 and all(ch in "我你他她它这那其之的人了也们" for ch in normalized):
        return True
    return False


def is_question(text: str) -> bool:
    stripped = (text or "").strip()
    if any(marker in stripped for marker in QUESTION_MARKS):
        return True
    return any(term in stripped for term in QUESTION_TERMS)


def contains_question_word(text: str) -> bool:
    return any(term in (text or "") for term in QUESTION_TERMS)


def select_question_span(turn_a: str) -> str:
    for clause in split_clauses(turn_a):
        if contains_question_word(clause) or any(mark in clause for mark in QUESTION_MARKS):
            return clause
    return (turn_a or "").strip()


def select_reference_span(turn_a: str) -> str:
    clauses = split_clauses(turn_a)
    if not clauses:
        return (turn_a or "").strip()
    for clause in reversed(clauses):
        if is_meaningful_span(clause, min_len=2) and len(normalize_for_length(clause)) <= 24:
            return clause
    if len(normalize_for_length(turn_a)) <= 24:
        return (turn_a or "").strip()
    return clauses[-1]


def select_answer_clause(turn_b: str) -> str:
    clauses = split_clauses(turn_b)
    if not clauses:
        return (turn_b or "").strip()
    for clause in clauses:
        normalized = normalize_for_length(clause)
        if not normalized:
            continue
        if clause in QUESTION_INTRO_B_SPANS:
            continue
        if "?" in clause or "？" in clause:
            continue
        if clause in {"这", "那"}:
            continue
        return clause
    return clauses[0]


def looks_like_answer_clause(clause: str) -> bool:
    normalized = normalize_for_length(clause)
    if not normalized:
        return False
    if "?" in clause or "？" in clause:
        return False
    if clause in QUESTION_INTRO_B_SPANS:
        return False
    return True


def select_contrast_clause(turn_b: str) -> str:
    for clause in split_clauses(turn_b):
        if any(marker in clause for marker in CONTRAST_MARKERS):
            return clause
    return select_answer_clause(turn_b)


def has_action_hint(text: str) -> bool:
    return any(marker in (text or "") for marker in ACTION_HINTS)


def has_response_action_context(text: str) -> bool:
    return any(marker in (text or "") for marker in RESPONSE_ACTION_MARKERS)


def should_allow_speaker_shift(a_text: str, b_text: str, span_a: str, span_b: str) -> bool:
    if span_a == "我" and span_b == "你":
        return has_action_hint(a_text) and has_response_action_context(b_text)
    if span_a == "你" and span_b == "我":
        return is_question(a_text) and has_action_hint(b_text)
    if {span_a, span_b} == {"你们", "我们"}:
        return is_question(a_text) or has_response_action_context(b_text)
    return False


def is_definition_question(text: str) -> bool:
    stripped = (text or "").strip()
    return stripped.startswith("什么是") or stripped.endswith("是什么") or stripped.endswith("是什么？") or stripped.endswith("是什么?")


def relation_score(relation_type: str, strength: str, confidence: str, span_a: str, span_b: str) -> float:
    relation_base = {
        "repair": 95.0,
        "slot_filling": 92.0,
        "short_answer": 88.0,
        "contrast": 86.0,
        "lexical_reproduction": 76.0,
        "coreference_or_demonstrative": 66.0,
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
                if is_low_information_lexical_span(span):
                    continue
                candidates.add(span)
    selected: List[str] = []
    for span in sorted(candidates, key=lambda item: (-len(normalize_for_length(item)), item)):
        if any(span in existing for existing in selected if len(existing) >= len(span)):
            continue
        if len(normalize_for_length(span)) == 2 and is_low_information_lexical_span(span):
            continue
        selected.append(span)
        if len(selected) >= MAX_LEXICAL_COLUMNS_PER_PAIR:
            break
    return selected


def build_lexical_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    candidates: List[CandidateColumn] = []
    for span in extract_common_substrings(row["turn_a"], row["turn_b"]):
        normalized_len = len(normalize_for_length(span))
        if normalized_len < 2:
            continue
        if normalized_len == 2 and is_low_information_lexical_span(span):
            continue
        candidate = make_candidate(
            row=row,
            span_a=span,
            span_b=span,
            relation_type="lexical_reproduction",
            relation_strength="strong" if normalized_len >= 5 else "medium",
            alignment_direction="mutual",
            is_core="0",
            supports_resonance="1",
            confidence="high" if normalized_len >= 4 else "medium",
            note="rule=lexical_reproduction; pruned exact common substring",
            rule_name="lexical_reproduction",
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def build_coreference_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    candidates: List[CandidateColumn] = []
    a_text = row["turn_a"]
    b_text = row["turn_b"]

    for span_a, span_b in [("你", "我"), ("我", "你"), ("你们", "我们"), ("我们", "你们")]:
        if span_a in a_text and span_b in b_text and should_allow_speaker_shift(a_text, b_text, span_a, span_b):
            candidate = make_candidate(
                row=row,
                span_a=span_a,
                span_b=span_b,
                relation_type="coreference_or_demonstrative",
                relation_strength="strong",
                alignment_direction="A_to_B",
                is_core="0",
                supports_resonance="1",
                confidence="high",
                note="rule=coreference; constrained speaker-role / deictic shift",
                rule_name="coreference_or_demonstrative",
            )
            if candidate is not None:
                candidates.append(candidate)
            break

    for marker in SAFE_DEMONSTRATIVES:
        if marker in b_text:
            span_a = select_reference_span(a_text)
            if len(normalize_for_length(span_a)) < 4 or len(normalize_for_length(span_a)) > 22:
                continue
            clause = next((piece for piece in split_clauses(b_text) if marker in piece), marker)
            if not looks_like_answer_clause(clause):
                continue
            if normalize_for_length(clause) == marker:
                continue
            candidate = make_candidate(
                row=row,
                span_a=span_a,
                span_b=marker,
                relation_type="coreference_or_demonstrative",
                relation_strength="medium",
                alignment_direction="A_to_B",
                is_core="0",
                supports_resonance="1",
                confidence="medium",
                note=f"rule=demonstrative; constrained proposition recall via {marker}",
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
    span_b = select_answer_clause(row["turn_b"])
    normalized_b_len = len(normalize_for_length(span_b))
    if not looks_like_answer_clause(span_b):
        return []

    if is_definition_question(row["turn_a"]):
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

    if span_b in ANSWER_SHORT_TOKENS:
        candidate = make_candidate(
            row=row,
            span_a=span_a,
            span_b=span_b,
            relation_type="short_answer",
            relation_strength="medium" if normalized_b_len > 1 else "weak",
            alignment_direction="A_to_B",
            is_core="1",
            supports_resonance="1",
            confidence="high",
            note="rule=short_answer; explicit short B-side answer",
            rule_name="short_answer",
        )
        return [candidate] if candidate is not None else []

    if contains_question_word(span_a) and 2 <= normalized_b_len <= 20 and not contains_question_word(span_b):
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
            note="rule=slot_filling; explicit wh-question answered by B-side clause",
            rule_name="slot_filling",
        )
        return [candidate] if candidate is not None else []

    return []


def build_repair_or_contrast_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    span_a = select_reference_span(row["turn_a"])
    first_b_clause = select_answer_clause(row["turn_b"])
    stripped_b = first_b_clause.strip()

    if stripped_b in BARE_NEGATION_TOKENS:
        candidate = make_candidate(
            row=row,
            span_a=row["turn_a"].strip(),
            span_b=stripped_b,
            relation_type="repair",
            relation_strength="strong",
            alignment_direction="A_to_B",
            is_core="1",
            supports_resonance="1",
            confidence="high",
            note="rule=repair; bare negation directly rejecting A-side judgment/action",
            rule_name="repair",
        )
        return [candidate] if candidate is not None else []

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
            confidence="medium",
            note="rule=repair; B-side negation / correction opener",
            rule_name="repair",
        )
        return [candidate] if candidate is not None else []

    contrast_clause = select_contrast_clause(row["turn_b"])
    if "?" not in contrast_clause and "？" not in contrast_clause and any(
        marker in contrast_clause for marker in ALTERNATIVE_PLAN_MARKERS
    ):
        candidate = make_candidate(
            row=row,
            span_a=span_a,
            span_b=contrast_clause,
            relation_type="contrast",
            relation_strength="medium" if len(normalize_for_length(contrast_clause)) <= 16 else "weak",
            alignment_direction="A_to_B",
            is_core="1",
            supports_resonance="1",
            confidence="medium",
            note="rule=contrast; alternative plan / subject shift / evaluative reversal in B",
            rule_name="contrast",
        )
        return [candidate] if candidate is not None else []

    return []


def build_semantic_substitution_candidates(row: Dict[str, str]) -> List[CandidateColumn]:
    # v1.1 remains intentionally conservative here.
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


def postprocess_core_flags(candidates: List[CandidateColumn]) -> List[CandidateColumn]:
    if not candidates:
        return candidates
    strong_types = {"slot_filling", "short_answer", "repair", "contrast"}
    has_strong_type = any(candidate.pred_relation_type in strong_types for candidate in candidates)
    updated: List[CandidateColumn] = []
    for candidate in candidates:
        new_core = candidate.pred_is_core_column
        if has_strong_type:
            if candidate.pred_relation_type in strong_types and candidate.pred_confidence in {"high", "medium"}:
                new_core = "1"
            elif candidate.pred_relation_type in {"lexical_reproduction", "coreference_or_demonstrative", "semantic_substitution"}:
                new_core = "0"
        elif candidate.pred_relation_type == "lexical_reproduction":
            new_core = "1" if len(normalize_for_length(candidate.pred_span_a)) >= 4 else "0"
        elif candidate.pred_relation_type == "coreference_or_demonstrative":
            new_core = "1" if candidate.pred_confidence == "high" and len(candidates) == 1 else "0"
        updated.append(replace(candidate, pred_is_core_column=new_core))
    if not any(candidate.pred_is_core_column == "1" for candidate in updated):
        updated[0] = replace(updated[0], pred_is_core_column="1")
    return updated


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
        "contrast": 3,
        "lexical_reproduction": 4,
        "coreference_or_demonstrative": 5,
        "semantic_substitution": 6,
    }
    ranked = sorted(
        deduped,
        key=lambda item: (
            relation_priority.get(item.pred_relation_type, 99),
            -item.score,
            item.pred_span_a,
            item.pred_span_b,
        ),
    )[:MAX_COLUMNS_PER_PAIR]
    return postprocess_core_flags(ranked)


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
    covered_pairs = sorted(annotation_id for annotation_id, items in pair_candidates.items() if items)
    uncovered_pairs = [row["annotation_id"] for row in pair_rows if not pair_candidates[row["annotation_id"]]]
    relation_counter = Counter(row["pred_relation_type"] for row in prediction_rows)
    confidence_counter = Counter(row["pred_confidence"] for row in prediction_rows)
    lines = [
        "# rule_baseline_v1_1 generation report",
        "",
        "## Overview",
        "",
        f"- total pairs scanned: {len(pair_rows)}",
        f"- predicted columns generated: {len(prediction_rows)}",
        f"- covered pairs: {len(covered_pairs)}",
        f"- empty-prediction pairs: {len(uncovered_pairs)}",
        f"- max candidates per pair: {MAX_COLUMNS_PER_PAIR}",
        "",
        "## Targeted v1.1 changes",
        "",
        "- lexical reproduction is pruned harder: low-information spans are filtered, and at most two lexical columns remain per pair.",
        "- demonstrative/coreference no longer emits low-confidence bare 这/那 style links.",
        "- slot_filling / short_answer now require a clearer answer-like clause.",
        "- repair / contrast are slightly strengthened for high-confidence negation / alternative-plan patterns.",
        "- core flags are rebalanced so lexical/coreference columns do not automatically crowd out stronger question/repair/contrast chains.",
        "- analogy is still intentionally not auto-generated; semantic_substitution remains extremely conservative.",
        "",
        "## Relation type distribution",
        "",
    ]
    for relation_type, count in relation_counter.most_common():
        lines.append(f"- {relation_type}: {count}")
    if not relation_counter:
        lines.append("- no predictions generated")
    lines.extend(["", "## Confidence distribution", ""])
    for confidence, count in confidence_counter.most_common():
        lines.append(f"- {confidence}: {count}")
    lines.extend(["", "## Pairs with no prediction", "", ", ".join(uncovered_pairs) if uncovered_pairs else "none", ""])
    GENERATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_evaluation_summary() -> None:
    summary_data = json.loads((EVALUATION_RUN_DIR / "evaluation_summary.json").read_text(encoding="utf-8"))
    summary = summary_data["summary"]
    invalid_rows = read_csv_dicts(EVALUATION_RUN_DIR / "invalid_predictions.csv")
    lines = [
        "# rule_baseline_v1_1 evaluation summary",
        "",
        f"- gold columns: {summary['gold_column_count']}",
        f"- valid predictions: {summary['valid_prediction_count']}",
        f"- invalid predictions: {summary['invalid_prediction_count']}",
        f"- exact precision / recall / F1: {summary['exact_column_precision']} / {summary['exact_column_recall']} / {summary['exact_column_f1']}",
        f"- relaxed precision / recall / F1: {summary['relaxed_column_precision']} / {summary['relaxed_column_recall']} / {summary['relaxed_column_f1']}",
        f"- relation_type accuracy on exact matches: {summary['relation_type_accuracy_on_exact_matches']}",
        f"- relation_type accuracy on relaxed matches: {summary['relation_type_accuracy_on_relaxed_matches']}",
        f"- core column precision / recall: {summary['core_column_precision']} / {summary['core_column_recall']}",
        f"- missing-core rate: {summary['missing_core_rate']}",
        f"- false-core rate: {summary['false_core_rate']}",
        f"- overgeneration rate: {summary['overgeneration_rate']}",
        f"- missing-column rate: {summary['missing_column_rate']}",
        "",
        "## Invalid prediction audit",
        "",
        "- no invalid predictions" if not invalid_rows else f"- invalid rows: {len(invalid_rows)}",
        "",
    ]
    EVALUATION_SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_error_analysis() -> None:
    gold_rows = read_csv_dicts(DEFAULT_GOLD_ACTIVE)
    matched_relaxed = read_csv_dicts(EVALUATION_RUN_DIR / "matched_columns_relaxed.csv")
    overgenerated_rows = read_csv_dicts(EVALUATION_RUN_DIR / "overgenerated_prediction_columns.csv")
    unmatched_rows = read_csv_dicts(EVALUATION_RUN_DIR / "unmatched_gold_columns.csv")
    core_errors = read_csv_dicts(EVALUATION_RUN_DIR / "core_column_error_report.csv")

    gold_relation_counts = Counter(row["relation_type"] for row in gold_rows)
    matched_relation_counts = Counter(row["gold_relation_type"] for row in matched_relaxed)
    missing_rows = []
    for relation_type, gold_count in gold_relation_counts.items():
        matched_count = matched_relation_counts.get(relation_type, 0)
        missing_rows.append((relation_type, gold_count - matched_count, gold_count))
    missing_rows.sort(key=lambda item: (-item[1], item[0]))

    lines = [
        "# rule_baseline_v1_1 error analysis",
        "",
        "## What v1.1 intentionally does not try to solve",
        "",
        "- analogy is still left to later semantic/BERT-assisted modules.",
        "- semantic_substitution remains conservative and should not expand into topic-related paraphrase guessing.",
        "- pragmatic_function is still mostly outside pure surface-rule coverage.",
        "",
        "## Relation types still missed most",
        "",
    ]
    for relation_type, missing_count, gold_count in missing_rows:
        lines.append(f"- {relation_type}: missed {missing_count} / gold {gold_count}")
    lines.extend(
        [
            "",
            "## Overgeneration hot spots",
            "",
            f"- overgenerated predictions: {len(overgenerated_rows)}",
            "- the main remaining risks should now cluster around residual demonstrative linking, question-template overreach, and weak lexical repeats rather than open-ended analogy/semantic guesses.",
            "",
            "## Core-chain risks",
            "",
            f"- core error rows: {len(core_errors)}",
            "- if core recall is still low, the remaining gaps are more likely to be true capability boundaries (pragmatic_function / analogy / long reasoning chain) than easy lexical cleanup issues.",
            "",
            "## Typical unmatched gold examples",
            "",
        ]
    )
    for row in unmatched_rows[:10]:
        lines.append(
            f"- {row['annotation_id']}/{row['column_id']}: {row['relation_type']} | A=`{row['span_a']}` | B=`{row['span_b']}`"
        )
    ERROR_ANALYSIS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def comparison_rows(v1_summary: Dict[str, object], v11_summary: Dict[str, object], pair_count: int) -> List[Tuple[str, object, object, object]]:
    return [
        ("predicted_columns", v1_summary["valid_prediction_count"], v11_summary["valid_prediction_count"], int(v11_summary["valid_prediction_count"]) - int(v1_summary["valid_prediction_count"])),
        ("covered_pairs", v1_summary["covered_pairs"], v11_summary["covered_pairs"], int(v11_summary["covered_pairs"]) - int(v1_summary["covered_pairs"])),
        ("invalid_predictions", v1_summary["invalid_prediction_count"], v11_summary["invalid_prediction_count"], int(v11_summary["invalid_prediction_count"]) - int(v1_summary["invalid_prediction_count"])),
        ("exact_precision", v1_summary["exact_column_precision"], v11_summary["exact_column_precision"], round(float(v11_summary["exact_column_precision"]) - float(v1_summary["exact_column_precision"]), 6)),
        ("exact_recall", v1_summary["exact_column_recall"], v11_summary["exact_column_recall"], round(float(v11_summary["exact_column_recall"]) - float(v1_summary["exact_column_recall"]), 6)),
        ("exact_f1", v1_summary["exact_column_f1"], v11_summary["exact_column_f1"], round(float(v11_summary["exact_column_f1"]) - float(v1_summary["exact_column_f1"]), 6)),
        ("relaxed_precision", v1_summary["relaxed_column_precision"], v11_summary["relaxed_column_precision"], round(float(v11_summary["relaxed_column_precision"]) - float(v1_summary["relaxed_column_precision"]), 6)),
        ("relaxed_recall", v1_summary["relaxed_column_recall"], v11_summary["relaxed_column_recall"], round(float(v11_summary["relaxed_column_recall"]) - float(v1_summary["relaxed_column_recall"]), 6)),
        ("relaxed_f1", v1_summary["relaxed_column_f1"], v11_summary["relaxed_column_f1"], round(float(v11_summary["relaxed_column_f1"]) - float(v1_summary["relaxed_column_f1"]), 6)),
        ("relation_type_accuracy_exact", v1_summary["relation_type_accuracy_on_exact_matches"], v11_summary["relation_type_accuracy_on_exact_matches"], round(float(v11_summary["relation_type_accuracy_on_exact_matches"]) - float(v1_summary["relation_type_accuracy_on_exact_matches"]), 6)),
        ("relation_type_accuracy_relaxed", v1_summary["relation_type_accuracy_on_relaxed_matches"], v11_summary["relation_type_accuracy_on_relaxed_matches"], round(float(v11_summary["relation_type_accuracy_on_relaxed_matches"]) - float(v1_summary["relation_type_accuracy_on_relaxed_matches"]), 6)),
        ("core_column_recall", v1_summary["core_column_recall"], v11_summary["core_column_recall"], round(float(v11_summary["core_column_recall"]) - float(v1_summary["core_column_recall"]), 6)),
        ("missing_core_rate", v1_summary["missing_core_rate"], v11_summary["missing_core_rate"], round(float(v11_summary["missing_core_rate"]) - float(v1_summary["missing_core_rate"]), 6)),
        ("overgeneration_rate", v1_summary["overgeneration_rate"], v11_summary["overgeneration_rate"], round(float(v11_summary["overgeneration_rate"]) - float(v1_summary["overgeneration_rate"]), 6)),
        ("empty_prediction_pairs", pair_count - int(v1_summary["covered_pairs"]), pair_count - int(v11_summary["covered_pairs"]), (pair_count - int(v11_summary["covered_pairs"])) - (pair_count - int(v1_summary["covered_pairs"]))),
    ]


def write_comparison_with_v1(
    pair_rows: List[Dict[str, str]],
    prediction_rows: List[Dict[str, str]],
) -> bool:
    v1_prediction_rows = read_csv_dicts(V1_PREDICTION_CSV_PATH)
    v1_summary_data = json.loads(V1_SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    v11_summary_data = json.loads((EVALUATION_RUN_DIR / "evaluation_summary.json").read_text(encoding="utf-8"))
    v1_summary = dict(v1_summary_data["summary"])
    v11_summary = dict(v11_summary_data["summary"])
    v1_summary["covered_pairs"] = len({row["annotation_id"] for row in v1_prediction_rows})
    v11_summary["covered_pairs"] = len({row["annotation_id"] for row in prediction_rows})

    v1_type_counts = Counter(row["pred_relation_type"] for row in v1_prediction_rows)
    v11_type_counts = Counter(row["pred_relation_type"] for row in prediction_rows)
    rows = comparison_rows(v1_summary, v11_summary, len(pair_rows))

    adopt_v11 = (
        int(v11_summary["invalid_prediction_count"]) == 0
        and float(v11_summary["overgeneration_rate"]) <= float(v1_summary["overgeneration_rate"]) + 0.02
        and float(v11_summary["relaxed_column_precision"]) >= float(v1_summary["relaxed_column_precision"]) - 0.01
        and float(v11_summary["core_column_recall"]) >= float(v1_summary["core_column_recall"]) - 0.01
    )

    lines = [
        "# rule_baseline_v1_1 comparison with v1",
        "",
        "| metric | v1 | v1.1 | delta |",
        "| --- | --- | --- | --- |",
    ]
    for metric, old_value, new_value, delta in rows:
        lines.append(f"| {metric} | {old_value} | {new_value} | {delta} |")

    lines.extend(
        [
            "",
            "## Relation type count changes",
            "",
            f"- lexical_reproduction: {v1_type_counts.get('lexical_reproduction', 0)} -> {v11_type_counts.get('lexical_reproduction', 0)}",
            f"- coreference_or_demonstrative: {v1_type_counts.get('coreference_or_demonstrative', 0)} -> {v11_type_counts.get('coreference_or_demonstrative', 0)}",
            f"- slot_filling + short_answer: {v1_type_counts.get('slot_filling', 0) + v1_type_counts.get('short_answer', 0)} -> {v11_type_counts.get('slot_filling', 0) + v11_type_counts.get('short_answer', 0)}",
            f"- repair + contrast: {v1_type_counts.get('repair', 0) + v1_type_counts.get('contrast', 0)} -> {v11_type_counts.get('repair', 0) + v11_type_counts.get('contrast', 0)}",
            f"- semantic_substitution: {v1_type_counts.get('semantic_substitution', 0)} -> {v11_type_counts.get('semantic_substitution', 0)}",
            "",
            "## Judgment",
            "",
        ]
    )
    if adopt_v11:
        lines.append("- v1.1 is acceptable as the better candidate pool baseline: it stays clean on invalid rows, should reduce obvious false positives, and does not violate the main guardrails.")
    else:
        lines.append("- v1.1 is a tradeoff or regression relative to v1; keep v1 as the formal baseline if the guardrails are not met.")
    lines.append(
        "- v1.1 is not expected to improve every metric; the main success criterion is cleaner candidates with controlled overgeneration and no collapse in core recall."
    )

    COMPARISON_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return adopt_v11


def write_manifest() -> None:
    files_and_uses = [
        ("rule_baseline_prediction_v1_1.csv", "rule-based baseline v1.1 prediction in schema-compliant CSV form"),
        ("rule_baseline_prediction_v1_1.xlsx", "spreadsheet view of the v1.1 prediction file"),
        ("rule_baseline_v1_1_generation_report.md", "generation-side summary of v1.1 scope and coverage"),
        ("rule_baseline_v1_1_evaluation_summary.md", "compact summary of evaluator metrics for v1.1"),
        ("rule_baseline_v1_1_error_analysis.md", "error analysis for v1.1 after evaluator"),
        ("rule_baseline_v1_1_comparison_with_v1.md", "metric and relation-count comparison between v1 and v1.1"),
        ("rule_baseline_v1_1_manifest.md", "artifact manifest for the v1.1 package"),
        ("evaluation_run/evaluation_summary.json", "machine-readable evaluator summary for v1.1"),
        ("evaluation_run/evaluation_summary.md", "default evaluator summary report for v1.1"),
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
    lines = ["# rule_baseline_v1_1 manifest", "", "| file | purpose |", "| --- | --- |"]
    for file_name, purpose in files_and_uses:
        lines.append(f"| `{file_name}` | {purpose} |")
    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
        run_name="rule_baseline_prediction_v1_1",
    )

    write_evaluation_summary()
    write_error_analysis()
    adopt_v11 = write_comparison_with_v1(pair_rows, prediction_rows)
    write_manifest()

    stats = {
        "prediction_csv": str(PREDICTION_CSV_PATH),
        "predicted_columns": len(prediction_rows),
        "covered_pairs": len({row["annotation_id"] for row in prediction_rows}),
        "empty_prediction_pairs": len(pair_rows) - len({row["annotation_id"] for row in prediction_rows}),
        "evaluation_run_dir": str(EVALUATION_RUN_DIR),
        "adopt_v1_1": adopt_v11,
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
