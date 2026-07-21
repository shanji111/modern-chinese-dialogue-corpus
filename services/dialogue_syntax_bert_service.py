"""Optional, read-only BERT calibration for the existing dialogue-syntax graph.

The model never filters search results or replaces the rule-built graph.  It only
returns exploratory probabilities for the original six mechanism labels.
"""

from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path


LABEL_KEYS = (
    "reproduction",
    "parallelism",
    "selective_reuse",
    "repair",
    "contrast",
    "analogy_candidate",
)

LABEL_NAMES = {
    "reproduction": "重现",
    "parallelism": "平行",
    "selective_reuse": "选择",
    "repair": "修正",
    "contrast": "对比",
    "analogy_candidate": "类比",
}

DEFAULT_THRESHOLDS = {
    "reproduction": 0.58,
    "parallelism": 0.42,
    "selective_reuse": 0.72,
    "repair": 0.24,
    "contrast": 0.26,
    "analogy_candidate": 0.90,
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = (
    PROJECT_ROOT
    / "experiments"
    / "dialogue_syntax_bert"
    / "artifacts"
    / "old_taxonomy_bert_v2_model_20260721"
    / "seed_20260723"
)
DEFAULT_EVALUATION_REPORT = (
    PROJECT_ROOT
    / "experiments"
    / "dialogue_syntax_bert"
    / "artifacts"
    / "old_taxonomy_bert_v2_evaluation_20260721"
    / "evaluation_report.json"
)


def _truthy(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_model_dir() -> Path:
    configured = os.getenv("DIALOGUE_SYNTAX_BERT_MODEL_DIR", "").strip()
    return Path(configured) if configured else DEFAULT_MODEL_DIR


def _calibration_enabled(model_dir: Path) -> bool:
    configured = os.getenv("ENABLE_DIALOGUE_SYNTAX_BERT_CALIBRATION")
    if configured is not None:
        return _truthy(configured)
    # Development worktrees can opt in simply by retaining the local artifact.
    # Deployed environments without the untracked model remain rule-only.
    return model_dir.is_dir()


def _load_thresholds() -> dict[str, float]:
    configured = os.getenv("DIALOGUE_SYNTAX_BERT_EVALUATION_REPORT", "").strip()
    report_path = Path(configured) if configured else DEFAULT_EVALUATION_REPORT
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        values = payload.get("thresholds") or {}
    except (OSError, TypeError, ValueError):
        values = {}
    return {
        key: float(values.get(key, DEFAULT_THRESHOLDS[key]))
        for key in LABEL_KEYS
    }


@lru_cache(maxsize=2)
def _load_runtime(model_dir_text: str):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_dir = Path(model_dir_text)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
    if int(model.config.num_labels) != len(LABEL_KEYS):
        raise ValueError(
            f"Expected {len(LABEL_KEYS)} old-taxonomy labels, got {model.config.num_labels}."
        )
    model.to(torch.device("cpu"))
    model.eval()
    return torch, tokenizer, model


@lru_cache(maxsize=512)
def _predict_cached(model_dir_text: str, text_a: str, text_b: str) -> tuple[float, ...]:
    torch, tokenizer, model = _load_runtime(model_dir_text)
    encoded = tokenizer(
        text_a,
        text_b,
        padding=True,
        truncation=True,
        max_length=128,
        return_tensors="pt",
    )
    with torch.no_grad():
        logits = model(**encoded).logits
        probabilities = torch.sigmoid(logits)[0].cpu().tolist()
    return tuple(float(value) for value in probabilities)


def _unavailable_payload(reason: str, enabled: bool) -> dict[str, object]:
    return {
        "available": False,
        "enabled": enabled,
        "mode": "exploratory_auxiliary",
        "taxonomy_changed": False,
        "labels": [],
        "reason": reason,
        "notice": "图谱继续按旧规则生成；BERT 不参与检索排序或自动改判。",
    }


def get_dialogue_syntax_calibration(text_a: str, text_b: str) -> dict[str, object]:
    """Return old-taxonomy probabilities without changing rule decisions."""

    model_dir = _resolve_model_dir()
    enabled = _calibration_enabled(model_dir)
    if not enabled:
        return _unavailable_payload("disabled", enabled=False)
    if not model_dir.is_dir():
        return _unavailable_payload("model_missing", enabled=True)

    try:
        probabilities = _predict_cached(
            str(model_dir.resolve()),
            str(text_a or ""),
            str(text_b or ""),
        )
        thresholds = _load_thresholds()
    except (ImportError, ModuleNotFoundError):
        return _unavailable_payload("optional_dependencies_missing", enabled=True)
    except Exception as exc:
        return _unavailable_payload(f"runtime_error:{type(exc).__name__}", enabled=True)

    labels = []
    for key, probability in zip(LABEL_KEYS, probabilities):
        threshold = thresholds[key]
        labels.append({
            "key": key,
            "label": LABEL_NAMES[key],
            "probability": round(probability, 4),
            "threshold": round(threshold, 4),
            "suggested": probability >= threshold,
        })
    return {
        "available": True,
        "enabled": True,
        "mode": "exploratory_auxiliary",
        "taxonomy_changed": False,
        "model_version": "old-taxonomy-macbert-v2-seed-20260723",
        "threshold_source": "development_only_f0_5",
        "labels": labels,
        "notice": (
            "BERT 仅为旧分类提供探索性置信度；规则与模型一致时显示联合支持，"
            "不一致时仍保留规则结果并提示人工复核。"
        ),
    }


def reset_dialogue_syntax_bert_cache() -> None:
    """Testing helper; it does not mutate corpus or model artifacts."""

    _predict_cached.cache_clear()
    _load_runtime.cache_clear()
