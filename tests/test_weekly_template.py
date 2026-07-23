"""周报模板空数据渲染测试。"""

from apps.reporter.weekly_template import WeeklyBriefContext, render_weekly_brief


def test_render_empty_weekly_brief() -> None:
    markdown = render_weekly_brief()
    assert "靶点情报周报" in markdown
    assert "IL-4Rα" in markdown
    assert "本周关键结论" in markdown
    assert "暂无" in markdown


def test_render_with_empty_context_object() -> None:
    markdown = render_weekly_brief(WeeklyBriefContext())
    assert isinstance(markdown, str)
    assert len(markdown) > 100
