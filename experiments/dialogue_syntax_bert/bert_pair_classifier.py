"""Offline BERT finetuning for multi-label dialogue syntax classification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from io_utils import artifact_path, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", required=True)
    parser.add_argument("--dev-jsonl", required=True)
    parser.add_argument(
        "--output-dir",
        default=str(artifact_path("models", "bert_pair_classifier")),
        help="Model and report output directory.",
    )
    parser.add_argument("--model-name", default="bert-base-chinese")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=160)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260616)
    return parser.parse_args()


def load_jsonl(path: str | Path) -> list[dict[str, object]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def micro_metrics(y_true: list[list[int]], y_pred: list[list[int]]) -> dict[str, float | int]:
    tp = fp = fn = 0
    for truth_row, pred_row in zip(y_true, y_pred):
        for truth, pred in zip(truth_row, pred_row):
            if truth and pred:
                tp += 1
            elif not truth and pred:
                fp += 1
            elif truth and not pred:
                fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def main() -> None:
    args = parse_args()
    try:
        import torch
        from torch.utils.data import DataLoader, Dataset
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, set_seed
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "BERT finetuning requires optional dependencies: torch and transformers. "
            "Install them in an experiment environment before running this script."
        ) from exc

    set_seed(args.seed)
    train_records = load_jsonl(args.train_jsonl)
    dev_records = load_jsonl(args.dev_jsonl)
    if not train_records:
        raise SystemExit("No training records found.")
    label_keys = list(train_records[0]["label_keys"])

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    class PairDataset(Dataset):
        def __init__(self, records: list[dict[str, object]]):
            self.records = records

        def __len__(self) -> int:
            return len(self.records)

        def __getitem__(self, index: int) -> dict[str, object]:
            record = self.records[index]
            encoded = tokenizer(
                str(record.get("text_a") or ""),
                str(record.get("text_b") or ""),
                padding="max_length",
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            item = {key: value.squeeze(0) for key, value in encoded.items()}
            item["labels"] = torch.tensor(record["labels"], dtype=torch.float)
            return item

    def collate_batch(batch):
        return {
            key: torch.stack([item[key] for item in batch])
            for key in batch[0]
        }

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(label_keys),
        problem_type="multi_label_classification",
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    train_loader = DataLoader(PairDataset(train_records), batch_size=args.batch_size, shuffle=True, collate_fn=collate_batch)
    dev_loader = DataLoader(PairDataset(dev_records), batch_size=args.batch_size, shuffle=False, collate_fn=collate_batch)

    def evaluate() -> dict[str, object]:
        model.eval()
        all_truth: list[list[int]] = []
        all_pred: list[list[int]] = []
        total_loss = 0.0
        total_batches = 0
        with torch.no_grad():
            for batch in dev_loader:
                batch = {key: value.to(device) for key, value in batch.items()}
                outputs = model(**batch)
                total_loss += float(outputs.loss.item())
                total_batches += 1
                probs = torch.sigmoid(outputs.logits).cpu()
                preds = (probs >= args.threshold).int().tolist()
                truth = batch["labels"].int().cpu().tolist()
                all_truth.extend(truth)
                all_pred.extend(preds)
        metrics = micro_metrics(all_truth, all_pred)
        metrics["loss"] = total_loss / total_batches if total_batches else 0.0
        return metrics

    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total_batches = 0
        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            outputs = model(**batch)
            outputs.loss.backward()
            optimizer.step()
            total_loss += float(outputs.loss.item())
            total_batches += 1
        dev_metrics = evaluate()
        epoch_summary = {
            "epoch": epoch,
            "train_loss": total_loss / total_batches if total_batches else 0.0,
            "dev": dev_metrics,
        }
        history.append(epoch_summary)
        print(json.dumps(epoch_summary, ensure_ascii=False))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    report = {
        "model_name": args.model_name,
        "label_keys": label_keys,
        "train_count": len(train_records),
        "dev_count": len(dev_records),
        "threshold": args.threshold,
        "history": history,
    }
    report_path = write_json(output_dir / "training_report.json", report)
    print(f"wrote_model={output_dir}")
    print(f"wrote_report={report_path}")


if __name__ == "__main__":
    main()

