"""药物实体解析 — 研发代码↔通用名↔公司↔靶点。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_ROOT = Path(__file__).resolve().parents[2]
_ASSETS_SEED = _ROOT / "config" / "assets-seed.yaml"


@dataclass(frozen=True)
class AssetEntry:
    asset_id: str
    inn: str | None
    brand: str | None
    codes: tuple[str, ...]
    organizations: tuple[str, ...]
    target: str
    mechanism: str | None
    confidence: str | None


@dataclass(frozen=True)
class ResolvedAsset:
    asset_id: str
    inn: str | None
    brand: str | None
    matched_token: str
    organizations: tuple[str, ...]


class AssetResolver:
    def __init__(self, entries: list[AssetEntry], target: str) -> None:
        self._entries = entries
        self._target = target
        self._tokens: list[tuple[str, AssetEntry]] = []
        for entry in entries:
            for token in self._alias_tokens(entry):
                self._tokens.append((token, entry))

    @classmethod
    def from_seed(cls, path: Path | None = None) -> AssetResolver:
        seed_path = path or _ASSETS_SEED
        raw = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
        target = str(raw.get("target", ""))
        entries: list[AssetEntry] = []
        for asset in raw.get("assets", []):
            codes = tuple(str(c) for c in asset.get("codes", []))
            entries.append(
                AssetEntry(
                    asset_id=asset["asset_id"],
                    inn=asset.get("inn"),
                    brand=asset.get("brand"),
                    codes=codes,
                    organizations=tuple(asset.get("organizations", [])),
                    target=target,
                    mechanism=asset.get("mechanism"),
                    confidence=asset.get("confidence"),
                )
            )
        return cls(entries, target)

    @staticmethod
    def _alias_tokens(entry: AssetEntry) -> list[str]:
        tokens: list[str] = []
        for value in (entry.inn, entry.brand, *entry.codes):
            if value:
                tokens.append(str(value))
        return tokens

    def resolve_in_text(self, text: str) -> list[ResolvedAsset]:
        if not text.strip():
            return []
        found: dict[str, ResolvedAsset] = {}
        lowered = text.lower()
        for token, entry in self._tokens:
            pattern = re.escape(token.lower())
            if re.search(rf"\b{pattern}\b", lowered):
                found[entry.asset_id] = ResolvedAsset(
                    asset_id=entry.asset_id,
                    inn=entry.inn,
                    brand=entry.brand,
                    matched_token=token,
                    organizations=entry.organizations,
                )
        return list(found.values())

    def same_asset(self, token_a: str, token_b: str) -> bool:
        hits_a = {r.asset_id for r in self.resolve_in_text(token_a)}
        hits_b = {r.asset_id for r in self.resolve_in_text(token_b)}
        return bool(hits_a & hits_b)
