"""Run non-finetuned similarity baselines for dialogue-pair annotations."""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

from io_utils import artifact_path, read_csv, write_csv, write_json
from labels import POSITIVE_LABEL_KEYS, human_labels_from_row, parse_bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, help="Annotation CSV or unfilled sample CSV.")
    parser.add_argument(
        "--output-csv",
        default=str(artifact_path("baselines", "similarity_scores.csv")),
        help="CSV with added baseline scores.",
    )
    parser.add_argument(
        "--output-json",
        default=str(artifact_path("baselines", "similarity_report.json")),
        help="Optional labeled-set report.",
    )
    parser.add_argument(
        "--bert-model",
        default="",
        help="Optional local or cached Hugging Face model name/path for BERT mean-pooled cosine.",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=128)
    return parser.parse_args()


def char_bigrams(text: str) -> set[str]:
    chars = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text or "")
    if len(chars) < 2:
        return set(chars)
    return {"".join(chars[index:index + 2]) for index in range(len(chars) - 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / len(left | right)


def dice(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))


def lexical_scores(row: dict[str, str]) -> dict[str, float]:
    a = char_bigrams(row.get("text_a", ""))
    b = char_bigrams(row.get("text_b", ""))
    return {
        "char_bigram_jaccard": jaccard(a, b),
        "char_bigram_dice": dice(a, b),
    }


def has_any_human_label(row: dict[str, str]) -> bool:
    if parse_bool(row.get("label_no_relation")):
        return True
    return any(parse_bool(row.get(f"label_{label_key}")) for label_key in POSITIVE_LABEL_KEYS)


def positive_any(row: dict[str, str]) -> bool:
    human = human_labels_from_row(row)
    return any(human[label_key] for label_key in POSITIVE_LABEL_KEYS)


def metrics_at_threshold(truth: list[bool], scores: list[float], threshold: float) -> dict[str, float | int]:
    preds = [score >= threshold for score in scores]
    tp = sum(1 for y, pred in zip(truth, preds) if y and pred)
    fp = sum(1 for y, pred in zip(truth, preds) if not y and pred)
    fn = sum(1 for y, pred in zip(truth, preds) if y and not pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"threshold": threshold, "precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def best_threshold_report(rows: list[dict[str, object]], score_column: str) -> dict[str, object]:
    labeled = [row for row in rows if row.get("_has_label")]
    truth = [bool(row["_positive_any"]) for row in labeled]
    scores = [float(row.get(score_column) or 0.0) for row in labeled]
    if not labeled:
        return {"score_column": score_column, "labeled_count": 0}
    candidates = sorted({0.0, 1.0, *scores})
    best = max((metrics_at_threshold(truth, scores, threshold) for threshold in candidates), key=lambda item: item["f1"])
    best["score_column"] = score_column
    best["labeled_count"] = len(labeled)
    best["support"] = sum(truth)
    return best


def compute_bert_cosine(rows: list[dict[str, object]], model_name: str, batch_size: int, max_length: int) -> list[float]:
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "BERT baseline requires optional dependencies: torch and transformers. "
            "Install them in an experiment environment, or omit --bert-model."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    def encode_texts(texts: list[str]):
        vectors = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch_texts = texts[start:start + batch_size]
                batch = tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                batch = {key: value.to(device) for key, value in batch.items()}
                outputs = model(**batch)
                mask = batch["attention_mask"].unsqueeze(-1).float()
                summed = (outputs.last_hidden_state * mask).sum(dim=1)
                counts = mask.sum(dim=1).clamp(min=1.0)
                vectors.append((summed / counts).cpu())
        return torch.cat(vectors, dim=0)

    left = encode_texts([str(row.get("text_a") or "") for row in rows])
    right = encode_texts([str(row.get("text_b") or "") for row in rows])
    numerator = (left * right).sum(dim=1)
    denominator = left.norm(dim=1) * right.norm(dim=1)
    cosine = numerator / denominator.clamp(min=1e-8)
    return [float(value) for value in cosine.tolist()]


def finite_float(value: float) -> float:
    return value if math.isfinite(value) else 0.0


def main() -> None:
    args = parse_args()
    raw_rows = read_csv(args.annotations)
    rows: list[dict[str, object]] = []
    for row in raw_rows:
        enriched: dict[str, object] = dict(row)
        enriched.update({key: finite_float(value) for key, value in lexical_scores(row).items()})
        enriched["_has_label"] = has_any_human_label(row)
        enriched["_positive_any"] = positive_any(row) if enriched["_has_label"] else False
        rows.append(enriched)

    score_columns = ["char_bigram_jaccard", "char_bigram_dice"]
    if args.bert_model:
        bert_scores = compute_bert_cosine(rows, args.bert_model, args.batch_size, args.max_length)
        for row, score in zip(rows, bert_scores):
            row["bert_embedding_cosine"] = finite_float(score)
        score_columns.append("bert_embedding_cosine")

    output_columns = list(raw_rows[0].keys()) if raw_rows else []
    for column in [*score_columns, "_has_label", "_positive_any"]:
        if column not in output_columns:
            output_columns.append(column)
    csv_path = write_csv(args.output_csv, rows, output_columns)
    report = {
        "row_count": len(rows),
        "score_reports": [best_threshold_report(rows, column) for column in score_columns],
    }
    json_path = write_json(args.output_json, report)
    print(f"rows={len(rows)}")
    print(f"wrote_csv={csv_path}")
    print(f"wrote_json={json_path}")


if __name__ == "__main__":
    main()

