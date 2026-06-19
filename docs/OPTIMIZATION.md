# Reducing Token Usage

This guide explains how to lower token consumption (and therefore cost and latency) in the Recursive Markdown Agent. Recommendations are grouped from highest to lowest impact and reference the actual code.

## Where the tokens go

For every node in the tree, the agent makes **one** chat completion call (`agent/recursion.py` -> `generate_markdown` -> `agent/llm.py`). Total tokens are roughly:

```
total_tokens  ≈  number_of_nodes  ×  (system_prompt + topic + output) per call
```

So there are two levers:

1. **Fewer calls** — reduce how many nodes the recursion creates.
2. **Fewer tokens per call** — trim the prompt and cap the output.

---

## 1. Fewer calls (biggest win)

The number of LLM calls equals the number of documents generated. The recursion fan-out grows fast, so controlling it matters most.

### 1.1 Lower `--max-depth` and `--max-nodes`

These are the hard guards in `expand()`. `max_nodes` is a direct cap on the number of API calls.

```bash
python -m agent.main "Your topic" --max-depth 2 --max-nodes 15
```

A shallow, narrow tree can cost an order of magnitude less than a deep, wide one.

### 1.2 Limit fan-out per node

Today every extracted step becomes a child. Cap how many children each node expands so a 12-step list doesn't trigger 12 calls. Suggested change in `agent/recursion.py`:

```python
max_children = config.get("max_children", 5)
for step in steps[:max_children]:
    ...
```

### 1.3 Deduplicate aggressively

The `seen` set already prevents regenerating an identical slug. To catch near-duplicates (e.g. "Set up database" vs "Setting up the database"), normalize topics before hashing (lowercase, strip stopwords) so semantically equal steps collapse into one call.

### 1.4 Reuse existing output (built in)

The agent is **resumable**: if a document already exists in the output directory, `expand()` reads it from disk instead of calling the API (see the "Resuming" section in the README). Re-running the same topic therefore costs nothing for already-generated nodes, and raising `--max-depth` / `--max-nodes` continues from where a previous run stopped. Use `--fresh` to force regeneration.

For an even stronger cache that survives renames or different output directories, hash `(model, system_prompt, topic)` and store completions in a central cache keyed by that hash.

### 1.5 Prune low-value branches

Add a cheap heuristic (or a tiny classifier call) to decide whether a step is "atomic" and should *not* be expanded — e.g. skip steps shorter than N words or that contain no verb. Fewer branches = fewer calls.

---

## 2. Fewer tokens per call

### 2.1 Cap the output with `max_tokens`

Output tokens are usually the largest and most expensive part of each call, and they are currently unbounded. Add a limit in `agent/llm.py`:

```python
response = _get_client().chat.completions.create(
    model=MODEL,
    messages=[...],
    temperature=0.4,
    max_tokens=600,   # cap document length
)
```

Set this to the smallest value that still produces useful documents.

### 2.2 Trim and reuse the system prompt

The system prompt in `agent/generator.py` is sent on **every** call. Every word there is multiplied by the number of nodes. Keep it terse:

- Remove redundant phrasing; keep only the rules that change the output.
- Move long, static instructions into as few tokens as possible.

> Tip: With providers that support **prompt caching**, a stable, unchanging system prompt can be cached server-side so repeated calls are billed at a reduced rate. Keeping the system prompt byte-for-byte identical across calls (which this agent already does) is what makes that caching effective.

### 2.3 Ask for terser documents

Instruct the model to be concise (e.g. "Keep each document under ~200 words; prefer short bullet steps"). Shorter target output directly lowers output tokens — the dominant cost.

### 2.4 Shorten step text used as child topics

Child topics are the full step strings (e.g. "Measure out the coffee beans: use a scale to weigh about 1 to 2 tablespoons..."). These long strings become both the next prompt's topic **and** the slugged filename. Summarize each step to a short title before recursing to shrink the next prompt:

```python
# before recursing, compress the step to a short title
topic_for_child = step.split(":")[0][:80]
```

---

## 3. Cheaper tokens

### 3.1 Use a smaller model

`AGENT_MODEL` defaults to `gpt-4o-mini`. For routine documentation, a smaller/cheaper model is usually sufficient. Override it without code changes:

```text
# .env
AGENT_MODEL=gpt-4o-mini
```

### 3.2 Tiered models by depth

Use a capable model for the root (depth 0) where quality matters most, and a cheaper model for deeper leaf nodes. Pass `depth` into the LLM layer and pick the model accordingly.

---

## 4. Measure what you save

You can't optimize what you don't measure. Log token usage per run by reading the `usage` field the API returns:

```python
resp = _get_client().chat.completions.create(...)
usage = resp.usage  # prompt_tokens, completion_tokens, total_tokens
```

Accumulate these across the run and print a summary (e.g. alongside the existing `Generated N document(s).` line) so you can compare before/after each optimization.

---

## Quick-reference checklist

- [ ] Lower `--max-depth` / `--max-nodes`
- [ ] Cap children per node (`max_children`)
- [ ] Add response caching by `(model, system_prompt, topic)`
- [ ] Set `max_tokens` in `agent/llm.py`
- [ ] Trim the system prompt and request terser output
- [ ] Shorten step strings before recursing
- [ ] Pick the smallest adequate `AGENT_MODEL` (optionally tier by depth)
- [ ] Log `usage` to measure savings
