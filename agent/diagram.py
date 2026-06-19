"""Generate flow-diagram SVGs from generated Markdown output.

Diagram types:
- ``<slug>.flow.svg`` — top-2 org chart (root + direct children from links).
- ``<slug>.pipeline.flow.svg`` — sequential pipeline of main workflow phases.
- ``<slug>.hierarchy.flow.svg`` — root + main phases + depth-2 substeps.
"""

import re
from pathlib import Path

_STEPS_LOG_RE = re.compile(
    r"^- \[(\d+)\] \((?:reuse|generate)\) (.+)$"
)
_MAIN_PHASE_RE = re.compile(r"\*\*(.+?)\*\*")
_STEPS_SECTION_RE = re.compile(
    r"^##\s+Steps\s*$(.*?)(^##\s+|\Z)",
    flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_NUMBERED_STEP_RE = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*", re.MULTILINE)

_H1_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)
_DETAILED_RE = re.compile(
    r"^##\s+Detailed Steps\s*$(.*)\Z",
    flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_LINK_RE = re.compile(r"^- \[(.*?)\]\((.*?\.md)\)\s*$", re.MULTILINE)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _read_title(markdown: str) -> str:
    match = _H1_RE.search(markdown)
    return match.group(1).strip() if match else ""


def _children_from_links(markdown: str) -> list[str]:
    """Return ordered child titles from the root's '## Detailed Steps' links."""
    section = _DETAILED_RE.search(markdown)
    if not section:
        return []
    return [title.strip() for title, _ in _LINK_RE.findall(section.group(1))]


def _wrap(text: str, max_chars: int, max_lines: int) -> list[str]:
    """Wrap text into lines, truncating with an ellipsis if it overflows."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    i = 0
    while i < len(words):
        word = words[i]
        candidate = word if not cur else f"{cur} {word}"
        if len(candidate) <= max_chars:
            cur = candidate
            i += 1
        elif cur:
            lines.append(cur)
            cur = ""
            if len(lines) == max_lines:
                break
        else:  # single word longer than the line
            lines.append(word[:max_chars])
            i += 1
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)

    truncated = i < len(words)
    if truncated and lines:
        last = lines[-1]
        if len(last) > max_chars - 3:
            last = last[: max_chars - 3].rstrip()
        lines[-1] = last + "..."
    return lines or [""]


def _box(x: float, y: float, w: float, h: float, text: str, fill: str, stroke: str,
         is_title: bool) -> str:
    font_size = 16 if is_title else 12.5
    weight = 700 if is_title else 600
    max_chars = 34 if is_title else 28
    max_lines = 2 if is_title else 3
    lines = _wrap(text, max_chars=max_chars, max_lines=max_lines)

    line_h = font_size + 4
    start_y = y + h / 2 - (len(lines) * line_h) / 2 + font_size - 2
    cx = x + w / 2

    parts = [
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" '
        f'rx="12" ry="12" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    ]
    for j, line in enumerate(lines):
        ty = start_y + j * line_h
        parts.append(
            f'<text x="{cx:.0f}" y="{ty:.0f}" text-anchor="middle" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif" '
            f'font-size="{font_size}" font-weight="{weight}" fill="#0f172a">'
            f"{_esc(line)}</text>"
        )
    return "\n".join(parts)


def build_diagram_svg(title: str, child_titles: list[str]) -> str:
    """Build an SVG flow diagram for a root node and its direct children."""
    margin = 40
    box_w, box_h = 210, 96
    gap_x = 34
    root_w, root_h = 380, 78
    root_y = margin
    trunk_y = root_y + root_h + 44
    children_y = trunk_y + 44
    n = len(child_titles)

    total_children_w = n * box_w + (n - 1) * gap_x if n else 0
    content_w = max(total_children_w, root_w)
    canvas_w = content_w + 2 * margin
    canvas_h = (children_y + box_h + margin) if n else (root_y + root_h + margin)
    cx = canvas_w / 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" '
        f'height="{canvas_h:.0f}" viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" '
        'refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L8,3 L0,6 Z" fill="#475569"/></marker></defs>',
        f'<rect x="0" y="0" width="{canvas_w:.0f}" height="{canvas_h:.0f}" fill="#f8fafc"/>',
        _box(cx - root_w / 2, root_y, root_w, root_h, title or "(untitled)",
             "#e0e7ff", "#6366f1", is_title=True),
    ]

    if n:
        offset = margin + (content_w - total_children_w) / 2 + box_w / 2
        child_cxs = [offset + i * (box_w + gap_x) for i in range(n)]
        root_bottom = root_y + root_h
        parts.append(
            f'<path d="M{cx:.0f},{root_bottom} L{cx:.0f},{trunk_y}" '
            f'fill="none" stroke="#475569" stroke-width="2"/>'
        )
        if n > 1:
            parts.append(
                f'<path d="M{child_cxs[0]:.0f},{trunk_y} L{child_cxs[-1]:.0f},{trunk_y}" '
                f'fill="none" stroke="#475569" stroke-width="2"/>'
            )
        for i, ccx in enumerate(child_cxs):
            parts.append(
                f'<path d="M{ccx:.0f},{trunk_y} L{ccx:.0f},{children_y}" '
                f'fill="none" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>'
            )
            parts.append(
                _box(ccx - box_w / 2, children_y, box_w, box_h,
                     f"{i + 1}. {child_titles[i]}", "#ffffff", "#94a3b8", is_title=False)
            )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def diagram_path_for(root_md: Path) -> Path:
    """Return the diagram path for a root document (``<slug>.flow.svg``)."""
    return root_md.with_name(root_md.stem + ".flow.svg")


def generate_diagram(root_md: Path, overwrite: bool = False) -> tuple[Path, bool]:
    """Generate the top-2-hierarchy diagram for a root document.

    Returns (path, created) where `created` is False if it already existed and
    `overwrite` was not set.
    """
    out_path = diagram_path_for(root_md)
    if out_path.exists() and not overwrite:
        return out_path, False
    markdown = root_md.read_text(encoding="utf-8")
    title = _read_title(markdown) or root_md.stem
    children = _children_from_links(markdown)
    out_path.write_text(build_diagram_svg(title, children), encoding="utf-8")
    return out_path, True


def generate_missing_diagrams(out_dir: Path) -> list[Path]:
    """Create diagrams for every root document that doesn't have one yet."""
    out_dir = Path(out_dir)
    created: list[Path] = []
    if not out_dir.is_dir():
        return created
    for root_md in sorted(out_dir.glob("*.md")):
        path, was_created = generate_diagram(root_md, overwrite=False)
        if was_created:
            created.append(path)
    return created


# --- steps.txt parsing & extended diagrams ---


def _read_text_auto(path: Path) -> str:
    """Read a text file, handling UTF-16 (common on Windows) and UTF-8."""
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8")


def parse_steps_log(path: Path) -> list[tuple[int, str]]:
    """Parse a steps log file into (depth, title) pairs."""
    entries: list[tuple[int, str]] = []
    for line in _read_text_auto(path).splitlines():
        match = _STEPS_LOG_RE.match(line.strip())
        if match:
            entries.append((int(match.group(1)), match.group(2).strip()))
    return entries


def main_phases_from_steps_log(entries: list[tuple[int, str]]) -> list[str]:
    """Return ordered main phase titles (bold ** markers at depth 1)."""
    phases: list[str] = []
    for depth, title in entries:
        if depth != 1:
            continue
        phase = _MAIN_PHASE_RE.search(title)
        if phase:
            phases.append(phase.group(1).strip())
    return phases


def substeps_by_phase_from_steps_log(
    entries: list[tuple[int, str]],
) -> dict[str, list[str]]:
    """Map each main phase to its depth-2 child step titles."""
    phases = main_phases_from_steps_log(entries)
    if not phases:
        return {}

    # Index of each main phase (depth-1 bold entry) in the log.
    phase_indices: list[int] = []
    for i, (depth, title) in enumerate(entries):
        if depth == 1 and _MAIN_PHASE_RE.search(title):
            phase_indices.append(i)

    result: dict[str, list[str]] = {p: [] for p in phases}
    for pi, phase in enumerate(phases):
        start = phase_indices[pi] + 1
        end = phase_indices[pi + 1] if pi + 1 < len(phase_indices) else len(entries)
        for depth, title in entries[start:end]:
            if depth == 1:
                break  # next sibling at depth 1
            if depth == 2:
                clean = _MAIN_PHASE_RE.sub(r"\1", title).strip()
                result[phase].append(clean)
    return result


def main_phases_from_markdown(markdown: str) -> list[str]:
    """Extract numbered main phases from the '## Steps' section."""
    section = _STEPS_SECTION_RE.search(markdown)
    if not section:
        return []
    return [m.strip() for m in _NUMBERED_STEP_RE.findall(section.group(1))]


def build_pipeline_svg(title: str, phases: list[str]) -> str:
    """Vertical sequential pipeline for main workflow phases."""
    margin = 48
    box_w, box_h = 420, 52
    gap_y = 36
    root_h = 64
    n = len(phases)

    canvas_w = box_w + 2 * margin
    canvas_h = margin + root_h + gap_y + n * (box_h + gap_y) + margin
    cx = canvas_w / 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" '
        'refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L8,3 L0,6 Z" fill="#475569"/></marker></defs>',
        f'<rect x="0" y="0" width="{canvas_w}" height="{canvas_h}" fill="#f8fafc"/>',
        f'<text x="{margin}" y="{margin - 8}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="13" fill="#64748b">Workflow pipeline ({n} phases)</text>',
        _box(cx - box_w / 2, margin, box_w, root_h, title, "#e0e7ff", "#6366f1", is_title=True),
    ]

    y = margin + root_h + gap_y
    prev_bottom = margin + root_h
    for i, phase in enumerate(phases):
        parts.append(
            f'<path d="M{cx},{prev_bottom} L{cx},{y}" fill="none" stroke="#475569" '
            f'stroke-width="2" marker-end="url(#arrow)"/>'
        )
        parts.append(
            _box(cx - box_w / 2, y, box_w, box_h, f"{i + 1}. {phase}",
                 "#ffffff", "#94a3b8", is_title=False)
        )
        prev_bottom = y + box_h
        y += box_h + gap_y

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def build_phase_hierarchy_svg(
    title: str,
    phases: list[str],
    substeps: dict[str, list[str]],
    *,
    max_substeps: int = 4,
) -> str:
    """Root + main phases in a grid, each with depth-2 substeps below."""
    margin = 40
    phase_w, phase_h = 200, 72
    sub_w, sub_h = 180, 44
    gap_x, gap_y = 24, 16
    cols = min(4, max(1, len(phases)))
    rows = (len(phases) + cols - 1) // cols

    root_w, root_h = 480, 64
    block_h = phase_h + gap_y + min(max_substeps, 1) * (sub_h + 8) + 28

    grid_w = cols * phase_w + (cols - 1) * gap_x
    canvas_w = max(grid_w, root_w) + 2 * margin
    canvas_h = margin + root_h + 48 + rows * block_h + margin
    cx = canvas_w / 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" '
        f'height="{canvas_h:.0f}" viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" '
        'refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L8,3 L0,6 Z" fill="#475569"/></marker></defs>',
        f'<rect x="0" y="0" width="{canvas_w:.0f}" height="{canvas_h:.0f}" fill="#f8fafc"/>',
        _box(cx - root_w / 2, margin, root_w, root_h, title, "#e0e7ff", "#6366f1", is_title=True),
    ]

    grid_x0 = margin + (canvas_w - 2 * margin - grid_w) / 2
    grid_y0 = margin + root_h + 48

    for i, phase in enumerate(phases):
        col, row = i % cols, i // cols
        px = grid_x0 + col * (phase_w + gap_x)
        py = grid_y0 + row * block_h

        parts.append(_box(px, py, phase_w, phase_h, f"{i + 1}. {phase}",
                          "#fef3c7", "#f59e0b", is_title=False))

        children = substeps.get(phase, [])[:max_substeps]
        extra = len(substeps.get(phase, [])) - len(children)
        sy = py + phase_h + gap_y
        for j, sub in enumerate(children):
            parts.append(
                f'<path d="M{px + phase_w / 2:.0f},{py + phase_h} '
                f'L{px + phase_w / 2:.0f},{sy + j * (sub_h + 8)}" '
                f'fill="none" stroke="#cbd5e1" stroke-width="1.5"/>'
            )
            parts.append(
                _box(px + (phase_w - sub_w) / 2, sy + j * (sub_h + 8), sub_w, sub_h,
                     sub, "#ffffff", "#cbd5e1", is_title=False)
            )
        if extra > 0:
            ty = sy + len(children) * (sub_h + 8) + 12
            parts.append(
                f'<text x="{px + phase_w / 2:.0f}" y="{ty:.0f}" text-anchor="middle" '
                f'font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" '
                f'fill="#64748b">+ {extra} more substeps</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def pipeline_path_for(root_md: Path) -> Path:
    return root_md.with_name(root_md.stem + ".pipeline.flow.svg")


def hierarchy_path_for(root_md: Path) -> Path:
    return root_md.with_name(root_md.stem + ".hierarchy.flow.svg")


def generate_extended_diagrams(
    root_md: Path,
    steps_log: Path | None = None,
    *,
    overwrite: bool = True,
) -> dict[str, Path]:
    """Generate pipeline + hierarchy diagrams from steps log and/or markdown."""
    markdown = root_md.read_text(encoding="utf-8")
    title = _read_title(markdown) or root_md.stem

    phases: list[str] = []
    substeps: dict[str, list[str]] = {}

    if steps_log and steps_log.is_file():
        entries = parse_steps_log(steps_log)
        phases = main_phases_from_steps_log(entries)
        substeps = substeps_by_phase_from_steps_log(entries)

    if not phases:
        phases = main_phases_from_markdown(markdown)

    paths: dict[str, Path] = {}
    if phases:
        pipeline_path = pipeline_path_for(root_md)
        if overwrite or not pipeline_path.exists():
            pipeline_path.write_text(build_pipeline_svg(title, phases), encoding="utf-8")
        paths["pipeline"] = pipeline_path

        hierarchy_path = hierarchy_path_for(root_md)
        if overwrite or not hierarchy_path.exists():
            hierarchy_path.write_text(
                build_phase_hierarchy_svg(title, phases, substeps), encoding="utf-8"
            )
        paths["hierarchy"] = hierarchy_path

    return paths
