"""Publication LLM 分析单测。"""

from apps.processor.publication_analysis import analyze_publication


def test_rule_based_analysis_without_llm() -> None:
    result, method = analyze_publication(
        title="IL-4Rα signaling in CSU",
        abstract="We studied IL-4Rα pathway.",
        matched_targets=["IL-4Rα"],
        study_type="other",
        use_llm=False,
    )
    assert method == "rule"
    assert result.suggested_action == "needs_info"
    assert result.summary_zh
