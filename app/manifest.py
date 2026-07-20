import json

from .config import DEFAULT_HAS_ABSTRACT, DEFAULT_MAIN_FILE, DEFAULT_SECTION_FILES


def load(paths) -> dict:
    """The current manuscript template's structure: which file is the main
    wrapper, which files are rewritable sections, and whether it has an
    abstract. Read fresh every call, since template_upload.py can replace it
    at any time without a server restart. `paths` is a projects.ProjectPaths.
    Falls back to the DEFAULT_* skeleton for projects with no
    template_manifest.json yet (e.g. the migrated legacy project)."""
    if paths.template_manifest_json.exists():
        return json.loads(paths.template_manifest_json.read_text(encoding="utf-8"))
    return {
        "main_file": DEFAULT_MAIN_FILE,
        "sections": list(DEFAULT_SECTION_FILES),
        "has_abstract": DEFAULT_HAS_ABSTRACT,
    }


def save(paths, manifest: dict) -> None:
    paths.template_manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main_file(paths) -> str:
    return load(paths)["main_file"]


def section_files(paths) -> list[str]:
    return load(paths)["sections"]


def has_abstract(paths) -> bool:
    return load(paths).get("has_abstract", True)


def all_files(paths) -> list[str]:
    m = load(paths)
    return [m["main_file"], *m["sections"]]


def main_tex_path(paths):
    return paths.manuscript_dir / f"{main_file(paths)}.tex"


def main_pdf_path(paths):
    # Tectonic names the output PDF after the source .tex file, so this tracks
    # main_file() rather than being a fixed "0_main.pdf".
    return paths.manuscript_dir / f"{main_file(paths)}.pdf"
