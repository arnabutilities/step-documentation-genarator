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
