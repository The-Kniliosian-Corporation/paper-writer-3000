from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import chat as chat_module
from . import compile_pdf as compile_module
from . import generate as generate_module
from . import git_ops
from . import manifest
from . import projects
from . import references as references_module
from . import template_upload
from .config import DEFAULT_MODEL, SELECTABLE_MODELS, STARTER_TEMPLATES

app = FastAPI(title="paper-writer-3000")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


@app.on_event("startup")
def _migrate_on_startup():
    projects.migrate_legacy_research_dir()


def _paths(project: str) -> projects.ProjectPaths:
    try:
        return projects.paths_for(project)
    except projects.ProjectError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _tex_paths(paths: projects.ProjectPaths) -> dict[str, str]:
    """Recomputed on every call rather than cached, since a template upload
    can change the section/main-file list at any moment."""
    return {name: f"manuscript/{name}.tex" for name in manifest.all_files(paths)}


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
    bib_key: str | None = None


class ReferencesRequest(BaseModel):
    entries: list[ReferenceEntry]


class NewProjectRequest(BaseModel):
    name: str
    template: str = "ieee_default"


class RenameProjectRequest(BaseModel):
    name: str


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/templates")
def list_templates():
    return list(STARTER_TEMPLATES.keys())


@app.get("/api/projects")
def list_projects():
    return projects.list_projects()


@app.post("/api/projects")
def create_project(body: NewProjectRequest):
    try:
        return projects.create_project(body.name, body.template)
    except projects.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{slug}/rename")
def rename_project(slug: str, body: RenameProjectRequest):
    try:
        projects.rename_project(slug, body.name)
    except projects.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except projects.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/projects/{slug}/archive")
def archive_project(slug: str):
    _paths(slug)
    projects.set_archived(slug, True)
    return {"ok": True}


@app.post("/api/projects/{slug}/unarchive")
def unarchive_project(slug: str):
    _paths(slug)
    projects.set_archived(slug, False)
    return {"ok": True}


@app.get("/api/notes")
def get_notes(project: str):
    paths = _paths(project)
    return {"content": paths.paper_md.read_text(encoding="utf-8")}


@app.post("/api/save")
def save_notes(project: str, body: SaveRequest):
    paths = _paths(project)
    paths.paper_md.write_text(body.content, encoding="utf-8")
    try:
        sha = git_ops.commit(paths.root, ["paper.md"], "notes: update")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.get("/api/models")
def get_models():
    return {"default": DEFAULT_MODEL, "models": SELECTABLE_MODELS}


@app.post("/api/generate")
def run_generate(project: str, body: GenerateRequest):
    paths = _paths(project)
    try:
        gen_result = generate_module.generate(paths, model=body.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # OpenAI/network/JSON errors
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc

    compile_result = compile_module.compile_pdf(paths)

    try:
        sha = git_ops.commit(paths.root, list(_tex_paths(paths).values()), f"regen: {gen_result['model']}")
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
def get_tex(project: str):
    paths = _paths(project)
    sections = {}
    for name in manifest.all_files(paths):
        path = paths.manuscript_dir / f"{name}.tex"
        sections[name] = path.read_text(encoding="utf-8") if path.exists() else ""
    return sections


@app.post("/api/tex/{name}")
def save_tex(name: str, project: str, body: TexSaveRequest):
    paths = _paths(project)
    tex_paths = _tex_paths(paths)
    if name not in tex_paths:
        raise HTTPException(status_code=404, detail=f"Unknown LaTeX file: {name}")
    path = paths.manuscript_dir / f"{name}.tex"
    path.write_text(body.content, encoding="utf-8")
    try:
        sha = git_ops.commit(paths.root, [tex_paths[name]], f"edit: {name}.tex")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.post("/api/compile")
def run_compile(project: str):
    paths = _paths(project)
    compile_result = compile_module.compile_pdf(paths)
    return {
        "ok": compile_result["ok"],
        "log": None if compile_result["ok"] else compile_result["log"],
    }


@app.get("/api/history")
def get_history(project: str):
    paths = _paths(project)
    return git_ops.log(paths.root)


@app.post("/api/revert")
def revert(project: str, body: RevertRequest):
    paths = _paths(project)
    revert_paths = ["paper.md", *_tex_paths(paths).values()]
    try:
        sha = git_ops.revert_to(paths.root, body.sha, revert_paths, f"revert: to {body.sha[:7]}")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.get("/api/references")
def get_references(project: str):
    paths = _paths(project)
    return references_module.load(paths)


@app.post("/api/references")
def save_references(project: str, body: ReferencesRequest):
    paths = _paths(project)
    entries = [entry.model_dump() for entry in body.entries]
    references_module.save(paths, entries)
    try:
        sha = git_ops.commit(paths.root, ["references.json"], "references: update")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"committed": sha is not None, "sha": sha}


@app.get("/api/figures")
def list_figures(project: str):
    paths = _paths(project)
    if not paths.figures_dir.exists():
        return []
    return sorted(
        p.name for p in paths.figures_dir.iterdir() if p.suffix.lower() in _IMAGE_EXTENSIONS
    )


@app.get("/api/figures/{filename}")
def get_figure(filename: str, project: str):
    paths = _paths(project)
    name = Path(filename).name
    path = paths.figures_dir / name
    if name != filename or path.suffix.lower() not in _IMAGE_EXTENSIONS or not path.is_file():
        raise HTTPException(status_code=404, detail="Figure not found")
    return FileResponse(path)


@app.post("/api/figures")
async def upload_figure(project: str, file: UploadFile = File(...)):
    paths = _paths(project)
    name = Path(file.filename).name
    suffix = Path(name).suffix.lower()
    if not name or suffix not in _IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {name or '(empty)'}")

    paths.figures_dir.mkdir(parents=True, exist_ok=True)
    path = paths.figures_dir / name
    path.write_bytes(await file.read())

    try:
        sha = git_ops.commit(paths.root, [f"manuscript/100_Figures/{name}"], f"figures: add {name}")
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"filename": name, "committed": sha is not None, "sha": sha}


@app.get("/api/pdf")
def get_pdf(project: str):
    paths = _paths(project)
    main_pdf = manifest.main_pdf_path(paths)
    if not main_pdf.exists():
        raise HTTPException(status_code=404, detail="No PDF compiled yet -- hit Generate first.")
    return FileResponse(main_pdf, media_type="application/pdf")


@app.get("/api/template")
def get_template(project: str):
    paths = _paths(project)
    return manifest.load(paths)


@app.post("/api/template")
async def upload_template(project: str, file: UploadFile = File(...)):
    paths = _paths(project)
    try:
        result = template_upload.install(paths, await file.read(), file.filename or "template.zip")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except git_ops.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/chat")
def run_chat(project: str, body: ChatRequest):
    paths = _paths(project)
    try:
        result = chat_module.chat(paths, body.message, body.history, model=body.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat failed: {exc}") from exc
    return result
