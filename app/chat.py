import json

from openai import OpenAI

from . import manifest
from . import references as references_module
from .config import CHAT_MODEL, OPENAI_API_KEY

SYSTEM_PROMPT = """You are a research-writing consultant helping the author think through the direction, \
structure, and framing of a Software Engineering research paper. You can see their current rough draft, \
the latest generated LaTeX paper (if any), and their gathered reference list below, for context.

You have live web search -- use it to find related work, check whether a claim already has a citation in \
the literature, or verify facts. When you cite a paper, name it and give the URL you found it at, so the \
author can look it up themselves; never state a paper exists or supports a claim without having actually \
searched for it.

You can also propose edits to paper.md (the rough draft) or any of the generated LaTeX section files, via \
the propose_edit tool. Edits are NEVER applied automatically -- calling the tool only shows the author a \
proposed replacement for that file, which they must explicitly review and apply themselves. Always pass \
the FULL new content of the target file (not a diff/snippet), and a short summary of what changed and why. \
Only propose an edit when the author asked for one or clearly wants a change made; otherwise just discuss."""


def _propose_edit_tool(paths) -> dict:
    return {
        "type": "function",
        "name": "propose_edit",
        "description": (
            "Propose a full replacement for the content of paper.md or one of the generated LaTeX section "
            "files. This does not write or commit anything -- it only surfaces a proposal for the author to "
            "review and apply themselves."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": ["paper.md", *manifest.all_files(paths)],
                    "description": "Which file this edit applies to.",
                },
                "content": {
                    "type": "string",
                    "description": "The full new content of the file, not a diff or partial snippet.",
                },
                "summary": {
                    "type": "string",
                    "description": "A short, human-readable description of what changed and why.",
                },
            },
            "required": ["target", "content", "summary"],
        },
    }


def _read_context(paths) -> str:
    notes = paths.paper_md.read_text(encoding="utf-8").strip() or "(empty)"

    sections = []
    for name in manifest.all_files(paths):
        path = paths.manuscript_dir / f"{name}.tex"
        if path.exists():
            sections.append(f"### {name}.tex\n{path.read_text(encoding='utf-8').strip()}")
    generated = "\n\n".join(sections) or "(not generated yet)"

    references = references_module.load(paths)
    if references:
        ref_lines = "\n".join(f"- {r['url']} -- {r['note']}" for r in references)
    else:
        ref_lines = "(none gathered yet)"

    return (
        f"## Current rough draft (paper.md)\n{notes}\n\n"
        f"## Current generated paper\n{generated}\n\n"
        f"## Reference sources the author has gathered\n{ref_lines}"
    )


def _extract_proposals(paths, response) -> list[dict]:
    valid_targets = ("paper.md", *manifest.all_files(paths))
    proposals = []
    for item in response.output:
        if getattr(item, "type", None) != "function_call" or item.name != "propose_edit":
            continue
        try:
            args = json.loads(item.arguments)
        except (json.JSONDecodeError, TypeError):
            continue
        if args.get("target") not in valid_targets:
            continue
        proposals.append(
            {
                "target": args["target"],
                "content": args.get("content", ""),
                "summary": args.get("summary", ""),
            }
        )
    return proposals


def chat(paths, message: str, history: list[dict], model: str | None = None) -> dict:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set -- copy .env.example to .env and fill it in.")

    client = OpenAI(api_key=OPENAI_API_KEY)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + _read_context(paths)},
        *history,
        {"role": "user", "content": message},
    ]
    response = client.responses.create(
        model=model or CHAT_MODEL,
        input=messages,
        tools=[{"type": "web_search"}, _propose_edit_tool(paths)],
    )
    reply = response.output_text
    proposals = _extract_proposals(paths, response)
    if not reply.strip() and proposals:
        reply = "I've drafted an edit for you to review below."
    return {"reply": reply, "proposals": proposals}
