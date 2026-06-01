import math

import corpus_repository


TEXT_DIALOGUE_SOURCE = "文本对话"
TEXT_DIALOGUE_CATEGORIES = (
    "论辩语录",
    "短篇叙事对白",
    "历史汉语会话教材",
    "古典章回小说对白",
    "戏剧对白",
    "现当代小说对白",
)

HOME_CORPUS_SECTIONS = [
    {
        "name": "日常对话",
        "description": "本板块收录日常问答、闲聊与口语互动语料，主要选取青云语料、ChatterBot 等公开中文对话资源，以及可公开使用的生活场景对话整理文本，用于观察高频口语表达、回应方式和话轮衔接特征。",
    },
    {
        "name": "影视对白",
        "description": "本板块汇集影视作品中的人物对白，主要依据公开字幕整理语料和可公开获取的字幕文本进行筛选与加工，适合考察不同情境中的人物互动、语气变化以及较强场景性的表达方式。",
    },
    {
        "name": "文本对话",
        "description": "本板块展示书面作品中的人物对话，主要选取公开出版文学文本、网络文学公开章节及其他可公开获取的叙事文本中的对话话轮，可用于比较书面叙述环境下的人物言语组织和表达风格。",
    },
    {
        "name": "网络回帖",
        "description": "本板块整理网络互动中的回帖语料，主要来源于贴吧、论坛及公开社交平台中的可获取互动文本，能够呈现网络语言、立场回应、跟帖链条和线上交流结构等较为鲜明的特点。",
    },
    {
        "name": "访谈语料",
        "description": "本板块收录访谈与问答实录，主要选取公开专访、新闻发布会文字实录、媒体问答整理稿等公开来源文本，适合分析提问方式、回应策略以及访谈过程中主题推进的语言特点。",
    },
    {
        "name": "课堂互动",
        "description": "本板块聚焦课堂教学中的师生互动，主要依据公开课程转写文本、教学实录和可公开获取的课堂问答材料整理而成，可用于观察课堂提问、即时回应以及教学话语组织方式。",
    },
    {
        "name": "多模态语料",
        "description": "本板块整合音频、视频与转写文本，主要选取带时间戳的公开转写语料、公开视频字幕文本及相关音视频整理材料，便于结合语音时序、画面线索和文本内容开展综合检索与分析。",
    },
]

STATIC_SOURCE_STATS = {
    "日常对话": {
        "source": "日常对话",
        "entry_count": 90075,
        "dialogue_count": 90075,
        "turn_count": 437704,
    },
    "影视对白": {
        "source": "影视对白",
        "entry_count": 6501,
        "dialogue_count": 6501,
        "turn_count": 43149,
    },
    "文本对话": {
        "source": "文本对话",
        "entry_count": 22910,
        "dialogue_count": 22910,
        "turn_count": 53382,
    },
    "网络回帖": {
        "source": "网络回帖",
        "entry_count": 9101,
        "dialogue_count": 9101,
        "turn_count": 18210,
    },
    "访谈语料": {
        "source": "访谈语料",
        "entry_count": 3101,
        "dialogue_count": 3101,
        "turn_count": 6473,
    },
    "课堂互动": {
        "source": "课堂互动",
        "entry_count": 1,
        "dialogue_count": 1,
        "turn_count": 1,
    },
    "多模态语料": {
        "source": "多模态语料",
        "entry_count": 129,
        "dialogue_count": 3,
        "turn_count": 129,
    },
}

STATIC_SOURCE_CATEGORIES = {
    "日常对话": (
        "豆瓣多轮对话",
        "青云语料",
        "chatterbot",
        "口语",
    ),
    "影视对白": (
        "subtitle",
        "对白",
    ),
    TEXT_DIALOGUE_SOURCE: TEXT_DIALOGUE_CATEGORIES,
    "网络回帖": (
        "贴吧回帖",
        "网络互动",
    ),
    "访谈语料": (
        "外交部记者会",
        "中国访谈",
        "发布会实录",
        "访谈",
    ),
    "课堂互动": (
        "教学互动",
    ),
    "多模态语料": (
        "音频转写",
        "音视频互动",
    ),
}

STATIC_SOURCE_DATASETS = {
    ("日常对话", "豆瓣多轮对话"): ("douban-multiturn-100w",),
    ("日常对话", "青云语料"): ("qingyun-11w", "青云语料"),
    ("日常对话", "chatterbot"): ("chatterbot-1k", "chatterbot"),
    ("日常对话", "口语"): ("口语",),
    ("影视对白", "subtitle"): ("subtitle-useless",),
    ("影视对白", "对白"): ("对白",),
    (TEXT_DIALOGUE_SOURCE, "论辩语录"): ("朱子语类", "孟子", "论语"),
    (TEXT_DIALOGUE_SOURCE, "短篇叙事对白"): ("唐传奇", "世说新语", "清平山堂话本"),
    (TEXT_DIALOGUE_SOURCE, "历史汉语会话教材"): ("朴通事", "老乞大"),
    (TEXT_DIALOGUE_SOURCE, "古典章回小说对白"): ("水浒传", "西游记"),
    (TEXT_DIALOGUE_SOURCE, "戏剧对白"): ("雷雨",),
    (TEXT_DIALOGUE_SOURCE, "现当代小说对白"): ("平凡的世界", "骆驼祥子"),
    ("网络回帖", "贴吧回帖"): ("tieba-305w", "贴吧回帖"),
    ("网络回帖", "网络互动"): ("网络互动",),
    ("访谈语料", "外交部记者会"): ("mfa_press",),
    ("访谈语料", "中国访谈"): ("china_interview",),
    ("访谈语料", "发布会实录"): ("china_live",),
    ("访谈语料", "访谈"): ("访谈",),
    ("课堂互动", "教学互动"): ("教学互动",),
    ("多模态语料", "音频转写"): ("local-audio-demo",),
    ("多模态语料", "音视频互动"): ("音视频互动",),
}

STATIC_TEXT_CATEGORY_COUNTS = {
    TEXT_DIALOGUE_CATEGORIES[0]: 8943,
    TEXT_DIALOGUE_CATEGORIES[1]: 1738,
    TEXT_DIALOGUE_CATEGORIES[2]: 157,
    TEXT_DIALOGUE_CATEGORIES[3]: 8098,
    TEXT_DIALOGUE_CATEGORIES[4]: 377,
    TEXT_DIALOGUE_CATEGORIES[5]: 3597,
}

STATIC_TEXT_DATASET_COUNTS = {
    "朱子语类": 8336,
    "孟子": 410,
    "论语": 197,
    "唐传奇": 718,
    "世说新语": 668,
    "清平山堂话本": 352,
    "朴通事": 110,
    "老乞大": 47,
    "水浒传": 2000,
    "西游记": 6098,
    "雷雨": 377,
    "平凡的世界": 3256,
    "骆驼祥子": 341,
}


def get_section_names():
    return [section["name"] for section in HOME_CORPUS_SECTIONS]


def get_home_source_stats():
    return {
        source: dict(STATIC_SOURCE_STATS.get(source, {
            "source": source,
            "entry_count": 0,
            "dialogue_count": 0,
            "turn_count": 0,
        }))
        for source in get_section_names()
    }


def parse_page_number(value):
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, page)


def parse_page_size(value):
    try:
        page_size = int(value)
    except (TypeError, ValueError):
        return 10
    return max(1, min(page_size, 20))


def get_source_stat(source_stats, source):
    return source_stats.get(source) or {
        "source": source,
        "entry_count": 0,
        "dialogue_count": 0,
        "turn_count": 0,
    }


def order_category_stats(source, category_stats):
    if source != TEXT_DIALOGUE_SOURCE:
        return category_stats
    order = {category: index for index, category in enumerate(TEXT_DIALOGUE_CATEGORIES)}
    return sorted(
        category_stats,
        key=lambda item: (order.get(item["category"], len(order)), item["category"]),
    )


def get_static_category_stats(source):
    stats = [
        {"category": category}
        for category in STATIC_SOURCE_CATEGORIES.get(source, ())
    ]
    if source == TEXT_DIALOGUE_SOURCE:
        for item in stats:
            item["dialogue_count"] = STATIC_TEXT_CATEGORY_COUNTS.get(item["category"], 0)
    return stats


def get_static_dataset_stats(source, category=""):
    categories = [category] if category else STATIC_SOURCE_CATEGORIES.get(source, ())
    datasets = []
    seen = set()
    for item_category in categories:
        for dataset_name in STATIC_SOURCE_DATASETS.get((source, item_category), ()):
            if dataset_name in seen:
                continue
            seen.add(dataset_name)
            item = {"dataset_name": dataset_name}
            if source == TEXT_DIALOGUE_SOURCE:
                item["dialogue_count"] = STATIC_TEXT_DATASET_COUNTS.get(dataset_name, 0)
            datasets.append(item)
    return datasets


def get_category_stats(source):
    return get_static_category_stats(source)


def get_dataset_stats(source, category=""):
    return get_static_dataset_stats(source, category)


def get_static_filter_total(source, category="", dataset_name="", active_stats=None):
    if source == TEXT_DIALOGUE_SOURCE:
        if dataset_name:
            return STATIC_TEXT_DATASET_COUNTS.get(dataset_name)
        if category:
            return STATIC_TEXT_CATEGORY_COUNTS.get(category)
    if not category and not dataset_name and active_stats:
        return active_stats.get("dialogue_count")
    return None


def build_home_context():
    return {
        "sources": get_section_names(),
        "years": [],
        "sections": HOME_CORPUS_SECTIONS,
        "source_stats": get_home_source_stats(),
    }


def build_browse_context(args):
    section_names = get_section_names()
    source = (args.get("source") or "").strip()
    category = (args.get("category") or "").strip()
    dataset_name = (args.get("dataset_name") or "").strip()
    if not source and section_names:
        source = section_names[0]

    page = parse_page_number(args.get("page", "1"))
    page_size = parse_page_size(args.get("page_size", "10"))
    source_stats = get_home_source_stats()
    active_stats = get_source_stat(source_stats, source)
    category_stats = order_category_stats(source, get_category_stats(source))
    dataset_stats = get_dataset_stats(source, category)

    static_total = get_static_filter_total(source, category, dataset_name, active_stats)
    total = static_total if static_total is not None else corpus_repository.count_browse_dialogues(source, category, dataset_name)

    total_pages = max(1, math.ceil(total / page_size))
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * page_size
    dialogues = []
    if total > 0:
        dialogues = corpus_repository.query_browse_dialogues(
            source,
            category,
            dataset_name,
            limit=page_size,
            offset=offset,
        )
    start_no = offset + 1 if total > 0 else 0
    end_no = min(offset + len(dialogues), total)

    categories = [item["category"] for item in category_stats]
    datasets = [item["dataset_name"] for item in dataset_stats]

    return {
        "sections": HOME_CORPUS_SECTIONS,
        "source_stats": source_stats,
        "active_stats": active_stats,
        "source": source,
        "category": category,
        "dataset_name": dataset_name,
        "sources": section_names,
        "categories": categories,
        "datasets": datasets,
        "category_stats": category_stats,
        "dataset_stats": dataset_stats,
        "dialogues": dialogues,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "start_no": start_no,
        "end_no": end_no,
        "query_args": {
            "source": source,
            "category": category,
            "dataset_name": dataset_name,
            "page_size": page_size,
        },
    }
