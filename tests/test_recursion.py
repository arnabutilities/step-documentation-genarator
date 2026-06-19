from pathlib import Path

import agent.recursion as recursion
from agent.recursion import expand


def _make_fake_generator(steps_by_topic: dict[str, list[str]], calls: list[str] | None = None):
    """Return a fake generate_markdown that emits a Steps section per topic.

    If `calls` is provided, each invoked topic is appended to it so tests can
    assert how many real generations happened.
    """

    def fake(topic: str) -> str:
        if calls is not None:
            calls.append(topic)
        steps = steps_by_topic.get(topic, [])
        body = f"# {topic}\n\nOverview of {topic}.\n"
        if steps:
            numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
            body += f"\n## Steps\n\n{numbered}\n"
        return body

    return fake


def _run(tmp_path, steps_by_topic, *, max_depth=3, max_nodes=50, resume=True):
    config = {"max_depth": max_depth, "max_nodes": max_nodes, "resume": resume}
    state = {"seen": set(), "count": 0, "generated": 0, "reused": 0}
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


def test_resume_reuses_existing_output_without_regenerating(tmp_path, monkeypatch):
    steps = {"Root": ["Step A", "Step B"], "Step A": ["Step A1"]}

    # First run: everything is generated.
    calls_first: list[str] = []
    monkeypatch.setattr(
        recursion, "generate_markdown", _make_fake_generator(steps, calls_first)
    )
    _, state1 = _run(tmp_path, steps)
    assert state1["generated"] == 4
    assert state1["reused"] == 0
    assert len(calls_first) == 4

    # Second run on the same directory: nothing should be regenerated.
    calls_second: list[str] = []
    monkeypatch.setattr(
        recursion, "generate_markdown", _make_fake_generator(steps, calls_second)
    )
    _, state2 = _run(tmp_path, steps)
    assert state2["reused"] == 4
    assert state2["generated"] == 0
    assert calls_second == []  # no API/generator calls at all


def test_resume_continues_only_missing_parts(tmp_path, monkeypatch):
    steps = {
        "Root": ["Step A", "Step B"],
        "Step A": ["Step A1"],
        "Step B": ["Step B1"],
    }

    # First run is cut short by the node budget (partial tree).
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator(steps))
    _, state1 = _run(tmp_path, steps, max_nodes=2)
    assert state1["generated"] == 2  # Root + Step A only

    # Second run with a larger budget reuses the two existing docs and
    # generates only the remaining ones.
    calls_second: list[str] = []
    monkeypatch.setattr(
        recursion, "generate_markdown", _make_fake_generator(steps, calls_second)
    )
    _, state2 = _run(tmp_path, steps, max_nodes=50)
    assert state2["reused"] == 2
    assert state2["generated"] >= 2
    # The previously generated nodes are not regenerated.
    assert "Root" not in calls_second
    assert "Step A" not in calls_second


def test_fresh_flag_regenerates_existing_output(tmp_path, monkeypatch):
    steps = {"Root": ["Step A"]}
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator(steps))
    _run(tmp_path, steps)

    calls_second: list[str] = []
    monkeypatch.setattr(
        recursion, "generate_markdown", _make_fake_generator(steps, calls_second)
    )
    _, state = _run(tmp_path, steps, resume=False)
    assert state["reused"] == 0
    assert state["generated"] == 2
    assert set(calls_second) == {"Root", "Step A"}


def test_resume_does_not_duplicate_detailed_steps_section(tmp_path, monkeypatch):
    steps = {"Root": ["Step A", "Step B"]}
    monkeypatch.setattr(recursion, "generate_markdown", _make_fake_generator(steps))

    _run(tmp_path, steps)
    _run(tmp_path, steps)  # resume

    content = (tmp_path / "root.md").read_text(encoding="utf-8")
    assert content.count("## Detailed Steps") == 1
