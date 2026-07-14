import json
import re

from openai import OpenAI

from . import git_ops
from .config import (
    DEFAULT_MODEL,
    MAIN_TEX,
    MANUSCRIPT_DIR,
    OPENAI_API_KEY,
    PAPER_MD,
    PROJECT_ROOT,
    ROUGH_DOCS_MD,
    SECTION_FILES,
)

SYSTEM_PROMPT = """You are an academic writing assistant helping a researcher turn rough, informal notes into a polished, professional Software Engineering research paper section, written in LaTeX, for a SANER-style conference submission.

Rules:
- Write in formal academic English, third person, precise and concise.
- Base every claim strictly on the rough notes provided. Never invent citations, numbers, dataset details, or results that are not present in the notes.
- Where the rough notes are missing something a section needs (e.g. a citation, a concrete number, unfinished content), insert the existing LaTeX placeholder macro instead of making something up: \\citeme for a missing citation, \\fillme for a missing short value, or \\TODO{...} for a longer missing passage.
- Preserve and use the template's existing macros where they fit the content: \\motivation, \\approach, \\results, \\summarybox{title}{body}, \\finding{...}. Do not redefine or remove them.
- Match the structure, subsections, and ordering implied by each section's instructions below, but replace all instructional/placeholder prose with real written content (or the placeholder macros above when content is genuinely unavailable).
- Output only the LaTeX body content for each section (starting from \\section{...}), not \\documentclass, \\begin{document}, or any preamble.
- Return ONLY a single JSON object, no prose outside it, no markdown code fences."""

_ABSTRACT_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL)


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def _read_template_main() -> str:
    return git_ops.show_template_file("manuscript/0_main.tex")


def _extract_abstract(main_tex: str) -> str:
    match = _ABSTRACT_RE.search(main_tex)
    return match.group(1) if match else ""


def _build_user_prompt() -> str:
    notes = _read(PAPER_MD).strip()
    if not notes:
        raise ValueError("paper.md is empty -- write some rough notes before generating.")
    guidance = _read(ROUGH_DOCS_MD).strip()

    section_blocks = []
    for name in SECTION_FILES:
        instructions = git_ops.show_template_file(f"manuscript/{name}.tex").strip()
        section_blocks.append(f"### {name}.tex -- original section instructions\n{instructions}")

    abstract_instructions = _extract_abstract(_read_template_main()).strip()
    keys = ", ".join(f'"{name}"' for name in ["abstract", *SECTION_FILES])

    return f"""## Rough notes from the author (the actual content to write from)
{notes}

## Overall paper structure guidance
{guidance}

## Abstract -- original instructions
{abstract_instructions}

{chr(10).join(section_blocks)}

## Output format
Return a JSON object with exactly these keys: {keys}.
Each value is a string containing the LaTeX content for that section (the abstract value is
plain LaTeX inline content only, without \\begin{{abstract}}/\\end{{abstract}}).
"""


def _write_sections(data: dict) -> list[str]:
    written = []
    for name in SECTION_FILES:
        content = data[name].strip() + "\n"
        path = MANUSCRIPT_DIR / f"{name}.tex"
        path.write_text(content, encoding="utf-8")
        written.append(path.relative_to(PROJECT_ROOT).as_posix())

    main_tex = _read(MAIN_TEX)
    new_abstract = data["abstract"].strip()
    new_main_tex = _ABSTRACT_RE.sub(
        lambda m: f"\\begin{{abstract}}\n{new_abstract}\n\\end{{abstract}}",
        main_tex,
        count=1,
    )
    MAIN_TEX.write_text(new_main_tex, encoding="utf-8")
    written.append(MAIN_TEX.relative_to(PROJECT_ROOT).as_posix())
    return written


def generate(model: str | None = None) -> dict:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set -- copy .env.example to .env and fill it in.")

    client = OpenAI(api_key=OPENAI_API_KEY)
    user_prompt = _build_user_prompt()
    used_model = model or DEFAULT_MODEL

    response = client.chat.completions.create(
        model=used_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    data = json.loads(response.choices[0].message.content)

    missing = [k for k in ["abstract", *SECTION_FILES] if k not in data]
    if missing:
        raise ValueError(f"Model response is missing keys: {missing}")

    written = _write_sections(data)
    return {"model": used_model, "written": written}


if __name__ == "__main__":
    result = generate()
    print(f"Generated with {result['model']}:")
    for path in result["written"]:
        print(f"  {path}")
