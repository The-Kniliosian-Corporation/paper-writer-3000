from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import chat as chat_module
from . import compile_pdf as compile_module
from . import generate as generate_module
from . import git_ops
from .config import DEFAULT_MODEL, MAIN_PDF, MANUSCRIPT_DIR, PAPER_MD, SECTION_FILES, SELECTABLE_MODELS

app = FastAPI(title="paper-writer-3000")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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

    paths = [f"manuscript/{name}.tex" for name in SECTION_FILES] + ["manuscript/0_main.tex"]
    try:
        sha = git_ops.commit(paths, f"regen: {gen_result['model']}")
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
    for name in SECTION_FILES:
        path = MANUSCRIPT_DIR / f"{name}.tex"
        sections[name] = path.read_text(encoding="utf-8") if path.exists() else ""
    return sections


@app.get("/api/history")
def get_history():
    return git_ops.log()


@app.post("/api/revert")
def revert(body: RevertRequest):
    try:
        sha = git_ops.revert_notes_to(body.sha)
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.get("/api/pdf")
def get_pdf():
    if not MAIN_PDF.exists():
        raise HTTPException(status_code=404, detail="No PDF compiled yet -- hit Generate first.")
    return FileResponse(MAIN_PDF, media_type="application/pdf")


@app.post("/api/chat")
def run_chat(body: ChatRequest):
    try:
        reply = chat_module.chat(body.message, body.history, model=body.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat failed: {exc}") from exc
    return {"reply": reply}
