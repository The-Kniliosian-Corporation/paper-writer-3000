from openai import OpenAI

from .config import CHAT_MODEL, MANUSCRIPT_DIR, OPENAI_API_KEY, PAPER_MD, SECTION_FILES

SYSTEM_PROMPT = """You are a research-writing consultant helping the author think through the direction, \
structure, and framing of a Software Engineering research paper. You can see their current rough notes and \
the latest generated LaTeX paper (if any) below, for context.

You have live web search -- use it to find related work, check whether a claim already has a citation in \
the literature, or verify facts. When you cite a paper, name it and give the URL you found it at, so the \
author can look it up themselves; never state a paper exists or supports a claim without having actually \
searched for it.

You are advisory only: discuss ideas, suggest direction, point out gaps or weak arguments, help them think -- \
but you cannot edit their files. If they want a change made, tell them to update paper.md and hit Generate."""


def _read_context() -> str:
    notes = PAPER_MD.read_text(encoding="utf-8").strip() or "(empty)"
    sections = []
    for name in SECTION_FILES:
        path = MANUSCRIPT_DIR / f"{name}.tex"
        if path.exists():
            sections.append(f"### {name}.tex\n{path.read_text(encoding='utf-8').strip()}")
    generated = "\n\n".join(sections) or "(not generated yet)"
    return f"## Current rough notes (paper.md)\n{notes}\n\n## Current generated paper\n{generated}"


def chat(message: str, history: list[dict], model: str | None = None) -> str:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set -- copy .env.example to .env and fill it in.")

    client = OpenAI(api_key=OPENAI_API_KEY)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + _read_context()},
        *history,
        {"role": "user", "content": message},
    ]
    response = client.responses.create(
        model=model or CHAT_MODEL,
        input=messages,
        tools=[{"type": "web_search"}],
    )
    return response.output_text
