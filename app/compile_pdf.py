import os
import shutil
import subprocess
from pathlib import Path

from . import manifest

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


def compile_pdf(paths) -> dict:
    tectonic = _find_tectonic()
    main_tex = manifest.main_tex_path(paths)
    main_pdf = manifest.main_pdf_path(paths)
    result = subprocess.run(
        [tectonic, main_tex.name],
        cwd=paths.manuscript_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    ok = result.returncode == 0 and main_pdf.exists()
    return {
        "ok": ok,
        "pdf_path": str(main_pdf) if ok else None,
        "log": result.stdout + "\n" + result.stderr,
    }

