"""Consult panel backend: runs the author's local Claude Code CLI (`claude -p`)
headlessly against a throwaway scratch copy of the project.

Claude Code reads and edits files in that scratch copy with its own tools,
and searches the web. Nothing it does touches the real project: once it
finishes, every editable file it changed (paper.md or one of the manifest's
.tex files) is returned as a proposal. The author still has to review each
one and click Apply in the UI before it is written.
"""

import difflib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import manifest
from . import references as references_module
from .config import CLAUDE_BIN, CLAUDE_CHAT_MODEL, CLAUDE_CHAT_TIMEOUT

# Everything the consultant needs: read and edit its scratch copy, and search
# the web. No Bash/PowerShell, so it can't run anything. `--restricted` also
# drops code-running tools and confines the file tools to the scratch
# directory.
_TOOLS = "Read,Edit,Write,Glob,Grep,WebSearch,WebFetch"

# Manuscript files copied in as read-only context (template macros,
# bibliography), besides the editable ones. IEEEtran.cls etc. are skipped:
# large and irrelevant to the conversation.
_CONTEXT_SUFFIXES = {".tex", ".bib", ".sty"}

_FALLBACK_REPLY = "I've drafted an edit for you to review below."

SYSTEM_PROMPT = """You are acting as a research-writing consultant, helping the author think through the \
direction, structure, and framing of a Software Engineering research paper. The author talks to you \
through the "Consult" chat panel of their paper-writing app, and your final message is shown there, \
rendered as Markdown.

Your working directory is a scratch copy of the author's paper project:
{file_overview}
Read whatever you need before answering -- never guess at what the draft or paper says.

You have live web search -- use it to find related work, check whether a claim already has a citation in \
the literature, or verify facts. When you cite a paper, name it and give the URL you found it at, so the \
author can look it up themselves; never state a paper exists or supports a claim without having actually \
searched for it.

You can propose edits by editing paper.md or the section files listed as editable above, directly in this \
scratch copy. Edits are NEVER applied automatically: when you finish, each editable file you changed is \
shown to the author as a proposed replacement, which they must explicitly review and apply themselves. \
Changes to any other file are thrown away. Only edit when the author asked for a change or clearly wants \
one; otherwise just discuss. When you do edit, say briefly in your reply what you changed in each file and \
why. Refer to files by name only (e.g. paper.md, 1_Introduction.tex), and don't mention the scratch copy \
itself -- to the author, you are simply proposing edits to their paper.

When editing a LaTeX section file (not paper.md itself), write nothing that is not stated in the rough \
draft or your web search findings -- never invent claims, numbers, or results. Where something is \
genuinely missing, use the template's placeholder macros instead: \\citeme for a missing citation, \
\\fillme for a missing short value, \\TODO{{...}} for a longer missing passage. Where the draft leaves \
something ambiguous or underspecified rather than genuinely missing, don't silently pick an \
interpretation -- mark it with \\TODO{{explain the ambiguity}} instead. Never invent a \\cite key: only \
use keys that exist in manuscript/references.bib, otherwise \\citeme. The template does not load \
natbib, so never use \\citet or \\citep."""


def _targets(paths) -> dict[str, tuple[Path, Path]]:
    """Proposal target name -> (real file, path relative to the scratch dir).
    Target names match what the UI's Apply button expects: "paper.md", or a
    manifest file name without its .tex suffix."""
    targets = {"paper.md": (paths.paper_md, Path("paper.md"))}
    for name in manifest.all_files(paths):
        targets[name] = (paths.manuscript_dir / f"{name}.tex", Path("manuscript") / f"{name}.tex")
    return targets


def _read(path: Path) -> str | None:
    # Universal-newline read, so a CRLF original and an LF copy compare equal.
    return path.read_text(encoding="utf-8") if path.exists() else None


def _populate_workspace(paths, workspace: Path, targets) -> tuple[dict[str, str | None], list[str]]:
    """Copy the project into the scratch dir. Returns each target's original
    text (None if the file doesn't exist yet) and the read-only context files
    copied alongside."""
    originals = {}
    editable = set()
    for target, (src, rel) in targets.items():
        originals[target] = _read(src)
        editable.add(rel)
        if src.exists():
            dst = workspace / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)

    context_files = []
    if paths.manuscript_dir.is_dir():
        for src in sorted(paths.manuscript_dir.iterdir()):
            rel = Path("manuscript") / src.name
            if src.is_file() and src.suffix.lower() in _CONTEXT_SUFFIXES and rel not in editable:
                (workspace / "manuscript").mkdir(exist_ok=True)
                shutil.copyfile(src, workspace / rel)
                context_files.append(src.name)

    refs = references_module.load(paths)
    if refs:
        lines = ["# Sources the author has gathered", ""]
        for r in refs:
            key = f" (cite key: {r['bib_key']})" if r.get("bib_key") else ""
            lines.append(f"- {r['url']}{key} -- {r.get('note', '')}")
        (workspace / "references.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return originals, context_files


def _file_overview(paths, targets, originals, context_files, has_refs: bool) -> str:
    sections = [n for n in targets if n != "paper.md"]
    missing = [n for n in sections if originals[n] is None]
    lines = [
        "- paper.md -- the author's rough draft, in their own words (editable)",
        "- manuscript/<name>.tex -- the generated LaTeX paper, one file per section (editable): "
        + ", ".join(f"{n}.tex" for n in sections),
    ]
    if missing:
        lines.append(
            "  (not generated yet, so not present: " + ", ".join(f"{n}.tex" for n in missing) + ")"
        )
    if context_files:
        lines.append(
            "- read-only template/bibliography context in manuscript/: " + ", ".join(context_files)
        )
    if has_refs:
        lines.append("- references.md -- sources the author has gathered, with their notes (read-only)")
    if paths.figures_dir.is_dir():
        figures = sorted(p.name for p in paths.figures_dir.iterdir() if p.is_file())
        if figures:
            lines.append(
                f"- figures the author has uploaded (not copied here, but usable in LaTeX as "
                f"{paths.figures_dir.name}/<file>): " + ", ".join(figures)
            )
    return "\n".join(lines)


def _build_prompt(message: str, history: list[dict]) -> str:
    if not history:
        return message
    parts = ["Our conversation so far, for context:\n"]
    for turn in history:
        who = "Author" if turn.get("role") == "user" else "You"
        parts.append(f"### {who}\n{turn.get('content', '')}\n")
    parts.append(f"### Author -- new message, reply to this\n{message}")
    return "\n".join(parts)


def _diff_summary(old: str | None, new: str) -> str:
    if old is None:
        return f"New file proposed by Claude Code ({len(new.splitlines())} lines)."
    a, b = old.splitlines(), new.splitlines()
    added = removed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return f"Claude Code's proposed version (+{added} / -{removed} lines) -- see its reply above for why."


def _collect_proposals(workspace: Path, targets, originals) -> list[dict]:
    proposals = []
    for target, (_src, rel) in targets.items():
        new = _read(workspace / rel)
        if new is None or new == (originals[target] or ""):
            continue
        proposals.append(
            {"target": target, "content": new, "summary": _diff_summary(originals[target], new)}
        )
    return proposals


def _claude_bin() -> str:
    path = CLAUDE_BIN or shutil.which("claude")
    if not path:
        raise ValueError(
            "Claude Code CLI not found -- install Claude Code and run `claude` once to log in, "
            "or set CLAUDE_BIN in .env to the full path of the claude executable."
        )
    return path


def _run_claude(workspace: Path, system_prompt_file: Path, prompt: str, model: str | None) -> str:
    cmd = [
        _claude_bin(), "-p",
        "--output-format", "json",
        "--restricted",
        "--strict-mcp-config",
        "--tools", _TOOLS,
        "--allowedTools", _TOOLS,
        "--permission-mode", "acceptEdits",
        "--permission-prompts", "none",
        "--no-session-persistence",
        "--append-system-prompt-file", str(system_prompt_file),
    ]
    if model:
        cmd += ["--model", model]

    # Claude Code has no use for the app's OpenAI key; don't hand it over.
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    try:
        # Prompt goes in via stdin (no command-line length/quoting limits), as
        # bytes so Windows text mode doesn't rewrite its newlines to CRLF.
        proc = subprocess.run(
            cmd,
            input=prompt.encode("utf-8"),
            capture_output=True,
            cwd=workspace,
            env=env,
            timeout=CLAUDE_CHAT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Claude Code didn't finish within {CLAUDE_CHAT_TIMEOUT}s.") from exc

    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    data = None
    for candidate in (stdout, *reversed(stdout.splitlines())):
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(data, dict):
        detail = (stderr or stdout)[-800:] or "no output"
        raise RuntimeError(f"Claude Code exited with code {proc.returncode}: {detail}")
    if data.get("is_error"):
        raise RuntimeError(f"Claude Code reported an error: {data.get('result') or data.get('subtype')}")
    return data.get("result") or ""


def chat(paths, message: str, history: list[dict], model: str | None = None) -> dict:
    targets = _targets(paths)
    with tempfile.TemporaryDirectory(prefix="paper-consult-", ignore_cleanup_errors=True) as tmp:
        workspace = Path(tmp) / "project"
        workspace.mkdir()
        originals, context_files = _populate_workspace(paths, workspace, targets)

        overview = _file_overview(
            paths, targets, originals, context_files, (workspace / "references.md").exists()
        )
        system_prompt_file = Path(tmp) / "system_prompt.txt"
        system_prompt_file.write_text(SYSTEM_PROMPT.format(file_overview=overview), encoding="utf-8")

        reply = _run_claude(
            workspace, system_prompt_file, _build_prompt(message, history), model or CLAUDE_CHAT_MODEL
        )
        proposals = _collect_proposals(workspace, targets, originals)

    if not reply.strip() and proposals:
        reply = _FALLBACK_REPLY
    return {"reply": reply, "proposals": proposals}
