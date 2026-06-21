"""Check local Hugging Face cache for BERT shadow v2 candidate models."""

from __future__ import annotations

import argparse
import json
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import artifact_path, write_json, write_text


CANDIDATE_MODELS = [
    {
        "rank": 1,
        "model_id": "hfl/chinese-macbert-base",
        "role": "preferred main model",
        "recommendation": "优先作为 BERT shadow v2 主模型。",
    },
    {
        "rank": 2,
        "model_id": "hfl/chinese-roberta-wwm-ext",
        "role": "fallback main model",
        "recommendation": "如果 MacBERT 不存在，优先使用 RoBERTa-wwm。",
    },
    {
        "rank": 3,
        "model_id": "hfl/chinese-bert-wwm-ext",
        "role": "fallback main model",
        "recommendation": "如果 MacBERT 和 RoBERTa-wwm 都不存在，使用 BERT-wwm。",
    },
    {
        "rank": 4,
        "model_id": "IDEA-CCNL/Erlangshen-Roberta-110M-NLI",
        "role": "sentence-pair / NLI comparison",
        "recommendation": "只作为 sentence-pair / NLI 对照，不作为唯一主模型。",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hf-cache-dir",
        default="",
        help="Optional Hugging Face hub cache root. Defaults to HF_HUB_CACHE/HF_HOME or ~/.cache/huggingface/hub.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(artifact_path("formal_300_v1", "bert_shadow_v2_model_check")),
        help="Directory for model_availability_report.md/json.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing model-check reports.")
    return parser.parse_args()


def default_hf_cache_dir() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def cache_dir_name(model_id: str) -> str:
    return f"models--{model_id.replace('/', '--')}"


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


def find_snapshot(model_cache_dir: Path) -> Path | None:
    snapshots_dir = model_cache_dir / "snapshots"
    if not snapshots_dir.exists():
        return None
    snapshots = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not snapshots:
        return None
    return max(snapshots, key=lambda path: path.stat().st_mtime)


def has_any(snapshot: Path | None, names: list[str]) -> bool:
    return bool(snapshot and any((snapshot / name).exists() for name in names))


def file_list(snapshot: Path | None) -> list[str]:
    if not snapshot or not snapshot.exists():
        return []
    return sorted(path.name for path in snapshot.iterdir())


def load_model_info(snapshot: Path | None) -> dict[str, Any]:
    if not snapshot:
        return {
            "tokenizer_loadable": False,
            "model_loadable": False,
            "load_error": "No local snapshot found.",
        }

    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    try:
        from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
    except ModuleNotFoundError as exc:
        return {
            "tokenizer_loadable": False,
            "model_loadable": False,
            "load_error": f"Missing optional dependency: {exc.name}",
        }

    info: dict[str, Any] = {
        "tokenizer_loadable": False,
        "model_loadable": False,
        "base_model_loadable": False,
        "load_error": "",
        "config_model_type": "",
        "hidden_size": None,
        "num_layers": None,
        "vocab_size": None,
    }
    try:
        tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True)
        info["tokenizer_loadable"] = True
        info["tokenizer_class"] = tokenizer.__class__.__name__
    except Exception as exc:  # noqa: BLE001 - record local load failure.
        info["load_error"] = f"Tokenizer load failed: {exc}"
        return info

    try:
        config = AutoConfig.from_pretrained(str(snapshot), local_files_only=True)
        info["config_model_type"] = getattr(config, "model_type", "")
        info["hidden_size"] = getattr(config, "hidden_size", None)
        info["num_layers"] = getattr(config, "num_hidden_layers", None)
        info["vocab_size"] = getattr(config, "vocab_size", None)
    except Exception as exc:  # noqa: BLE001
        info["load_error"] = f"Config load failed: {exc}"
        return info

    try:
        model = AutoModelForSequenceClassification.from_pretrained(
            str(snapshot),
            num_labels=2,
            local_files_only=True,
        )
        info["model_loadable"] = True
        info["model_class"] = model.__class__.__name__
        del model
    except Exception as exc:  # noqa: BLE001
        info["load_error"] = f"SequenceClassification load failed: {exc}"
    return info


def inspect_model(model: dict[str, Any], hf_cache_dir: Path) -> dict[str, Any]:
    model_id = model["model_id"]
    model_cache_dir = hf_cache_dir / cache_dir_name(model_id)
    snapshot = find_snapshot(model_cache_dir) if model_cache_dir.exists() else None
    snapshot_files = file_list(snapshot)
    result: dict[str, Any] = {
        "rank": model["rank"],
        "model_id": model_id,
        "role": model["role"],
        "recommendation": model["recommendation"],
        "cache_dir": str(model_cache_dir),
        "cache_dir_exists": model_cache_dir.exists(),
        "selected_snapshot": str(snapshot) if snapshot else "",
        "snapshot_exists": bool(snapshot),
        "snapshot_files": snapshot_files,
        "has_config": bool(snapshot and (snapshot / "config.json").exists()),
        "has_tokenizer": has_any(
            snapshot,
            [
                "tokenizer.json",
                "vocab.txt",
                "spiece.model",
                "sentencepiece.bpe.model",
                "tokenizer_config.json",
            ],
        ),
        "has_weights": has_any(
            snapshot,
            [
                "pytorch_model.bin",
                "model.safetensors",
                "tf_model.h5",
                "flax_model.msgpack",
            ],
        ),
        "disk_size_bytes": dir_size_bytes(model_cache_dir),
    }
    result.update(load_model_info(snapshot))
    return result


def choose_recommendation(results: list[dict[str, Any]]) -> dict[str, Any]:
    loadable = [item for item in results if item.get("model_loadable")]
    main_candidates = [
        item
        for item in loadable
        if item["model_id"]
        in {
            "hfl/chinese-macbert-base",
            "hfl/chinese-roberta-wwm-ext",
            "hfl/chinese-bert-wwm-ext",
        }
    ]
    if main_candidates:
        selected = min(main_candidates, key=lambda item: item["rank"])
        return {
            "selected_model_id": selected["model_id"],
            "selected_snapshot": selected["selected_snapshot"],
            "reason": selected["recommendation"],
            "needs_manual_download": False,
        }
    nli = next((item for item in loadable if item["model_id"] == "IDEA-CCNL/Erlangshen-Roberta-110M-NLI"), None)
    if nli:
        return {
            "selected_model_id": nli["model_id"],
            "selected_snapshot": nli["selected_snapshot"],
            "reason": "Only the NLI comparison model is available locally; it should be used as a comparison, not the sole main model.",
            "needs_manual_download": True,
        }
    return {
        "selected_model_id": "",
        "selected_snapshot": "",
        "reason": "None of the requested Chinese candidate models are present and loadable in the local Hugging Face cache.",
        "needs_manual_download": True,
    }


def manual_download_advice() -> list[str]:
    return [
        "在可联网环境中手动下载首选模型，例如使用 huggingface-cli 或 transformers 预缓存；本脚本不会联网下载。",
        "建议优先缓存 hfl/chinese-macbert-base；若不可用，再缓存 hfl/chinese-roberta-wwm-ext 或 hfl/chinese-bert-wwm-ext。",
        "下载后重新运行本检查脚本，并把 --model-name-or-path 指向报告中的 selected_snapshot。",
    ]


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# BERT Shadow v2 Model Availability Report",
        "",
        "本报告只检查本地 Hugging Face cache，不联网下载模型，不训练模型，不读取正式数据库，不修改 gold/split 文件，也不接入网站。",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- HF cache dir: `{payload['hf_cache_dir']}`",
        f"- Python: {payload['environment']['python']}",
        f"- Platform: {payload['environment']['platform']}",
        "",
        "## Summary",
        "",
        "| Rank | Model | Cache | Tokenizer | Weights | Loadable | hidden/layers/vocab | Size |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in payload["models"]:
        shape = f"{item.get('hidden_size')}/{item.get('num_layers')}/{item.get('vocab_size')}"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["rank"]),
                    item["model_id"],
                    "yes" if item["cache_dir_exists"] else "no",
                    "yes" if item["has_tokenizer"] else "no",
                    "yes" if item["has_weights"] else "no",
                    "yes" if item.get("model_loadable") else "no",
                    shape,
                    format_size(int(item["disk_size_bytes"])),
                ]
            )
            + " |"
        )
    recommendation = payload["recommendation"]
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- Selected model: `{recommendation['selected_model_id'] or '(none)'}`",
            f"- Selected snapshot: `{recommendation['selected_snapshot'] or '(none)'}`",
            f"- Reason: {recommendation['reason']}",
            f"- Needs manual download: {recommendation['needs_manual_download']}",
            "",
            "## Details",
            "",
        ]
    )
    for item in payload["models"]:
        lines.extend(
            [
                f"### {item['model_id']}",
                "",
                f"- Role: {item['role']}",
                f"- Cache dir exists: {item['cache_dir_exists']}",
                f"- Cache dir: `{item['cache_dir']}`",
                f"- Selected snapshot: `{item['selected_snapshot'] or '(none)'}`",
                f"- Has config/tokenizer/weights: {item['has_config']} / {item['has_tokenizer']} / {item['has_weights']}",
                f"- Tokenizer loadable: {item.get('tokenizer_loadable')}",
                f"- SequenceClassification loadable: {item.get('model_loadable')}",
                f"- model_type: `{item.get('config_model_type') or ''}`",
                f"- hidden_size / num_layers / vocab_size: {item.get('hidden_size')} / {item.get('num_layers')} / {item.get('vocab_size')}",
                f"- Disk size: {format_size(int(item['disk_size_bytes']))}",
            ]
        )
        if item.get("load_error"):
            lines.append(f"- Load note: {item['load_error']}")
        lines.append("")
    if recommendation["needs_manual_download"]:
        lines.extend(["## Manual Download Advice", ""])
        lines.extend(f"- {line}" for line in payload["manual_download_advice"])
        lines.append("")
    lines.extend(
        [
            "## Safety Notes",
            "",
            "- 本轮没有训练任何模型。",
            "- 本轮没有运行批量 forward/prediction。",
            "- 本轮没有读取或写入正式 corpus.db。",
            "- 本轮没有修改 frozen gold_v1、gold_v1_binary 或 train/dev/test split。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    hf_cache_dir = Path(args.hf_cache_dir).expanduser() if args.hf_cache_dir else default_hf_cache_dir()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [inspect_model(model, hf_cache_dir) for model in CANDIDATE_MODELS]
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "hf_cache_dir": str(hf_cache_dir),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE", ""),
            "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE", ""),
        },
        "models": results,
        "recommendation": choose_recommendation(results),
        "manual_download_advice": manual_download_advice(),
        "safety": {
            "trained_model": False,
            "ran_batch_prediction": False,
            "read_or_wrote_corpus_db": False,
            "modified_gold_or_split": False,
            "connected_website": False,
        },
    }
    write_json(output_dir / "model_availability_report.json", payload, overwrite=args.overwrite)
    write_text(output_dir / "model_availability_report.md", markdown_report(payload), overwrite=args.overwrite)
    print(f"wrote={output_dir}")
    print(f"selected_model={payload['recommendation']['selected_model_id'] or '(none)'}")
    print(f"needs_manual_download={payload['recommendation']['needs_manual_download']}")


if __name__ == "__main__":
    main()
