import json


def load(paths) -> list[dict]:
    if not paths.references_json.exists():
        return []
    return json.loads(paths.references_json.read_text(encoding="utf-8"))


def save(paths, entries: list[dict]) -> None:
    paths.references_json.write_text(json.dumps(entries, indent=2), encoding="utf-8")
