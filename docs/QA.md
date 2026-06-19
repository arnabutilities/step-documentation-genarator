# Q&A

## Q: Can this application be considered an example of an "AI agent"?

Short answer: it's a borderline case. It's most accurately described as an **LLM-powered workflow (pipeline)** with *some* agent-like traits — not a fully autonomous "AI agent" in the strict sense.

### What the app actually does

The core loop in `agent/recursion.py` is:

```python
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
```

So the flow is: **call LLM → parse output → recurse**. The LLM is used purely as a *text generator*. Every decision about control flow (when to recurse, when to stop, what counts as a "step", where to write files) is hardcoded in Python.

### Measuring it against common "AI agent" criteria

| Agent trait | Present here? | Notes |
|---|---|---|
| Uses an LLM / AI model | ✅ Yes | `agent/llm.py` calls the model |
| Goal-directed | ✅ Partial | Goal ("expand topic into a tree") is fixed by you, not chosen |
| Autonomy / runs multi-step without a human | ✅ Yes | Recurses on its own until limits hit |
| Maintains state across steps | ✅ Yes | `state` dict tracks `seen`/`count` |
| Acts on its environment (tools) | ✅ Partial | Writes files, but via fixed code, not model-chosen actions |
| **LLM decides the control flow / next action** | ❌ No | The recursion is a `for` loop, not the model choosing what to do |
| **LLM selects tools dynamically** | ❌ No | There's exactly one "tool" (generate text), always called the same way |
| Adapts/plans/reflects | ❌ No | No planning, no self-correction, no feedback loop |

### The key distinction

The widely-used framing (e.g. Anthropic's *"Building effective agents"*) separates two things:

- **Workflows** — LLMs orchestrated through **predefined code paths**.
- **Agents** — systems where the **LLM dynamically directs its own process and tool use**, deciding what to do next.

By that definition, this app is a **workflow**: it's a deterministic recursive pipeline that happens to call an LLM at each node. The "intelligence" decides the *content*, but the *behavior/structure* is fully programmed.

### What would push it toward a true agent

- Let the LLM **decide** whether a step is worth expanding (instead of always recursing on every list item).
- Give it **multiple tools** (e.g. web search, read existing files, validate output) and let it choose which to call.
- Add a **planning + reflection** loop where it critiques and revises its own output.
- Replace the hardcoded `## Steps` regex extraction with the model deciding the next action via tool/function calling.

### Verdict

It's a legitimate and useful example of **agentic AI plumbing** — autonomous, stateful, multi-step, and acting on the filesystem — and many people would loosely call it an "AI agent." But strictly speaking it's an **LLM orchestration workflow**, because the LLM isn't the one steering the decisions; the Python recursion is. Interestingly, the README itself markets it as an "agent," which is common in practice even when the system is really a workflow.
