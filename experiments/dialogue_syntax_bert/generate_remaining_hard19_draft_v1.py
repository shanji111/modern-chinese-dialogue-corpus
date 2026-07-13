from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


ROOT = Path(r"D:\现代汉语对话语料库-BERT实验\experiments\dialogue_syntax_bert")
BASE_DIR = ROOT / "artifacts" / "formal_300_v1" / "diagraph_gold_50"
OUTPUT_DIR = BASE_DIR / "remaining_hard19"

PRIORITY_PATH = BASE_DIR / "diagraph_gold_50_annotation_priority.csv"
PAIR_LIST_PATH = BASE_DIR / "diagraph_gold_50_pair_list.csv"
PILOT_REVIEWED_PATH = BASE_DIR / "pilot10_review" / "pilot10_column_annotation_reviewed_v1.csv"
EASY_MEDIUM_REVIEWED_PATH = (
    BASE_DIR
    / "remaining_easy_medium21"
    / "reviewed_v1"
    / "remaining_easy_medium21_column_reviewed_v1.csv"
)

PAIR_LIST_OUT = OUTPUT_DIR / "remaining_hard19_pair_list.csv"
DRAFT_OUT = OUTPUT_DIR / "remaining_hard19_column_draft_v1.csv"
REVIEW_PACKET_MD_OUT = OUTPUT_DIR / "remaining_hard19_review_packet.md"
HIGH_RISK_OUT = OUTPUT_DIR / "remaining_hard19_high_risk_items.csv"
VALIDATION_OUT = OUTPUT_DIR / "remaining_hard19_validation_report.md"
SUMMARY_OUT = OUTPUT_DIR / "remaining_hard19_annotation_summary.md"


VALID_RELATION_TYPES = {
    "lexical_reproduction",
    "syntactic_parallelism",
    "semantic_substitution",
    "coreference_or_demonstrative",
    "slot_filling",
    "short_answer",
    "contrast",
    "repair",
    "analogy",
    "pragmatic_function",
    "punctuation_or_modal",
    "other",
}
VALID_STRENGTHS = {"strong", "medium", "weak"}
VALID_DIRECTIONS = {"A_to_B", "B_to_A", "mutual"}
VALID_BINARY = {"0", "1"}
HIGH_RISK_RELATIONS = {
    "analogy",
    "semantic_substitution",
    "short_answer",
    "pragmatic_function",
    "coreference_or_demonstrative",
}


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def csv_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def as_int(value: str) -> int:
    return int(value) if value else 0


DRAFT_SPECS: Dict[str, List[Dict[str, str]]] = {
    "F300V1-0219": [
        {
            "span_a": "卖去",
            "span_b": "卖之",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B直接复现A中被建议的处理动作“卖去”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "或语令卖去",
            "span_b": "宁可不安己而移于他人哉？",
            "relation_type": "repair",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B对“卖去”的建议提出伦理性纠偏，指出不能把祸患转移给他人。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "该栏兼具反驳与伦理推理，需人工确认 relation_type 以免把单纯反对误标成 repair。",
        },
        {
            "span_a": "卖去",
            "span_b": "移于他人",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把“卖去”明确改写为“把后果移于他人”，用于解释其为何反对该建议。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "“卖去→移于他人”是解释性替换，需人工确认是否具备足够明确的替换位。",
        },
    ],
    "F300V1-0154": [
        {
            "span_a": "拜",
            "span_b": "拜",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B落实了A中建议的“拜”这一动作。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "遥拜",
            "span_b": "便拜",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A建议的“遥拜”改写为抵达后的实际拜见动作。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "“遥拜→便拜”既像动作落实也像语义改写，需人工确认是否保留为辅助栏。",
        },
    ],
    "F300V1-0106": [
        {
            "span_a": "他",
            "span_b": "他",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A/B都围绕同一人物“他”继续展开。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "他回到队上了",
            "span_b": "不敢相信",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B对A给出的命题作出惊讶性回应，而不是提供新的平行内容。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "命题到情态反应的映射较抽象，需人工确认该栏是否足以构成稳定跨句纵栏。",
        },
    ],
    "F300V1-0013": [
        {
            "span_a": "胜于",
            "span_b": "胜于",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A/B共享同一比较构式中心“胜于”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "优美胜于丑陋.",
            "span_b": "明了胜于晦涩.",
            "relation_type": "syntactic_parallelism",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "两轮都采用“X 胜于 Y”的稳定比较框架，是该样本的主链。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "优美",
            "span_b": "明了",
            "relation_type": "analogy",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A中的正面评价位迁移到另一组正向属性上。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "评价词替换是否上升为 analogy 需要人工确认，避免只因平行结构就自动类比化。",
        },
        {
            "span_a": "丑陋",
            "span_b": "晦涩",
            "relation_type": "analogy",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A中的负向评价位迁移到另一组负向属性上。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "该栏与整句平行链高度相关，需人工确认是否保留为辅助 analogy 栏。",
        },
    ],
    "F300V1-0043": [
        {
            "span_a": "一旦",
            "span_b": "就",
            "relation_type": "syntactic_parallelism",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A的条件前件由B以“就”引出结果后件，形成典型跨句条件结构配对。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "“一旦…就…”的跨句配对较强，但仍需人工确认是否作为 syntactic_parallelism 主链保留。",
        },
        {
            "span_a": "你一旦告诉我它是兔子",
            "span_b": "我就没法吃了",
            "relation_type": "pragmatic_function",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B补足了A提出的条件句后果，是该样本的核心跨句承接。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "该栏属于条件到结果的跨句补全，需人工确认是否应保留为 pragmatic_function 而非更纯结构类标签。",
        },
    ],
    "F300V1-0008": [
        {
            "span_a": "我",
            "span_b": "你",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "A中的自称“我”在B中被转成对该说话人的“你”。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "赁出一辆，我自己拉一辆，凑合了！",
            "span_b": "那还不是一样？",
            "relation_type": "contrast",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B直接否定A提出方案的改善效果，是该样本的主链。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "凑合了！",
            "span_b": "还是不着家儿！",
            "relation_type": "semantic_substitution",
            "relation_strength": "weak",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A所说的“凑合”后果重释为“仍旧不着家”的负面结果。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "这类结果性改写容易滑向普通话题评论，需人工确认是否真有明确替换位。",
        },
    ],
    "F300V1-0081": [
        {
            "span_a": "少平",
            "span_b": "他",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B中的“他”稳定回指A中的“少平”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "要交给你。",
            "span_b": "让他进来一块吃饭嘛！",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B围绕A中的交接场景给出新的行动安排，形成对前句事件的语用性回应。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "交接场景到邀请行动的承接较自然，但其是否构成稳定纵栏仍需人工复核。",
        },
    ],
    "F300V1-0224": [
        {
            "span_a": "先生",
            "span_b": "小生",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A对B的称呼“先生”在B中转换为自称“小生”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "琴中之意，妾已备知。",
            "span_b": "死也甘心。",
            "relation_type": "pragmatic_function",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B以强烈情感回应A对琴中情意的判断，是该样本的主链。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "情意判断到情感回应的映射跨度较大，需人工确认该栏的边界是否过宽。",
        },
        {
            "span_a": "有私奔之心",
            "span_b": "得见花颜",
            "relation_type": "semantic_substitution",
            "relation_strength": "weak",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B没有直接回应“私奔之心”，而是把情意落到“得见花颜”的愿望上。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "该栏较容易退化为普通情感同题相关，需人工确认是否应保留。",
        },
    ],
    "F300V1-0159": [
        {
            "span_a": "你摘馈我些叶儿。",
            "span_b": "要做甚麽？",
            "relation_type": "pragmatic_function",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B不是回答A，而是追问A提出行动的用途，是典型语用性承接。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "该样本只有追问链，需人工确认单栏是否足够支撑 pair-level resonance。",
        },
    ],
    "F300V1-0214": [
        {
            "span_a": "真.破车迷",
            "span_b": "还是孔帝不行",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B用继续抱怨球队人与决策的方式，语用上承接A的讽刺性标签。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "该样本高度依赖论坛语境，需人工确认“标签→抱怨内容”是否足以构成稳定跨句纵栏。",
        },
    ],
    "F300V1-0117": [
        {
            "span_a": "浑忘却。",
            "span_b": "斯言",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "weak",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B用“斯言”指向A中被忘却的那番话语内容。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "A中未明说被忘内容，需人工确认“浑忘却→斯言”是否允许作为跨句指称栏。",
        },
        {
            "span_a": "浑忘却。",
            "span_b": "何人不欲斯言耶？",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B对A所忘之言作出评价式追问，而不是简单重复该内容。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "该栏的命题桥接较强依赖解释，需人工确认是否保留辅助栏。",
        },
    ],
    "F300V1-0111": [
        {
            "span_a": "某些球迷",
            "span_b": "破车迷",
            "relation_type": "semantic_substitution",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B用更具体也更带立场色彩的“破车迷”压缩概括A中的群体。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "“某些球迷→破车迷”带强烈论坛语境色彩，需人工确认是否属于稳定可解释替换位。",
        },
        {
            "span_a": "某些球迷是多么的可笑",
            "span_b": "真.破车迷",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B用短标签压缩承接A的整体评价立场。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "评价命题被压缩成标签时容易过宽，需人工确认是否保留为辅助栏。",
        },
    ],
    "F300V1-0097": [
        {
            "span_a": "哈哈哈",
            "span_b": "好笑",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A的笑声行为转写为显性的“好笑”评价位。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "笑声行为与“好笑”概念间是解释性改写，需人工确认是否具备足够明确替换位。",
        },
        {
            "span_a": "哈哈哈~丝车~",
            "span_b": "有什么好笑的",
            "relation_type": "pragmatic_function",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B将A的笑声与调侃话语转化为追问式回应。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0017": [
        {
            "span_a": "像果腐那样新鲜的果腐",
            "span_b": "不是",
            "relation_type": "repair",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B用极简否定直接纠正A的整体判断，是该样本的唯一稳定主链。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0150": [
        {
            "span_a": "井丹高洁",
            "span_b": "未若长卿慢世。",
            "relation_type": "syntactic_parallelism",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "两轮都采用“人物 + 品评”的紧凑框架，B在同框架下反向比较。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "该样本同时带比较与人物替换，需人工确认主链应归为平行还是类比。",
        },
        {
            "span_a": "井丹",
            "span_b": "长卿",
            "relation_type": "analogy",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B以另一人物接管A中的人物评价位置，形成结构性转移。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "人物位替换是否足以上升为 analogy 需要人工确认。",
        },
        {
            "span_a": "高洁",
            "span_b": "慢世",
            "relation_type": "analogy",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B以不同评价维度承接A的人物品评位。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "评价维度更替容易和普通并列品评混淆，需人工确认是否保留。",
        },
    ],
    "F300V1-0128": [
        {
            "span_a": "今之乐犹古之乐也",
            "span_b": "可得闻与？",
            "relation_type": "pragmatic_function",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A关于“今之乐/古之乐”的论断转成进一步听闻的请求。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "该样本主要依赖追问承接，需人工确认单栏是否足够支撑该 pair 的共鸣。",
        },
    ],
    "F300V1-0092": [
        {
            "span_a": "之",
            "span_b": "某",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B用“某”填出A中“之”所指的人物或对象。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "A中的“之”过于简略，需人工确认其是否足以与“某”构成稳定跨句指称位。",
        },
        {
            "span_a": "深忆之。",
            "span_b": "即某是也。",
            "relation_type": "pragmatic_function",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B给出A所深忆之人的识别性回应，是该样本的核心问答式承接。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "A并未显式提问而是陈述性前提，需人工确认“识别性回应”是否宜放在 pragmatic_function 下。",
        },
    ],
    "F300V1-0205": [
        {
            "span_a": "皇极",
            "span_b": "此",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B中的“此”直接回指A单独提出的术语“皇极”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "皇极",
            "span_b": "人君为治之心法",
            "relation_type": "pragmatic_function",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B对A给出的术语做出定义式说明，是该样本的主链。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "单词提示到定义解释的跨句关系较强，需人工确认是否保留为 pragmatic_function 而非更窄标签。",
        },
    ],
    "F300V1-0220": [
        {
            "span_a": "此非距心之所得为也",
            "span_b": "今有受人之牛羊而为之牧之者",
            "relation_type": "analogy",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B先搭建一个“受托照料牛羊”的责任结构，用来映射A中的判断难题。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "A命题与B设喻之间的映射依赖解释链，需人工确认 analogy 主链是否成立。",
        },
        {
            "span_a": "非距心之所得为也",
            "span_b": "则反诸其人乎？抑亦立而视其死与？",
            "relation_type": "analogy",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A的判断转移到“应否放任牛羊死去”的责任追问上，以设喻推进论证。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "该栏属于长跨度类比链，需人工确认其是否过宽以及主链边界应如何切分。",
        },
        {
            "span_a": "距心",
            "span_b": "为之牧之者",
            "relation_type": "analogy",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B以受托牧者的位置映射A中承担责任的行动者。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "行动者位映射高度依赖注释性理解，需人工判断是否保留为辅助 analogy 栏。",
        },
    ],
}


def build_pair_rows() -> tuple[List[Dict[str, str]], set[str], set[str]]:
    priority_rows = read_csv_dicts(PRIORITY_PATH)
    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    pair_map = {row["annotation_id"]: row for row in pair_rows}
    pilot_ids = {row["annotation_id"] for row in read_csv_dicts(PILOT_REVIEWED_PATH)}
    easy_medium_ids = {
        row["annotation_id"] for row in read_csv_dicts(EASY_MEDIUM_REVIEWED_PATH)
    }

    selected: List[Dict[str, str]] = []
    for row in priority_rows:
        annotation_id = row["annotation_id"]
        if annotation_id in pilot_ids or annotation_id in easy_medium_ids:
            continue
        if row["difficulty_level"] != "hard":
            continue
        pair_row = pair_map[annotation_id]
        merged = {
            "annotation_id": annotation_id,
            "pair_id": row["pair_id"],
            "source": row["source"],
            "dataset_name": row["dataset_name"],
            "sample_stratum": pair_row["sample_stratum"],
            "difficulty_level": row["difficulty_level"],
            "priority_rank": row["priority_rank"],
            "expected_column_count": row["expected_column_count"],
            "dominant_relation_types": row["dominant_relation_types"],
            "why_this_difficulty": row["why_this_difficulty"],
            "annotation_warning": row["annotation_warning"],
            "suggested_first_pass": row["suggested_first_pass"],
            "turn_a": row["turn_a"],
            "turn_b": row["turn_b"],
            "resonance_present": pair_row["resonance_present"],
            "label_reproduction": pair_row["label_reproduction"],
            "label_parallelism": pair_row["label_parallelism"],
            "label_selective_reuse": pair_row["label_selective_reuse"],
            "label_repair": pair_row["label_repair"],
            "label_contrast": pair_row["label_contrast"],
            "label_analogy_candidate": pair_row["label_analogy_candidate"],
            "evidence_span_a": pair_row["evidence_span_a"],
            "evidence_span_b": pair_row["evidence_span_b"],
            "annotator_note": pair_row["annotator_note"],
            "rule_any_positive": pair_row["rule_any_positive"],
            "bert_prob": pair_row["bert_prob"],
            "hybrid_pred": pair_row["hybrid_pred"],
        }
        selected.append(merged)
    selected.sort(key=lambda row: int(row["priority_rank"]))
    return selected, pilot_ids, easy_medium_ids


def build_draft_rows(selected_pairs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    draft_rows: List[Dict[str, str]] = []
    for pair in selected_pairs:
        annotation_id = pair["annotation_id"]
        if annotation_id not in DRAFT_SPECS:
            raise KeyError(f"Missing hard draft spec for {annotation_id}")
        for idx, spec in enumerate(DRAFT_SPECS[annotation_id], start=1):
            row = {
                "annotation_id": annotation_id,
                "pair_id": pair["pair_id"],
                "column_id": f"C{idx:02d}",
                "span_a": spec["span_a"],
                "span_b": spec["span_b"],
                "relation_type": spec["relation_type"],
                "relation_strength": spec["relation_strength"],
                "alignment_direction": spec["alignment_direction"],
                "is_core_column": spec["is_core_column"],
                "supports_resonance": spec["supports_resonance"],
                "notes": spec["notes"],
                "draft_confidence": spec["draft_confidence"],
                "needs_human_review": spec["needs_human_review"],
                "review_reason": spec["review_reason"],
            }
            draft_rows.append(row)
    return draft_rows


def validate(
    selected_pairs: List[Dict[str, str]],
    draft_rows: List[Dict[str, str]],
    pilot_ids: set[str],
    easy_medium_ids: set[str],
) -> Dict[str, object]:
    pair_ids = {row["annotation_id"] for row in selected_pairs}
    pair_map = {row["annotation_id"]: row for row in selected_pairs}
    draft_pair_ids = {row["annotation_id"] for row in draft_rows}
    rows_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in draft_rows:
        rows_by_pair[row["annotation_id"]].append(row)

    errors: List[str] = []
    span_a_failures: List[str] = []
    span_b_failures: List[str] = []
    invalid_relation_rows: List[str] = []
    invalid_strength_rows: List[str] = []
    invalid_direction_rows: List[str] = []
    invalid_binary_rows: List[str] = []
    missing_rows_pairs: List[str] = []
    missing_core_pairs: List[str] = []
    non_hard_pairs: List[str] = []

    for annotation_id in pair_ids:
        pair = pair_map[annotation_id]
        if pair["difficulty_level"] != "hard":
            non_hard_pairs.append(annotation_id)
        rows = rows_by_pair.get(annotation_id, [])
        if not rows:
            missing_rows_pairs.append(annotation_id)
            continue
        if not any(row["is_core_column"] == "1" for row in rows):
            missing_core_pairs.append(annotation_id)

        turn_a = pair["turn_a"]
        turn_b = pair["turn_b"]
        for row in rows:
            tag = f"{annotation_id}/{row['column_id']}"
            if row["span_a"] not in turn_a:
                span_a_failures.append(tag)
            if row["span_b"] not in turn_b:
                span_b_failures.append(tag)
            if row["relation_type"] not in VALID_RELATION_TYPES:
                invalid_relation_rows.append(tag)
            if row["relation_strength"] not in VALID_STRENGTHS:
                invalid_strength_rows.append(tag)
            if row["alignment_direction"] not in VALID_DIRECTIONS:
                invalid_direction_rows.append(tag)
            if (
                row["is_core_column"] not in VALID_BINARY
                or row["supports_resonance"] not in VALID_BINARY
                or row["needs_human_review"] not in VALID_BINARY
            ):
                invalid_binary_rows.append(tag)

    if len(selected_pairs) != 19:
        errors.append(f"Expected 19 hard pairs, got {len(selected_pairs)}")
    if pair_ids & pilot_ids:
        errors.append(f"Pilot10 overlap detected: {sorted(pair_ids & pilot_ids)}")
    if pair_ids & easy_medium_ids:
        errors.append(
            f"remaining_easy_medium21 overlap detected: {sorted(pair_ids & easy_medium_ids)}"
        )
    if draft_pair_ids - pair_ids:
        errors.append(f"Unexpected draft ids: {sorted(draft_pair_ids - pair_ids)}")
    if missing_rows_pairs:
        errors.append(f"Pairs with no draft rows: {missing_rows_pairs}")
    if missing_core_pairs:
        errors.append(f"Pairs with no core column: {missing_core_pairs}")
    if span_a_failures:
        errors.append(f"span_a failures: {span_a_failures}")
    if span_b_failures:
        errors.append(f"span_b failures: {span_b_failures}")
    if invalid_relation_rows:
        errors.append(f"Invalid relation_type rows: {invalid_relation_rows}")
    if invalid_strength_rows:
        errors.append(f"Invalid relation_strength rows: {invalid_strength_rows}")
    if invalid_direction_rows:
        errors.append(f"Invalid alignment_direction rows: {invalid_direction_rows}")
    if invalid_binary_rows:
        errors.append(f"Invalid binary rows: {invalid_binary_rows}")
    if non_hard_pairs:
        errors.append(f"Non-hard pairs present: {non_hard_pairs}")

    review_rows = [row for row in draft_rows if row["needs_human_review"] == "1"]
    review_reason_counts = Counter(
        row["review_reason"] for row in review_rows if row["review_reason"]
    )
    relation_counts = Counter(row["relation_type"] for row in draft_rows)
    by_pair_counts = {annotation_id: len(rows) for annotation_id, rows in rows_by_pair.items()}
    core_counts = {
        annotation_id: sum(1 for row in rows if row["is_core_column"] == "1")
        for annotation_id, rows in rows_by_pair.items()
    }
    aux_counts = {
        annotation_id: sum(1 for row in rows if row["is_core_column"] == "0")
        for annotation_id, rows in rows_by_pair.items()
    }
    expected_ge_6 = sorted(
        annotation_id
        for annotation_id, pair in pair_map.items()
        if as_int(pair["expected_column_count"]) >= 6
    )
    overannotation_risk = sorted(
        annotation_id
        for annotation_id, count in by_pair_counts.items()
        if count > as_int(pair_map[annotation_id]["expected_column_count"]) + 1
        or aux_counts[annotation_id] > core_counts[annotation_id]
    )

    return {
        "errors": errors,
        "selected_count": len(selected_pairs),
        "draft_count": len(draft_rows),
        "review_count": len(review_rows),
        "review_reason_counts": review_reason_counts,
        "relation_counts": relation_counts,
        "by_pair_counts": by_pair_counts,
        "core_counts": core_counts,
        "aux_counts": aux_counts,
        "expected_ge_6": expected_ge_6,
        "overannotation_risk": overannotation_risk,
        "span_a_failures": span_a_failures,
        "span_b_failures": span_b_failures,
    }


def build_high_risk_rows(
    selected_pairs: List[Dict[str, str]],
    draft_rows: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    pair_map = {row["annotation_id"]: row for row in selected_pairs}
    rows_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in draft_rows:
        rows_by_pair[row["annotation_id"]].append(row)

    high_risk_rows: List[Dict[str, str]] = []
    for row in draft_rows:
        pair = pair_map[row["annotation_id"]]
        pair_rows = rows_by_pair[row["annotation_id"]]
        reasons: List[str] = []
        if row["relation_type"] in HIGH_RISK_RELATIONS:
            reasons.append(f"relation_type={row['relation_type']}")
        if as_int(pair["expected_column_count"]) >= 6:
            reasons.append("expected_column_count >= 6")
        if len(row["span_a"]) >= 16 or len(row["span_b"]) >= 16:
            reasons.append("long span boundary")
        if sum(1 for item in pair_rows if item["is_core_column"] == "0") > sum(
            1 for item in pair_rows if item["is_core_column"] == "1"
        ):
            reasons.append("auxiliary columns > core columns")
        if row["needs_human_review"] == "1":
            reasons.append("needs_human_review=1")
        if row["draft_confidence"] == "low":
            reasons.append("draft_confidence=low")
        if not reasons:
            continue

        focus_bits = []
        if row["relation_type"] == "analogy":
            focus_bits.append("确认 A 的结构是否真的被 B 转移、延展或反讽映射")
        if row["relation_type"] == "semantic_substitution":
            focus_bits.append("确认是否存在明确替换位，而不是单纯同题相关")
        if row["relation_type"] == "short_answer":
            focus_bits.append("确认该短答是否足以支撑稳定映射，而非普通接话")
        if row["relation_type"] == "pragmatic_function":
            focus_bits.append("确认该栏是否真是语用回应，而不是可更精确归类为 short_answer / semantic_substitution")
        if row["relation_type"] == "coreference_or_demonstrative":
            focus_bits.append("确认指称映射确实跨越 turn_a / turn_b")
        if as_int(pair["expected_column_count"]) >= 6:
            focus_bits.append("复核主链与辅助链切分，避免长样本无限增殖")
        if row["needs_human_review"] == "1" and row["review_reason"]:
            focus_bits.append(row["review_reason"])
        if not focus_bits:
            focus_bits.append("按 guide_v2 复核该栏的主链必要性与边界")

        high_risk_rows.append(
            {
                "annotation_id": row["annotation_id"],
                "pair_id": row["pair_id"],
                "column_id": row["column_id"],
                "reason": " | ".join(reasons),
                "suspected_relation_type": row["relation_type"],
                "why_high_risk": row["notes"],
                "suggested_review_focus": "；".join(dict.fromkeys(focus_bits)),
            }
        )
    return high_risk_rows


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_review_packet_md(
    selected_pairs: List[Dict[str, str]],
    draft_rows: List[Dict[str, str]],
) -> None:
    rows_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in draft_rows:
        rows_by_pair[row["annotation_id"]].append(row)

    lines: List[str] = ["# remaining_hard19 review packet", ""]
    for pair in selected_pairs:
        annotation_id = pair["annotation_id"]
        lines.extend(
            [
                f"## {annotation_id}",
                "",
                f"- pair_id: {pair['pair_id']}",
                f"- difficulty_level: {pair['difficulty_level']}",
                f"- source: {pair['source']}",
                f"- dataset_name: {pair['dataset_name']}",
                f"- dominant_relation_types: {pair['dominant_relation_types']}",
                f"- annotation_warning: {pair['annotation_warning'] or '无'}",
                f"- expected_column_count: {pair['expected_column_count']}",
                f"- pair-level labels: reproduction={pair['label_reproduction']}, parallelism={pair['label_parallelism']}, selective_reuse={pair['label_selective_reuse']}, repair={pair['label_repair']}, contrast={pair['label_contrast']}, analogy_candidate={pair['label_analogy_candidate']}",
                f"- evidence_span_a: {pair['evidence_span_a']}",
                f"- evidence_span_b: {pair['evidence_span_b']}",
                "",
                f"**turn_a**: {pair['turn_a']}",
                "",
                f"**turn_b**: {pair['turn_b']}",
                "",
                "| column_id | span_a | span_b | relation_type | strength | direction | core | supports | confidence | review | reason | notes |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        review_focus: List[str] = []
        for row in rows_by_pair[annotation_id]:
            lines.append(
                f"| {row['column_id']} | {csv_escape(row['span_a'])} | {csv_escape(row['span_b'])} | "
                f"{row['relation_type']} | {row['relation_strength']} | {row['alignment_direction']} | "
                f"{row['is_core_column']} | {row['supports_resonance']} | {row['draft_confidence']} | "
                f"{row['needs_human_review']} | {csv_escape(row['review_reason']) or '-'} | {csv_escape(row['notes'])} |"
            )
            if row["needs_human_review"] == "1" and row["review_reason"]:
                review_focus.append(row["review_reason"])
        if not review_focus:
            review_focus.append("先确认 core column 是否足够，再检查是否仍有可删的弱辅助栏。")
        lines.extend(["", "**human review focus**", ""])
        for item in dict.fromkeys(review_focus):
            lines.append(f"- {item}")
        lines.append("")

    REVIEW_PACKET_MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def write_validation_report(
    selected_pairs: List[Dict[str, str]],
    validation: Dict[str, object],
) -> None:
    review_reason_counts: Counter = validation["review_reason_counts"]  # type: ignore[assignment]
    lines = [
        "# remaining_hard19 validation report",
        "",
        "## Scope",
        f"- 样本数量: {validation['selected_count']}",
        "- 全部为 hard: 是" if validation["selected_count"] == 19 else "- 全部为 hard: 需复核",
        "- 不含 pilot10: 是" if not any("Pilot10 overlap" in err for err in validation["errors"]) else "- 不含 pilot10: 否",
        "- 不含 remaining_easy_medium21: 是" if not any("remaining_easy_medium21 overlap" in err for err in validation["errors"]) else "- 不含 remaining_easy_medium21: 否",
        f"- column draft 行数: {validation['draft_count']}",
        "",
        "## Structural checks",
        f"- 每个 pair 至少 1 行: {'通过' if not any('Pairs with no draft rows' in err for err in validation['errors']) else '未通过'}",
        f"- 每个 pair 至少 1 个 core column: {'通过' if not any('Pairs with no core column' in err for err in validation['errors']) else '未通过'}",
        f"- span_a 全部能在 turn_a 中找到: {'通过' if not validation['span_a_failures'] else '未通过'}",
        f"- span_b 全部能在 turn_b 中找到: {'通过' if not validation['span_b_failures'] else '未通过'}",
        f"- relation_type 合法: {'通过' if not any('Invalid relation_type' in err for err in validation['errors']) else '未通过'}",
        f"- relation_strength 合法: {'通过' if not any('Invalid relation_strength' in err for err in validation['errors']) else '未通过'}",
        f"- alignment_direction 合法: {'通过' if not any('Invalid alignment_direction' in err for err in validation['errors']) else '未通过'}",
        f"- is_core_column / supports_resonance / needs_human_review 合法: {'通过' if not any('Invalid binary rows' in err for err in validation['errors']) else '未通过'}",
        "",
        "## Human review load",
        f"- needs_human_review=1 的 column 数量: {validation['review_count']}",
    ]
    if review_reason_counts:
        lines.append("- 主要原因:")
        for reason, count in review_reason_counts.most_common():
            lines.append(f"  - {reason}: {count}")
    else:
        lines.append("- 主要原因: 无")

    lines.extend(
        [
            "",
            "## Long / dense samples",
            f"- expected_column_count >= 6 的样本: {', '.join(validation['expected_ge_6']) if validation['expected_ge_6'] else '无'}",
            f"- 过度标注风险样本: {', '.join(validation['overannotation_risk']) if validation['overannotation_risk'] else '无'}",
            "",
            "## Per-pair row counts",
        ]
    )
    pair_map = {row["annotation_id"]: row for row in selected_pairs}
    for annotation_id in sorted(validation["by_pair_counts"]):  # type: ignore[index]
        lines.append(
            f"- {annotation_id}: {validation['by_pair_counts'][annotation_id]} 行，"
            f"core={validation['core_counts'][annotation_id]}，"
            f"aux={validation['aux_counts'][annotation_id]}，"
            f"expected={pair_map[annotation_id]['expected_column_count']}"
        )

    lines.extend(["", "## Errors"])
    if validation["errors"]:
        for err in validation["errors"]:
            lines.append(f"- {err}")
    else:
        lines.append("- 无结构性错误。")

    VALIDATION_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(
    selected_pairs: List[Dict[str, str]],
    draft_rows: List[Dict[str, str]],
    validation: Dict[str, object],
    high_risk_rows: List[Dict[str, str]],
) -> None:
    review_counts_by_pair = Counter(
        row["annotation_id"] for row in draft_rows if row["needs_human_review"] == "1"
    )
    most_review_ids = [item[0] for item in review_counts_by_pair.most_common(8)]

    lines = [
        "# remaining_hard19 annotation summary",
        "",
        f"- 实际样本数量: {validation['selected_count']}",
        f"- 总 column 行数: {validation['draft_count']}",
        f"- needs_human_review 数量: {validation['review_count']}",
        f"- 最需要人工复核的 annotation_id: {', '.join(most_review_ids) if most_review_ids else '无'}",
        "",
        "## Per-pair counts",
    ]
    for annotation_id in sorted(validation["by_pair_counts"]):  # type: ignore[index]
        lines.append(
            f"- {annotation_id}: {validation['by_pair_counts'][annotation_id]} 行"
        )

    lines.extend(
        [
            "",
            "## Core / auxiliary distribution",
            f"- core 总数: {sum(row['is_core_column'] == '1' for row in draft_rows)}",
            f"- auxiliary 总数: {sum(row['is_core_column'] == '0' for row in draft_rows)}",
            "",
            "## relation_type distribution",
        ]
    )
    for relation_type, count in validation["relation_counts"].most_common():  # type: ignore[index]
        lines.append(f"- {relation_type}: {count}")

    lines.extend(
        [
            "",
            "## Hard-stage drift risks",
            "- analogy 容易被“有设喻/有评价/有人物替换”误触发，必须讲清结构链条。",
            "- semantic_substitution 最容易退化为普通话题相关，需要明确替换位。",
            "- short_answer 与 pragmatic_function 的边界在 hard 样本里会变得更模糊，宁可保守标 pragmatic_function 并加人工复核。",
            "- coreference_or_demonstrative 只能跨 turn_a / turn_b，不能拿单轮内部指称硬凑纵栏。",
            "",
            "## Why this is still draft",
            "- 本轮 hard19 含大量设喻、压缩回应、单句标签和强语境依赖样本，自动草拟只能提供候选链，不能直接等于 final gold。",
            "- 多数高风险栏已通过 needs_human_review=1 明示，需要人工在 high-risk review 中决定保留、改类或删除。",
            "",
            "## Review readiness",
            f"- 高风险条目数量: {len(high_risk_rows)}",
            "- 可以进入人工 high-risk review：是",
        ]
    )

    SUMMARY_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    selected_pairs, pilot_ids, easy_medium_ids = build_pair_rows()
    draft_rows = build_draft_rows(selected_pairs)
    validation = validate(selected_pairs, draft_rows, pilot_ids, easy_medium_ids)
    high_risk_rows = build_high_risk_rows(selected_pairs, draft_rows)

    pair_fieldnames = [
        "annotation_id",
        "pair_id",
        "source",
        "dataset_name",
        "sample_stratum",
        "difficulty_level",
        "priority_rank",
        "expected_column_count",
        "dominant_relation_types",
        "why_this_difficulty",
        "annotation_warning",
        "suggested_first_pass",
        "turn_a",
        "turn_b",
        "resonance_present",
        "label_reproduction",
        "label_parallelism",
        "label_selective_reuse",
        "label_repair",
        "label_contrast",
        "label_analogy_candidate",
        "evidence_span_a",
        "evidence_span_b",
        "annotator_note",
        "rule_any_positive",
        "bert_prob",
        "hybrid_pred",
    ]
    draft_fieldnames = [
        "annotation_id",
        "pair_id",
        "column_id",
        "span_a",
        "span_b",
        "relation_type",
        "relation_strength",
        "alignment_direction",
        "is_core_column",
        "supports_resonance",
        "notes",
        "draft_confidence",
        "needs_human_review",
        "review_reason",
    ]
    high_risk_fieldnames = [
        "annotation_id",
        "pair_id",
        "column_id",
        "reason",
        "suspected_relation_type",
        "why_high_risk",
        "suggested_review_focus",
    ]

    write_csv(PAIR_LIST_OUT, selected_pairs, pair_fieldnames)
    write_csv(DRAFT_OUT, draft_rows, draft_fieldnames)
    write_csv(HIGH_RISK_OUT, high_risk_rows, high_risk_fieldnames)
    write_review_packet_md(selected_pairs, draft_rows)
    write_validation_report(selected_pairs, validation)
    write_summary(selected_pairs, draft_rows, validation, high_risk_rows)


if __name__ == "__main__":
    main()
