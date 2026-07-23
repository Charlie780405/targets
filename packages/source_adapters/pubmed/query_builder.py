"""PubMed 检索式构建 — 靶点别名 + 适应症。"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

_ROOT = Path(__file__).resolve().parents[3]
_TARGETS_DIR = _ROOT / "config" / "targets"
_INDICATIONS_DIR = _ROOT / "config" / "indications"


def _load_terms(directory: Path, *, name_keys: tuple[str, ...]) -> list[str]:
    terms: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not data:
            continue
        for key in name_keys:
            value = data.get(key)
            if value:
                terms.append(str(value))
        for alias in data.get("aliases", []):
            terms.append(str(alias))
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique.append(term)
    return unique


def build_pubmed_query(
    targets_dir: Path | None = None,
    indications_dir: Path | None = None,
) -> str:
    """(靶点 OR ...) AND (适应症 OR ...)，供 esearch term 参数使用。"""
    target_terms = _load_terms(
        targets_dir or _TARGETS_DIR,
        name_keys=("canonical_name", "gene"),
    )
    indication_terms = _load_terms(
        indications_dir or _INDICATIONS_DIR,
        name_keys=("canonical_name", "name_en"),
    )
    target_clause = " OR ".join(f'"{t}"[Title/Abstract]' for t in target_terms)
    indication_clause = " OR ".join(f'"{t}"[Title/Abstract]' for t in indication_terms)
    return f"({target_clause}) AND ({indication_clause})"
