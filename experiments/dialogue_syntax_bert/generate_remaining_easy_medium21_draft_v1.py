from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


ROOT = Path(r"D:\现代汉语对话语料库-BERT实验\experiments\dialogue_syntax_bert")
BASE_DIR = ROOT / "artifacts" / "formal_300_v1" / "diagraph_gold_50"
OUTPUT_DIR = BASE_DIR / "remaining_easy_medium21"

PRIORITY_PATH = BASE_DIR / "diagraph_gold_50_annotation_priority.csv"
PILOT10_LIST_PATH = BASE_DIR / "diagraph_gold_50_pilot10_list.csv"
PAIR_LIST_PATH = BASE_DIR / "diagraph_gold_50_pair_list.csv"
REVIEWED_V1_PATH = BASE_DIR / "pilot10_review" / "pilot10_column_annotation_reviewed_v1.csv"
GUIDE_V2_PATH = BASE_DIR / "diagraph_gold_50_annotation_guide_v2.md"
PLAN_V2_PATH = BASE_DIR / "diagraph_gold_50_remaining40_annotation_plan_v2.md"

PAIR_LIST_OUT = OUTPUT_DIR / "remaining_easy_medium21_pair_list.csv"
DRAFT_OUT = OUTPUT_DIR / "remaining_easy_medium21_column_draft_v1.csv"
VALIDATION_OUT = OUTPUT_DIR / "remaining_easy_medium21_validation_report.md"
REVIEW_PACKET_OUT = OUTPUT_DIR / "remaining_easy_medium21_review_packet.md"
HIGH_RISK_OUT = OUTPUT_DIR / "remaining_easy_medium21_high_risk_items.csv"
SUMMARY_OUT = OUTPUT_DIR / "remaining_easy_medium21_annotation_summary.md"


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
    "semantic_substitution",
    "analogy",
    "short_answer",
    "coreference_or_demonstrative",
}


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_pilot10_ids_from_first_column(path: Path) -> List[str]:
    ids: List[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            if row and row[0].startswith("F300V1-"):
                ids.append(row[0])
    return ids


def csv_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def as_int(value: str) -> int:
    return int(value) if value else 0


DRAFT_SPECS: Dict[str, List[Dict[str, str]]] = {
    "F300V1-0024": [
        {
            "span_a": "毒敌山琵琶洞",
            "span_b": "那山洞",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B用“那山洞”回指A中已经给出的具体洞府地点。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "在西梁国毒敌山琵琶洞。",
            "span_b": "那山洞有甚妖怪",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B围绕A提供的地点继续追问该地所涉对象，承接的是地点话题而非单纯复述。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "地点承接是否宜单列为column需要人工把关，避免把普通话题延续标得过宽。",
        },
    ],
    "F300V1-0209": [
        {
            "span_a": "五美",
            "span_b": "五美",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B直接复现A中的核心概念“五美”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "尊五美",
            "span_b": "何谓五美？",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A中提出的概念转成解释请求，属于确认并追问概念内涵的语用性承接。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0010": [
        {
            "span_a": "msf",
            "span_b": "msf",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "两轮都围绕“msf”这一对象展开。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "加入msf",
            "span_b": "申请msf",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A中的加入意图改写为更具体的申请行动。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "“加入”与“申请”更像行动改写，需人工确认是否应降为pragmatic_function。",
        },
        {
            "span_a": "决心加入msf的进",
            "span_b": "可以申请msf吗",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A的加入主题转成资格与可行性追问。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "A是标题式残句，是否整句入栏及其功能分类都需人工复核。",
        },
    ],
    "F300V1-0185": [
        {
            "span_a": "是",
            "span_b": "是",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B复现A中的肯定成分“是”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "是也",
            "span_b": "是知津矣",
            "relation_type": "syntactic_parallelism",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B沿着肯定式结构推进A的判断。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "是也",
            "span_b": "知津矣",
            "relation_type": "semantic_substitution",
            "relation_strength": "weak",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A的简单肯定扩展为对人物状态的解释性判断。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "“知津”是否应视为明确替换位仍需人工确认，避免过度解释。",
        },
    ],
    "F300V1-0271": [
        {
            "span_a": "私人飞机",
            "span_b": "私人飞机",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B复现A中的核心对象“私人飞机”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "私人飞机呢？",
            "span_b": "也会派私人飞机接",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A的追问改写成带条件的回应方案。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "我魔",
            "span_b": "我抬",
            "relation_type": "contrast",
            "relation_strength": "weak",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "A/B分别以内群体称呼定位不同球队立场。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "论坛昵称高度依赖语境，需人工确认是否真的构成稳定对照位。",
        },
    ],
    "F300V1-0002": [
        {
            "span_a": "为政",
            "span_b": "为政",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B多次复现A中的核心概念“为政”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "不为政",
            "span_b": "是亦为政",
            "relation_type": "repair",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B纠正A中“子不为政”的预设，明确提出“这也是为政”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "子奚不为政？",
            "span_b": "奚其为为政！",
            "relation_type": "syntactic_parallelism",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B沿用“奚/为政”的设问框架，但把设问方向反转。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "设问反转兼具平行和反驳性质，relation_type 主次需要人工定口径。",
        },
        {
            "span_a": "不为政",
            "span_b": "奚其为为政！",
            "relation_type": "contrast",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A的否定性设问改写成强调式追问，形成反向对照。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "此栏可能与C02/C03重叠，需人工判断是否保留以免过度标注。",
        },
    ],
    "F300V1-0055": [
        {
            "span_a": "和晓霞一个班",
            "span_b": "和晓霞不一个班",
            "relation_type": "repair",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B直接修正A关于班级关系的判断。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "和晓霞一个班",
            "span_b": "和润生是一个班",
            "relation_type": "contrast",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把同一“一个班”关系转移到新的同班对象上。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "一个班",
            "span_b": "一个班",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A/B共享“一个班”的关系框架。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "晓霞",
            "span_b": "润生",
            "relation_type": "contrast",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B用新的人物替换A预设的同班对象。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0187": [
        {
            "span_a": "倒了它",
            "span_b": "倒了它",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B最终回到A提出的原动作。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "倒了它？",
            "span_b": "你还是倒了它",
            "relation_type": "repair",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B在犹豫后重新确认A提出的动作方案。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "倒了它",
            "span_b": "先把它放在那儿",
            "relation_type": "repair",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B先提出暂放方案，随后又改回执行A动作；该栏记录中间修正路径。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "B内部先改后回的修正链是否需要单列辅助栏，需人工确认。",
        },
    ],
    "F300V1-0265": [
        {
            "span_a": "哭",
            "span_b": "哭",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A/B都把“哭”作为焦点动作。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "哭吊喭毕",
            "span_b": "君何为哭？",
            "relation_type": "repair",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B对A的哭吊行为提出礼法性纠偏。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "哭吊喭毕",
            "span_b": "阮既不哭",
            "relation_type": "contrast",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B以“阮既不哭”引入规范参照，对A的做法形成对照。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "礼法说明与核心修正规则之间的主次需要人工复核。",
        },
    ],
    "F300V1-0290": [
        {
            "span_a": "宫嫔",
            "span_b": "宫嫔",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B复现A中的场景对象“宫嫔”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "无双在焉",
            "span_b": "岂便及无双",
            "relation_type": "contrast",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A担忧“无双在焉”，B则明确否定其轻易可及。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "汝为我一窥，可乎？",
            "span_b": "宫嫔数千，岂便及无双。",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B没有直接执行“窥”，而是先对A的推测与请求作反驳式回应。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "整句语用回应是否单列为辅助栏，需要人工把关。",
        },
        {
            "span_a": "无双",
            "span_b": "无双",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B复现A关注的核心人物“无双”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0299": [
        {
            "span_a": "死在家里",
            "span_b": "死在哥哥家里",
            "relation_type": "syntactic_parallelism",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B延续“死在X里”的论证框架，只替换家庭关系位置。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "太太的好心弄坏了",
            "span_b": "害了哥哥",
            "relation_type": "analogy",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B沿用A的“会连累照拂者”的关系结构，替换受害对象并反向劝说。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "此栏属于结构类比主链，需人工确认是否保留为analogy而非普通contrast。",
        },
        {
            "span_a": "我该死在家里才是。",
            "span_b": "若是死在哥哥家里，岂不又害了哥哥呢。",
            "relation_type": "analogy",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A的整句论证结构迁移到“哥哥家里”的新位置上。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "整句类比链较强，但也最容易和并行改写混淆，需人工复核。",
        },
        {
            "span_a": "死在这里",
            "span_b": "死在哥哥家里",
            "relation_type": "contrast",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A的地点论证转移到新的家庭关系上，形成场所对照。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "地点对照与类比链存在重叠，需人工判断是否辅助保留。",
        },
    ],
    "F300V1-0298": [
        {
            "span_a": "撬动",
            "span_b": "撬动",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B复现A中的关键行动词“撬动”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "国际文化产业资源",
            "span_b": "“一带一路”国家",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A中的资源来源具体化为可参与的国家主体。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "“资源”与“国家主体”的替换位可能被质疑过宽，需人工确认。",
        },
        {
            "span_a": "实现合作共荣地可持续发展",
            "span_b": "参与“一带一路”建设",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B给出实现合作发展的操作路径，属于回答“如何实现”的语用性回应。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0287": [
        {
            "span_a": "北约",
            "span_b": "北约",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A/B都以“北约”为核心评论对象。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "与俄罗斯发生更广泛的冲突",
            "span_b": "与俄冲突",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B压缩复现A中的冲突前提。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "中国在欧洲拥有的基础设施项目",
            "span_b": "中欧合作",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A中的具体基础设施项目概括为更宽的中欧合作议题。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "概括层级较高，需人工确认是否属于明确替换位。",
        },
        {
            "span_a": "中方对此有何评论？",
            "span_b": "毫无道理，各方应坚决抵制。",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B给出明确的评论性结论。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "将收回一些中国在欧洲拥有的基础设施项目",
            "span_b": "干扰破坏中欧合作",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A中的项目收回风险改写为干扰破坏合作的行为后果。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "语义改写跨度较大，需人工确认是否过度抽象。",
        },
    ],
    "F300V1-0300": [
        {
            "span_a": "为善",
            "span_b": "为善",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "mutual",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A/B共享“为善”这一核心判断位。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "为不善",
            "span_b": "为不善，非才之罪也",
            "relation_type": "repair",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B承接A提出的“为不善”可能性，并给出修正式解释。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "今曰‘性善’，然则彼皆非与？",
            "span_b": "乃若其情，则可以为善矣，乃所谓善也。",
            "relation_type": "pragmatic_function",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B正面回应A对“性善”命题的质疑。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "整句回应跨度较大，需人工确认核心边界是否应更细分。",
        },
        {
            "span_a": "性善",
            "span_b": "善也",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A中的命题焦点收束为“乃所谓善也”的定义性改写。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "概念层面的收束是否宜视作semantic_substitution，需人工确认。",
        },
        {
            "span_a": "彼皆非与？",
            "span_b": "非才之罪也",
            "relation_type": "repair",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B对A的质疑路径作局部修正，转而解释“不善”之来源。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "此栏可能与C02/C03存在解释链重叠，需人工确认是否保留。",
        },
    ],
    "F300V1-0204": [
        {
            "span_a": "两岸交流",
            "span_b": "两岸交流合作",
            "relation_type": "lexical_reproduction",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B延续A中的“两岸交流”议题，并扩展为合作表述。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "对台新举措",
            "span_b": "十项促进两岸交流合作的政策措施",
            "relation_type": "semantic_substitution",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A中的笼统“新举措”具体化为政策措施。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "虽然替换位较清楚，但政治问答中概括层级需人工复核。",
        },
        {
            "span_a": "“介选”行为",
            "span_b": "攻击、污蔑、反对",
            "relation_type": "contrast",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A中的指控性标签反向改写为对民进党当局行为的批评。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "该栏既可看作语义反驳，也可看作评价转移，需人工定型。",
        },
        {
            "span_a": "请问对此有何评论？",
            "span_b": "这再次充分暴露了民进党当局图谋“台独”的真实面目",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B给出正式评论性结论，承接A的问政式提问。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "台湾当局主导",
            "span_b": "民进党当局顽固坚持“台独”分裂立场",
            "relation_type": "contrast",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B没有沿用A的“当局主导”框架，而是转向政治立场批评。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "该栏更像评论立场转向，是否保留需人工权衡过度标注风险。",
        },
    ],
    "F300V1-0052": [
        {
            "span_a": "怎麽写",
            "span_b": "金”傍做“昔”字便是",
            "relation_type": "slot_filling",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B直接回答A关于写法的提问。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "错”字",
            "span_b": "金”傍做“昔”字",
            "relation_type": "slot_filling",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B用构字说明具体填补“错”字的写法槽位。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "字",
            "span_b": "字",
            "relation_type": "lexical_reproduction",
            "relation_strength": "medium",
            "alignment_direction": "mutual",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "A/B都围绕“字”的书写问题。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0167": [
        {
            "span_a": "什么样的电脑",
            "span_b": "各种计算机",
            "relation_type": "slot_filling",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B用设备类型范围填入A的“什么样的电脑”槽位。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "电脑",
            "span_b": "计算机",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把口语化“电脑”改写为“计算机”。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "“电脑/计算机”更像术语改写，但仍需人工确认是否单列替换位。",
        },
        {
            "span_a": "什么样",
            "span_b": "MAC,IBM或UNIX",
            "relation_type": "slot_filling",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B以并列列表进一步细化设备类型。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0046": [
        {
            "span_a": "什么是共产主义",
            "span_b": "一个社会政治运动主张生产资料,并带来一个无阶级社会的阶级解决冲突的共同所有权。",
            "relation_type": "slot_filling",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B以定义式回答填补A的“什么是X”槽位。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "什么",
            "span_b": "一个社会政治运动",
            "relation_type": "slot_filling",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B先给出类别层面的定义起点。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "共产主义",
            "span_b": "无阶级社会",
            "relation_type": "semantic_substitution",
            "relation_strength": "weak",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把“共产主义”定义中的结果性特征压缩到“无阶级社会”。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "定义链较乱，此栏容易滑向纯话题相关，需人工严格复核。",
        },
    ],
    "F300V1-0033": [
        {
            "span_a": "何计通耗",
            "span_b": "可附信",
            "relation_type": "slot_filling",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B以具体通信方法回答A的“何计通耗”提问。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "通耗",
            "span_b": "附信",
            "relation_type": "semantic_substitution",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把抽象的通耗之计落实为附信之法。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "“通耗/附信”既像填槽也像语义落实，需人工确认主标签。",
        },
        {
            "span_a": "仙人路绝",
            "span_b": "若遇雁府上人",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B先设定能够通信的条件，再给出方法。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "条件设定是否单列为辅助栏需要人工判断。",
        },
    ],
    "F300V1-0250": [
        {
            "span_a": "定没这事",
            "span_b": "怕不做出来",
            "relation_type": "contrast",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "A否认事件发生，B反向坚持其可能发生。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "这事",
            "span_b": "做出来",
            "relation_type": "coreference_or_demonstrative",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B沿着A否认的同一事件位继续断言其可能发生。",
            "draft_confidence": "medium",
            "needs_human_review": "1",
            "review_reason": "事件位映射较抽象，需人工确认是否足够稳定。",
        },
        {
            "span_a": "莫要造次",
            "span_b": "他在东京兀自去李师师家去",
            "relation_type": "pragmatic_function",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B通过补充事证反驳A的安抚和劝止。",
            "draft_confidence": "medium",
            "needs_human_review": "0",
            "review_reason": "",
        },
    ],
    "F300V1-0053": [
        {
            "span_a": "何以不下意",
            "span_b": "会不能用。",
            "relation_type": "slot_filling",
            "relation_strength": "strong",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B以原因性短答回应A的“何以”提问。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "何以",
            "span_b": "不能用",
            "relation_type": "slot_filling",
            "relation_strength": "medium",
            "alignment_direction": "A_to_B",
            "is_core_column": "1",
            "supports_resonance": "1",
            "notes": "B把A的原因槽位具体填为“不能用”。",
            "draft_confidence": "high",
            "needs_human_review": "0",
            "review_reason": "",
        },
        {
            "span_a": "不下意",
            "span_b": "不能用",
            "relation_type": "pragmatic_function",
            "relation_strength": "weak",
            "alignment_direction": "A_to_B",
            "is_core_column": "0",
            "supports_resonance": "1",
            "notes": "B把A对态度问题的追问转成能力或条件解释。",
            "draft_confidence": "low",
            "needs_human_review": "1",
            "review_reason": "态度位与能力位的对应较弱，需人工确认是否保留辅助栏。",
        },
    ],
}


def build_pair_rows() -> tuple[List[Dict[str, str]], Dict[str, Dict[str, str]], Dict[str, str], Dict[str, str]]:
    priority_rows = read_csv_dicts(PRIORITY_PATH)
    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    reviewed_rows = read_csv_dicts(REVIEWED_V1_PATH)
    pilot10_ids_from_reviewed = {row["annotation_id"] for row in reviewed_rows}
    pilot10_ids_from_list = set(read_pilot10_ids_from_first_column(PILOT10_LIST_PATH))

    pair_map = {row["annotation_id"]: row for row in pair_rows}
    priority_map = {row["annotation_id"]: row for row in priority_rows}

    selected: List[Dict[str, str]] = []
    for row in priority_rows:
        annotation_id = row["annotation_id"]
        if annotation_id in pilot10_ids_from_reviewed:
            continue
        if row["difficulty_level"] not in {"easy", "medium"}:
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

    notes = {
        "pilot10_list_note": (
            "diagraph_gold_50_pilot10_list.csv 带有额外拖尾列；本轮使用其首列 annotation_id，并与 "
            "pilot10 reviewed_v1 的 10 个唯一 annotation_id 交叉核对后排除 pilot10。"
        ),
        "guide_v2_path": str(GUIDE_V2_PATH),
        "plan_v2_path": str(PLAN_V2_PATH),
    }
    return selected, priority_map, pilot10_ids_from_reviewed, notes


def build_draft_rows(selected_pairs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    draft_rows: List[Dict[str, str]] = []
    for pair in selected_pairs:
        annotation_id = pair["annotation_id"]
        if annotation_id not in DRAFT_SPECS:
            raise KeyError(f"Missing draft spec for {annotation_id}")
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
    pilot10_ids: set[str],
) -> Dict[str, object]:
    pair_ids = {row["annotation_id"] for row in selected_pairs}
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

    pair_meta = {row["annotation_id"]: row for row in selected_pairs}
    for annotation_id in pair_ids:
        rows = rows_by_pair.get(annotation_id, [])
        if not rows:
            missing_rows_pairs.append(annotation_id)
            continue
        if not any(row["is_core_column"] == "1" for row in rows):
            missing_core_pairs.append(annotation_id)
        turn_a = pair_meta[annotation_id]["turn_a"]
        turn_b = pair_meta[annotation_id]["turn_b"]
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
            if row["is_core_column"] not in VALID_BINARY or row["supports_resonance"] not in VALID_BINARY or row["needs_human_review"] not in VALID_BINARY:
                invalid_binary_rows.append(tag)

    unexpected_pilot_overlap = sorted(pair_ids & pilot10_ids)
    if unexpected_pilot_overlap:
        errors.append(f"Pilot10 overlap found: {unexpected_pilot_overlap}")
    if draft_pair_ids - pair_ids:
        errors.append(f"Draft contains unexpected ids: {sorted(draft_pair_ids - pair_ids)}")
    if missing_rows_pairs:
        errors.append(f"Pairs with no rows: {missing_rows_pairs}")
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

    review_rows = [row for row in draft_rows if row["needs_human_review"] == "1"]
    review_reason_counts = Counter(row["review_reason"] for row in review_rows if row["review_reason"])
    relation_counts = Counter(row["relation_type"] for row in draft_rows)
    by_pair_counts = {annotation_id: len(rows) for annotation_id, rows in rows_by_pair.items()}
    core_counts = {annotation_id: sum(1 for row in rows if row["is_core_column"] == "1") for annotation_id, rows in rows_by_pair.items()}
    aux_counts = {annotation_id: sum(1 for row in rows if row["is_core_column"] == "0") for annotation_id, rows in rows_by_pair.items()}
    expected_ge_6 = sorted(
        annotation_id
        for annotation_id, pair in pair_meta.items()
        if as_int(pair["expected_column_count"]) >= 6
    )
    overannotation_risk = sorted(
        annotation_id
        for annotation_id, count in by_pair_counts.items()
        if count > as_int(pair_meta[annotation_id]["expected_column_count"]) + 1
        or aux_counts[annotation_id] > core_counts[annotation_id]
    )

    return {
        "errors": errors,
        "selected_count": len(selected_pairs),
        "draft_count": len(draft_rows),
        "easy_count": sum(1 for row in selected_pairs if row["difficulty_level"] == "easy"),
        "medium_count": sum(1 for row in selected_pairs if row["difficulty_level"] == "medium"),
        "pair_ids": sorted(pair_ids),
        "review_count": len(review_rows),
        "review_reason_counts": review_reason_counts,
        "relation_counts": relation_counts,
        "by_pair_counts": by_pair_counts,
        "core_counts": core_counts,
        "aux_counts": aux_counts,
        "expected_ge_6": expected_ge_6,
        "overannotation_risk": overannotation_risk,
        "pilot_overlap": unexpected_pilot_overlap,
        "span_a_failures": span_a_failures,
        "span_b_failures": span_b_failures,
    }


def build_high_risk_rows(selected_pairs: List[Dict[str, str]], draft_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    pair_meta = {row["annotation_id"]: row for row in selected_pairs}
    rows_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in draft_rows:
        rows_by_pair[row["annotation_id"]].append(row)

    high_risk_rows: List[Dict[str, str]] = []
    for annotation_id, rows in rows_by_pair.items():
        pair = pair_meta[annotation_id]
        reasons: List[str] = []
        suspected_types = sorted({row["relation_type"] for row in rows if row["relation_type"] in HIGH_RISK_RELATIONS})
        if any(row["needs_human_review"] == "1" for row in rows):
            reasons.append("needs_human_review=1")
        if any(row["relation_type"] in HIGH_RISK_RELATIONS for row in rows):
            reasons.append("contains high-risk relation_type")
        if as_int(pair["expected_column_count"]) >= 6:
            reasons.append("expected_column_count >= 6")
        if any(len(row["span_a"]) >= 16 or len(row["span_b"]) >= 16 for row in rows):
            reasons.append("long span boundary")
        core_count = sum(1 for row in rows if row["is_core_column"] == "1")
        aux_count = sum(1 for row in rows if row["is_core_column"] == "0")
        if aux_count > core_count:
            reasons.append("auxiliary columns > core columns")
        if not reasons:
            continue

        focus_bits = []
        if any(row["relation_type"] == "semantic_substitution" for row in rows):
            focus_bits.append("确认 semantic_substitution 是否有明确替换位")
        if any(row["relation_type"] == "analogy" for row in rows):
            focus_bits.append("确认 analogy 是否真的有结构推理链")
        if any(row["relation_type"] == "short_answer" for row in rows):
            focus_bits.append("确认 short_answer 是否足以支撑稳定映射")
        if any(row["relation_type"] == "coreference_or_demonstrative" for row in rows):
            focus_bits.append("确认指称映射是否跨越 A/B 而非单轮内部")
        if as_int(pair["expected_column_count"]) >= 6:
            focus_bits.append("复核 core / auxiliary 切分，避免长样本过度标注")
        if not focus_bits:
            focus_bits.append("按 guide_v2 重点复核主链与辅助链边界")

        why_parts = []
        if pair["annotation_warning"]:
            why_parts.append(pair["annotation_warning"])
        if any(row["needs_human_review"] == "1" for row in rows):
            why_parts.extend(sorted({row["review_reason"] for row in rows if row["review_reason"]}))

        high_risk_rows.append(
            {
                "annotation_id": annotation_id,
                "pair_id": pair["pair_id"],
                "reason": " | ".join(reasons),
                "suspected_relation_type": " | ".join(suspected_types) if suspected_types else pair["dominant_relation_types"],
                "why_high_risk": " ".join(why_parts) if why_parts else "该样本含高风险 relation_type 或长跨度映射，需要人工复核。",
                "suggested_review_focus": "；".join(focus_bits),
            }
        )
    return high_risk_rows


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_validation_report(
    selected_pairs: List[Dict[str, str]],
    validation: Dict[str, object],
    notes: Dict[str, str],
) -> None:
    review_reason_counts: Counter = validation["review_reason_counts"]  # type: ignore[assignment]
    pair_meta = {row["annotation_id"]: row for row in selected_pairs}
    lines = [
        "# remaining_easy_medium21 validation report",
        "",
        "## 1. Scope",
        f"- 样本数量: {validation['selected_count']}",
        f"- easy 数量: {validation['easy_count']}",
        f"- medium 数量: {validation['medium_count']}",
        f"- column draft 行数: {validation['draft_count']}",
        "- 仅包含 remaining40 中的 easy / medium 样本: 是",
        f"- 已排除 pilot10: {'是' if not validation['pilot_overlap'] else '否'}",
        "",
        "## 2. Pilot10 exclusion note",
        f"- {notes['pilot10_list_note']}",
        "",
        "## 3. Structural checks",
        f"- 每个 pair 至少 1 行: {'通过' if not any('Pairs with no rows' in err for err in validation['errors']) else '未通过'}",
        f"- 每个 pair 至少 1 个 core column: {'通过' if not any('Pairs with no core column' in err for err in validation['errors']) else '未通过'}",
        f"- span_a 全部能在 turn_a 中找到: {'通过' if not validation['span_a_failures'] else '未通过'}",
        f"- span_b 全部能在 turn_b 中找到: {'通过' if not validation['span_b_failures'] else '未通过'}",
        f"- relation_type 合法: {'通过' if not any('Invalid relation_type' in err for err in validation['errors']) else '未通过'}",
        f"- relation_strength 合法: {'通过' if not any('Invalid relation_strength' in err for err in validation['errors']) else '未通过'}",
        f"- alignment_direction 合法: {'通过' if not any('Invalid alignment_direction' in err for err in validation['errors']) else '未通过'}",
        f"- is_core_column / supports_resonance / needs_human_review 合法: {'通过' if not any('Invalid binary rows' in err for err in validation['errors']) else '未通过'}",
        "",
        "## 4. Human review load",
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
            "## 5. Long / dense samples",
            f"- expected_column_count >= 6 的样本: {', '.join(validation['expected_ge_6']) if validation['expected_ge_6'] else '无'}",
            f"- 过度标注风险样本: {', '.join(validation['overannotation_risk']) if validation['overannotation_risk'] else '无'}",
            "",
            "## 6. Per-pair row counts",
        ]
    )
    for annotation_id in sorted(validation["by_pair_counts"]):  # type: ignore[index]
        lines.append(
            f"- {annotation_id}: {validation['by_pair_counts'][annotation_id]} 行，"
            f"core={validation['core_counts'][annotation_id]}，"
            f"aux={validation['aux_counts'][annotation_id]}，"
            f"expected={pair_meta[annotation_id]['expected_column_count']}"
        )

    lines.extend(
        [
            "",
            "## 7. Errors",
        ]
    )
    if validation["errors"]:
        for err in validation["errors"]:
            lines.append(f"- {err}")
    else:
        lines.append("- 无结构性错误。")

    VALIDATION_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review_packet(selected_pairs: List[Dict[str, str]], draft_rows: List[Dict[str, str]]) -> None:
    rows_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in draft_rows:
        rows_by_pair[row["annotation_id"]].append(row)

    lines: List[str] = ["# remaining_easy_medium21 review packet", ""]
    for pair in selected_pairs:
        annotation_id = pair["annotation_id"]
        lines.extend(
            [
                f"## {annotation_id}",
                "",
                f"- pair_id: {pair['pair_id']}",
                f"- difficulty_level: {pair['difficulty_level']}",
                f"- dominant_relation_types: {pair['dominant_relation_types']}",
                f"- annotation_warning: {pair['annotation_warning'] or '无'}",
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
            review_focus.append("先确认 core column 是否足够，再快速检查是否有可删的辅助栏。")
        lines.extend(
            [
                "",
                "**human review focus**",
                "",
            ]
        )
        for item in dict.fromkeys(review_focus):
            lines.append(f"- {item}")
        lines.append("")

    REVIEW_PACKET_OUT.write_text("\n".join(lines), encoding="utf-8")


def write_summary(
    selected_pairs: List[Dict[str, str]],
    draft_rows: List[Dict[str, str]],
    validation: Dict[str, object],
    high_risk_rows: List[Dict[str, str]],
) -> None:
    top_review_ids = sorted(
        {
            row["annotation_id"]
            for row in draft_rows
            if row["needs_human_review"] == "1"
        }
    )
    lines = [
        "# remaining_easy_medium21 annotation summary",
        "",
        f"- 实际样本数量: {validation['selected_count']}",
        f"- easy / medium 分布: {validation['easy_count']} / {validation['medium_count']}",
        f"- 总 column 行数: {validation['draft_count']}",
        f"- span 校验: {'全部通过' if not validation['span_a_failures'] and not validation['span_b_failures'] else '未全部通过'}",
        f"- needs_human_review=1 的 column 数量: {validation['review_count']}",
        f"- 高风险样本数量: {len(high_risk_rows)}",
        f"- 最需要人工复核的 annotation_id: {', '.join(top_review_ids[:12]) if top_review_ids else '无'}",
        "",
        "## Notes",
        "- 本轮产物是 column draft，不是 final gold。",
        "- 生成顺序遵循 guide_v2：先 core，后 auxiliary；不确定时优先打 needs_human_review。",
        "- 对 expected_column_count >= 6 的样本，建议在正式吸收前单独二次复核。",
    ]
    SUMMARY_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    selected_pairs, _, pilot10_ids, notes = build_pair_rows()
    selected_pairs.sort(key=lambda row: int(row["priority_rank"]))
    draft_rows = build_draft_rows(selected_pairs)
    validation = validate(selected_pairs, draft_rows, pilot10_ids)
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
        "reason",
        "suspected_relation_type",
        "why_high_risk",
        "suggested_review_focus",
    ]

    write_csv(PAIR_LIST_OUT, selected_pairs, pair_fieldnames)
    write_csv(DRAFT_OUT, draft_rows, draft_fieldnames)
    write_csv(HIGH_RISK_OUT, high_risk_rows, high_risk_fieldnames)
    write_validation_report(selected_pairs, validation, notes)
    write_review_packet(selected_pairs, draft_rows)
    write_summary(selected_pairs, draft_rows, validation, high_risk_rows)

if __name__ == "__main__":
    main()
