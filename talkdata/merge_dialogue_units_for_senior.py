from __future__ import annotations

r"""
Merge overlapping dialogue-unit windows into larger conversations.

This script only reads exported CSV files and writes review exports. It does
not touch corpus.db and does not import anything.

Usage:
    python .\talkdata\merge_dialogue_units_for_senior.py --preset pilot --show 20
    python .\talkdata\merge_dialogue_units_for_senior.py --preset all-current --show 20
"""

import argparse
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_BASE = PROJECT_ROOT / "talkdata" / "review_exports"
IMPORT_READY = PROJECT_ROOT / "talkdata" / "import_ready"
DEFAULT_OUTPUT_DIR = EXPORT_BASE / "merged_dialogues_pilot"
DEFAULT_SHOW = 20

TURN_RE = re.compile(r"^\s*【([^】]+)】\s*[:：]\s*(.*)\s*$")
PLAIN_TURN_RE = re.compile(r"^\s*([^【】\s：:]{1,24})\s*[:：]\s*(.*)\s*$")
TITLE_CHAPTER_RE = re.compile(
    r"^《[^》]+》(?P<chapter>.+?)\s+(?:对话单元|片段|规则|LLM|合并大对话)\s*\d*"
)
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SourceSpec:
    slug: str
    dataset_name: str
    path: Path
    method: str


SOURCES: dict[str, SourceSpec] = {
    "mengzi": SourceSpec(
        slug="mengzi",
        dataset_name="孟子",
        path=EXPORT_BASE / "mengzi_rule_full" / "mengzi_rule_units.csv",
        method="规则抽取",
    ),
    "pingfandeshijie": SourceSpec(
        slug="pingfandeshijie",
        dataset_name="平凡的世界",
        path=EXPORT_BASE
        / "pingfandeshijie_llm_first_full_zhipu_retry_glm-4.5-air"
        / "kept_units.csv",
        method="LLM分块抽取",
    ),
    "shuihuzhuan": SourceSpec(
        slug="shuihuzhuan",
        dataset_name="水浒传",
        path=EXPORT_BASE / "shuihuzhuan_llm_first_full_zhipu_retry_glm-4.5-air" / "kept_units.csv",
        method="LLM分块抽取",
    ),
    "hongloumeng": SourceSpec(
        slug="hongloumeng",
        dataset_name="红楼梦",
        path=IMPORT_READY / "hongloumeng_dialogue_units_full_import_cleaned_v9.csv",
        method="规则抽取",
    ),
    "xiyouji": SourceSpec(
        slug="xiyouji",
        dataset_name="西游记",
        path=EXPORT_BASE / "xiyouji_llm_first_full_zhipu" / "kept_units.csv",
        method="LLM分块抽取",
    ),
    "tangchuanqi": SourceSpec(
        slug="tangchuanqi",
        dataset_name="唐传奇",
        path=EXPORT_BASE / "tangchuanqi_llm_first_full_zhipu_retry_glm-4.5-air" / "kept_units.csv",
        method="LLM分块抽取",
    ),
    "qingpingshantang": SourceSpec(
        slug="qingpingshantang",
        dataset_name="清平山堂话本",
        path=EXPORT_BASE / "qingpingshantang_llm_first_full_zhipu_retry_glm-4.5-air" / "kept_units.csv",
        method="LLM分块抽取",
    ),
    "shishuoxinyu": SourceSpec(
        slug="shishuoxinyu",
        dataset_name="世说新语",
        path=EXPORT_BASE / "shishuoxinyu_retry_final_no_proxy" / "kept_units.csv",
        method="LLM分块抽取",
    ),
    "luotuoxiangzi": SourceSpec(
        slug="luotuoxiangzi",
        dataset_name="骆驼祥子",
        path=EXPORT_BASE / "luotuoxiangzi_llm_first_full_zhipu_retry_glm-4.5-air" / "kept_units.csv",
        method="LLM分块抽取",
    ),
    "lunyu": SourceSpec(
        slug="lunyu",
        dataset_name="论语",
        path=EXPORT_BASE / "lunyu_rule_full" / "lunyu_rule_units.csv",
        method="规则抽取",
    ),
    "zhuziyulei": SourceSpec(
        slug="zhuziyulei",
        dataset_name="朱子语类",
        path=EXPORT_BASE / "zhuziyulei_rule_full" / "zhuziyulei_rule_units.csv",
        method="规则抽取",
    ),
    "leiyu": SourceSpec(
        slug="leiyu",
        dataset_name="雷雨",
        path=IMPORT_READY / "leiyu_text_dialogue_377_ordered" / "leiyu_text_dialogue_377_ordered.csv",
        method="规则抽取",
    ),
    "laoqida": SourceSpec(
        slug="laoqida",
        dataset_name="老乞大",
        path=EXPORT_BASE / "laoqida_rule_full" / "laoqida_rule_units.csv",
        method="规则抽取",
    ),
    "putongshi": SourceSpec(
        slug="putongshi",
        dataset_name="朴通事",
        path=EXPORT_BASE / "putongshi_rule_full" / "putongshi_rule_units.csv",
        method="规则抽取",
    ),
    "zhanguoce": SourceSpec(
        slug="zhanguoce",
        dataset_name="战国策",
        path=EXPORT_BASE / "zhanguoce_rule_full" / "zhanguoce_rule_units_import_format.csv",
        method="规则抽取",
    ),
    "xixiangji": SourceSpec(
        slug="xixiangji",
        dataset_name="西厢记",
        path=EXPORT_BASE / "xixiangji_rule_full_speaker_fixed" / "kept_units.csv",
        method="规则抽取",
    ),
}

PRESET_GROUPS: dict[str, tuple[str, ...]] = {
    "pilot": ("mengzi", "pingfandeshijie", "shuihuzhuan"),
    "all-current": (
        "hongloumeng",
        "shuihuzhuan",
        "xiyouji",
        "pingfandeshijie",
        "luotuoxiangzi",
        "tangchuanqi",
        "qingpingshantang",
        "shishuoxinyu",
        "zhuziyulei",
        "mengzi",
        "lunyu",
        "leiyu",
        "laoqida",
        "putongshi",
        "zhanguoce",
        "xixiangji",
    ),
}


MERGED_FIELDS = (
    "dataset_name",
    "dialogue_id",
    "title",
    "chapter",
    "content",
    "turn_count",
    "speaker_count",
    "speakers",
    "source_unit_count",
    "source_unit_indices",
    "source_chunks",
    "source_span_ids",
    "source_titles",
    "source",
    "category",
    "year",
    "merge_method",
    "issues",
)

MANUAL_FIELDS = (
    "manual_pass",
    "manual_note",
    "dataset_name",
    "dialogue_id",
    "chapter",
    "content",
    "turn_count",
    "speaker_count",
    "speakers",
    "source_unit_count",
    "source_chunks",
    "source_span_ids",
    "title",
)


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str


@dataclass
class UnitRow:
    dataset_name: str
    row_index: int
    title: str
    content: str
    source: str
    year: str
    category: str
    chapter: str
    chunk_id: str
    span_id: str
    unit_index: str
    turns: list[Turn]
    issues: str


@dataclass
class Conversation:
    dataset_name: str
    title_prefix: str
    chapter: str
    source: str
    year: str
    category: str
    turns: list[Turn]
    source_titles: list[str] = field(default_factory=list)
    source_unit_indices: list[str] = field(default_factory=list)
    source_chunks: list[str] = field(default_factory=list)
    source_span_ids: list[str] = field(default_factory=list)
    issues: set[str] = field(default_factory=set)
    merge_count: int = 0
    contained_count: int = 0


def clean_cell(value: Any) -> str:
    return "" if value is None else str(value).strip()


def compact_text(value: str) -> str:
    return SPACE_RE.sub("", value)


def turn_key(turn: Turn) -> tuple[str, str]:
    return (compact_text(turn.speaker), compact_text(turn.text))


def turns_signature(turns: list[Turn]) -> tuple[tuple[str, str], ...]:
    return tuple(turn_key(turn) for turn in turns)


def parse_turns(content: str) -> list[Turn]:
    turns: list[Turn] = []
    current_speaker = ""
    current_text: list[str] = []

    def flush() -> None:
        nonlocal current_speaker, current_text
        if current_speaker:
            text = "\n".join(part.strip() for part in current_text if part.strip()).strip()
            if text:
                turns.append(Turn(current_speaker.strip(), text))
        current_speaker = ""
        current_text = []

    for raw_line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        match = TURN_RE.match(line)
        if not match:
            match = PLAIN_TURN_RE.match(line)
        if match:
            flush()
            current_speaker = match.group(1).strip()
            current_text = [match.group(2).strip()]
        elif current_speaker:
            current_text.append(line)
    flush()
    return turns


def infer_chapter(title: str) -> str:
    match = TITLE_CHAPTER_RE.match(title.strip())
    if not match:
        return ""
    return match.group("chapter").strip()


def format_turns(turns: list[Turn]) -> str:
    return "\n".join(f"【{turn.speaker}】：{turn.text}" for turn in turns)


def find_subsequence(haystack: list[Turn], needle: list[Turn]) -> int:
    if not needle or len(needle) > len(haystack):
        return -1
    hay = [turn_key(turn) for turn in haystack]
    ned = [turn_key(turn) for turn in needle]
    for index in range(0, len(hay) - len(ned) + 1):
        if hay[index : index + len(ned)] == ned:
            return index
    return -1


def conversation_contains(haystack: Conversation, needle: Conversation) -> bool:
    return find_subsequence(haystack.turns, needle.turns) >= 0


def chunk_number(chunk_id: str) -> int | None:
    match = re.search(r"chunk0*(\d+)", chunk_id)
    if not match:
        return None
    return int(match.group(1))


def source_chunk_numbers(conversation: Conversation) -> set[int]:
    numbers: set[int] = set()
    for chunk_id in conversation.source_chunks:
        number = chunk_number(chunk_id)
        if number is not None:
            numbers.add(number)
    return numbers


def likely_same_llm_overlap(left: Conversation, right: Conversation) -> bool:
    left_chunks = source_chunk_numbers(left)
    right_chunks = source_chunk_numbers(right)
    if not left_chunks or not right_chunks:
        return False
    if left_chunks & right_chunks:
        return True
    return min(abs(a - b) for a in left_chunks for b in right_chunks) <= 1


def suffix_prefix_overlap(left: list[Turn], right: list[Turn]) -> int:
    max_size = min(len(left), len(right))
    left_keys = [turn_key(turn) for turn in left]
    right_keys = [turn_key(turn) for turn in right]
    for size in range(max_size, 0, -1):
        if left_keys[-size:] == right_keys[:size]:
            return size
    return 0


def append_unique(target: list[str], value: str) -> None:
    value = value.strip()
    if value and value not in target:
        target.append(value)


def absorb_metadata(conversation: Conversation, row: UnitRow) -> None:
    append_unique(conversation.source_titles, row.title)
    append_unique(conversation.source_unit_indices, row.unit_index or str(row.row_index))
    append_unique(conversation.source_chunks, row.chunk_id)
    append_unique(conversation.source_span_ids, row.span_id)
    if row.issues:
        conversation.issues.add(row.issues)


def same_context(conversation: Conversation, row: UnitRow) -> bool:
    if conversation.dataset_name != row.dataset_name:
        return False
    if conversation.chapter and row.chapter and conversation.chapter != row.chapter:
        return False
    return True


def merge_row(conversation: Conversation, row: UnitRow) -> bool:
    if find_subsequence(conversation.turns, row.turns) >= 0:
        conversation.contained_count += 1
        absorb_metadata(conversation, row)
        return True

    existing_inside_new = find_subsequence(row.turns, conversation.turns)
    if existing_inside_new >= 0:
        conversation.turns = row.turns[:]
        conversation.merge_count += 1
        absorb_metadata(conversation, row)
        return True

    overlap = suffix_prefix_overlap(conversation.turns, row.turns)
    if overlap > 0:
        conversation.turns.extend(row.turns[overlap:])
        conversation.merge_count += 1
        absorb_metadata(conversation, row)
        return True

    return False


def make_conversation(row: UnitRow) -> Conversation:
    conversation = Conversation(
        dataset_name=row.dataset_name,
        title_prefix=row.title.rsplit(" ", 1)[0] if row.title else f"《{row.dataset_name}》合并对话",
        chapter=row.chapter,
        source=row.source,
        year=row.year,
        category=row.category,
        turns=row.turns[:],
    )
    absorb_metadata(conversation, row)
    return conversation


def read_units(spec: SourceSpec) -> tuple[list[UnitRow], Counter[str]]:
    stats: Counter[str] = Counter()
    units: list[UnitRow] = []
    with spec.path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row_index, row in enumerate(reader, start=1):
            content = clean_cell(row.get("content"))
            turns = parse_turns(content)
            if len(turns) < 2:
                stats["skipped_less_than_2_turns"] += 1
                continue
            dataset_name = clean_cell(row.get("dataset_name")) or spec.dataset_name
            title = clean_cell(row.get("title"))
            chapter = clean_cell(row.get("chapter")) or infer_chapter(title)
            units.append(
                UnitRow(
                    dataset_name=dataset_name,
                    row_index=row_index,
                    title=title,
                    content=content,
                    source=clean_cell(row.get("source")) or spec.method,
                    year=clean_cell(row.get("year")),
                    category=clean_cell(row.get("category")),
                    chapter=chapter,
                    chunk_id=clean_cell(row.get("chunk_id")),
                    span_id=clean_cell(row.get("span_id")),
                    unit_index=clean_cell(row.get("unit_index")),
                    turns=turns,
                    issues=clean_cell(row.get("issues")),
                )
            )
    stats["input_rows"] = len(units)
    return units, stats


def merge_units(units: list[UnitRow]) -> tuple[list[Conversation], Counter[str]]:
    conversations: list[Conversation] = []
    stats: Counter[str] = Counter()
    current: Conversation | None = None

    for row in units:
        if current is None:
            current = make_conversation(row)
            continue

        if same_context(current, row) and merge_row(current, row):
            continue

        conversations.append(current)
        current = make_conversation(row)

    if current is not None:
        conversations.append(current)

    exact_deduped: list[Conversation] = []
    seen: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
    for conversation in conversations:
        signature = (conversation.dataset_name, conversation.chapter, turns_signature(conversation.turns))
        if signature in seen:
            stats["duplicate_conversations_removed"] += 1
            continue
        seen.add(signature)
        exact_deduped.append(conversation)

    contained_indexes: set[int] = set()
    for small_index, small in enumerate(exact_deduped):
        for large_index, large in enumerate(exact_deduped):
            if small_index == large_index:
                continue
            if len(small.turns) >= len(large.turns):
                continue
            if small.dataset_name != large.dataset_name or small.chapter != large.chapter:
                continue
            if not likely_same_llm_overlap(small, large):
                continue
            if conversation_contains(large, small):
                contained_indexes.add(small_index)
                break

    deduped: list[Conversation] = []
    for index, conversation in enumerate(exact_deduped):
        if index in contained_indexes:
            stats["contained_conversations_removed"] += 1
            continue
        deduped.append(conversation)

    stats["merged_conversations"] = len(deduped)
    stats["contained_windows_absorbed"] = sum(conv.contained_count for conv in deduped)
    stats["overlap_merges"] = sum(conv.merge_count for conv in deduped)
    return deduped, stats


def speakers_for(turns: list[Turn]) -> list[str]:
    speakers: list[str] = []
    for turn in turns:
        append_unique(speakers, turn.speaker)
    return speakers


def conversation_to_row(conversation: Conversation, dialogue_index: int) -> dict[str, str]:
    speakers = speakers_for(conversation.turns)
    dialogue_id = f"{conversation.dataset_name}_{dialogue_index:04d}"
    title = f"《{conversation.dataset_name}》合并大对话 {dialogue_index:04d}"
    if conversation.chapter:
        title = f"《{conversation.dataset_name}》{conversation.chapter} 合并大对话 {dialogue_index:04d}"
    issues = sorted(conversation.issues)
    merge_notes: list[str] = []
    if conversation.merge_count:
        merge_notes.append(f"overlap_merges={conversation.merge_count}")
    if conversation.contained_count:
        merge_notes.append(f"contained_windows={conversation.contained_count}")
    return {
        "dataset_name": conversation.dataset_name,
        "dialogue_id": dialogue_id,
        "title": title,
        "chapter": conversation.chapter,
        "content": format_turns(conversation.turns),
        "turn_count": str(len(conversation.turns)),
        "speaker_count": str(len(speakers)),
        "speakers": "、".join(speakers),
        "source_unit_count": str(len(conversation.source_titles)),
        "source_unit_indices": " | ".join(conversation.source_unit_indices),
        "source_chunks": " | ".join(conversation.source_chunks),
        "source_span_ids": " | ".join(conversation.source_span_ids),
        "source_titles": " | ".join(conversation.source_titles[:20]),
        "source": conversation.source,
        "category": conversation.category,
        "year": conversation.year,
        "merge_method": "; ".join(merge_notes) if merge_notes else "no_overlap_merge_needed",
        "issues": " | ".join(issues),
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    selected: list[SourceSpec],
    per_source_stats: dict[str, Counter[str]],
    rows_by_source: dict[str, list[dict[str, str]]],
    show: int,
) -> None:
    lines: list[str] = [
        "# 对话单元合并报告",
        "",
        "## 概要",
        "",
        "- 目标：把 AB / ABC / BCD 这类重叠话轮窗口合并成 ABCD 式大对话。",
        "- 方式：解析 `【说话人】：文本`，用相邻单元的最长后缀/前缀重叠进行合并。",
        "- 数据库：未写入，未导入。",
        "",
        "## 统计",
        "",
        "| 作品 | 输入单元 | 合并后大对话 | 吸收重叠/包含窗口 | 重复删除 | 子集删除 | 最大话轮数 | 平均话轮数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for spec in selected:
        rows = rows_by_source.get(spec.slug, [])
        stats = per_source_stats[spec.slug]
        turn_counts = [int(row["turn_count"]) for row in rows]
        max_turns = max(turn_counts) if turn_counts else 0
        avg_turns = sum(turn_counts) / len(turn_counts) if turn_counts else 0
        absorbed = stats["contained_windows_absorbed"] + stats["overlap_merges"]
        lines.append(
            f"| {spec.dataset_name} | {stats['input_rows']} | {stats['merged_conversations']} | "
            f"{absorbed} | {stats['duplicate_conversations_removed']} | "
            f"{stats['contained_conversations_removed']} | {max_turns} | {avg_turns:.2f} |"
        )

    lines.extend(["", "## 输出文件", ""])
    for spec in selected:
        lines.append(f"- `{spec.slug}_merged_dialogues.csv`")
    lines.extend(
        [
            "- `merged_dialogues_all.csv`",
            "- `merged_dialogues_manual_check.csv`",
            "",
            "## 样例",
            "",
        ]
    )

    shown = 0
    for spec in selected:
        rows = rows_by_source.get(spec.slug, [])
        if not rows or shown >= show:
            continue
        lines.append(f"### {spec.dataset_name}")
        lines.append("")
        for row in rows[: max(1, min(3, show - shown))]:
            shown += 1
            lines.append(f"#### {row['dialogue_id']}")
            lines.append("")
            lines.append(f"- chapter: `{row['chapter']}`")
            lines.append(f"- turns: `{row['turn_count']}`")
            lines.append(f"- speakers: `{row['speakers']}`")
            lines.append("")
            lines.append("```text")
            lines.append(row["content"])
            lines.append("```")
            lines.append("")
            if shown >= show:
                break

    path.write_text("\n".join(lines), encoding="utf-8")


def resolve_sources(preset: str, explicit_sources: list[str]) -> list[SourceSpec]:
    if explicit_sources:
        keys = explicit_sources
    elif preset in PRESET_GROUPS:
        keys = list(PRESET_GROUPS[preset])
    else:
        keys = [preset]

    selected: list[SourceSpec] = []
    unknown = [key for key in keys if key not in SOURCES]
    if unknown:
        valid = ", ".join(sorted(SOURCES))
        raise SystemExit(f"Unknown source: {', '.join(unknown)}. Valid sources: {valid}")
    for key in keys:
        spec = SOURCES[key]
        if not spec.path.exists():
            raise SystemExit(f"Missing input for {spec.dataset_name}: {spec.path}")
        selected.append(spec)
    return selected


def run(args: argparse.Namespace) -> dict[str, Any]:
    selected = resolve_sources(args.preset, args.source)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str]] = []
    rows_by_source: dict[str, list[dict[str, str]]] = {}
    per_source_stats: dict[str, Counter[str]] = {}

    for spec in selected:
        units, read_stats = read_units(spec)
        conversations, merge_stats = merge_units(units)
        stats = read_stats + merge_stats
        per_source_stats[spec.slug] = stats

        rows = [conversation_to_row(conversation, index) for index, conversation in enumerate(conversations, start=1)]
        rows_by_source[spec.slug] = rows
        all_rows.extend(rows)
        write_csv(output_dir / f"{spec.slug}_merged_dialogues.csv", rows, MERGED_FIELDS)

    manual_rows = [{**{field: "" for field in ("manual_pass", "manual_note")}, **row} for row in all_rows]
    write_csv(output_dir / "merged_dialogues_all.csv", all_rows, MERGED_FIELDS)
    write_csv(output_dir / "merged_dialogues_manual_check.csv", manual_rows, MANUAL_FIELDS)
    write_report(output_dir / "merged_dialogues_report.md", selected, per_source_stats, rows_by_source, args.show)

    return {
        "output_dir": str(output_dir),
        "selected": [spec.slug for spec in selected],
        "total_input_rows": sum(stats["input_rows"] for stats in per_source_stats.values()),
        "total_merged_conversations": len(all_rows),
        "per_source": {slug: dict(stats) for slug, stats in per_source_stats.items()},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge overlapping dialogue units for manual review.")
    parser.add_argument(
        "--preset",
        default="pilot",
        help="Source preset or single source key. Default: pilot. Other useful value: all-current.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Explicit source key. Can be passed multiple times; overrides --preset.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for merged exports.")
    parser.add_argument("--show", type=int, default=DEFAULT_SHOW, help="Number of sample conversations in report.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = run(args)
    print(f"output_dir: {summary['output_dir']}")
    print(f"sources: {', '.join(summary['selected'])}")
    print(f"input units: {summary['total_input_rows']}")
    print(f"merged conversations: {summary['total_merged_conversations']}")
    for slug, stats in summary["per_source"].items():
        absorbed = stats.get("contained_windows_absorbed", 0) + stats.get("overlap_merges", 0)
        print(
            f"{slug}: input={stats.get('input_rows', 0)}, merged={stats.get('merged_conversations', 0)}, "
            f"absorbed={absorbed}, duplicates_removed={stats.get('duplicate_conversations_removed', 0)}, "
            f"contained_removed={stats.get('contained_conversations_removed', 0)}"
        )


if __name__ == "__main__":
    main()
