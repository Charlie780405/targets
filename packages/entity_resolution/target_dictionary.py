"""靶点词典 — 从 config/targets/*.yaml 加载别名并归一。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_CONFIG_TARGETS_DIR = Path(__file__).resolve().parents[2] / "config" / "targets"


def _normalize(token: str) -> str:
    """大小写、空格、连字符、下划线变体归一。"""
    return re.sub(r"[\s\-_]+", "", token.lower())


@dataclass(frozen=True)
class TargetEntry:
    target_id: str
    canonical_name: str
    gene: str | None
    aliases: tuple[str, ...]
    exclude_patterns: tuple[str, ...]


@dataclass(frozen=True)
class TargetMatch:
    target_id: str
    canonical_name: str
    matched_alias: str


class TargetDictionary:
    def __init__(self, entries: list[TargetEntry]) -> None:
        self._entries = entries
        self._alias_index: dict[str, TargetEntry] = {}
        for entry in entries:
            keys = {entry.canonical_name, *entry.aliases}
            if entry.gene:
                keys.add(entry.gene)
            for alias in keys:
                self._alias_index[_normalize(alias)] = entry

    @classmethod
    def from_config_dir(cls, config_dir: Path | None = None) -> TargetDictionary:
        directory = config_dir or _CONFIG_TARGETS_DIR
        entries: list[TargetEntry] = []
        for path in sorted(directory.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not raw:
                continue
            entries.append(
                TargetEntry(
                    target_id=raw["target_id"],
                    canonical_name=raw["canonical_name"],
                    gene=raw.get("gene"),
                    aliases=tuple(raw.get("aliases", [])),
                    exclude_patterns=tuple(raw.get("exclude_patterns", [])),
                )
            )
        return cls(entries)

    def resolve(self, text: str) -> TargetMatch | None:
        if not text or not text.strip():
            return None
        for item in self._entries:
            for pattern in item.exclude_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return None
        key = _normalize(text.strip())
        matched = self._alias_index.get(key)
        if matched is None:
            return None
        return TargetMatch(
            target_id=matched.target_id,
            canonical_name=matched.canonical_name,
            matched_alias=text.strip(),
        )

    def all_entries(self) -> list[TargetEntry]:
        return list(self._entries)
