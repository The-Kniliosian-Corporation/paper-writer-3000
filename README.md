# paper-writer-3000

Write rough, informal research notes in [`paper.md`](paper.md); generate a polished, submission-ready
IEEE-conference LaTeX paper (and a compiled PDF) from them on demand, with every change tracked in git so
nothing is ever lost.

See [PLAN.md](PLAN.md) for the full design rationale and decisions behind the app.

## How it works

- **Save** — edit `paper.md` in the web UI, hit Save. Writes the file and commits it. No LLM call.
- **Generate** — hit Generate (pick a model first if you like). Sends your notes, plus the paper's
  section-by-section writing guidance, to OpenAI; writes the rewritten LaTeX into `manuscript/*.tex`;
  compiles it to `manuscript/0_main.pdf` with Tectonic; commits the regenerated `.tex` files.
- **History** — every save and generate is a real git commit. The history panel lists them; "revert notes
  here" restores `paper.md` to an earlier point as a new commit (nothing is destroyed).
- **Consult** — a chat panel for talking through direction, gaps, and framing with the same model. It's
  advisory only: it can see your notes and generated paper for context but never edits files itself.

The model never invents citations, numbers, or claims that aren't in your notes — where something's
missing it inserts the template's existing `\citeme`, `\fillme`, or `\TODO{...}` placeholders instead.

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

Then open `.env` and fill in `OPENAI_API_KEY` (and optionally `OPENAI_MODEL` / `OPENAI_MODELS`).

## Running

```
.venv\Scripts\python -m uvicorn app.server:app --reload
```

Open http://127.0.0.1:8000.

## Project structure

```
paper.md                    rough notes (your input)
Research Rough Docs.md      section-by-section writing guidance
manuscript/                 IEEE LaTeX template + generated output + compiled PDF
app/
  server.py                 FastAPI app and routes
  generate.py                paper.md + guidance -> rewritten manuscript/*.tex via OpenAI
  compile_pdf.py             manuscript/0_main.tex -> manuscript/0_main.pdf via Tectonic
  chat.py                    advisory consultation endpoint
  git_ops.py                 thin git wrapper (commit, log, revert)
  static/                    the single-page frontend (vanilla HTML/JS)
```

The pristine, un-generated section instructions are preserved forever at the `template-baseline` git tag,
since `generate.py` overwrites `manuscript/*.tex` on every run — `git show template-baseline:manuscript/1_Introduction.tex`
always gets you the original skeleton back.
