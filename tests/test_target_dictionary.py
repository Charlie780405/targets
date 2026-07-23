"""靶点词典别名归一测试。"""

from packages.entity_resolution.target_dictionary import TargetDictionary


def test_resolve_cd124_to_il4ra() -> None:
    dictionary = TargetDictionary.from_config_dir()
    match = dictionary.resolve("CD124")
    assert match is not None
    assert match.canonical_name == "IL-4Rα"
    assert match.target_id == "TGT_001"


def test_resolve_case_and_hyphen_variants() -> None:
    dictionary = TargetDictionary.from_config_dir()
    for alias in ("il4r", "IL-4R", "IL4RA", "interleukin-4 receptor subunit alpha"):
        match = dictionary.resolve(alias)
        assert match is not None, f"failed for alias: {alias}"
        assert match.canonical_name == "IL-4Rα"


def test_resolve_unknown_returns_none() -> None:
    dictionary = TargetDictionary.from_config_dir()
    assert dictionary.resolve("NOT_A_TARGET") is None


def test_all_entries_loaded() -> None:
    dictionary = TargetDictionary.from_config_dir()
    entries = dictionary.all_entries()
    assert len(entries) >= 1
    assert entries[0].target_id == "TGT_001"
