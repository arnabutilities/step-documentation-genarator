from agent.extractor import extract_steps


def test_extracts_numbered_steps():
    md = """# Title

Overview paragraph.

## Steps

1. First step
2. Second step
3. Third step

## Notes

Some trailing content.
"""
    assert extract_steps(md) == ["First step", "Second step", "Third step"]


def test_handles_paren_and_bullet_markers():
    md = """## Steps

1) Alpha
- Beta
* Gamma
"""
    assert extract_steps(md) == ["Alpha", "Beta", "Gamma"]


def test_returns_empty_when_no_steps_section():
    md = """# Concept

This document is purely conceptual and has no steps.
"""
    assert extract_steps(md) == []


def test_section_stops_at_next_h2():
    md = """## Steps

1. Inside steps

## Other

1. Should not be captured
"""
    assert extract_steps(md) == ["Inside steps"]


def test_case_insensitive_heading():
    md = """## steps

1. lower-case heading still works
"""
    assert extract_steps(md) == ["lower-case heading still works"]


def test_ignores_blank_list_items():
    md = """## Steps

1. Real step
2.
3. Another step
"""
    assert extract_steps(md) == ["Real step", "Another step"]
