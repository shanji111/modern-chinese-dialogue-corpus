"""Shared label schema for dialogue syntax experiments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DialogueSyntaxLabel:
    key: str
    zh_name: str
    short_definition: str
    positive_cues: tuple[str, ...]
    negative_cues: tuple[str, ...]

    @property
    def annotation_column(self) -> str:
        return f"label_{self.key}"

    @property
    def rule_column(self) -> str:
        return f"rule_{self.key}"


LABELS: tuple[DialogueSyntaxLabel, ...] = (
    DialogueSyntaxLabel(
        key="reproduction",
        zh_name="重现",
        short_definition="B turn reuses a lexical item, phrase, or compact expression from A turn.",
        positive_cues=("exact or near-exact lexical echo", "same key phrase in both turns"),
        negative_cues=("only topic similarity", "only shared stop words or function words"),
    ),
    DialogueSyntaxLabel(
        key="parallel",
        zh_name="平行",
        short_definition="A and B share a recognizable constructional or functional frame.",
        positive_cues=("same clause frame", "same question or stance pattern", "slot-by-slot parallelism"),
        negative_cues=("same words without comparable frame", "adjacent but structurally unrelated turns"),
    ),
    DialogueSyntaxLabel(
        key="selection",
        zh_name="选择/修正",
        short_definition="B selectively takes up part of A and extends, repairs, narrows, or reformulates it.",
        positive_cues=("partial uptake plus correction", "reformulation marker", "supplement after echo"),
        negative_cues=("plain repetition without change", "new answer with no selected material"),
    ),
    DialogueSyntaxLabel(
        key="contrast",
        zh_name="对比",
        short_definition="B responds by negating, opposing, replacing, or contrastively reframing A.",
        positive_cues=("negation of A material", "but/however contrast", "not X but Y pattern"),
        negative_cues=("negation unrelated to A", "negative word used in an independent answer"),
    ),
    DialogueSyntaxLabel(
        key="qa_response",
        zh_name="问答回应",
        short_definition="A creates an interrogative slot and B answers, rejects, or otherwise addresses it.",
        positive_cues=("question followed by answer", "question followed by accountable non-answer"),
        negative_cues=("rhetorical adjacency without response", "question marker inside quoted or unrelated text"),
    ),
    DialogueSyntaxLabel(
        key="analogy",
        zh_name="类比",
        short_definition="A and B map different surface material onto a similar relational structure.",
        positive_cues=("different words but parallel roles", "metaphoric or analogical structural mapping"),
        negative_cues=("only semantic similarity", "only shared topic without relation mapping"),
    ),
    DialogueSyntaxLabel(
        key="no_relation",
        zh_name="无明显关系",
        short_definition="No clear dialogue-syntax relation is present at the current annotation granularity.",
        positive_cues=("adjacent turns are unrelated", "response is too generic to classify"),
        negative_cues=("any confidently marked positive label"),
    ),
)

POSITIVE_LABEL_KEYS: tuple[str, ...] = tuple(label.key for label in LABELS if label.key != "no_relation")
ALL_LABEL_KEYS: tuple[str, ...] = tuple(label.key for label in LABELS)

ANNOTATION_COLUMNS: tuple[str, ...] = tuple(label.annotation_column for label in LABELS)
RULE_COLUMNS: tuple[str, ...] = tuple(label.rule_column for label in LABELS)

RULE_FLAG_COLUMNS: dict[str, str | None] = {
    "reproduction": "has_lexical_echo",
    "parallel": "has_pattern_reuse",
    "selection": "has_repair_repetition",
    "contrast": "has_negation_turn",
    "qa_response": "has_question_response",
    "analogy": None,
}

TRUE_VALUES = {"1", "true", "yes", "y", "是", "对", "有", "positive", "pos", "x", "✓"}
FALSE_VALUES = {"0", "false", "no", "n", "否", "错", "无", "negative", "neg", ""}


def parse_bool(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return False


def rule_labels_from_row(row: dict[str, object]) -> dict[str, bool]:
    predictions: dict[str, bool] = {}
    for label_key in POSITIVE_LABEL_KEYS:
        flag_name = RULE_FLAG_COLUMNS[label_key]
        predictions[label_key] = parse_bool(row.get(flag_name)) if flag_name else False
    predictions["no_relation"] = not any(predictions.values())
    return predictions


def human_labels_from_row(row: dict[str, object]) -> dict[str, bool]:
    labels = {
        label_key: parse_bool(row.get(f"label_{label_key}"))
        for label_key in ALL_LABEL_KEYS
    }
    if labels["no_relation"]:
        for label_key in POSITIVE_LABEL_KEYS:
            labels[label_key] = False
    return labels


def label_schema_markdown() -> str:
    lines = ["# Dialogue Syntax Label Schema", ""]
    for label in LABELS:
        lines.append(f"## {label.zh_name} (`{label.key}`)")
        lines.append("")
        lines.append(label.short_definition)
        lines.append("")
        lines.append("Positive cues:")
        for cue in label.positive_cues:
            lines.append(f"- {cue}")
        lines.append("")
        lines.append("Negative cues:")
        for cue in label.negative_cues:
            lines.append(f"- {cue}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

