from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parent
BASE_DIR = ROOT / "artifacts" / "formal_300_v1" / "diagraph_gold_50"
INPUT_DIR = BASE_DIR / "remaining_hard19"
OUTPUT_DIR = INPUT_DIR / "reviewed_v1"

DRAFT_PATH = INPUT_DIR / "remaining_hard19_column_draft_v1.csv"
PAIR_LIST_PATH = INPUT_DIR / "remaining_hard19_pair_list.csv"
REVIEW_PACKET_PATH = INPUT_DIR / "remaining_hard19_review_packet.md"
VALIDATION_SOURCE_PATH = INPUT_DIR / "remaining_hard19_validation_report.md"
HIGH_RISK_PATH = INPUT_DIR / "remaining_hard19_high_risk_items.csv"
PILOT_REVIEWED_PATH = BASE_DIR / "pilot10_review" / "pilot10_column_annotation_reviewed_v1.csv"
EASY_MEDIUM_REVIEWED_PATH = (
    BASE_DIR
    / "remaining_easy_medium21"
    / "reviewed_v1"
    / "remaining_easy_medium21_column_reviewed_v1.csv"
)

REVIEWED_V1_PATH = OUTPUT_DIR / "remaining_hard19_column_reviewed_v1.csv"
DECISIONS_PATH = OUTPUT_DIR / "remaining_hard19_review_decisions.csv"
SUMMARY_PATH = OUTPUT_DIR / "remaining_hard19_review_summary.md"
VALIDATION_PATH = OUTPUT_DIR / "remaining_hard19_review_validation_report.md"

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
VALID_BINARY = {"0", "1"}

DELETE_NOTES = {
    "F300V1-0013/C03": "“优美→明了”不宜上升为 analogy。该样本主链已经由“胜于→胜于”和整句“X胜于Y”平行结构承担，拆出评价词 analogy 容易过度标注。",
    "F300V1-0013/C04": "“丑陋→晦涩”与 C03 同理，不宜因为平行结构就自动标为 analogy；删除以避免把平行结构过度类比化。",
    "F300V1-0008/C03": "“凑合了→还是不着家儿”结果性改写较宽，容易滑向普通话题评论；C02 已足够支撑主链。",
    "F300V1-0224/C03": "“有私奔之心→得见花颜”情感同题相关较强，但明确替换位不足，容易过度解释；C01/C02 已足够。",
    "F300V1-0117/C02": "“浑忘却→何人不欲斯言耶”命题桥接依赖解释较多，作为辅助栏必要性不足；C01 已覆盖核心指称承接。",
    "F300V1-0111/C02": "“某些球迷是多么的可笑→真.破车迷”整句评价压缩过宽，容易把论坛标签承接扩展成普通话题相关；C01 已足够。",
    "F300V1-0150/C02": "“井丹→长卿”只是人物评价位替换，不宜单独上升为 analogy；主链由 C01 的人物品评对照承担。",
    "F300V1-0150/C03": "“高洁→慢世”是评价维度更替，容易与普通并列品评混淆，不宜单独保留为 analogy 栏。",
    "F300V1-0220/C03": "“距心→为之牧之者”行动者位映射高度依赖注释性理解，作为辅助 analogy 栏过细；主类比链由 C01/C02 承担。",
}

REVISE_RULES = {
    "F300V1-0154/C02": {
        "reviewed_relation_type": "semantic_substitution",
        "reviewed_relation_strength": "weak",
        "reviewed_is_core_column": "0",
        "reviewed_supports_resonance": "1",
        "reviewer_note": "“遥拜→便拜”可以保留为动作落实/动作改写的辅助栏，但它不是主链，强度降为 weak。",
    },
    "F300V1-0214/C01": {
        "reviewed_relation_type": "pragmatic_function",
        "reviewed_relation_strength": "weak",
        "reviewed_is_core_column": "1",
        "reviewed_supports_resonance": "1",
        "reviewer_note": "该样本高度依赖论坛语境，只能弱保留为“标签→继续抱怨内容”的语用承接；因该 pair 只有一栏，仍保留为 core。",
    },
    "F300V1-0097/C01": {
        "reviewed_relation_type": "semantic_substitution",
        "reviewed_relation_strength": "medium",
        "reviewed_is_core_column": "0",
        "reviewed_supports_resonance": "1",
        "reviewer_note": "“哈哈哈→好笑”可保留为笑声行为到显性评价位的辅助替换，但主链应由 C02 的追问式回应承担。",
    },
    "F300V1-0150/C01": {
        "reviewed_relation_type": "contrast",
        "reviewed_relation_strength": "strong",
        "reviewed_is_core_column": "1",
        "reviewed_supports_resonance": "1",
        "reviewer_note": "该样本主链不是严格 analogy，而是人物品评结构中的比较/评价对照；用 contrast 比 syntactic_parallelism 或 analogy 更稳。",
    },
}

KEEP_WITH_NOTE = {
    "F300V1-0219/C02": "可保留为 repair；B 不只是反对“卖去”，而是对该处理方案作伦理性纠偏。",
    "F300V1-0219/C03": "“卖去→移于他人”有明确替换位，可保留为辅助 semantic_substitution。",
    "F300V1-0106/C02": "命题到情态反应的映射较抽象，但 B 明确对 A 的命题作出惊讶性回应，可保留为 pragmatic_function。",
    "F300V1-0043/C01": "“一旦…就…”跨话轮配对明确，可保留为 core syntactic_parallelism。",
    "F300V1-0043/C02": "A 提供条件前件，B 补出结果后件，构成条件到结果的核心语用承接，可保留。",
    "F300V1-0081/C02": "交接场景到邀请行动的承接虽然依赖语境，但 B 的行动安排明确围绕 A 中“少平”事件展开，可保留。",
    "F300V1-0224/C02": "情意判断到强烈情感回应跨度较大，但这是该 pair 的主要语用承接，可保留为 core。",
    "F300V1-0159/C01": "该 pair 只有追问链，但 B 明确追问 A 所提出行动的用途，可作为单栏 core 保留。",
    "F300V1-0117/C01": "“浑忘却→斯言”虽简略，但 B 的“斯言”可回指 A 所涉话语内容，弱保留为 core。",
    "F300V1-0111/C01": "“某些球迷→破车迷”可保留为论坛语境中的群体标签替换，但不再扩展整句评价辅助栏。",
    "F300V1-0128/C01": "单栏追问承接可保留；B 把 A 关于“今之乐/古之乐”的论断转为进一步请求说明。",
    "F300V1-0092/C01": "“之→某”可保留为跨句指称位，B 显化 A 所深忆之对象。",
    "F300V1-0092/C02": "A 的陈述性前提由 B 转成识别性回应，可保留为 pragmatic_function。",
    "F300V1-0205/C02": "单词提示到定义解释的关系较强，可保留为 core pragmatic_function。",
    "F300V1-0220/C01": "A 命题与 B 设喻之间的主类比链成立，可保留为 core analogy。",
    "F300V1-0220/C02": "B 将 A 的判断难题转化为“是否放任牛羊死去”的责任追问，可保留为 core analogy，但不再额外保留 C03 行动者位辅助栏。",
}

DEFAULT_KEEP_NOTE = "accepted in hard19 review"


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def row_key(row: Dict[str, str]) -> str:
    return f"{row['annotation_id']}/{row['column_id']}"


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_reviewed_rows(
    draft_rows: List[Dict[str, str]],
) -> tuple[List[Dict[str, str]], List[Dict[str, str]], Counter]:
    reviewed_rows: List[Dict[str, str]] = []
    decision_rows: List[Dict[str, str]] = []
    decision_counts: Counter = Counter()

    for row in draft_rows:
        key = row_key(row)
        reviewed = dict(row)
        reviewed["reviewed_relation_type"] = row["relation_type"]
        reviewed["reviewed_relation_strength"] = row["relation_strength"]
        reviewed["reviewed_is_core_column"] = row["is_core_column"]
        reviewed["reviewed_supports_resonance"] = row["supports_resonance"]

        if key in DELETE_NOTES:
            reviewed["reviewer_decision"] = "delete"
            reviewed["reviewer_note"] = DELETE_NOTES[key]
            reviewed["reviewed_status"] = "excluded_from_gold_candidate"
        elif key in REVISE_RULES:
            rule = REVISE_RULES[key]
            reviewed["reviewer_decision"] = "revise"
            reviewed["reviewer_note"] = rule["reviewer_note"]
            reviewed["reviewed_relation_type"] = rule["reviewed_relation_type"]
            reviewed["reviewed_relation_strength"] = rule["reviewed_relation_strength"]
            reviewed["reviewed_is_core_column"] = rule["reviewed_is_core_column"]
            reviewed["reviewed_supports_resonance"] = rule["reviewed_supports_resonance"]
            reviewed["reviewed_status"] = "revised_in_gold_candidate"
        else:
            reviewed["reviewer_decision"] = "keep"
            reviewed["reviewer_note"] = KEEP_WITH_NOTE.get(key, DEFAULT_KEEP_NOTE)
            reviewed["reviewed_status"] = "kept_in_gold_candidate"

        decision_counts[reviewed["reviewer_decision"]] += 1
        reviewed_rows.append(reviewed)
        decision_rows.append(
            {
                "annotation_id": row["annotation_id"],
                "pair_id": row["pair_id"],
                "column_id": row["column_id"],
                "reviewer_decision": reviewed["reviewer_decision"],
                "reviewer_note": reviewed["reviewer_note"],
                "original_relation_type": row["relation_type"],
                "original_relation_strength": row["relation_strength"],
                "original_is_core_column": row["is_core_column"],
                "original_supports_resonance": row["supports_resonance"],
                "reviewed_relation_type": reviewed["reviewed_relation_type"],
                "reviewed_relation_strength": reviewed["reviewed_relation_strength"],
                "reviewed_is_core_column": reviewed["reviewed_is_core_column"],
                "reviewed_supports_resonance": reviewed["reviewed_supports_resonance"],
                "reviewed_status": reviewed["reviewed_status"],
            }
        )

    return reviewed_rows, decision_rows, decision_counts


def validate(
    pair_rows: List[Dict[str, str]],
    reviewed_rows: List[Dict[str, str]],
    pilot_ids: set[str],
    easy_medium_ids: set[str],
) -> Dict[str, object]:
    pair_map = {row["annotation_id"]: row for row in pair_rows}
    reviewed_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    errors: List[str] = []
    span_a_failures: List[str] = []
    span_b_failures: List[str] = []
    bad_relation: List[str] = []
    bad_strength: List[str] = []
    bad_binary: List[str] = []
    non_hard_rows: List[str] = []
    missing_pairs: List[str] = []
    missing_core_after_delete: List[str] = []

    for row in reviewed_rows:
        annotation_id = row["annotation_id"]
        reviewed_by_pair[annotation_id].append(row)
        key = row_key(row)
        pair = pair_map.get(annotation_id)
        if pair is None:
            errors.append(f"Unexpected annotation_id in reviewed_v1: {annotation_id}")
            continue
        if row["span_a"] not in pair["turn_a"]:
            span_a_failures.append(key)
        if row["span_b"] not in pair["turn_b"]:
            span_b_failures.append(key)
        if row["reviewed_relation_type"] not in VALID_RELATION_TYPES:
            bad_relation.append(key)
        if row["reviewed_relation_strength"] not in VALID_STRENGTHS:
            bad_strength.append(key)
        if (
            row["reviewed_is_core_column"] not in VALID_BINARY
            or row["reviewed_supports_resonance"] not in VALID_BINARY
        ):
            bad_binary.append(key)
        if pair["difficulty_level"] != "hard":
            non_hard_rows.append(key)

    for annotation_id in pair_map:
        rows = reviewed_by_pair.get(annotation_id, [])
        if not rows:
            missing_pairs.append(annotation_id)
            continue
        active_rows = [
            row
            for row in rows
            if row["reviewed_status"] != "excluded_from_gold_candidate"
        ]
        if not any(row["reviewed_is_core_column"] == "1" for row in active_rows):
            missing_core_after_delete.append(annotation_id)

    if len(reviewed_rows) != 41:
        errors.append(f"Expected 41 reviewed rows, got {len(reviewed_rows)}")
    if len(pair_map) != 19:
        errors.append(f"Expected 19 pair rows, got {len(pair_map)}")

    overlap_with_pilot = sorted(set(reviewed_by_pair) & pilot_ids)
    if overlap_with_pilot:
        errors.append(f"Pilot10 overlap detected: {overlap_with_pilot}")

    overlap_with_easy_medium = sorted(set(reviewed_by_pair) & easy_medium_ids)
    if overlap_with_easy_medium:
        errors.append(
            f"remaining_easy_medium21 overlap detected: {overlap_with_easy_medium}"
        )

    if missing_pairs:
        errors.append(f"Missing pair coverage: {missing_pairs}")
    if missing_core_after_delete:
        errors.append(
            f"Pairs missing active core column after delete: {missing_core_after_delete}"
        )
    if span_a_failures:
        errors.append(f"span_a failures: {span_a_failures}")
    if span_b_failures:
        errors.append(f"span_b failures: {span_b_failures}")
    if bad_relation:
        errors.append(f"Invalid reviewed_relation_type rows: {bad_relation}")
    if bad_strength:
        errors.append(f"Invalid reviewed_relation_strength rows: {bad_strength}")
    if bad_binary:
        errors.append(f"Invalid reviewed binary rows: {bad_binary}")
    if non_hard_rows:
        errors.append(f"Non-hard rows present: {non_hard_rows}")

    active_rows = [
        row for row in reviewed_rows if row["reviewed_status"] != "excluded_from_gold_candidate"
    ]
    return {
        "errors": errors,
        "span_a_failures": span_a_failures,
        "span_b_failures": span_b_failures,
        "active_column_count": len(active_rows),
        "decision_counts": Counter(row["reviewer_decision"] for row in reviewed_rows),
        "pair_count": len(pair_map),
        "row_count": len(reviewed_rows),
        "active_relation_counts": Counter(
            row["reviewed_relation_type"] for row in active_rows
        ),
        "missing_core_after_delete": missing_core_after_delete,
        "active_core_counts": {
            annotation_id: sum(
                1
                for row in reviewed_by_pair.get(annotation_id, [])
                if row["reviewed_status"] != "excluded_from_gold_candidate"
                and row["reviewed_is_core_column"] == "1"
            )
            for annotation_id in pair_map
        },
    }


def write_validation_report(validation: Dict[str, object]) -> None:
    decision_counts: Counter = validation["decision_counts"]  # type: ignore[assignment]
    active_relation_counts: Counter = validation["active_relation_counts"]  # type: ignore[assignment]
    lines = [
        "# remaining_hard19 review validation report",
        "",
        "## Coverage",
        f"- reviewed_v1 pair 数量: {validation['pair_count']}",
        f"- reviewed_v1 行数: {validation['row_count']}",
        f"- 有效 column 数量: {validation['active_column_count']}",
        "",
        "## Decision counts",
        f"- keep: {decision_counts['keep']}",
        f"- revise: {decision_counts['revise']}",
        f"- delete: {decision_counts['delete']}",
        "",
        "## Checks",
        f"- 覆盖 19 个 hard pair: {'通过' if validation['pair_count'] == 19 else '未通过'}",
        f"- 原始 41 行全部保留: {'通过' if validation['row_count'] == 41 else '未通过'}",
        f"- 有效 column 数量 = 41 - delete: {'通过' if validation['active_column_count'] == 32 else '未通过'}",
        f"- span_a 校验: {'通过' if not validation['span_a_failures'] else '未通过'}",
        f"- span_b 校验: {'通过' if not validation['span_b_failures'] else '未通过'}",
        f"- 每个 pair 删除后仍至少 1 个 core column: {'通过' if not validation['missing_core_after_delete'] else '未通过'}",
        f"- 无 pilot10 annotation_id: {'通过' if not any('Pilot10 overlap' in err for err in validation['errors']) else '未通过'}",
        f"- 无 remaining_easy_medium21 annotation_id: {'通过' if not any('remaining_easy_medium21 overlap' in err for err in validation['errors']) else '未通过'}",
        f"- 全部为 hard: {'通过' if not any('Non-hard rows present' in err for err in validation['errors']) else '未通过'}",
        "",
        "## Active relation types",
    ]
    for relation_type, count in active_relation_counts.most_common():
        lines.append(f"- {relation_type}: {count}")

    lines.extend(["", "## Active core counts by pair"])
    for annotation_id, count in sorted(validation["active_core_counts"].items()):  # type: ignore[index]
        lines.append(f"- {annotation_id}: {count}")

    lines.extend(["", "## Errors"])
    if validation["errors"]:
        for err in validation["errors"]:
            lines.append(f"- {err}")
    else:
        lines.append("- 无结构性错误。")

    VALIDATION_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(
    decision_counts: Counter,
    reviewed_rows: List[Dict[str, str]],
) -> None:
    deleted = [row for row in reviewed_rows if row["reviewer_decision"] == "delete"]
    revised = [row for row in reviewed_rows if row["reviewer_decision"] == "revise"]
    lines = [
        "# remaining_hard19 review summary",
        "",
        "## Overall status",
        "- 本轮仍是 reviewed_v1，不是 final gold。",
        f"- keep / revise / delete: {decision_counts['keep']} / {decision_counts['revise']} / {decision_counts['delete']}",
        f"- 有效 column 数量: {len(reviewed_rows) - decision_counts['delete']}",
        "",
        "## Deleted columns",
    ]
    for row in deleted:
        lines.append(f"- {row_key(row)}: {row['reviewer_note']}")

    lines.extend(["", "## Revised columns"])
    for row in revised:
        lines.append(
            f"- {row_key(row)}: {row['relation_type']} -> {row['reviewed_relation_type']}；"
            f"strength {row['relation_strength']} -> {row['reviewed_relation_strength']}；"
            f"core {row['is_core_column']} -> {row['reviewed_is_core_column']}；{row['reviewer_note']}"
        )

    lines.extend(
        [
            "",
            "## Why hard is stricter",
            "- hard 样本更容易出现低表面重合、强语境依赖、设喻扩展和解释性桥接，因此宁可少保留辅助栏，也不要把可解释关系都吸收进 gold candidate。",
            "- easy/medium 阶段还能接受较宽的辅助说明栏；hard 阶段则必须更严控 analogy、semantic_substitution 和长跨度 pragmatic_function 的边界。",
            "",
            "## Relation-type tightening",
            "- analogy 被收紧在三处：`F300V1-0013/C03`、`F300V1-0013/C04` 被删，避免把平行结构自动类比化；`F300V1-0150/C02`、`F300V1-0150/C03` 被删，避免把人物位/评价位更替单独抬成 analogy；`F300V1-0220/C03` 被删，只保留主类比链。",
            "- semantic_substitution 被收紧在两类位置：一类是删除替换位不够明确的宽解释栏，如 `F300V1-0008/C03`、`F300V1-0224/C03`；另一类是把可保留但不再承担主链的栏降为辅助，如 `F300V1-0154/C02`、`F300V1-0097/C01`。",
            "- pragmatic_function 仍保留在确实承担追问、解释或情态回应的位置，如 `F300V1-0106/C02`、`F300V1-0214/C01`、`F300V1-0224/C02`、`F300V1-0159/C01`、`F300V1-0128/C01`、`F300V1-0092/C02`、`F300V1-0205/C02`。",
            "",
            "## Core / auxiliary adjustments",
            "- `F300V1-0154/C02` 由 medium 辅助栏降为 weak auxiliary。",
            "- `F300V1-0097/C01` 从 core 降为 auxiliary，主链交给 `C02` 的追问式回应。",
            "- `F300V1-0214/C01` 保持 core，但强度从 medium 降为 weak，因为它高度依赖论坛语境且该 pair 只有一栏。",
            "- `F300V1-0150/C01` 由 `syntactic_parallelism` 改为 `contrast`，保留为强 core；`C02/C03` 删除后，主链更清晰地落在人物品评对照上。",
            "",
            "## Focused cases",
            "- `F300V1-0150` 从 analogy 倾向转为 contrast，因为它更像两组人物品评的比较/评价对照，而不是 A 关系结构被 B 转移后的类比链。",
            "- `F300V1-0220` 保留主类比链 `C01/C02`，删除过细的行动者位辅助栏 `C03`，以避免把注释性理解过重的映射硬塞进 gold candidate。",
            "",
            "## Merge readiness",
            "- 可以进入 full `diagraph_gold_50` column gold candidate 合并，但应以 reviewed candidate 身份进入，而不直接等同于 final gold。",
            "- 更稳的顺序是：先合并 `pilot10 reviewed_v1`、`remaining_easy_medium21 reviewed_v1`、`remaining_hard19 reviewed_v1`，再做一次全量 candidate integrity audit。",
        ]
    )

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    required_inputs = [
        DRAFT_PATH,
        PAIR_LIST_PATH,
        REVIEW_PACKET_PATH,
        VALIDATION_SOURCE_PATH,
        HIGH_RISK_PATH,
    ]
    missing_inputs = [str(path) for path in required_inputs if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"Missing required inputs: {missing_inputs}")

    draft_rows = read_csv_dicts(DRAFT_PATH)
    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    pilot_ids = (
        {row["annotation_id"] for row in read_csv_dicts(PILOT_REVIEWED_PATH)}
        if PILOT_REVIEWED_PATH.exists()
        else set()
    )
    easy_medium_ids = (
        {row["annotation_id"] for row in read_csv_dicts(EASY_MEDIUM_REVIEWED_PATH)}
        if EASY_MEDIUM_REVIEWED_PATH.exists()
        else set()
    )

    reviewed_rows, decision_rows, decision_counts = build_reviewed_rows(draft_rows)

    reviewed_fieldnames = list(draft_rows[0].keys()) + [
        "reviewer_decision",
        "reviewer_note",
        "reviewed_relation_type",
        "reviewed_relation_strength",
        "reviewed_is_core_column",
        "reviewed_supports_resonance",
        "reviewed_status",
    ]
    decisions_fieldnames = [
        "annotation_id",
        "pair_id",
        "column_id",
        "reviewer_decision",
        "reviewer_note",
        "original_relation_type",
        "original_relation_strength",
        "original_is_core_column",
        "original_supports_resonance",
        "reviewed_relation_type",
        "reviewed_relation_strength",
        "reviewed_is_core_column",
        "reviewed_supports_resonance",
        "reviewed_status",
    ]

    write_csv(REVIEWED_V1_PATH, reviewed_rows, reviewed_fieldnames)
    write_csv(DECISIONS_PATH, decision_rows, decisions_fieldnames)

    validation = validate(pair_rows, reviewed_rows, pilot_ids, easy_medium_ids)
    write_validation_report(validation)
    write_summary(decision_counts, reviewed_rows)


if __name__ == "__main__":
    main()
