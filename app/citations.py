import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?", re.IGNORECASE)
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ARXIV_API = "https://export.arxiv.org/api/query?id_list={id}"


def arxiv_id_from_url(url: str) -> str | None:
    match = _ARXIV_URL_RE.search(url)
    return match.group(1) if match else None


def fetch_arxiv_metadata(arxiv_id: str, timeout: float = 10.0) -> dict | None:
    """Look up an arXiv paper's title/authors/year via the public arXiv API.
    Returns None on any network or parse failure so callers can degrade
    gracefully (skip the citation) instead of blocking generation on a flaky
    third-party call."""
    try:
        with urllib.request.urlopen(_ARXIV_API.format(id=arxiv_id), timeout=timeout) as resp:
            body = resp.read()
    except (urllib.error.URLError, OSError):
        return None

    try:
        root = ET.fromstring(body)
        entry = root.find(f"{_ATOM_NS}entry")
        if entry is None:
            return None
        title = re.sub(r"\s+", " ", entry.findtext(f"{_ATOM_NS}title", "").strip())
        published = entry.findtext(f"{_ATOM_NS}published", "")
        year = published[:4] if published else ""
        authors = [
            name.strip()
            for a in entry.findall(f"{_ATOM_NS}author")
            if (name := a.findtext(f"{_ATOM_NS}name", "").strip())
        ]
    except ET.ParseError:
        return None

    if not title or not authors:
        return None
    return {"title": title, "authors": authors, "year": year}


def _slug_word(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def make_bib_key(meta: dict, existing_keys: set[str]) -> str:
    last_name = meta["authors"][0].split()[-1] if meta["authors"] else "ref"
    base = f"{_slug_word(last_name) or 'ref'}{meta.get('year') or ''}"
    key = base
    n = 2
    while key in existing_keys:
        key = f"{base}{chr(96 + n)}"  # a, b, c, ...
        n += 1
    return key


def _escape_bibtex(text: str) -> str:
    return text.replace("{", "\\{").replace("}", "\\}")


def to_bibtex_entry(key: str, meta: dict, url: str, arxiv_id: str) -> str:
    authors = " and ".join(meta["authors"])
    return (
        f"@misc{{{key},\n"
        f"  title = {{{_escape_bibtex(meta['title'])}}},\n"
        f"  author = {{{_escape_bibtex(authors)}}},\n"
        f"  year = {{{meta.get('year') or 'n.d.'}}},\n"
        f"  eprint = {{{arxiv_id}}},\n"
        f"  archivePrefix = {{arXiv}},\n"
        f"  url = {{{url}}}\n"
        f"}}\n"
    )
