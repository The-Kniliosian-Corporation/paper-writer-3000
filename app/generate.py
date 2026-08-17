import json
import re

from openai import OpenAI

from . import git_ops, manifest, references
from .config import DEFAULT_MODEL, OPENAI_API_KEY, ROUGH_DOCS_MD

SYSTEM_PROMPT = """You are an academic writing assistant helping a researcher turn a rough draft into a polished, professional Software Engineering research paper section, written in LaTeX, for a SANER-style conference submission.

Rules:
- Write in formal academic English, third person, precise and concise.
- Write nothing that is not stated in, or a direct restatement of, the rough draft. Never invent claims,
  mechanisms, motivations, citations, numbers, dataset details, or results that are not present in the
  draft -- if writing a sentence would require guessing at content the draft doesn't actually contain, stop
  and use a placeholder instead of guessing.
- Where the rough draft is missing something a section needs (e.g. a citation, a concrete number, unfinished content), insert the existing LaTeX placeholder macro instead of making something up: \\citeme for a missing citation, \\fillme for a missing short value, or \\TODO{...} for a longer missing passage. Never invent a citation key (e.g. \\cite{Doe2020}) that isn't backed by an actual entry in the draft, the bibliography, or the "Reference materials the author has collected" list below -- use \\citeme instead. This template does not load natbib, so only use plain \\cite{...} or \\citeme, never \\citet{...} or \\citep{...}.
- If the "Reference materials the author has collected" list below gives a \\cite{key} for a specific paper, use that exact key when discussing that paper -- it is a real, verified bibliography entry, not a guess. Entries in that list with no key are background context only; still use \\citeme if the surrounding text needs a formal citation for them.
- \\citeme, \\fillme, and \\TODO{...} draw colored boxes and cannot appear directly inside a \\section{...}, \\subsection{...}, \\caption{...}, or \\title{...} argument -- hyperref cannot convert a box into PDF bookmark text and compilation will fail. If one of these placeholders is genuinely needed inside such a heading/caption, wrap it as \\texorpdfstring{\\TODO{...}}{plain text fallback} (same for \\fillme/\\citeme); otherwise prefer plain bracketed placeholder text like [State the question] in headings/captions.
- Where the rough draft touches on something but leaves it ambiguous, underspecified, or open to more than
  one reading, do not silently pick an interpretation and write as if it were settled. Write the
  unambiguous part normally and mark the unclear part with \\TODO{explain the ambiguity and what the author
  needs to clarify}, so it stands out and the author resolves it themselves rather than the model guessing.
- Preserve and use the template's existing macros where they fit the content: \\motivation, \\approach, \\results, \\summarybox{title}{body}, \\finding{...}. Do not redefine or remove them.
- The rough draft may contain a marker of the form [figure: <filename>], showing where the author wants an already-uploaded image included. That file lives at 100_Figures/<filename> relative to the LaTeX source. Replace the marker with a proper LaTeX figure environment at that point in the section, e.g.:
  \\begin{figure}[htbp]
      \\centering
      \\includegraphics[width=\\linewidth]{100_Figures/<filename>}
      \\caption{...}
      \\label{fig:<short-label>}
  \\end{figure}
  Write a real caption only if the surrounding draft describes what the figure shows; otherwise use \\fillme for the caption instead of inventing one.
- Match the structure, subsections, and ordering implied by each section's instructions below, but only write real prose for the structural items (subsections, RQs, pipeline components, analysis steps, etc.) that the rough draft actually has content for. Do not extend coverage to sibling items just because the draft covered one of them -- e.g. if the draft describes subject selection but says nothing about tooling or the common analysis steps, write subject selection properly and leave tooling/analysis steps as bare placeholders. For a structural item with no corresponding draft content, keep it to a single \\TODO{...} naming what the author still needs to write (or \\fillme for a short value) -- do not write multiple sentences of plausible-sounding filler to round it out.
- If asked for "front_abstract" or "front_acknowledgement" keys, write plain prose paragraphs only (no \\chapter/\\section heading, no \\begin{abstract}) drawn from the rough draft's "# Abstract"/"# Acknowledgement" notes -- the same placeholder rules (\\TODO, \\fillme, \\citeme) apply if that material is thin or missing.
- Output only the LaTeX body content for each section (starting from \\section{...}), not \\documentclass, \\begin{document}, or any preamble.
- Return ONLY a single JSON object, no prose outside it, no markdown code fences."""

_ABSTRACT_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL)

_FRONT_ABSTRACT_START = "% GENERATED:ABSTRACT:START"
_FRONT_ABSTRACT_END = "% GENERATED:ABSTRACT:END"
_FRONT_ACK_START = "% GENERATED:ACKNOWLEDGEMENT:START"
_FRONT_ACK_END = "% GENERATED:ACKNOWLEDGEMENT:END"

_TITLE_PAGE_ALIASES = {
    "report title": "reporttitle",
    "company name": "companyname",
    "student name": "studentname",
    "student id": "studentid",
    "academic year": "academicyear",
}
_TITLE_PAGE_SECTION_RE = re.compile(r"^#\s*Title Page\s*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^#\s", re.MULTILINE)


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_abstract(main_tex: str) -> str:
    match = _ABSTRACT_RE.search(main_tex)
    return match.group(1) if match else ""


def _has_front_matter_markers(main_tex: str) -> bool:
    return _FRONT_ABSTRACT_START in main_tex and _FRONT_ACK_START in main_tex


def _replace_marked_block(text: str, start_marker: str, end_marker: str, new_body: str) -> str:
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
    replacement = f"{start_marker}\n{new_body}\n{end_marker}"
    return pattern.sub(replacement, text, count=1)


def _build_reference_block(ref_entries: list[dict]) -> str:
    if not ref_entries:
        return ""
    lines = []
    for entry in ref_entries:
        note = entry.get("note", "").strip()
        url = entry.get("url", "")
        key = entry.get("bib_key")
        if key:
            lines.append(f"- \\cite{{{key}}} -- {note} (source: {url})")
        else:
            lines.append(f"- no citation key available -- {note} (source: {url})")
    return "## Reference materials the author has collected\n" + "\n".join(lines) + "\n\n"


def _parse_title_page(notes: str) -> dict[str, str]:
    match = _TITLE_PAGE_SECTION_RE.search(notes)
    if not match:
        return {}
    rest = notes[match.end():]
    next_heading = _NEXT_HEADING_RE.search(rest)
    block = rest[:next_heading.start()] if next_heading else rest

    fields = {}
    for line in block.splitlines():
        line = line.strip().lstrip("-").strip()
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        macro = _TITLE_PAGE_ALIASES.get(label.strip().lower())
        value = value.strip()
        if macro and value:
            fields[macro] = value
    return fields


def _escape_latex(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("_", r"\_")
    )


def _sync_title_page(paths, notes: str) -> str | None:
    """Fill setting_variable.tex's title-page macros (\\reporttitle,
    \\studentname, ...) from paper.md's '# Title Page' bullet list, for
    templates that use that macro-based front matter (currently
    ku_coop_report). Deterministic string substitution -- these are literal
    values the author already typed out, no LLM call needed. Returns the
    written path relative to the project root, or None if there's no such
    section/file or nothing changed."""
    fields = _parse_title_page(notes)
    var_path = paths.manuscript_dir / "setting_variable.tex"
    if not fields or not var_path.exists():
        return None

    text = _read(var_path)
    changed = False
    for macro, value in fields.items():
        pattern = re.compile(r"(\\newcommand\{\\" + macro + r"\}\{)[^}]*(\})")
        text, n = pattern.subn(lambda m: m.group(1) + _escape_latex(value) + m.group(2), text)
        changed = changed or n > 0

    if "studentname" in fields:
        pattern = re.compile(r"(\\newcommand\{\\reportername\}\{)[^}]*(\})")
        text, n = pattern.subn(
            lambda m: m.group(1) + "Mr./Ms.\\ " + _escape_latex(fields["studentname"]) + m.group(2),
            text,
        )
        changed = changed or n > 0

    if not changed:
        return None
    var_path.write_text(text, encoding="utf-8")
    return var_path.relative_to(paths.root).as_posix()


def _build_user_prompt(
    paths,
    section_files: list[str],
    main_file: str,
    has_abstract: bool,
    has_front_matter: bool,
    ref_entries: list[dict],
    notes: str,
) -> str:
    guidance = _read(ROUGH_DOCS_MD).strip()

    section_blocks = []
    for name in section_files:
        instructions = git_ops.show_template_file(paths.root, f"manuscript/{name}.tex").strip()
        section_blocks.append(f"### {name}.tex -- original section instructions\n{instructions}")

    keys = list(section_files)
    if has_abstract:
        keys.insert(0, "abstract")
    if has_front_matter:
        keys += ["front_abstract", "front_acknowledgement"]
    keys_str = ", ".join(f'"{k}"' for k in keys)

    abstract_block = ""
    if has_abstract:
        template_main = git_ops.show_template_file(paths.root, f"manuscript/{main_file}.tex")
        abstract_instructions = _extract_abstract(template_main).strip()
        abstract_block = f"## Abstract -- original instructions\n{abstract_instructions}\n\n"

    front_matter_block = ""
    if has_front_matter:
        front_matter_block = (
            "## Front matter -- original instructions\n"
            "\"front_abstract\": a plain-prose abstract paragraph for the report, drawn from the "
            "rough draft's \"# Abstract\" notes.\n"
            "\"front_acknowledgement\": a plain-prose acknowledgement paragraph, drawn from the "
            "rough draft's \"# Acknowledgement\" notes.\n\n"
        )

    reference_block = _build_reference_block(ref_entries)

    return f"""## Rough draft from the author (the actual content to write from)
{notes}

## Overall paper structure guidance
{guidance}

{reference_block}{abstract_block}{front_matter_block}{chr(10).join(section_blocks)}

## Output format
Return a JSON object with exactly these keys: {keys_str}.
Each value is a string containing the LaTeX content for that section (the abstract value is
plain LaTeX inline content only, without \\begin{{abstract}}/\\end{{abstract}}).
"""


def _write_sections(
    paths,
    data: dict,
    section_files: list[str],
    main_file: str,
    has_abstract: bool,
    has_front_matter: bool,
) -> list[str]:
    written = []
    for name in section_files:
        content = data[name].strip() + "\n"
        path = paths.manuscript_dir / f"{name}.tex"
        path.write_text(content, encoding="utf-8")
        written.append(path.relative_to(paths.root).as_posix())

    main_tex_path = paths.manuscript_dir / f"{main_file}.tex"
    main_tex = _read(main_tex_path)
    main_tex_changed = False

    if has_abstract and "abstract" in data:
        new_abstract = data["abstract"].strip()
        main_tex = _ABSTRACT_RE.sub(
            lambda m: f"\\begin{{abstract}}\n{new_abstract}\n\\end{{abstract}}",
            main_tex,
            count=1,
        )
        main_tex_changed = True

    if has_front_matter:
        main_tex = _replace_marked_block(
            main_tex, _FRONT_ABSTRACT_START, _FRONT_ABSTRACT_END, data["front_abstract"].strip()
        )
        main_tex = _replace_marked_block(
            main_tex, _FRONT_ACK_START, _FRONT_ACK_END, data["front_acknowledgement"].strip()
        )
        main_tex_changed = True

    if main_tex_changed:
        main_tex_path.write_text(main_tex, encoding="utf-8")
        written.append(main_tex_path.relative_to(paths.root).as_posix())

    return written


def generate(paths, model: str | None = None) -> dict:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set -- copy .env.example to .env and fill it in.")

    m = manifest.load(paths)
    section_files, main_file, has_abstract = m["sections"], m["main_file"], m.get("has_abstract", True)

    notes = _read(paths.paper_md).strip()
    if not notes:
        raise ValueError("The rough draft is empty -- write something before generating.")

    main_tex_path = paths.manuscript_dir / f"{main_file}.tex"
    has_front_matter = _has_front_matter_markers(_read(main_tex_path))

    ref_entries = references.sync_bib(paths)

    client = OpenAI(api_key=OPENAI_API_KEY)
    user_prompt = _build_user_prompt(
        paths, section_files, main_file, has_abstract, has_front_matter, ref_entries, notes
    )
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

    required_keys = list(section_files)
    if has_abstract:
        required_keys.append("abstract")
    if has_front_matter:
        required_keys += ["front_abstract", "front_acknowledgement"]
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ValueError(f"Model response is missing keys: {missing}")

    written = _write_sections(paths, data, section_files, main_file, has_abstract, has_front_matter)

    title_page_written = _sync_title_page(paths, notes)
    if title_page_written:
        written.append(title_page_written)

    return {"model": used_model, "written": written}
