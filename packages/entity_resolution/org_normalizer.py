"""公司名归一 — 读取 config/orgs-seed.yaml。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_ROOT = Path(__file__).resolve().parents[2]
_ORGS_SEED = _ROOT / "config" / "orgs-seed.yaml"


def _normalize(name: str) -> str:
    return re.sub(r"[\s\-_]+", " ", name.lower()).strip()


@dataclass(frozen=True)
class OrganizationEntry:
    org_id: str
    canonical_name: str
    name_zh: str | None
    aliases: tuple[str, ...]
    country: str | None
    sec_cik: str | None = None


class OrganizationNormalizer:
    def __init__(self, entries: list[OrganizationEntry]) -> None:
        self._entries = entries
        self._index: dict[str, str] = {}
        for entry in entries:
            keys = {entry.canonical_name, entry.org_id, *entry.aliases}
            if entry.name_zh:
                keys.add(entry.name_zh)
            for key in keys:
                self._index[_normalize(key)] = entry.org_id

    @classmethod
    def from_seed(cls, path: Path | None = None) -> OrganizationNormalizer:
        seed_path = path or _ORGS_SEED
        raw = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
        entries: list[OrganizationEntry] = []
        for org in raw.get("organizations", []):
            cik = org.get("sec_cik")
            if cik:
                cik = str(cik).zfill(10)
            entries.append(
                OrganizationEntry(
                    org_id=org["org_id"],
                    canonical_name=org["canonical_name"],
                    name_zh=org.get("name_zh"),
                    aliases=tuple(org.get("aliases", [])),
                    country=org.get("country"),
                    sec_cik=cik,
                )
            )
        return cls(entries)

    def resolve(self, text: str) -> str | None:
        if not text.strip():
            return None
        key = _normalize(text.strip())
        if key in self._index:
            return self._index[key]
        for alias, org_id in self._index.items():
            if alias in key or key in alias:
                return org_id
        return None

    def get(self, org_id: str) -> OrganizationEntry | None:
        for entry in self._entries:
            if entry.org_id == org_id:
                return entry
        return None

    def all_with_sec_cik(self) -> list[OrganizationEntry]:
        return [e for e in self._entries if e.sec_cik]
