import json
import re

from . import citations

_BIB_KEY_RE = re.compile(r"@\w+\{\s*([^,\s]+)\s*,")


def load(paths) -> list[dict]:
    if not paths.references_json.exists():
        return []
    return json.loads(paths.references_json.read_text(encoding="utf-8"))


def save(paths, entries: list[dict]) -> None:
    paths.references_json.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _existing_bib_keys(bib_text: str) -> set[str]:
    return set(_BIB_KEY_RE.findall(bib_text))


def sync_bib(paths) -> list[dict]:
    """Ensure every reference the author has added via the references panel
    has a real bibtex entry in references.bib, so generate.py can hand the
    model a \\cite{key} it's actually allowed to use instead of falling back
    to \\citeme for a paper the author already pointed it at. Fetches
    metadata from the arXiv API; entries that fail to resolve (non-arXiv URL,
    network hiccup) are left without a bib_key and are passed to the model as
    background context only. Idempotent -- entries that already have a
    bib_key are skipped."""
    entries = load(paths)
    if not entries:
        return entries

    bib_path = paths.references_bib
    bib_text = bib_path.read_text(encoding="utf-8") if bib_path.exists() else ""
    existing_keys = _existing_bib_keys(bib_text)

    appended = []
    changed = False
    for entry in entries:
        if entry.get("bib_key"):
            continue
        arxiv_id = citations.arxiv_id_from_url(entry.get("url", ""))
        if not arxiv_id:
            continue
        meta = citations.fetch_arxiv_metadata(arxiv_id)
        if not meta:
            continue
        key = citations.make_bib_key(meta, existing_keys)
        existing_keys.add(key)
        entry["bib_key"] = key
        appended.append(citations.to_bibtex_entry(key, meta, entry["url"], arxiv_id))
        changed = True

    if appended:
        separator = "\n" if bib_text.strip() else ""
        bib_path.write_text(bib_text.rstrip("\n") + separator + "\n\n" + "\n".join(appended), encoding="utf-8")

    if changed:
        save(paths, entries)

    return entries
