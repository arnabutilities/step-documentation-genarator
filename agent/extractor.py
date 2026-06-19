import re


def extract_steps(markdown: str) -> list[str]:
    """Return the numbered steps under a '## Steps' heading, if present."""
    # Isolate the Steps section (until the next H2 or end of document).
    match = re.search(
        r"^##\s+Steps\s*$(.*?)(^##\s+|\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return []

    section = match.group(1)
    steps = []
    for line in section.splitlines():
        line = line.strip()
        # Match "1. text", "2) text", "- text", "* text"
        item = re.match(r"^(?:\d+[.)]|[-*])\s+(.*)", line)
        if item:
            text = item.group(1).strip()
            if text:
                steps.append(text)
    return steps
