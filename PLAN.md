# paper-writer-3000 — Plan

## Goal

Turn rough, informally-written ideas in [`paper.md`](paper.md) into a professional, submission-ready
LaTeX paper inside [`manuscript/`](manuscript/), with:

- A local web app for editing notes, triggering regeneration, and consulting an LLM about direction.
- Git-based versioning (real `git`, not reinvented) — every change is a commit, every commit can be reverted.
- On-demand regeneration of the formal LaTeX paper (and a compiled PDF), decoupled from saving notes — you
  can save and walk away without generating.

## Non-goals (v1)

- No multi-user / auth / deployment — single local user, runs on `localhost` only.
- No custom diff/history engine — `git log` / `git diff` / `git revert` are the history UI, just surfaced nicely.
- No agentic file-editing chat — the in-app chat is **read-only/advisory** (sees notes + generated paper for
  context, helps you think through direction and phrasing) but does not write files itself in v1. You already
  have Claude Code for that.

## Inputs already in the repo

- [`paper.md`](paper.md) — rough notes (currently empty, to be filled in by you).
- [`Research Rough Docs.md`](Research%20Rough%20Docs.md) — section-by-section writing guidance (markdown).
- [`manuscript/`](manuscript/) — real IEEEtran conference
  template. `0_main.tex` includes `1_Introduction.tex` … `8_Conclusion.tex`, each currently holding
  instructional placeholder text instead of real content.

These three together form the generation prompt: rough notes = content, the two skeletons = structure/style
guide. Only the numbered section `.tex` files get rewritten — `0_main.tex`, the `setting_*.tex` files,
`IEEEtran.cls`, and `references.bib` are left alone.

## Tech stack

| Piece | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | small, async, easy to add a chat endpoint later |
| LLM | OpenAI API, model configurable | you have a key for this, not Anthropic; model not decided yet so make it a setting, not a hardcoded default |
| Frontend | Single static page, vanilla HTML/JS | no build step, no framework overhead |
| Versioning | real `git` via subprocess | free history/revert, nothing to reinvent |
| Regen trigger | Manual — explicit "Generate" action, separate from "Save" | you want to save rough notes and leave without generating; save and generate must not be coupled |
| PDF compile | Tectonic | single self-contained binary, no system-wide LaTeX install, scriptable via subprocess |

## Directory layout (planned additions)

```
paper-writer-3000/
├── paper.md                          # your rough notes (existing)
├── Research Rough Docs.md            # section skeleton (existing)
├── manuscript/                       # LaTeX template + generated output (existing)
├── app/
│   ├── server.py                     # FastAPI app: routes + static file serving
│   ├── generate.py                   # builds the prompt, calls OpenAI, writes N_Section.tex files
│   ├── compile_pdf.py                # invokes Tectonic on 0_main.tex, writes output PDF
│   ├── chat.py                       # advisory chat endpoint (reads notes+paper as context)
│   ├── git_ops.py                    # thin wrapper: commit, log, revert, diff
│   └── static/
│       ├── index.html                # notes editor with separate Save/Generate buttons + model
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
state of `paper.md`. This only restores notes; you then hit Generate again if you want the paper regenerated
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
- `POST /chat` — advisory consultation; sends your message + current notes/paper as context to OpenAI,
  streams back a reply. No file writes.

## GitHub

Repo will be **public**, so secret hygiene matters more than usual:

- `.gitignore` must exclude `.env` (holds `OPENAI_API_KEY`), Python cache dirs, the compiled `paper.pdf`,
  and Tectonic/LaTeX build artifacts (`*.aux`, `*.log`, `*.out`, `*.bbl`, `*.blg`) — set this up **before**
  `git init` + first commit, so the key is never committed or exposed publicly.
- The repo will contain both the app source and your paper's notes/LaTeX — since it's public, your rough
  ideas and unpublished results will be publicly visible too. Worth a final confirmation once notes are
  actually filled in, in case any of it needs to stay private until submission.

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
