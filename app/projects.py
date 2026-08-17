import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import git_ops
from . import manifest as manifest_module
from . import template_upload
from .config import PROJECT_ROOT, PROJECTS_ROOT, STARTER_TEMPLATE_DIR, STARTER_TEMPLATES

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PROJECT_JSON = "project.json"
_LEGACY_RESEARCH_DIR = PROJECT_ROOT / "research"


class ProjectError(Exception):
    """A project-related request couldn't be satisfied (e.g. an empty name).
    Callers should treat this as a 400."""


class ProjectNotFoundError(ProjectError):
    """The given slug is invalid or doesn't refer to an existing project.
    Callers should treat this as a 404."""


@dataclass
class ProjectPaths:
    slug: str
    root: Path
    manuscript_dir: Path
    paper_md: Path
    references_json: Path
    references_bib: Path
    figures_dir: Path
    template_manifest_json: Path


def _paths_from_root(slug: str, root: Path) -> ProjectPaths:
    manuscript_dir = root / "manuscript"
    return ProjectPaths(
        slug=slug,
        root=root,
        manuscript_dir=manuscript_dir,
        paper_md=root / "paper.md",
        references_json=root / "references.json",
        references_bib=manuscript_dir / "references.bib",
        figures_dir=manuscript_dir / "100_Figures",
        template_manifest_json=manuscript_dir / "template_manifest.json",
    )


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "project"


def _project_json_path(slug: str) -> Path:
    return PROJECTS_ROOT / slug / _PROJECT_JSON


def _read_project_json(slug: str) -> dict:
    return json.loads(_project_json_path(slug).read_text(encoding="utf-8"))


def _write_project_json(slug: str, data: dict) -> None:
    _project_json_path(slug).write_text(json.dumps(data, indent=2), encoding="utf-8")


def paths_for(slug: str) -> ProjectPaths:
    """Resolve a project slug to its paths, validating both the slug format
    and that it refers to a real, existing project. Raises ProjectError for
    anything invalid or unknown -- callers should map that to a 404."""
    if not slug or not _SLUG_RE.match(slug):
        raise ProjectNotFoundError(f"Invalid project: {slug!r}")

    root = (PROJECTS_ROOT / slug).resolve()
    projects_root_resolved = PROJECTS_ROOT.resolve()
    try:
        root.relative_to(projects_root_resolved)
    except ValueError:
        raise ProjectNotFoundError(f"Invalid project: {slug!r}") from None

    if not _project_json_path(slug).exists():
        raise ProjectNotFoundError(f"Unknown project: {slug!r}")

    return _paths_from_root(slug, root)


def list_projects(include_archived: bool = False) -> list[dict]:
    if not PROJECTS_ROOT.exists():
        return []
    projects = []
    for entry in sorted(PROJECTS_ROOT.iterdir()):
        if not entry.is_dir() or not (entry / _PROJECT_JSON).exists():
            continue
        data = json.loads((entry / _PROJECT_JSON).read_text(encoding="utf-8"))
        if data.get("archived") and not include_archived:
            continue
        projects.append({"slug": entry.name, **data})
    projects.sort(key=lambda p: p.get("created", ""), reverse=True)
    return projects


def _unique_slug(base_slug: str) -> str:
    slug = base_slug
    n = 2
    while (PROJECTS_ROOT / slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1
    return slug


def _install_starter_template(manuscript_dir: Path, root: Path, template_dir: Path) -> list[str]:
    """Copy the bundled starter template into a new project: the .gitignore
    goes at the project root (its patterns are root-relative), everything
    else into manuscript/. Returns the starter's section file base names."""
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    for item in template_dir.iterdir():
        if item.name == ".gitignore":
            shutil.copy2(item, root / ".gitignore")
        elif item.is_dir():
            shutil.copytree(item, manuscript_dir / item.name)
        else:
            shutil.copy2(item, manuscript_dir / item.name)

    return sorted(
        p.stem
        for p in template_dir.glob("*.tex")
        if p.stem != "0_main" and re.match(r"^\d", p.stem)
    )


def create_project(name: str, template: str = "ieee_default") -> dict:
    name = name.strip()
    if not name:
        raise ProjectError("Project name cannot be empty.")
    if template not in STARTER_TEMPLATES:
        raise ProjectError(f"Unknown template: {template!r}. Choose from: {', '.join(STARTER_TEMPLATES)}")

    slug = _unique_slug(_slugify(name))
    root = PROJECTS_ROOT / slug
    paths = _paths_from_root(slug, root)

    template_dir = STARTER_TEMPLATES[template]
    section_files = _install_starter_template(paths.manuscript_dir, root, template_dir)
    manifest_module.save(paths, {"main_file": "0_main", "sections": section_files, "has_abstract": True})
    template_upload.scaffold_draft(paths, section_files)

    created = datetime.now(timezone.utc).isoformat()
    project_data = {"name": name, "created": created, "archived": False}
    _write_project_json_at(root, project_data)

    git_ops.init(root)
    sha = git_ops.commit(root, ["."], "init: new project")
    if sha is not None:
        git_ops.tag_template_baseline(root)

    return {"slug": slug, **project_data}


def _write_project_json_at(root: Path, data: dict) -> None:
    (root / _PROJECT_JSON).write_text(json.dumps(data, indent=2), encoding="utf-8")


def rename_project(slug: str, new_name: str) -> None:
    new_name = new_name.strip()
    if not new_name:
        raise ProjectError("Project name cannot be empty.")
    paths_for(slug)  # validates existence/slug format
    data = _read_project_json(slug)
    data["name"] = new_name
    _write_project_json(slug, data)


def set_archived(slug: str, archived: bool) -> None:
    paths_for(slug)
    data = _read_project_json(slug)
    data["archived"] = archived
    _write_project_json(slug, data)


def migrate_legacy_research_dir() -> dict | None:
    """One-time migration: the original single-project layout kept everything
    in a top-level research/ directory. If that still exists and the new
    projects/ layout hasn't been set up yet, move it in as the first project
    (a same-volume move preserves its .git history and tags intact)."""
    if not _LEGACY_RESEARCH_DIR.exists() or PROJECTS_ROOT.exists():
        return None

    PROJECTS_ROOT.mkdir(parents=True)
    slug = _unique_slug("my-paper")
    destination = PROJECTS_ROOT / slug
    shutil.move(str(_LEGACY_RESEARCH_DIR), str(destination))

    created = datetime.now(timezone.utc).isoformat()
    project_data = {"name": "My Paper", "created": created, "archived": False}
    _write_project_json_at(destination, project_data)
    return {"slug": slug, **project_data}
