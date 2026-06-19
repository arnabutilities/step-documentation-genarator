import re
from pathlib import Path

from slugify import slugify

from agent.generator import generate_markdown
from agent.extractor import extract_steps

# Marks the auto-generated child-links section so it can be recomputed safely.
_DETAILED_STEPS_RE = re.compile(
    r"\n*##\s+Detailed Steps\s*$.*\Z",
    flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def _strip_detailed_steps(markdown: str) -> str:
    """Remove a previously appended '## Detailed Steps' section, if any."""
    return _DETAILED_STEPS_RE.sub("", markdown).rstrip()


def expand(topic: str, out_dir: Path, depth: int, config: dict, state: dict) -> Path | None:
    """Recursively generate a Markdown tree for `topic`.

    Resumable: if a document already exists on disk it is reused (no API call)
    and only the missing parts of the tree are generated.
    """
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

    out_dir.mkdir(parents=True, exist_ok=True)
    doc_path = out_dir / f"{key}.md"

    # --- Reuse existing output when resuming ---
    resume = config.get("resume", True)
    if resume and doc_path.exists():
        markdown = _strip_detailed_steps(doc_path.read_text(encoding="utf-8"))
        state["reused"] += 1
        print(f"{'  ' * depth}- [{depth}] (reuse) {topic}")
    else:
        print(f"{'  ' * depth}- [{depth}] (generate) {topic}")
        markdown = generate_markdown(topic)
        state["generated"] += 1

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
