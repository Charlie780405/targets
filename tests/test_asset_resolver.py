"""资产解析与公司事件分类测试。"""

from apps.processor.company_event_classifier import classify_company_release
from apps.processor.source_reliability import confidence_from_evidence_level
from packages.domain.enums import EventType, EvidenceLevel
from packages.entity_resolution.asset_resolver import AssetResolver
from packages.entity_resolution.org_normalizer import OrganizationNormalizer


def test_same_asset_old_code_and_inn() -> None:
    resolver = AssetResolver.from_seed()
    assert resolver.same_asset("REGN668 results", "dupilumab met endpoint")
    assert resolver.same_asset("CM310", "stapokibart trial")


def test_resolve_dupilumab_in_text() -> None:
    resolver = AssetResolver.from_seed()
    hits = resolver.resolve_in_text("Dupixent (dupilumab) improved EASI-75")
    assert any(h.asset_id == "AST_dupilumab" for h in hits)


def test_org_normalizer_regeneron() -> None:
    normalizer = OrganizationNormalizer.from_seed()
    assert normalizer.resolve("Regeneron") == "regeneron"
    assert normalizer.resolve("REGN") == "regeneron"


def test_classify_clinical_result() -> None:
    event_type = classify_company_release(
        "Dupilumab Phase 3 met primary endpoint in CSU",
        "Topline results announced",
    )
    assert event_type == EventType.CLINICAL_RESULT


def test_classify_deal() -> None:
    event_type = classify_company_release(
        "Company announces licensing agreement for IL-4Rα asset",
        "Global collaboration and investment",
    )
    assert event_type == EventType.DEAL


def test_confidence_from_evidence_level_c() -> None:
    assert confidence_from_evidence_level(EvidenceLevel.C) == 0.70
