from scripts.fixers.url_join import fix, detect


def test_same_line_url_joined():
    # Agent World:arxiv.org/abs/ 2601.05808
    text = "see https://arxiv.org/abs/ 2601.05808 for details"
    assert fix(text) == "see https://arxiv.org/abs/2601.05808 for details"


def test_cjk_followup_not_joined():
    # token 含 CJK(中文正文),不接
    assert fix("https://example.com/page 对于") == "https://example.com/page 对于"


def test_cross_line_reported_not_fixed():
    text = "see https://arxiv.org/abs/\n 2601.05808 for details"
    assert fix(text) == text
    problems = detect(text)
    assert any("split across lines" in p.message for p in problems)


def test_detect_cross_line_line_number():
    text = "first line\nsee https://arxiv.org/abs/\n 2601.05808\n"
    problems = detect(text)
    hits = [p for p in problems if "split across lines" in p.message]
    assert len(hits) == 1 and hits[0].line == 3


def test_code_zone_url_untouched():
    text = "```\nsee https://arxiv.org/abs/ 2601.05808\n```"
    assert fix(text) == text


def test_detect_clean_on_joined_same_line():
    # 同行已接合的 URL 不报
    text = "see https://arxiv.org/abs/2601.05808 for details"
    assert detect(text) == []
