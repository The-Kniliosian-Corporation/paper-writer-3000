import subprocess

from .config import RESEARCH_DIR, TEMPLATE_TAG


class GitError(RuntimeError):
    pass


def _run(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=RESEARCH_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def commit(paths: list[str], message: str) -> str | None:
    """Stage the given paths and commit. Returns the new commit sha, or None if
    there was nothing to commit (working tree already matched)."""
    _run("add", *paths)
    staged = _run("diff", "--cached", "--name-only")
    if not staged:
        return None
    _run("commit", "-m", message)
    return _run("rev-parse", "HEAD")


def log(limit: int = 50) -> list[dict]:
    sep = "\x1f"
    out = _run(
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


def show_file_at_ref(ref: str, path: str) -> str:
    return _run("show", f"{ref}:{path}")


def show_template_file(path: str) -> str:
    """Read a file's pristine, un-generated content from the template-baseline
    tag rather than the working tree (which gets overwritten by generation)."""
    return show_file_at_ref(TEMPLATE_TAG, path)


def revert_notes_to(sha: str, message: str | None = None) -> str | None:
    """Restore paper.md to its state at `sha` and commit that as a new commit."""
    _run("checkout", sha, "--", "paper.md")
    return commit(["paper.md"], message or f"revert: paper.md to {sha[:7]}")
