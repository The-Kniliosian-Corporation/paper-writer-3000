from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import chat as chat_module
from . import compile_pdf as compile_module
from . import generate as generate_module
from . import git_ops
from . import references as references_module
from .config import (
    ALL_TEX_FILES,
    DEFAULT_MODEL,
    FIGURES_DIR,
    MAIN_PDF,
    MANUSCRIPT_DIR,
    PAPER_MD,
    SELECTABLE_MODELS,
)

app = FastAPI(title="paper-writer-3000")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

TEX_FILES = ALL_TEX_FILES
_TEX_PATHS = {name: f"manuscript/{name}.tex" for name in TEX_FILES}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


class SaveRequest(BaseModel):
    content: str


class GenerateRequest(BaseModel):
    model: str | None = None


class RevertRequest(BaseModel):
    sha: str


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    model: str | None = None


class TexSaveRequest(BaseModel):
    content: str


class ReferenceEntry(BaseModel):
    url: str
    note: str


class ReferencesRequest(BaseModel):
    entries: list[ReferenceEntry]


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/notes")
def get_notes():
    return {"content": PAPER_MD.read_text(encoding="utf-8")}


@app.post("/api/save")
def save_notes(body: SaveRequest):
    PAPER_MD.write_text(body.content, encoding="utf-8")
    try:
        sha = git_ops.commit(["paper.md"], "notes: update")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.get("/api/models")
def get_models():
    return {"default": DEFAULT_MODEL, "models": SELECTABLE_MODELS}


@app.post("/api/generate")
def run_generate(body: GenerateRequest):
    try:
        gen_result = generate_module.generate(model=body.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # OpenAI/network/JSON errors
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc

    compile_result = compile_module.compile_pdf()

    try:
        sha = git_ops.commit(list(_TEX_PATHS.values()), f"regen: {gen_result['model']}")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "model": gen_result["model"],
        "written": gen_result["written"],
        "compiled": compile_result["ok"],
        "compile_log": None if compile_result["ok"] else compile_result["log"],
        "sha": sha,
    }


@app.get("/api/tex")
def get_tex():
    sections = {}
    for name in TEX_FILES:
        path = MANUSCRIPT_DIR / f"{name}.tex"
        sections[name] = path.read_text(encoding="utf-8") if path.exists() else ""
    return sections


@app.post("/api/tex/{name}")
def save_tex(name: str, body: TexSaveRequest):
    if name not in _TEX_PATHS:
        raise HTTPException(status_code=404, detail=f"Unknown LaTeX file: {name}")
    path = MANUSCRIPT_DIR / f"{name}.tex"
    path.write_text(body.content, encoding="utf-8")
    try:
        sha = git_ops.commit([_TEX_PATHS[name]], f"edit: {name}.tex")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.post("/api/compile")
def run_compile():
    compile_result = compile_module.compile_pdf()
    return {
        "ok": compile_result["ok"],
        "log": None if compile_result["ok"] else compile_result["log"],
    }


@app.get("/api/history")
def get_history():
    return git_ops.log()


@app.post("/api/revert")
def revert(body: RevertRequest):
    paths = ["paper.md", *_TEX_PATHS.values()]
    try:
        sha = git_ops.revert_to(body.sha, paths, f"revert: to {body.sha[:7]}")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.get("/api/references")
def get_references():
    return references_module.load()


@app.post("/api/references")
def save_references(body: ReferencesRequest):
    entries = [entry.model_dump() for entry in body.entries]
    references_module.save(entries)
    try:
        sha = git_ops.commit(["references.json"], "references: update")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.get("/api/figures")
def list_figures():
    if not FIGURES_DIR.exists():
        return []
    return sorted(
        p.name for p in FIGURES_DIR.iterdir() if p.suffix.lower() in _IMAGE_EXTENSIONS
    )


@app.get("/api/figures/{filename}")
def get_figure(filename: str):
    name = Path(filename).name
    path = FIGURES_DIR / name
    if name != filename or path.suffix.lower() not in _IMAGE_EXTENSIONS or not path.is_file():
        raise HTTPException(status_code=404, detail="Figure not found")
    return FileResponse(path)


@app.post("/api/figures")
async def upload_figure(file: UploadFile = File(...)):
    name = Path(file.filename).name
    suffix = Path(name).suffix.lower()
    if not name or suffix not in _IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {name or '(empty)'}")

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    path.write_bytes(await file.read())

    try:
        sha = git_ops.commit([f"manuscript/100_Figures/{name}"], f"figures: add {name}")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"filename": name, "committed": sha is not None, "sha": sha}


@app.get("/api/pdf")
def get_pdf():
    if not MAIN_PDF.exists():
        raise HTTPException(status_code=404, detail="No PDF compiled yet -- hit Generate first.")
    return FileResponse(MAIN_PDF, media_type="application/pdf")


@app.post("/api/chat")
def run_chat(body: ChatRequest):
    try:
        result = chat_module.chat(body.message, body.history, model=body.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat failed: {exc}") from exc
    return result
