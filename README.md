# paper-writer-3000

Write a rough draft of your research; generate a polished, submission-ready IEEE-conference LaTeX paper (and
a compiled PDF) from it on demand, with every change tracked in git so nothing is ever lost. Write multiple
papers side by side as separate **projects**, each with its own draft, manuscript, references, and git
history.

See [PLAN.md](PLAN.md) for the full design rationale and decisions behind the app.

## Projects

Each paper is a **project**: its own rough draft, generated LaTeX, references, figures, and git history,
completely isolated from every other project. The "Projects" button in the header lists your projects and
lets you create new ones or switch. Which project is open lives in the page URL
(`?project=<slug>`) -- open a second browser tab with a different project URL to work on two papers at
once, the same way you'd open two separate windows in an IDE.

A new project starts from a bundled generic IEEEtran skeleton, so it's ready to write into immediately; use
the Template button afterwards if you'd rather use your own `.zip`'d template instead.

## How it works

- **Save** — edit your rough draft in the web UI, hit Save. Writes the file and commits it. No LLM call.
- **Generate** — hit Generate (pick a model first if you like). Sends your rough draft, plus the paper's
  section-by-section writing guidance, to OpenAI; writes the rewritten LaTeX into `manuscript/*.tex`;
  compiles it to a PDF with Tectonic; commits the regenerated `.tex` files.
- **History** — every save and generate is a real git commit. The history panel lists them; "revert draft
  here" restores your rough draft (and the generated paper) to an earlier point as a new commit (nothing is
  destroyed).
- **Consult** — a chat panel for talking through direction, gaps, and framing, backed by your local
  [Claude Code](https://claude.com/claude-code) CLI (`claude -p`, using whatever account it's logged in
  with). Each message runs Claude Code in a throwaway scratch copy of the project, with read/edit tools and
  live web search but no shell, so it can read your draft, paper, bibliography, and gathered references,
  look up related work, and check claims instead of guessing. It never edits your real files: anything it
  changes in `paper.md` or a section `.tex` comes back as a proposed edit that you review and Apply
  yourself. Optional `.env` settings: `CLAUDE_CHAT_MODEL` (e.g. `sonnet`, `opus`), `CLAUDE_BIN` (if
  `claude` isn't on PATH), `CLAUDE_CHAT_TIMEOUT` (seconds, default 600).

The model never invents citations, numbers, or claims that aren't in your rough draft — where something's
missing it inserts the template's existing `\citeme`, `\fillme`, or `\TODO{...}` placeholders instead.

## Your paper content is a separate git repo per project

`projects/<slug>/` — a project's rough draft, generated LaTeX, and compiled PDF — is its **own, separate
local git repo**, entirely gitignored from this one. This repo (the app) is meant to be pushed to GitHub;
`projects/` is not connected to any remote and never will be by anything this app does. That split exists
specifically so your actual, unpublished paper content never ends up in this app's (potentially public)
GitHub history.

## Requirements

- Python 3.10+
- [Tectonic](https://tectonic-typesetting.github.io/) on your `PATH` (or set `TECTONIC_BIN` to its full path)
- An OpenAI API key (for Generate)
- [Claude Code](https://claude.com/claude-code) installed and logged in (for Consult)

## Setup

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` and fill in `OPENAI_API_KEY` (and optionally `OPENAI_MODEL` / `OPENAI_MODELS`). Consult
needs no key: it uses whatever account your `claude` CLI is logged in with (see the `CLAUDE_*` settings).

`projects/` is created automatically the first time you create a project from the UI -- nothing to set up
by hand. (If you have an older, single-project checkout of this app with a top-level `research/` directory,
it's migrated into `projects/` automatically the first time the server starts.)

## Running

```
.venv\Scripts\python -m uvicorn app.server:app --reload
```

Open http://127.0.0.1:8000, then use the Projects button to create your first project.

## Project structure

```
Research Rough Docs.md      generic section-by-section writing guidance (not paper-specific)
projects/                   SEPARATE git repos, gitignored here entirely -- one per paper
  <slug>/
    paper.md                  rough draft (your input)
    manuscript/                IEEE LaTeX template + generated output + compiled PDF
    project.json                display name / created date / archived flag
app/
  server.py                 FastAPI app and routes
  projects.py                project registry: list/create/rename/archive, legacy research/ migration
  generate.py                rough draft + guidance -> rewritten manuscript/*.tex via OpenAI
  compile_pdf.py             manuscript/<main>.tex -> PDF via Tectonic
  chat.py                    advisory consultation endpoint
  git_ops.py                 thin git wrapper (commit, log, revert) -- operates on a project's dir, not this repo
  manifest.py                 per-project manuscript structure (main file, sections, has_abstract)
  template_upload.py          parses an uploaded LaTeX template zip into a new manuscript structure
  starter_templates/           bundled generic IEEEtran skeleton used for new projects
  static/                    the single-page frontend (vanilla HTML/JS)
```

The pristine, un-generated section instructions are preserved forever at the `template-baseline` git tag
**inside each project's own repo**, since `generate.py` overwrites `manuscript/*.tex` on every run --
`git -C projects/<slug> show template-baseline:manuscript/1_Introduction.tex` always gets you the original
skeleton back.
