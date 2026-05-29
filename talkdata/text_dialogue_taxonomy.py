from __future__ import annotations

TEXT_DIALOGUE_SOURCE = "文本对话"

TEXT_DIALOGUE_CATEGORIES = (
    "论辩语录",
    "短篇叙事对白",
    "历史汉语会话教材",
    "古典章回小说对白",
    "戏剧对白",
    "现当代小说对白",
)

DATASET_CATEGORY_MAP = {
    "论语": "论辩语录",
    "孟子": "论辩语录",
    "朱子语类": "论辩语录",
    "唐传奇": "短篇叙事对白",
    "清平山堂话本": "短篇叙事对白",
    "世说新语": "短篇叙事对白",
    "老乞大": "历史汉语会话教材",
    "朴通事": "历史汉语会话教材",
    "红楼梦": "古典章回小说对白",
    "水浒传": "古典章回小说对白",
    "西游记": "古典章回小说对白",
    "雷雨": "戏剧对白",
    "西厢记": "戏剧对白",
    "平凡的世界": "现当代小说对白",
    "骆驼祥子": "现当代小说对白",
}


def normalize_dataset_name(dataset_name: str | None) -> str:
    return (dataset_name or "").strip().strip("《》")


def text_dialogue_category_for_dataset(dataset_name: str | None, fallback: str = "") -> str:
    dataset_key = normalize_dataset_name(dataset_name)
    return DATASET_CATEGORY_MAP.get(dataset_key, fallback)
