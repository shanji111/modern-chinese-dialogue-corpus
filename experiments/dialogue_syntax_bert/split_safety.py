"""Helpers for future train/dev/test split leakage checks.

This module does not create splits. It only defines the fields that must remain
disjoint across train/dev/test once split generation is implemented.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


DISJOINT_SPLIT_FIELDS = ("pair_id", "normalized_pair_hash", "conversation_group_key")


def collect_split_keys(rows: Sequence[Mapping[str, object]], field: str) -> set[str]:
    return {str(row.get(field) or "").strip() for row in rows if str(row.get(field) or "").strip()}


def find_split_leakage(named_splits: Mapping[str, Sequence[Mapping[str, object]]]) -> dict[str, list[dict[str, object]]]:
    """Return cross-split overlaps for pair, duplicate-text, and conversation keys."""
    leakage: dict[str, list[dict[str, object]]] = {}
    split_names = list(named_splits)
    for field in DISJOINT_SPLIT_FIELDS:
        field_leakage = []
        for left_index, left_name in enumerate(split_names):
            left_keys = collect_split_keys(named_splits[left_name], field)
            for right_name in split_names[left_index + 1:]:
                right_keys = collect_split_keys(named_splits[right_name], field)
                overlap = sorted(left_keys & right_keys)
                if overlap:
                    field_leakage.append({
                        "left": left_name,
                        "right": right_name,
                        "count": len(overlap),
                        "examples": overlap[:10],
                    })
        leakage[field] = field_leakage
    return leakage


def has_split_leakage(named_splits: Mapping[str, Sequence[Mapping[str, object]]]) -> bool:
    leakage = find_split_leakage(named_splits)
    return any(items for items in leakage.values())

