import json

from .config import REFERENCES_JSON


def load() -> list[dict]:
    if not REFERENCES_JSON.exists():
        return []
    return json.loads(REFERENCES_JSON.read_text(encoding="utf-8"))


def save(entries: list[dict]) -> None:
    REFERENCES_JSON.write_text(json.dumps(entries, indent=2), encoding="utf-8")
