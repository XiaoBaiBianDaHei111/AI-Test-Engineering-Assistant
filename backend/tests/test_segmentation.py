"""Long-PRD segmentation tests (P2-007, R003 MINOR-003 fallback)."""

from app.services.ai.agents.requirements_analyst import segment_text


def test_short_text_not_segmented():
    assert segment_text("短文本", 100) == ["短文本"]


def test_blank_text_returns_empty():
    assert segment_text("   ", 100) == []


def test_long_text_split_by_headings():
    text = "# 章节一\n" + "a" * 30 + "\n# 章节二\n" + "b" * 30
    segments = segment_text(text, 40)
    assert len(segments) == 2
    assert "章节一" in segments[0]
    assert "章节二" in segments[1]


def test_long_text_no_headings_split_by_paragraphs():
    text = ("第一段内容。 " * 30) + "\n\n" + ("第二段内容。 " * 30) + "\n\n" + ("第三段内容。 " * 30)
    segments = segment_text(text, 100)
    assert len(segments) >= 2
    assert all(len(s) <= 100 for s in segments)


def test_long_text_no_headings_no_paragraphs_fixed_chunks():
    text = "x" * 250
    segments = segment_text(text, 100)
    assert segments == ["x" * 100, "x" * 100, "x" * 50]
    assert all(len(s) <= 100 for s in segments)
