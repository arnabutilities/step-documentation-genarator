from pathlib import Path

from slugify import slugify

from agent.generator import generate_markdown
from agent.extractor import extract_steps


def expand(topic: str, out_dir: Path, depth: int, config: dict, state: dict) -> Path | None:
    """Recursively generate a Markdown tree for `topic`."""
    # --- Safeguards ---
    if depth > config["max_depth"]:
        return None
    if state["count"] >= config["max_nodes"]:
        return None
    key = slugify(topic)
    if not key:
        return None
    if key in state["seen"]:
        return None  # avoid regenerating the same step twice
    state["seen"].add(key)
    state["count"] += 1

    # --- Generate this document ---
    print(f"{'  ' * depth}• [{depth}] {topic}")
    markdown = generate_markdown(topic)

    out_dir.mkdir(parents=True, exist_ok=True)
    doc_path = out_dir / f"{key}.md"

    # --- Extract steps and recurse ---
    steps = extract_steps(markdown)
    child_links = []
    for step in steps:
        child_dir = out_dir / key
        child_path = expand(step, child_dir, depth + 1, config, state)
        if child_path:
            rel = child_path.relative_to(out_dir).as_posix()
            child_links.append(f"- [{step}]({rel})")

    # --- Append links to children so the tree is navigable ---
    if child_links:
        markdown += "\n\n## Detailed Steps\n\n" + "\n".join(child_links) + "\n"

    doc_path.write_text(markdown, encoding="utf-8")
    return doc_path
