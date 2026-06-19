from pathlib import Path

from agent import diagram


ROOT_MD = """# How to Make Tea

Overview paragraph.

## Steps

1. Boil water
2. Add tea leaves
3. Steep and serve

## Detailed Steps

- [Boil water](how-to-make-tea/boil-water.md)
- [Add tea leaves](how-to-make-tea/add-tea-leaves.md)
- [Steep and serve](how-to-make-tea/steep-and-serve.md)
"""

ROOT_NO_CHILDREN = """# Standalone Concept

Just an overview, no steps.
"""


def _write_root(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_build_svg_contains_root_and_children():
    svg = diagram.build_diagram_svg("How to Make Tea", ["Boil water", "Add tea leaves"])
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "How to Make Tea" in svg
    assert "Boil water" in svg
    assert "Add tea leaves" in svg
    # children are numbered
    assert "1. Boil water" in svg
    assert "2. Add tea leaves" in svg


def test_build_svg_escapes_special_characters():
    svg = diagram.build_diagram_svg("A & B <tag>", ["x > y"])
    assert "&amp;" in svg
    assert "&lt;tag&gt;" in svg
    assert "x &gt; y" in svg
    assert "<tag>" not in svg.replace("<svg", "")  # no raw tag injected


def test_children_parsed_in_order_from_links():
    titles = diagram._children_from_links(ROOT_MD)
    assert titles == ["Boil water", "Add tea leaves", "Steep and serve"]


def test_generate_diagram_creates_file(tmp_path):
    root = _write_root(tmp_path, "how-to-make-tea.md", ROOT_MD)
    path, created = diagram.generate_diagram(root)
    assert created is True
    assert path == tmp_path / "how-to-make-tea.flow.svg"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "How to Make Tea" in content
    assert "Steep and serve" in content


def test_generate_diagram_skips_when_present(tmp_path):
    root = _write_root(tmp_path, "how-to-make-tea.md", ROOT_MD)
    diagram.generate_diagram(root)
    _, created_again = diagram.generate_diagram(root)
    assert created_again is False


def test_generate_diagram_overwrite(tmp_path):
    root = _write_root(tmp_path, "how-to-make-tea.md", ROOT_MD)
    diagram.generate_diagram(root)
    _, created = diagram.generate_diagram(root, overwrite=True)
    assert created is True


def test_diagram_for_root_without_children(tmp_path):
    root = _write_root(tmp_path, "concept.md", ROOT_NO_CHILDREN)
    path, created = diagram.generate_diagram(root)
    assert created is True
    content = path.read_text(encoding="utf-8")
    assert "Standalone Concept" in content


def test_generate_missing_diagrams_backfills_only_absent(tmp_path):
    _write_root(tmp_path, "tree-a.md", ROOT_MD)
    root_b = _write_root(tmp_path, "tree-b.md", ROOT_MD)
    # Pre-create a diagram for tree-b so it should be skipped.
    diagram.generate_diagram(root_b)

    created = diagram.generate_missing_diagrams(tmp_path)
    created_names = {p.name for p in created}
    assert "tree-a.flow.svg" in created_names
    assert "tree-b.flow.svg" not in created_names
    assert (tmp_path / "tree-a.flow.svg").exists()


def test_generate_missing_diagrams_on_missing_dir(tmp_path):
    assert diagram.generate_missing_diagrams(tmp_path / "nope") == []


def test_parse_steps_log_utf16(tmp_path):
    log = tmp_path / "steps.txt"
    log.write_text(
        "- [0] (reuse) Root topic\n  - [1] (reuse) **Phase One**\n    - [2] (reuse) Sub A\n",
        encoding="utf-16",
    )
    entries = diagram.parse_steps_log(log)
    assert len(entries) == 3
    assert entries[0] == (0, "Root topic")
    assert diagram.main_phases_from_steps_log(entries) == ["Phase One"]
    subs = diagram.substeps_by_phase_from_steps_log(entries)
    assert subs["Phase One"] == ["Sub A"]


def test_build_pipeline_svg_has_sequential_steps():
    svg = diagram.build_pipeline_svg("Root", ["Alpha", "Beta"])
    assert "Workflow pipeline (2 phases)" in svg
    assert "1. Alpha" in svg
    assert "2. Beta" in svg


def test_generate_extended_diagrams(tmp_path):
    root = tmp_path / "project.md"
    root.write_text(
        "# Project\n\n## Steps\n\n1. **Step A**\n2. **Step B**\n",
        encoding="utf-8",
    )
    paths = diagram.generate_extended_diagrams(root)
    assert "pipeline" in paths
    assert "hierarchy" in paths
    assert paths["pipeline"].exists()
