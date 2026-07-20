import json

from .config import (
    DEFAULT_HAS_ABSTRACT,
    DEFAULT_MAIN_FILE,
    DEFAULT_SECTION_FILES,
    MANUSCRIPT_DIR,
    TEMPLATE_MANIFEST_JSON,
)


def load() -> dict:
    """The current manuscript template's structure: which file is the main
    wrapper, which files are rewritable sections, and whether it has an
    abstract. Read fresh every call, since template_upload.py can replace it
    at any time without a server restart."""
    if TEMPLATE_MANIFEST_JSON.exists():
        return json.loads(TEMPLATE_MANIFEST_JSON.read_text(encoding="utf-8"))
    return {
        "main_file": DEFAULT_MAIN_FILE,
        "sections": list(DEFAULT_SECTION_FILES),
        "has_abstract": DEFAULT_HAS_ABSTRACT,
    }


def save(manifest: dict) -> None:
    TEMPLATE_MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main_file() -> str:
    return load()["main_file"]


def section_files() -> list[str]:
    return load()["sections"]


def has_abstract() -> bool:
    return load().get("has_abstract", True)


def all_files() -> list[str]:
    m = load()
    return [m["main_file"], *m["sections"]]


def main_tex_path():
    return MANUSCRIPT_DIR / f"{main_file()}.tex"


def main_pdf_path():
    # Tectonic names the output PDF after the source .tex file, so this tracks
    # main_file() rather than being a fixed "0_main.pdf".
    return MANUSCRIPT_DIR / f"{main_file()}.pdf"
