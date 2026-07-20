import subprocess
from pathlib import Path

from .config import TEMPLATE_TAG


class GitError(RuntimeError):
    pass


def _run(research_dir: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=research_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def init(research_dir: Path) -> None:
    _run(research_dir, "init")


def commit(research_dir: Path, paths: list[str], message: str) -> str | None:
    """Stage the given paths and commit. Returns the new commit sha, or None if
    there was nothing to commit (working tree already matched)."""
    _run(research_dir, "add", *paths)
    staged = _run(research_dir, "diff", "--cached", "--name-only")
    if not staged:
        return None
    _run(research_dir, "commit", "-m", message)
    return _run(research_dir, "rev-parse", "HEAD")


def log(research_dir: Path, limit: int = 50) -> list[dict]:
    sep = "\x1f"
    out = _run(
        research_dir,
        "log",
        f"--max-count={limit}",
        f"--pretty=format:%H{sep}%ad{sep}%s",
        "--date=iso-strict",
    )
    entries = []
    for line in out.splitlines():
        if not line:
            continue
        sha, date, message = line.split(sep, 2)
        entries.append({"sha": sha, "date": date, "message": message})
    return entries


def show_file_at_ref(research_dir: Path, ref: str, path: str) -> str:
    return _run(research_dir, "show", f"{ref}:{path}")


def show_template_file(research_dir: Path, path: str) -> str:
    """Read a file's pristine, un-generated content from the template-baseline
    tag rather than the working tree (which gets overwritten by generation)."""
    return show_file_at_ref(research_dir, TEMPLATE_TAG, path)


def revert_to(research_dir: Path, sha: str, paths: list[str], message: str | None = None) -> str | None:
    """Restore the given paths to their state at `sha` and commit that as a new commit."""
    _run(research_dir, "checkout", sha, "--", *paths)
    return commit(research_dir, paths, message or f"revert: to {sha[:7]}")


def tag_template_baseline(research_dir: Path) -> None:
    """(Re)point the template-baseline tag at the current HEAD. Used after installing
    a new template, since its pristine, un-generated section files become the new
    baseline that generate.py reads section instructions from."""
    _run(research_dir, "tag", "-f", TEMPLATE_TAG)
