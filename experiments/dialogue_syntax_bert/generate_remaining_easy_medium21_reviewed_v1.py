from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


ROOT = Path(r"D:\现代汉语对话语料库-BERT实验\experiments\dialogue_syntax_bert")
BASE_DIR = ROOT / "artifacts" / "formal_300_v1" / "diagraph_gold_50"
INPUT_DIR = BASE_DIR / "remaining_easy_medium21"
OUTPUT_DIR = INPUT_DIR / "reviewed_v1"

DRAFT_PATH = INPUT_DIR / "remaining_easy_medium21_column_draft_v1.csv"
PAIR_LIST_PATH = INPUT_DIR / "remaining_easy_medium21_pair_list.csv"
PILOT_REVIEWED_PATH = BASE_DIR / "pilot10_review" / "pilot10_column_annotation_reviewed_v1.csv"

REVIEWED_V1_PATH = OUTPUT_DIR / "remaining_easy_medium21_column_reviewed_v1.csv"
DECISIONS_PATH = OUTPUT_DIR / "remaining_easy_medium21_review_decisions.csv"
SUMMARY_PATH = OUTPUT_DIR / "remaining_easy_medium21_review_summary.md"
VALIDATION_PATH = OUTPUT_DIR / "remaining_easy_medium21_review_validation_report.md"

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
VALID_DIFFICULTIES = {"easy", "medium"}

DELETE_NOTES = {
    "F300V1-0024/C02": "地点承接过宽，容易把普通话题延续标成 column；C01“毒敌山琵琶洞→那山洞”已足够支撑主链。",
    "F300V1-0010/C03": "A 是标题式残句，整句入栏过宽；C01“msf→msf”和 C02“加入msf→申请msf”已足够。",
    "F300V1-0185/C03": "“是也→知津矣”解释性较强，明确替换位不足，容易过度解释；C01/C02 已足够支撑。",
    "F300V1-0002/C04": "与 C02/C03 高度重叠，保留会增加过度标注风险。",
    "F300V1-0300/C05": "与 C02/C03 的解释链重叠，作为独立 column 的必要性不足。",
    "F300V1-0204/C05": "该栏更像评论立场转向，跨度过宽，容易退化为普通话题相关或政治立场相关。",
    "F300V1-0053/C03": "“不下意→不能用”对应较弱，C01/C02 已经覆盖核心原因填槽链。",
}

REVISE_RULES = {
    "F300V1-0271/C03": {
        "reviewed_relation_type": "semantic_substitution",
        "reviewed_relation_strength": "weak",
        "reviewed_is_core_column": "0",
        "reviewed_supports_resonance": "1",
        "reviewer_note": "“我魔/我抬”不宜标为 contrast；更像论坛语境中的球队昵称/立场称呼替换，且只能作为弱辅助栏。",
    },
    "F300V1-0287/C03": {
        "reviewed_relation_type": "semantic_substitution",
        "reviewed_relation_strength": "medium",
        "reviewed_is_core_column": "0",
        "reviewed_supports_resonance": "1",
        "reviewer_note": "“中国在欧洲拥有的基础设施项目→中欧合作”可以保留为概括性替换，但跨度较大，不宜作为 core column。",
    },
    "F300V1-0167/C02": {
        "reviewed_relation_type": "semantic_substitution",
        "reviewed_relation_strength": "medium",
        "reviewed_is_core_column": "0",
        "reviewed_supports_resonance": "1",
        "reviewer_note": "“电脑/计算机”是术语层面的替换，可以作为辅助栏；核心链由“什么样的电脑→各种计算机”和设备列表承担。",
    },
    "F300V1-0033/C02": {
        "reviewed_relation_type": "slot_filling",
        "reviewed_relation_strength": "medium",
        "reviewed_is_core_column": "0",
        "reviewed_supports_resonance": "1",
        "reviewer_note": "“通耗/附信”更像对 A 中通信方法槽位的具体落实，不宜标为 semantic_substitution；核心栏由 C01 承担。",
    },
}

KEEP_WITH_NOTE = {
    "F300V1-0299/C02": "类比主链成立；B 沿用 A 的“死亡会连累照拂者”关系结构，将受害对象从太太转为哥哥。",
    "F300V1-0299/C03": "整句类比链可以保留为 core；它体现 A 的论证结构被 B 迁移到“哥哥家里”的新情境。",
    "F300V1-0299/C04": "地点对照与类比链有重叠，但作为 auxiliary contrast 可保留，不承担主链。",
    "F300V1-0204/C02": "“对台新举措→十项促进两岸交流合作的政策措施”替换位较清楚，可保留为 core semantic_substitution。",
    "F300V1-0204/C03": "可保留为 auxiliary contrast；它体现 A 的“介选”指控被 B 反向评价为“攻击、污蔑、反对”。",
    "F300V1-0300/C03": "虽然跨度较大，但该栏是 B 对 A 关于“性善”质疑的核心回应，可保留为 core pragmatic_function。",
    "F300V1-0300/C04": "“性善→善也”可保留为 auxiliary semantic_substitution，不承担主链。",
    "F300V1-0287/C05": "可保留为 auxiliary semantic_substitution，用于说明“收回项目”被 B 改写为“干扰破坏合作”的行为后果。",
}

DEFAULT_KEEP_NOTE = "accepted in easy_medium21 review"


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
) -> Dict[str, object]:
    pair_map = {row["annotation_id"]: row for row in pair_rows}
    reviewed_by_pair: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    errors: List[str] = []
    span_a_failures: List[str] = []
    span_b_failures: List[str] = []
    bad_relation: List[str] = []
    bad_strength: List[str] = []
    bad_binary: List[str] = []
    hard_rows: List[str] = []
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
        if row["reviewed_is_core_column"] not in VALID_BINARY or row["reviewed_supports_resonance"] not in VALID_BINARY:
            bad_binary.append(key)
        if pair["difficulty_level"] not in VALID_DIFFICULTIES:
            hard_rows.append(key)

    for annotation_id, pair in pair_map.items():
        rows = reviewed_by_pair.get(annotation_id, [])
        if not rows:
            missing_pairs.append(annotation_id)
            continue
        active_rows = [row for row in rows if row["reviewed_status"] != "excluded_from_gold_candidate"]
        if not any(row["reviewed_is_core_column"] == "1" for row in active_rows):
            missing_core_after_delete.append(annotation_id)

    if len(reviewed_rows) != 71:
        errors.append(f"Expected 71 reviewed rows, got {len(reviewed_rows)}")
    if len(pair_map) != 21:
        errors.append(f"Expected 21 pair rows, got {len(pair_map)}")
    overlap_with_pilot = sorted(set(reviewed_by_pair) & pilot_ids)
    if overlap_with_pilot:
        errors.append(f"Pilot10 overlap detected: {overlap_with_pilot}")
    if missing_pairs:
        errors.append(f"Missing pair coverage: {missing_pairs}")
    if missing_core_after_delete:
        errors.append(f"Pairs missing active core column after delete: {missing_core_after_delete}")
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
    if hard_rows:
        errors.append(f"Hard/non easy-medium rows present: {hard_rows}")

    active_rows = [row for row in reviewed_rows if row["reviewed_status"] != "excluded_from_gold_candidate"]
    kept_relation_counts = Counter(row["reviewed_relation_type"] for row in active_rows)

    return {
        "errors": errors,
        "span_a_failures": span_a_failures,
        "span_b_failures": span_b_failures,
        "active_column_count": len(active_rows),
        "decision_counts": Counter(row["reviewer_decision"] for row in reviewed_rows),
        "pair_count": len(pair_map),
        "row_count": len(reviewed_rows),
        "kept_relation_counts": kept_relation_counts,
        "missing_core_after_delete": missing_core_after_delete,
    }


def write_validation_report(
    validation: Dict[str, object],
    reviewed_rows: List[Dict[str, str]],
) -> None:
    decision_counts: Counter = validation["decision_counts"]  # type: ignore[assignment]
    lines = [
        "# remaining_easy_medium21 review validation report",
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
        f"- 覆盖 21 个 pair: {'通过' if validation['pair_count'] == 21 else '未通过'}",
        f"- 原始 71 行全部保留: {'通过' if validation['row_count'] == 71 else '未通过'}",
        f"- span_a 校验: {'通过' if not validation['span_a_failures'] else '未通过'}",
        f"- span_b 校验: {'通过' if not validation['span_b_failures'] else '未通过'}",
        f"- 每个 pair 删除后仍至少 1 个 core column: {'通过' if not validation['missing_core_after_delete'] else '未通过'}",
        f"- 无 pilot10 annotation_id: {'通过' if not any('Pilot10 overlap' in err for err in validation['errors']) else '未通过'}",
        f"- 无 hard 样本: {'通过' if not any('Hard/non easy-medium' in err for err in validation['errors']) else '未通过'}",
        "",
        "## Active relation types",
    ]
    for relation_type, count in validation["kept_relation_counts"].most_common():  # type: ignore[index]
        lines.append(f"- {relation_type}: {count}")

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
    deleted_keys = [row_key(row) for row in deleted]
    revised_keys = [row_key(row) for row in revised]

    lines = [
        "# remaining_easy_medium21 review summary",
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
            f"- {row_key(row)}: {row['relation_type']} -> {row['reviewed_relation_type']}，"
            f"strength {row['relation_strength']} -> {row['reviewed_relation_strength']}，"
            f"core {row['is_core_column']} -> {row['reviewed_is_core_column']}；{row['reviewer_note']}"
        )

    lines.extend(
        [
            "",
            "## Interpretation notes",
            "- semantic_substitution 被收紧在两类位置：一类是直接删除解释性过强或跨度过宽的弱替换栏，如 `F300V1-0185/C03`、`F300V1-0204/C05`；另一类是把本来更像填槽的栏改回 `slot_filling`，如 `F300V1-0033/C02`。",
            "- pragmatic_function 继续保留在确实承担“回应 / 解释 / 评论请求”的位置，比如 `F300V1-0209/C02`、`F300V1-0298/C03`、`F300V1-0300/C03`、`F300V1-0204/C04`。",
            "- analogy 主链保留在 `F300V1-0299/C02` 和 `F300V1-0299/C03`，说明 easy+medium 阶段的类比链可以保留，但必须明确其结构迁移逻辑。",
            "- core / auxiliary 调整主要体现在：`F300V1-0271/C03`、`F300V1-0287/C03`、`F300V1-0167/C02`、`F300V1-0033/C02` 均被收缩为辅助性或较弱的 reviewed 栏位；多处 delete 也进一步压低了过度标注风险。",
            "",
            "## Next step",
            "- 可以进入 hard19 draft，但建议把本轮 reviewed_v1 先作为 hard 样本的判定参照，而不是直接视作 full gold。",
            "- 仍建议做一次人工二次复核，重点盯住：跨句类比链、长整句 pragmatic_function、以及被保留下来的弱 semantic_substitution。",
            "",
            "## Key lists",
            f"- delete keys: {', '.join(deleted_keys)}",
            f"- revise keys: {', '.join(revised_keys)}",
        ]
    )

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    draft_rows = read_csv_dicts(DRAFT_PATH)
    pair_rows = read_csv_dicts(PAIR_LIST_PATH)
    pilot_ids = set()
    if PILOT_REVIEWED_PATH.exists():
        pilot_ids = {row["annotation_id"] for row in read_csv_dicts(PILOT_REVIEWED_PATH)}

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

    validation = validate(pair_rows, reviewed_rows, pilot_ids)
    write_validation_report(validation, reviewed_rows)
    write_summary(decision_counts, reviewed_rows)


if __name__ == "__main__":
    main()
