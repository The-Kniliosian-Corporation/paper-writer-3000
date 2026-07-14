import os
import shutil
import subprocess
from pathlib import Path

from .config import MAIN_PDF, MAIN_TEX, MANUSCRIPT_DIR

_FALLBACK_TECTONIC = Path.home() / "AppData" / "Local" / "tectonic" / "tectonic.exe"


def _find_tectonic() -> str:
    candidate = os.environ.get("TECTONIC_BIN") or shutil.which("tectonic")
    if candidate:
        return candidate
    if _FALLBACK_TECTONIC.exists():
        return str(_FALLBACK_TECTONIC)
    raise FileNotFoundError(
        "tectonic executable not found. Install it (see PLAN.md) or set TECTONIC_BIN."
    )


def compile_pdf() -> dict:
    tectonic = _find_tectonic()
    result = subprocess.run(
        [tectonic, MAIN_TEX.name],
        cwd=MANUSCRIPT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    ok = result.returncode == 0 and MAIN_PDF.exists()
    return {
        "ok": ok,
        "pdf_path": str(MAIN_PDF) if ok else None,
        "log": result.stdout + "\n" + result.stderr,
    }


if __name__ == "__main__":
    outcome = compile_pdf()
    if outcome["ok"]:
        print(f"PDF written to {outcome['pdf_path']}")
    else:
        print("Compilation failed:")
        print(outcome["log"])
