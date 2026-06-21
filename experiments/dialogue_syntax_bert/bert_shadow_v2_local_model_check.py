"""Check a local Chinese model path for BERT shadow v2 without training."""

from __future__ import annotations

import argparse
import json
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ARTIFACTS_DIR, artifact_path, write_json, write_text


DEFAULT_MODEL_PATH = Path(r"D:\hf_models\hfl_chinese_macbert_base")
DEFAULT_OUTPUT_DIR = artifact_path("formal_300_v1", "bert_shadow_v2_model_check")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-path",
        default=str(DEFAULT_MODEL_PATH),
        help="Local model directory to check. No network download is attempted.",
    )
    parser.add_argument(
        "--model-id",
        default="hfl/chinese-macbert-base",
        help="Human-readable model id for the report.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for model_availability_report_v2.md/json.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting v2 model-check reports.")
    return parser.parse_args()


def ensure_artifact_dir(path: str | Path) -> Path:
    output_dir = Path(path)
    artifacts_root = ARTIFACTS_DIR.resolve()
    try:
        output_dir.resolve().relative_to(artifacts_root)
    except ValueError as exc:
        raise SystemExit(f"Output directory must be under {artifacts_root}: {output_dir}") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for file_path in path.rglob("*"):
        if file_path.is_file():
            try:
                total += file_path.stat().st_size
            except OSError:
                pass
    return total


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def has_any(path: Path, names: list[str]) -> bool:
    return any((path / name).exists() for name in names)


def file_status(path: Path) -> dict[str, Any]:
    return {
        "exists": path.exists(),
        "files": sorted(child.name for child in path.iterdir()) if path.exists() and path.is_dir() else [],
        "has_config": (path / "config.json").exists(),
        "has_tokenizer": has_any(
            path,
            [
                "tokenizer.json",
                "vocab.txt",
                "spiece.model",
                "sentencepiece.bpe.model",
                "tokenizer_config.json",
            ],
        ),
        "has_pytorch_or_safetensors_weights": has_any(path, ["pytorch_model.bin", "model.safetensors"]),
        "has_any_weights": has_any(path, ["pytorch_model.bin", "model.safetensors", "tf_model.h5", "flax_model.msgpack"]),
        "disk_size_bytes": dir_size_bytes(path),
    }


def load_status(path: Path) -> dict[str, Any]:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    status: dict[str, Any] = {
        "tokenizer_loadable": False,
        "sequence_classification_loadable": False,
        "base_model_loadable": False,
        "tokenizer_class": "",
        "sequence_classification_class": "",
        "base_model_class": "",
        "config_model_type": "",
        "hidden_size": None,
        "num_layers": None,
        "vocab_size": None,
        "load_errors": [],
    }
    if not path.exists():
        status["load_errors"].append("Local model path does not exist.")
        return status
    try:
        from transformers import AutoConfig, AutoModel, AutoModelForSequenceClassification, AutoTokenizer
    except ModuleNotFoundError as exc:
        status["load_errors"].append(f"Missing optional dependency: {exc.name}")
        return status

    try:
        tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        status["tokenizer_loadable"] = True
        status["tokenizer_class"] = tokenizer.__class__.__name__
    except Exception as exc:  # noqa: BLE001
        status["load_errors"].append(f"AutoTokenizer failed: {exc}")

    try:
        config = AutoConfig.from_pretrained(str(path), local_files_only=True)
        status["config_model_type"] = getattr(config, "model_type", "")
        status["hidden_size"] = getattr(config, "hidden_size", None)
        status["num_layers"] = getattr(config, "num_hidden_layers", None)
        status["vocab_size"] = getattr(config, "vocab_size", None)
    except Exception as exc:  # noqa: BLE001
        status["load_errors"].append(f"AutoConfig failed: {exc}")

    try:
        model = AutoModelForSequenceClassification.from_pretrained(
            str(path),
            num_labels=2,
            local_files_only=True,
        )
        status["sequence_classification_loadable"] = True
        status["sequence_classification_class"] = model.__class__.__name__
        del model
    except Exception as exc:  # noqa: BLE001
        status["load_errors"].append(f"AutoModelForSequenceClassification failed: {exc}")
        try:
            base_model = AutoModel.from_pretrained(str(path), local_files_only=True)
            status["base_model_loadable"] = True
            status["base_model_class"] = base_model.__class__.__name__
            del base_model
        except Exception as base_exc:  # noqa: BLE001
            status["load_errors"].append(f"AutoModel fallback failed: {base_exc}")

    return status


def recommendation(payload: dict[str, Any]) -> dict[str, Any]:
    files = payload["files"]
    load = payload["load"]
    usable = bool(
        files["exists"]
        and files["has_config"]
        and files["has_tokenizer"]
        and files["has_pytorch_or_safetensors_weights"]
        and load["tokenizer_loadable"]
        and (load["sequence_classification_loadable"] or load["base_model_loadable"])
    )
    if usable:
        return {
            "usable_for_shadow_v2": True,
            "recommended_as_main_model": True,
            "needs_redownload": False,
            "reason": "Local MacBERT has config, tokenizer, PyTorch/safetensors weights, and loads offline. Recommend it as BERT shadow v2 main model.",
        }
    missing = []
    if not files["exists"]:
        missing.append("model directory")
    if not files["has_config"]:
        missing.append("config.json")
    if not files["has_tokenizer"]:
        missing.append("tokenizer files")
    if not files["has_pytorch_or_safetensors_weights"]:
        missing.append("pytorch_model.bin or model.safetensors")
    if not load["tokenizer_loadable"]:
        missing.append("loadable tokenizer")
    if not (load["sequence_classification_loadable"] or load["base_model_loadable"]):
        missing.append("loadable model")
    return {
        "usable_for_shadow_v2": False,
        "recommended_as_main_model": False,
        "needs_redownload": True,
        "reason": "Model is not usable offline. Missing or failed: " + ", ".join(missing),
    }


def markdown_report(payload: dict[str, Any]) -> str:
    files = payload["files"]
    load = payload["load"]
    rec = payload["recommendation"]
    lines = [
        "# BERT Shadow v2 Local Model Check",
        "",
        "本报告只检查指定本地模型路径，不联网下载，不训练模型，不运行批量预测，不读取正式数据库，不修改 gold/split 文件，也不接入网站。",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Model id: `{payload['model_id']}`",
        f"- Model path: `{payload['model_path']}`",
        f"- Python: {payload['environment']['python']}",
        f"- Platform: {payload['environment']['platform']}",
        "",
        "## File Availability",
        "",
        f"- Directory exists: {files['exists']}",
        f"- Has config: {files['has_config']}",
        f"- Has tokenizer: {files['has_tokenizer']}",
        f"- Has PyTorch/safetensors weights: {files['has_pytorch_or_safetensors_weights']}",
        f"- Has any weights: {files['has_any_weights']}",
        f"- Disk size: {format_size(int(files['disk_size_bytes']))}",
        "",
        "## Offline Load Check",
        "",
        f"- AutoTokenizer loadable: {load['tokenizer_loadable']}",
        f"- Tokenizer class: `{load['tokenizer_class']}`",
        f"- AutoModelForSequenceClassification loadable: {load['sequence_classification_loadable']}",
        f"- Sequence classification class: `{load['sequence_classification_class']}`",
        f"- AutoModel fallback loadable: {load['base_model_loadable']}",
        f"- Base model class: `{load['base_model_class']}`",
        f"- model_type: `{load['config_model_type']}`",
        f"- hidden_size / num_layers / vocab_size: {load['hidden_size']} / {load['num_layers']} / {load['vocab_size']}",
        "",
        "## Recommendation",
        "",
        f"- Usable for shadow v2: {rec['usable_for_shadow_v2']}",
        f"- Recommended as main model: {rec['recommended_as_main_model']}",
        f"- Needs redownload: {rec['needs_redownload']}",
        f"- Reason: {rec['reason']}",
        "",
    ]
    if load["load_errors"]:
        lines.extend(["## Load Notes", ""])
        lines.extend(f"- {item}" for item in load["load_errors"])
        lines.append("")
    lines.extend(
        [
            "## Safety Notes",
            "",
            "- No model training was run.",
            "- No batch forward/prediction was run.",
            "- No formal corpus.db access was performed.",
            "- No frozen gold_v1, gold_v1_binary, or train/dev/test split files were modified.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    output_dir = ensure_artifact_dir(args.output_dir)
    model_path = Path(args.model_path)
    payload: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model_id": args.model_id,
        "model_path": str(model_path),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE", ""),
            "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE", ""),
        },
        "files": file_status(model_path),
        "load": load_status(model_path),
        "safety": {
            "trained_model": False,
            "ran_batch_prediction": False,
            "read_or_wrote_corpus_db": False,
            "modified_gold_or_split": False,
            "connected_website": False,
        },
    }
    payload["recommendation"] = recommendation(payload)
    write_json(output_dir / "model_availability_report_v2.json", payload, overwrite=args.overwrite)
    write_text(output_dir / "model_availability_report_v2.md", markdown_report(payload), overwrite=args.overwrite)
    print(f"wrote={output_dir}")
    print(f"model_exists={payload['files']['exists']}")
    print(f"tokenizer_loadable={payload['load']['tokenizer_loadable']}")
    print(f"model_loadable={payload['load']['sequence_classification_loadable'] or payload['load']['base_model_loadable']}")
    print(f"recommended={payload['recommendation']['recommended_as_main_model']}")


if __name__ == "__main__":
    main()
