import math
import time

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

SOURCE_STATS_CACHE_TTL_SECONDS = 60
_SOURCE_STATS_CACHE = {
    "expires_at": 0,
    "stats": None,
}


def get_section_names():
    return [section["name"] for section in HOME_CORPUS_SECTIONS]


def get_home_source_stats():
    now = time.monotonic()
    cached_stats = _SOURCE_STATS_CACHE.get("stats")
    if cached_stats is not None and _SOURCE_STATS_CACHE.get("expires_at", 0) > now:
        return cached_stats

    stats = corpus_repository.get_source_statistics(get_section_names())
    _SOURCE_STATS_CACHE["stats"] = stats
    _SOURCE_STATS_CACHE["expires_at"] = now + SOURCE_STATS_CACHE_TTL_SECONDS
    return stats


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


def build_home_context():
    sources, years = corpus_repository.get_filter_options()
    return {
        "sources": sources,
        "years": years,
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
    category_stats = order_category_stats(source, corpus_repository.get_browse_category_statistics(source))
    dataset_stats = corpus_repository.get_browse_dataset_statistics(source, category)

    if not category and not dataset_name and source in source_stats:
        total = active_stats["dialogue_count"]
    else:
        total = corpus_repository.count_browse_dialogues(source, category, dataset_name)

    total_pages = max(1, math.ceil(total / page_size))
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * page_size
    dialogues = corpus_repository.query_browse_dialogues(
        source,
        category,
        dataset_name,
        limit=page_size,
        offset=offset,
    )
    start_no = offset + 1 if total > 0 else 0
    end_no = min(offset + len(dialogues), total)

    sources, years = corpus_repository.get_filter_options()
    global_categories, _datasets = corpus_repository.get_advanced_filter_options()
    categories = [item["category"] for item in category_stats] or global_categories
    datasets = [item["dataset_name"] for item in dataset_stats]

    return {
        "sections": HOME_CORPUS_SECTIONS,
        "source_stats": source_stats,
        "active_stats": active_stats,
        "source": source,
        "category": category,
        "dataset_name": dataset_name,
        "sources": sources,
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
