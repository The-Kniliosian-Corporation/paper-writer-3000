import json
import re

from openai import OpenAI

from . import git_ops, manifest
from .config import DEFAULT_MODEL, MANUSCRIPT_DIR, OPENAI_API_KEY, PAPER_MD, RESEARCH_DIR, ROUGH_DOCS_MD

SYSTEM_PROMPT = """You are an academic writing assistant helping a researcher turn a rough draft into a polished, professional Software Engineering research paper section, written in LaTeX, for a SANER-style conference submission.

Rules:
- Write in formal academic English, third person, precise and concise.
- Base every claim strictly on the rough draft provided. Never invent citations, numbers, dataset details, or results that are not present in the draft.
- Where the rough draft is missing something a section needs (e.g. a citation, a concrete number, unfinished content), insert the existing LaTeX placeholder macro instead of making something up: \\citeme for a missing citation, \\fillme for a missing short value, or \\TODO{...} for a longer missing passage.
- Preserve and use the template's existing macros where they fit the content: \\motivation, \\approach, \\results, \\summarybox{title}{body}, \\finding{...}. Do not redefine or remove them.
- The rough draft may contain a marker of the form [figure: <filename>], showing where the author wants an already-uploaded image included. That file lives at 100_Figures/<filename> relative to the LaTeX source. Replace the marker with a proper LaTeX figure environment at that point in the section, e.g.:
  \\begin{figure}[htbp]
      \\centering
      \\includegraphics[width=\\linewidth]{100_Figures/<filename>}
      \\caption{...}
      \\label{fig:<short-label>}
  \\end{figure}
  Write a real caption only if the surrounding draft describes what the figure shows; otherwise use \\fillme for the caption instead of inventing one.
- Match the structure, subsections, and ordering implied by each section's instructions below, but replace all instructional/placeholder prose with real written content (or the placeholder macros above when content is genuinely unavailable).
- Output only the LaTeX body content for each section (starting from \\section{...}), not \\documentclass, \\begin{document}, or any preamble.
- Return ONLY a single JSON object, no prose outside it, no markdown code fences."""

_ABSTRACT_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL)


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_abstract(main_tex: str) -> str:
    match = _ABSTRACT_RE.search(main_tex)
    return match.group(1) if match else ""


def _build_user_prompt(section_files: list[str], main_file: str, has_abstract: bool) -> str:
    notes = _read(PAPER_MD).strip()
    if not notes:
        raise ValueError("The rough draft is empty -- write something before generating.")
    guidance = _read(ROUGH_DOCS_MD).strip()

    section_blocks = []
    for name in section_files:
        instructions = git_ops.show_template_file(f"manuscript/{name}.tex").strip()
        section_blocks.append(f"### {name}.tex -- original section instructions\n{instructions}")

    keys = ["abstract", *section_files] if has_abstract else list(section_files)
    keys_str = ", ".join(f'"{k}"' for k in keys)

    abstract_block = ""
    if has_abstract:
        template_main = git_ops.show_template_file(f"manuscript/{main_file}.tex")
        abstract_instructions = _extract_abstract(template_main).strip()
        abstract_block = f"## Abstract -- original instructions\n{abstract_instructions}\n\n"

    return f"""## Rough draft from the author (the actual content to write from)
{notes}

## Overall paper structure guidance
{guidance}

{abstract_block}{chr(10).join(section_blocks)}

## Output format
Return a JSON object with exactly these keys: {keys_str}.
Each value is a string containing the LaTeX content for that section (the abstract value is
plain LaTeX inline content only, without \\begin{{abstract}}/\\end{{abstract}}).
"""


def _write_sections(data: dict, section_files: list[str], main_file: str, has_abstract: bool) -> list[str]:
    written = []
    for name in section_files:
        content = data[name].strip() + "\n"
        path = MANUSCRIPT_DIR / f"{name}.tex"
        path.write_text(content, encoding="utf-8")
        written.append(path.relative_to(RESEARCH_DIR).as_posix())

    main_tex_path = MANUSCRIPT_DIR / f"{main_file}.tex"
    if has_abstract and "abstract" in data:
        main_tex = _read(main_tex_path)
        new_abstract = data["abstract"].strip()
        new_main_tex = _ABSTRACT_RE.sub(
            lambda m: f"\\begin{{abstract}}\n{new_abstract}\n\\end{{abstract}}",
            main_tex,
            count=1,
        )
        main_tex_path.write_text(new_main_tex, encoding="utf-8")
        written.append(main_tex_path.relative_to(RESEARCH_DIR).as_posix())

    return written


def generate(model: str | None = None) -> dict:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set -- copy .env.example to .env and fill it in.")

    m = manifest.load()
    section_files, main_file, has_abstract = m["sections"], m["main_file"], m.get("has_abstract", True)

    client = OpenAI(api_key=OPENAI_API_KEY)
    user_prompt = _build_user_prompt(section_files, main_file, has_abstract)
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

    required_keys = ["abstract", *section_files] if has_abstract else section_files
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ValueError(f"Model response is missing keys: {missing}")

    written = _write_sections(data, section_files, main_file, has_abstract)
    return {"model": used_model, "written": written}


if __name__ == "__main__":
    result = generate()
    print(f"Generated with {result['model']}:")
    for path in result["written"]:
        print(f"  {path}")
