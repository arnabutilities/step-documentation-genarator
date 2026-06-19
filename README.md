# Recursive Markdown Agent

An AI agent that turns a single **topic** into a tree of detailed Markdown documents.

Given a topic, the agent:

1. Generates a detailed Markdown file describing the topic.
2. Scans that file for any **steps** it mentions.
3. For every step found, it generates a new Markdown file detailing that step.
4. Repeats the process **recursively** for each generated file until there are no more steps to expand (or a depth/size limit is reached).

The result is a folder of linked Markdown files that drill down from a high-level overview into fine-grained, step-by-step detail.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Step-by-Step Build Guide](#step-by-step-build-guide)
  - [Step 1 — Project Setup](#step-1--project-setup)
  - [Step 2 — Configure the LLM Client](#step-2--configure-the-llm-client)
  - [Step 3 — Generate a Markdown File from a Topic](#step-3--generate-a-markdown-file-from-a-topic)
  - [Step 4 — Extract Steps from the Generated File](#step-4--extract-steps-from-the-generated-file)
  - [Step 5 — Recurse Into Each Step](#step-5--recurse-into-each-step)
  - [Step 6 — Add Safeguards (Depth, Limits, Dedup)](#step-6--add-safeguards-depth-limits-dedup)
  - [Step 7 — Wire Up the CLI](#step-7--wire-up-the-cli)
- [Running the Agent](#running-the-agent)
- [Output Structure](#output-structure)
- [Configuration](#configuration)
- [Extending the Agent](#extending-the-agent)
- [Troubleshooting](#troubleshooting)

---

## How It Works

```
topic ──▶ [Generate MD] ──▶ topic.md
                               │
                               ├─ extract steps ──▶ [step 1, step 2, step 3, ...]
                               │
                               ▼
            for each step ──▶ [Generate MD] ──▶ step-N.md
                               │
                               └─ extract steps ──▶ recurse... (until no steps or max depth)
```

The agent is a recursive function. Each call:

1. Asks the LLM to write a detailed Markdown document for the current topic/step.
2. Saves the document to disk.
3. Parses the document to find a list of actionable steps.
4. Calls itself once per discovered step, with that step as the new topic.

Recursion stops when a document contains **no steps**, or when a **maximum depth** or **node budget** is reached. These limits are essential — without them, an LLM can keep inventing sub-steps forever.

---

## Architecture

| Component | Responsibility |
|-----------|----------------|
| **LLM Client** | Sends prompts to a model and returns text. |
| **Generator** | Builds the prompt and produces a Markdown document for a topic/step. |
| **Step Extractor** | Reads a document and returns a structured list of steps. |
| **Recursion Engine** | Orchestrates generation → extraction → recursion with safeguards. |
| **File Writer** | Saves documents to a structured output folder and links them. |
| **CLI** | Entry point that accepts the topic and configuration. |

---

## Prerequisites

- **Python 3.10+** (the reference implementation uses Python; the same design works in any language).
- An **LLM API key** (e.g. OpenAI, Anthropic, or a local model via Ollama).
- Basic familiarity with the terminal.

---

## Step-by-Step Build Guide

### Step 1 — Project Setup

Create the project structure:

```bash
mkdir recursive-markdown-agent && cd recursive-markdown-agent
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install openai python-slugify python-dotenv
```

Create a `requirements.txt`:

```text
openai>=1.0.0
python-slugify>=8.0.0
python-dotenv>=1.0.0
```

Provide your API key. Copy `.env.example` to `.env` and fill it in:

```text
OPENAI_API_KEY=sk-your-key-here
AGENT_MODEL=gpt-4o-mini
```

The agent loads `.env` automatically at startup (via `python-dotenv`). Alternatively,
set it as a system environment variable:

```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY = "sk-..."
# macOS / Linux
# export OPENAI_API_KEY="sk-..."
```

---

### Step 2 — Configure the LLM Client

Create `agent/llm.py`. This thin wrapper isolates the model so you can swap providers later. The client is created **lazily** so the key is only required when an actual LLM call is made (this keeps `--help` and unit tests runnable without a key).

```python
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.environ.get("AGENT_MODEL", "gpt-4o-mini")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Create the OpenAI client lazily so the key is only needed at call time."""
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your "
                "key, or set the environment variable before running."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def complete(system: str, user: str) -> str:
    """Send a prompt to the LLM and return the text response."""
    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()
```

---

### Step 3 — Generate a Markdown File from a Topic

Create `agent/generator.py`. The key is to instruct the model to **always express actionable parts as a numbered "Steps" section**, so they are easy to extract later.

```python
from agent.llm import complete

SYSTEM_PROMPT = """You are a technical writer.
Write a clear, detailed Markdown document for the given topic.
Rules:
- Start with an H1 title.
- Include a short overview paragraph.
- If the topic involves a process, include a section titled '## Steps'
  containing a numbered list. Each list item must be a concise, self-contained
  action (one step per line).
- Do not nest sub-steps inside a single list item; keep each step atomic.
- If the topic is purely conceptual with no process, omit the Steps section.
"""


def generate_markdown(topic: str) -> str:
    """Produce a detailed Markdown document for a topic or step."""
    user_prompt = f"Topic: {topic}\n\nWrite the Markdown document now."
    return complete(SYSTEM_PROMPT, user_prompt)
```

---

### Step 4 — Extract Steps from the Generated File

Create `agent/extractor.py`. It finds the `## Steps` section and pulls each numbered item. Using a strict output contract (a `## Steps` numbered list) keeps parsing deterministic and avoids a second LLM call.

```python
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
```

> **Tip:** If you prefer maximum flexibility over determinism, you can ask the LLM to return the steps as JSON instead of parsing Markdown. The regex approach above is cheaper and faster.

---

### Step 5 — Recurse Into Each Step

Create `agent/recursion.py`. This is the heart of the agent: generate → save → extract → recurse.

```python
from pathlib import Path
from slugify import slugify

from agent.generator import generate_markdown
from agent.extractor import extract_steps


def expand(topic: str, out_dir: Path, depth: int, config: dict, state: dict) -> Path | None:
    """Recursively generate a Markdown tree for `topic`."""
    # --- Safeguards (see Step 6) ---
    if depth > config["max_depth"]:
        return None
    if state["count"] >= config["max_nodes"]:
        return None
    key = slugify(topic)
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
```

---

### Step 6 — Add Safeguards (Depth, Limits, Dedup)

Recursion against an LLM **must** be bounded. The `config` and `state` objects above enforce three guards:

- **`max_depth`** — how many levels deep the agent may drill (e.g. `3`).
- **`max_nodes`** — a hard cap on total documents generated (e.g. `50`), protecting your budget.
- **`seen` set** — prevents the agent from re-expanding a step it already covered, stopping loops where the model keeps repeating a step.

These three together guarantee the process **terminates**.

---

### Step 7 — Wire Up the CLI

Create `agent/main.py` as the entry point.

```python
import argparse
from pathlib import Path

from agent.recursion import expand


def main():
    parser = argparse.ArgumentParser(description="Recursive Markdown Agent")
    parser.add_argument("topic", help="The topic to expand into a Markdown tree")
    parser.add_argument("--out", default="output", help="Output directory")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=50)
    args = parser.parse_args()

    config = {"max_depth": args.max_depth, "max_nodes": args.max_nodes}
    state = {"seen": set(), "count": 0}

    root = expand(args.topic, Path(args.out), depth=0, config=config, state=state)
    print(f"\nDone. Generated {state['count']} document(s).")
    print(f"Root document: {root}")


if __name__ == "__main__":
    main()
```

Add an empty `agent/__init__.py` so the package imports correctly.

---

## Running the Agent

```bash
python -m agent.main "How to deploy a web app to production" --max-depth 2 --max-nodes 20
```

Example console output:

```
• [0] How to deploy a web app to production
  • [1] Provision a server
  • [1] Configure the database
    • [2] Create the database schema
  • [1] Set up CI/CD
```

---

## Output Structure

The agent mirrors the recursion tree on disk. Each document links to its children:

```
output/
├── how-to-deploy-a-web-app-to-production.md
└── how-to-deploy-a-web-app-to-production/
    ├── provision-a-server.md
    ├── configure-the-database.md
    └── configure-the-database/
        └── create-the-database-schema.md
```

Open the root `.md` file in any Markdown viewer and follow the **Detailed Steps** links to navigate down the tree.

---

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `topic` | _(required)_ | The starting topic. |
| `--out` | `output` | Output directory for generated files. |
| `--max-depth` | `3` | Maximum recursion depth. |
| `--max-nodes` | `50` | Maximum total documents (budget guard). |
| `AGENT_MODEL` (env) | `gpt-4o-mini` | Model used for generation. |
| `OPENAI_API_KEY` (env) | _(required)_ | Your LLM API key. |

---

## Extending the Agent

- **Swap providers:** Edit only `agent/llm.py` to use Anthropic, Azure, or a local model (Ollama, llama.cpp).
- **JSON step extraction:** Replace the regex in `extractor.py` with a structured LLM call returning a JSON array of steps.
- **Parallelism:** Expand sibling steps concurrently with `asyncio` or a thread pool to speed up large trees (mind rate limits).
- **Caching:** Cache LLM responses by topic hash to make re-runs free and deterministic.
- **Single-file output:** Add a post-processing step that concatenates the tree into one document with nested headings.
- **Quality gate:** Add a review pass where the LLM critiques and refines each document before saving.

---

## Troubleshooting

| Problem | Cause / Fix |
|---------|-------------|
| Recursion never stops | Lower `--max-depth` / `--max-nodes`; confirm the `seen` dedup set is active. |
| No child files generated | The model didn't emit a `## Steps` section — strengthen the system prompt in `generator.py`. |
| Duplicate documents | Slugged topics collide; include the parent path in the slug or key. |
| `KeyError: OPENAI_API_KEY` | Set the environment variable before running. |
| Rate-limit errors | Reduce concurrency, add retries/backoff in `llm.py`, or lower `--max-nodes`. |
