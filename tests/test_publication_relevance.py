"""Publication relevance 单测。"""

from apps.processor.publication_relevance import score_publication_relevance
from packages.source_adapters.pubmed.query_builder import build_pubmed_query


def test_score_high_when_target_in_title() -> None:
    score = score_publication_relevance(
        title="IL-4Rα antagonism in atopic dermatitis",
        abstract="Methods and results.",
        matched_targets=["IL-4Rα"],
        study_type="clinical_trial",
    )
    assert score >= 0.6


def test_score_low_without_target() -> None:
    score = score_publication_relevance(
        title="General dermatology review",
        abstract="No target mention.",
        matched_targets=[],
        study_type="other",
    )
    assert score < 0.45


def test_query_requires_title_by_default() -> None:
    q = build_pubmed_query(require_target_in_title=True)
    assert "[Title]" in q
    assert "[Title/Abstract]" not in q.split("AND")[0]
