"""Export a generated Markdown tree to a single PDF guide."""

import re
from pathlib import Path

import markdown
from xhtml2pdf import pisa

_DETAILED_STEPS_RE = re.compile(
    r"\n*##\s+Detailed Steps\s*$.*\Z",
    flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_LINK_RE = re.compile(r"^- \[(.*?)\]\((.*?\.md)\)\s*$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)


def _strip_detailed_steps(text: str) -> str:
    return _DETAILED_STEPS_RE.sub("", text).rstrip()


def _child_links(text: str) -> list[tuple[str, str]]:
    section = re.search(
        r"^##\s+Detailed Steps\s*$(.*?)\Z",
        text,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not section:
        return []
    return _LINK_RE.findall(section.group(1))


def _heading_title(text: str) -> str:
    match = _H1_RE.search(text)
    return match.group(1).strip() if match else ""


def collect_documents(root_md: Path) -> list[tuple[int, Path, str, str]]:
    """Walk the tree via Detailed Steps links; return (depth, path, body, title)."""
    root_md = root_md.resolve()
    out: list[tuple[int, Path, str, str]] = []
    seen: set[Path] = set()

    def visit(md_path: Path, depth: int) -> None:
        resolved = md_path.resolve()
        if resolved in seen or not resolved.is_file():
            return
        seen.add(resolved)

        raw = md_path.read_text(encoding="utf-8")
        body = _strip_detailed_steps(raw)
        title = _heading_title(body) or md_path.stem.replace("-", " ").title()
        out.append((depth, resolved, body, title))

        for _, rel in _child_links(raw):
            child = (md_path.parent / rel).resolve()
            visit(child, depth + 1)

    visit(root_md, 0)
    return out


def _html_shell(title: str, toc_html: str, body_html: str, *, doc_count: int) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>{_esc_html(title)}</title>
<style>
  @page {{
    size: A4;
    margin: 2cm 2.2cm;
    @frame footer {{
      -pdf-frame-content: footerContent;
      bottom: 0.8cm;
      margin-left: 2.2cm;
      margin-right: 2.2cm;
      height: 1cm;
    }}
  }}
  body {{
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #1e293b;
  }}
  .cover {{
    text-align: center;
    padding-top: 6cm;
  }}
  .cover h1 {{
    font-size: 22pt;
    color: #0f172a;
    margin-bottom: 0.6em;
    page-break-before: avoid;
  }}
  .cover p {{
    font-size: 12pt;
    color: #64748b;
  }}
  .toc {{
    page-break-after: always;
  }}
  .toc h2 {{
    font-size: 18pt;
    color: #0f172a;
    border-bottom: 2px solid #6366f1;
    padding-bottom: 0.3em;
  }}
  .toc ol {{
    line-height: 1.4;
    font-size: 9pt;
  }}
  .toc li {{
    margin-bottom: 0.15em;
  }}
  .section {{
    page-break-before: always;
  }}
  .section.depth-0 {{
    page-break-before: avoid;
  }}
  h1 {{ font-size: 18pt; color: #0f172a; margin-top: 0; }}
  h2 {{ font-size: 14pt; color: #334155; margin-top: 1em; }}
  h3 {{ font-size: 12pt; color: #475569; }}
  p {{ margin: 0.5em 0; }}
  ul, ol {{ margin: 0.4em 0 0.8em 1.2em; }}
  li {{ margin-bottom: 0.25em; }}
  code {{
    font-family: Courier, monospace;
    font-size: 9.5pt;
    background: #f1f5f9;
    padding: 0.1em 0.25em;
  }}
  pre {{
    font-family: Courier, monospace;
    font-size: 9pt;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 0.6em;
    white-space: pre-wrap;
    word-wrap: break-word;
  }}
  a {{ color: #4f46e5; text-decoration: none; }}
  strong {{ color: #0f172a; }}
  .depth-badge {{
    font-size: 9pt;
    color: #64748b;
    margin-bottom: 0.5em;
  }}
</style>
</head>
<body>
<div class="cover">
  <h1>{_esc_html(title)}</h1>
  <p>Step-by-step guide</p>
  <p>{doc_count} sections</p>
</div>

<div class="toc">
  <h2>Table of Contents</h2>
  {toc_html}
</div>

{body_html}

<div id="footerContent">
  <pdf:pagenumber/>
</div>
</body>
</html>"""


def _esc_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_toc_html(docs: list[tuple[int, Path, str, str]]) -> str:
    items = []
    for depth, _, _, title in docs:
        indent = "&nbsp;" * (depth * 4)
        items.append(f"<li>{indent}{_esc_html(title)}</li>")
    return f"<ol>{''.join(items)}</ol>"


def _build_body_html(docs: list[tuple[int, Path, str, str]]) -> str:
    md_ext = ["fenced_code", "tables", "nl2br", "sane_lists"]
    parts: list[str] = []

    for depth, path, body, title in docs:
        section_class = f"section depth-{depth}"
        converted = markdown.markdown(body, extensions=md_ext)
        parts.append(
            f'<div class="{section_class}">'
            f'<div class="depth-badge">Section {len(parts)} · depth {depth}</div>'
            f"{converted}"
            f"</div>"
        )
    return "".join(parts)


def export_tree_to_pdf(root_md: Path, pdf_path: Path | None = None) -> Path:
    """Collect a Markdown tree and write a single PDF guide."""
    root_md = Path(root_md).resolve()
    if not root_md.is_file():
        raise FileNotFoundError(f"Root document not found: {root_md}")

    docs = collect_documents(root_md)
    if not docs:
        raise ValueError(f"No documents found starting from {root_md}")

    title = docs[0][3] if docs else root_md.stem
    pdf_path = Path(pdf_path) if pdf_path else root_md.with_suffix(".pdf")

    toc_html = _build_toc_html(docs)
    body_html = _build_body_html(docs)
    html = _html_shell(title, toc_html, body_html, doc_count=len(docs))

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with pdf_path.open("wb") as dest:
        status = pisa.CreatePDF(html, dest=dest, encoding="utf-8")
    if status.err:
        raise RuntimeError(f"PDF generation failed with {status.err} error(s)")

    return pdf_path
