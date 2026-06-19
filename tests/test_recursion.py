from pathlib import Path

import agent.recursion as recursion
from agent.recursion import expand


def _make_fake_generator(steps_by_topic: dict[str, list[str]]):
    """Return a fake generate_markdown that emits a Steps section per topic."""

    def fake(topic: str) -> str:
        steps = steps_by_topic.get(topic, [])
        body = f"# {topic}\n\nOverview of {topic}.\n"
        if steps:
            numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
            body += f"\n## Steps\n\n{numbered}\n"
        return body

    return fake


def _run(tmp_path, steps_by_topic, *, max_depth=3, max_nodes=50):
    config = {"max_depth": max_depth, "max_nodes": max_nodes}
    state = {"seen": set(), "count": 0}
    root = expand("Root", tmp_path, depth=0, config=config, state=state)
    return root, state


def test_builds_recursive_tree(tmp_path, monkeypatch):
    steps = {
        "Root": ["Step A", "Step B"],
        "Step A": ["Step A1"],
    }
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator(steps))

    root, state = _run(tmp_path, steps)

    # Root + Step A + Step B + Step A1 = 4 documents.
    assert state["count"] == 4
    assert root == tmp_path / "root.md"
    assert (tmp_path / "root.md").exists()
    assert (tmp_path / "root" / "step-a.md").exists()
    assert (tmp_path / "root" / "step-b.md").exists()
    assert (tmp_path / "root" / "step-a" / "step-a1.md").exists()


def test_parent_links_to_children(tmp_path, monkeypatch):
    steps = {"Root": ["Step A", "Step B"]}
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator(steps))

    _run(tmp_path, steps)

    content = (tmp_path / "root.md").read_text(encoding="utf-8")
    assert "## Detailed Steps" in content
    assert "(root/step-a.md)" in content
    assert "(root/step-b.md)" in content


def test_respects_max_depth(tmp_path, monkeypatch):
    steps = {
        "Root": ["Step A"],
        "Step A": ["Step A1"],
        "Step A1": ["Step A1a"],
    }
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator(steps))

    # depth 0 (Root) and depth 1 (Step A) only.
    _, state = _run(tmp_path, steps, max_depth=1)
    assert state["count"] == 2
    assert (tmp_path / "root" / "step-a.md").exists()
    assert not (tmp_path / "root" / "step-a" / "step-a1.md").exists()


def test_respects_max_nodes(tmp_path, monkeypatch):
    steps = {"Root": ["Step A", "Step B", "Step C", "Step D"]}
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator(steps))

    _, state = _run(tmp_path, steps, max_nodes=3)
    assert state["count"] == 3


def test_deduplicates_repeated_steps(tmp_path, monkeypatch):
    # Two different parents both reference the same "Shared" step.
    steps = {
        "Root": ["Step A", "Step B"],
        "Step A": ["Shared"],
        "Step B": ["Shared"],
    }
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator(steps))

    _, state = _run(tmp_path, steps)
    # Root, Step A, Step B, Shared (only once) = 4.
    assert state["count"] == 4


def test_no_steps_produces_single_file(tmp_path, monkeypatch):
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator({}))

    root, state = _run(tmp_path, {})
    assert state["count"] == 1
    assert root.exists()
    assert "## Detailed Steps" not in root.read_text(encoding="utf-8")
