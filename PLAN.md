# paper-writer-3000 — Plan

## Goal

Turn rough, informally-written ideas in `research/paper.md` into a professional, submission-ready
LaTeX paper inside `research/manuscript/`, with:

- A local web app for editing the rough draft, triggering regeneration, and consulting an LLM about direction.
- Git-based versioning (real `git`, not reinvented) — every change is a commit, every commit can be reverted.
- On-demand regeneration of the formal LaTeX paper (and a compiled PDF), decoupled from saving the rough draft — you
  can save and walk away without generating.

## Non-goals (v1)

- No multi-user / auth / deployment — single local user, runs on `localhost` only.
- No custom diff/history engine — `git log` / `git diff` / `git revert` are the history UI, just surfaced nicely.
- No agentic file-editing chat — the in-app chat is **read-only/advisory** (sees the rough draft + generated paper for
  context, helps you think through direction and phrasing) but does not write files itself in v1. You already
  have Claude Code for that.

## Inputs

- `research/paper.md` — rough draft (filled in by you).
- [`Research Rough Docs.md`](Research%20Rough%20Docs.md) — section-by-section writing guidance (markdown,
  generic template guidance, not paper-specific — lives in this repo, not `research/`).
- `research/manuscript/` — real IEEEtran conference
  template. `0_main.tex` includes `1_Introduction.tex` … `8_Conclusion.tex`, initially holding
  instructional placeholder text, later real content.

These three together form the generation prompt: the rough draft = content, the two skeletons = structure/style
guide. Only the numbered section `.tex` files get rewritten — `0_main.tex`, the `setting_*.tex` files,
`IEEEtran.cls`, and `references.bib` are left alone.

## Tech stack

| Piece | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | small, async, easy to add a chat endpoint later |
| LLM | OpenAI API, model configurable | you have a key for this, not Anthropic; model not decided yet so make it a setting, not a hardcoded default |
| Frontend | Single static page, vanilla HTML/JS | no build step, no framework overhead |
| Versioning | real `git` via subprocess | free history/revert, nothing to reinvent |
| Regen trigger | Manual — explicit "Generate" action, separate from "Save" | you want to save the rough draft and leave without generating; save and generate must not be coupled |
| PDF compile | Tectonic | single self-contained binary, no system-wide LaTeX install, scriptable via subprocess |

## The research/ split

`paper.md` and `manuscript/` are your actual, unpublished research content — not app source. They live in
`research/`, a **separate, dedicated local git repo** with its own history, gitignored from this repo
entirely (`research/` is a single line in `.gitignore`). This repo's own git history is for the *tool*; it
gets pushed to GitHub. `research/`'s history is for the *paper*; it doesn't, ever.

Practically: `app/config.py` defines `RESEARCH_DIR`, and `git_ops.py` runs all git commands with
`cwd=RESEARCH_DIR` instead of the project root — every save/generate/revert commit lands in `research/`'s
repo, invisible to this one. The `template-baseline` tag (pristine section instructions, see below) also
lives inside `research/`'s repo, not this one.

## Directory layout

```
paper-writer-3000/
├── Research Rough Docs.md            # generic section skeleton -- not paper-specific, stays here
├── research/                          # SEPARATE git repo, gitignored here entirely
│   ├── paper.md                       # your rough draft
│   └── manuscript/                    # LaTeX template + generated output + compiled PDF
├── app/
│   ├── server.py                     # FastAPI app: routes + static file serving
│   ├── generate.py                   # builds the prompt, calls OpenAI, writes N_Section.tex files
│   ├── compile_pdf.py                # invokes Tectonic on 0_main.tex, writes output PDF
│   ├── chat.py                       # advisory chat endpoint (reads rough draft+paper as context)
│   ├── git_ops.py                    # thin wrapper: commit, log, revert, diff
│   └── static/
│       ├── index.html                # rough draft editor with separate Save/Generate buttons + model
│       │                              # selector + PDF preview + chat + history panel
│       ├── app.js
│       └── style.css
├── .env                              # OPENAI_API_KEY=..., OPENAI_MODEL=... (gitignored)
├── .gitignore                        # .env, __pycache__/, *.pyc, tectonic binary, build artifacts
└── requirements.txt
```

Tectonic itself is a single binary, not a Python dependency — installed once (e.g. `winget install
tectonic-typesetting.tectonic`) rather than vendored into the repo, so it never ends up in git or on GitHub.

## Data flow

**Save (independent, no LLM call):**

1. You edit `paper.md` in the web UI and hit **Save**.
2. App writes the file and creates a git commit (e.g. `notes: update`). Done — no generation happens. You
   can close the app here.

**Generate (explicit, separate action, whenever you're ready):**

1. You hit **Generate** (optionally picking a model from the selector first).
2. `generate.py` sends the current `paper.md` + both skeleton files to OpenAI, gets back rewritten content
   for each `N_Section.tex`, writes them.
3. `compile_pdf.py` runs Tectonic on `0_main.tex`, producing `manuscript/paper.pdf`.
   If compilation fails (e.g. malformed LaTeX from the model), the error is surfaced in the UI and the
   previous PDF is left in place rather than deleted.
4. The regenerated `.tex` files are committed (e.g. `regen: from <notes commit sha>`). The PDF is a build
   artifact regenerated from tracked `.tex` source, so it's gitignored rather than committed — keeps the
   repo diffable and avoids bloating it with binary blobs on every regen.
5. UI refreshes to show the new PDF (embedded `<iframe>`/PDF.js viewer), the generated LaTeX, and the updated
   commit history.

**Reverting:** pick a commit in the history panel → app runs `git revert`/`git checkout` to restore that
state of `paper.md`. This only restores the rough draft; you then hit Generate again if you want the paper regenerated
from that point.

## API endpoints (backend)

- `GET /` — serves the UI.
- `POST /save` — writes `paper.md`, commits it. Does not call the LLM or touch the `.tex` output.
- `POST /generate` — runs the OpenAI regeneration pass + Tectonic PDF compile, only when explicitly called
  from the UI. Accepts an optional `model` field to override the default.
- `GET /models` — returns the list of selectable OpenAI models for the UI dropdown.
- `GET /history` — returns `git log` entries for the history panel.
- `POST /revert` — reverts `paper.md` to a given commit.
- `GET /pdf` — serves the latest compiled PDF for the viewer panel.
- `POST /chat` — advisory consultation; sends your message + current rough draft/paper as context to OpenAI,
  streams back a reply. No file writes.

## GitHub

Repo will be **public**, so secret hygiene matters more than usual:

- `.gitignore` must exclude `.env` (holds `OPENAI_API_KEY`), Python cache dirs, and `research/` itself —
  set this up **before** `git init` + first commit, so neither the key nor any paper content is ever
  committed or exposed publicly.
- Only the app (this repo) is public. `research/` (your actual rough draft, generated paper, and PDF) is a
  separate local repo with no remote — it never gets pushed anywhere. See "The research/ split" above.

## Build order

0. Install Tectonic locally (e.g. `winget install tectonic-typesetting.tectonic`) — one-time setup, not part
   of the repo.
1. `git init` + `.gitignore` + initial commit of existing files.
2. `generate.py` as a standalone script first (no server) — prove the OpenAI call + prompt produces good
   section rewrites from `paper.md`. Fastest way to validate quality before building UI around it.
3. `compile_pdf.py` as a standalone script — prove Tectonic compiles the existing template as-is, then
   compiles the regenerated output.
4. FastAPI server wrapping both (`/save`, `/generate`, `/models`, `/history`, `/revert`, `/pdf`), with
   `/save` and `/generate` kept fully independent.
5. Static frontend: separate Save and Generate buttons, model dropdown, PDF viewer + generated LaTeX view +
   history.
6. Chat endpoint + panel.

## Resolved decisions

- Repo visibility: **public**.
- OpenAI model: **not fixed** — exposed as a configurable setting (`.env` default + UI dropdown override
  per generate call) rather than hardcoded, since you haven't picked one yet.

## Extension: multi-project support

Everything above described v1: exactly one paper, living in a single `research/` directory. That's since
been generalized to **multiple projects**, each with the same internal shape (`paper.md`, `manuscript/`,
`references.json`, its own git repo) but living under `projects/<slug>/` instead of a single fixed
`research/`. This supersedes the "research/ split", "Directory layout", and "API endpoints" sections above
in the following ways -- the rest of the design (git-based history, Save/Generate decoupling, advisory-only
chat) is unchanged:

- **Which project is "current" is client-side, via the URL** (`?project=<slug>`), not server-side state.
  Every `/api/*` route (except `/api/projects` itself and `/api/models`) takes a `project` query parameter;
  `app/server.py`'s `_paths(project)` resolves it to an `app/projects.py::ProjectPaths` via
  `projects.paths_for()`, which every downstream module (`git_ops`, `manifest`, `generate`, `chat`,
  `compile_pdf`, `references`, `template_upload`) now takes as an explicit first argument instead of reading
  fixed constants from `config.py`. Two browser tabs with different `?project=` values are two fully
  independent sessions.
- **New project lifecycle** lives in `app/projects.py`: `create_project` (slugifies the name, copies the
  bundled `app/starter_templates/ieee_default/` skeleton into a fresh `manuscript/`, scaffolds a
  heading-per-section `paper.md`, `git init`s + commits + tags `template-baseline`), `rename_project` (only
  touches `project.json`'s `name`, never the slug/directory, so existing URLs keep working),
  `set_archived` (hide/unhide from the list; never deletes anything on disk), and `list_projects`.
  New endpoints: `GET/POST /api/projects`, `POST /api/projects/{slug}/rename`,
  `POST /api/projects/{slug}/{,un}archive`.
- **One-time migration**: `projects.migrate_legacy_research_dir()` runs on server startup; if a top-level
  `research/` still exists and `projects/` doesn't, it's `shutil.move`'d into `projects/<slug>/` (a
  same-volume move, so `.git` history and the `template-baseline` tag survive intact) and given a
  `project.json` so it shows up as an ordinary project, renamable from the UI.
- **Starter template provenance**: extracted from the original `research/`'s pristine `template-baseline`
  tag, with `setting_variable.tex` specifically excluded and replaced by an empty placeholder -- that one
  file, unlike the rest of the tag, turned out to hold that paper's real macros/data rather than generic
  instructional content, so it was not safe to bundle into this (public) app repo.
