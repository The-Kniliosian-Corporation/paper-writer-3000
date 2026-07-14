# paper-writer-3000

Write rough, informal research notes in `research/paper.md`; generate a polished, submission-ready
IEEE-conference LaTeX paper (and a compiled PDF) from them on demand, with every change tracked in git so
nothing is ever lost.

See [PLAN.md](PLAN.md) for the full design rationale and decisions behind the app.

## How it works

- **Save** — edit your notes in the web UI, hit Save. Writes the file and commits it. No LLM call.
- **Generate** — hit Generate (pick a model first if you like). Sends your notes, plus the paper's
  section-by-section writing guidance, to OpenAI; writes the rewritten LaTeX into `research/manuscript/*.tex`;
  compiles it to a PDF with Tectonic; commits the regenerated `.tex` files.
- **History** — every save and generate is a real git commit. The history panel lists them; "revert notes
  here" restores your notes to an earlier point as a new commit (nothing is destroyed).
- **Consult** — a chat panel for talking through direction, gaps, and framing. It has live web search (via
  OpenAI's `web_search` tool), so it can look up related work and check claims instead of guessing. It's
  advisory only: it can see your notes and generated paper for context but never edits files itself.

The model never invents citations, numbers, or claims that aren't in your notes — where something's
missing it inserts the template's existing `\citeme`, `\fillme`, or `\TODO{...}` placeholders instead.

## Your paper content is a separate git repo

`research/` — your notes, the generated LaTeX, and the compiled PDF — is its **own, separate local git
repo**, entirely gitignored from this one. This repo (the app) is meant to be pushed to GitHub; `research/`
is not connected to any remote and never will be by anything this app does. That split exists specifically
so your actual, unpublished paper content never ends up in this app's (potentially public) GitHub history.

## Requirements

- Python 3.10+
- [Tectonic](https://tectonic-typesetting.github.io/) on your `PATH` (or set `TECTONIC_BIN` to its full path)
- An OpenAI API key

## Setup

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` and fill in `OPENAI_API_KEY` (and optionally `OPENAI_MODEL` / `OPENAI_MODELS` /
`OPENAI_CHAT_MODEL` — the chat model needs to be one your account can use with the `web_search` tool).

If `research/` doesn't already exist (fresh checkout of this repo), create it and `git init` it once:

```
mkdir research
cd research
git init
```

Then put `paper.md` and a `manuscript/` LaTeX template inside it.

## Running

```
.venv\Scripts\python -m uvicorn app.server:app --reload
```

Open http://127.0.0.1:8000.

## Project structure

```
Research Rough Docs.md      generic section-by-section writing guidance (not paper-specific)
research/                   SEPARATE git repo, gitignored here entirely -- your actual paper content
  paper.md                    rough notes (your input)
  manuscript/                 IEEE LaTeX template + generated output + compiled PDF
app/
  server.py                 FastAPI app and routes
  generate.py                notes + guidance -> rewritten manuscript/*.tex via OpenAI
  compile_pdf.py             manuscript/0_main.tex -> PDF via Tectonic
  chat.py                    advisory consultation endpoint
  git_ops.py                 thin git wrapper (commit, log, revert) -- operates on research/, not this repo
  static/                    the single-page frontend (vanilla HTML/JS)
```

The pristine, un-generated section instructions are preserved forever at the `template-baseline` git tag
**inside the `research/` repo**, since `generate.py` overwrites `manuscript/*.tex` on every run —
`git -C research show template-baseline:manuscript/1_Introduction.tex` always gets you the original
skeleton back.
