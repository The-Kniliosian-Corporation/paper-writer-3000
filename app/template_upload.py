import io
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from . import git_ops, manifest

_INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
_COMMENT_RE = re.compile(r"(?<!\\)%.*$")
_ABSTRACT_RE = re.compile(r"\\begin\{abstract\}")
_TITLE_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _find_main_tex(tex_contents: dict[str, str]) -> str:
    candidates = [name for name, content in tex_contents.items() if "\\begin{document}" in content]
    if not candidates:
        raise ValueError(
            "No .tex file with \\begin{document} was found in the uploaded archive -- "
            "it must contain the main LaTeX file."
        )
    if len(candidates) > 1:
        raise ValueError(
            "Multiple .tex files contain \\begin{document}: "
            f"{', '.join(candidates)}. Upload a template with exactly one main file."
        )
    return candidates[0]


def _parse_sections(main_content: str) -> tuple[list[str], bool]:
    doc_start = main_content.find("\\begin{document}")
    doc_end = main_content.find("\\end{document}")
    body = main_content[doc_start:] if doc_end == -1 else main_content[doc_start:doc_end]

    sections = []
    for line in body.splitlines():
        clean_line = _COMMENT_RE.sub("", line)
        for m in _INPUT_RE.finditer(clean_line):
            name = m.group(1).strip()
            if name.endswith(".tex"):
                name = name[:-4]
            sections.append(name)

    has_abstract = bool(_ABSTRACT_RE.search(main_content))
    return sections, has_abstract


def humanize(section_name: str) -> str:
    """'3_StudyDesign' -> 'Study Design', 'sec_intro' -> 'Sec Intro', for the
    scaffolded rough draft headings."""
    name = re.sub(r"^\d+[_\-]?", "", section_name)
    name = name.replace("_", " ").replace("-", " ")
    name = _TITLE_SPLIT_RE.sub(" ", name)
    words = [w.capitalize() if w.islower() else w for w in name.split()]
    return " ".join(words).strip() or section_name


def scaffold_draft(paths, sections: list[str]) -> None:
    """Write a heading-per-section skeleton into paper.md, but only if it's
    currently empty -- never overwrite an existing rough draft. Shared by
    template uploads (replacing an existing project's template) and
    projects.create_project (a brand-new project's first draft)."""
    if paths.paper_md.exists() and paths.paper_md.read_text(encoding="utf-8").strip():
        return
    skeleton = "\n\n\n".join(f"# {humanize(name)}" for name in sections) + "\n\n\n"
    paths.paper_md.write_text(skeleton, encoding="utf-8")


def install(paths, zip_bytes: bytes, filename: str) -> dict:
    """Replace a project's manuscript/ with the contents of an uploaded LaTeX
    template zip, auto-detecting its main file and section files, and
    re-baseline the template-baseline tag so generate.py's section
    instructions come from the new template. Returns the new manifest plus
    the commit sha."""
    buf = io.BytesIO(zip_bytes)
    if not zipfile.is_zipfile(buf):
        raise ValueError(f"'{filename}' is not a valid .zip archive.")

    with zipfile.ZipFile(buf) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/") and not n.startswith("__MACOSX/")]
        if not names:
            raise ValueError("The uploaded zip archive is empty.")

        tex_contents = {
            n: zf.read(n).decode("utf-8", errors="replace") for n in names if n.lower().endswith(".tex")
        }
        if not tex_contents:
            raise ValueError("No .tex files found in the uploaded archive.")

        main_path = _find_main_tex(tex_contents)
        sections, has_abstract = _parse_sections(tex_contents[main_path])
        if not sections:
            raise ValueError(
                f"Could not find any \\input{{...}}/\\include{{...}} section files in {main_path}'s "
                "document body -- the template must split its sections into separate files."
            )

        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            main_dir = (Path(tmp) / main_path).parent

            missing = [f"{s}.tex" for s in sections if not (main_dir / f"{s}.tex").exists()]
            if missing:
                raise ValueError(
                    f"Section file(s) referenced by \\input/\\include but not found in the archive: "
                    f"{', '.join(missing)}"
                )

            if paths.manuscript_dir.exists():
                shutil.rmtree(paths.manuscript_dir)
            shutil.copytree(main_dir, paths.manuscript_dir)

    main_name = Path(main_path).stem
    new_manifest = {"main_file": main_name, "sections": sections, "has_abstract": has_abstract}
    manifest.save(paths, new_manifest)
    scaffold_draft(paths, sections)

    try:
        sha = git_ops.commit(paths.root, ["manuscript", "paper.md"], f"template: install {main_name}")
        if sha is not None:
            git_ops.tag_template_baseline(paths.root)
    except git_ops.GitError as exc:
        raise ValueError(f"Template files were written, but committing failed: {exc}") from exc

    return {**new_manifest, "sha": sha}
