import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Actual paper content lives in its own gitignored, dedicated git repo, kept
# separate from this app's repo so it's never pushed to GitHub with it.
RESEARCH_DIR = PROJECT_ROOT / "research"
MANUSCRIPT_DIR = RESEARCH_DIR / "manuscript"
PAPER_MD = RESEARCH_DIR / "paper.md"
ROUGH_DOCS_MD = PROJECT_ROOT / "Research Rough Docs.md"
MAIN_TEX = MANUSCRIPT_DIR / "0_main.tex"
MAIN_PDF = MANUSCRIPT_DIR / "0_main.pdf"
REFERENCES_JSON = RESEARCH_DIR / "references.json"
FIGURES_DIR = MANUSCRIPT_DIR / "100_Figures"

load_dotenv(PROJECT_ROOT / ".env")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
# Comma-separated list of models offered in the UI dropdown. Adjust to whatever
# your OpenAI account actually has access to.
SELECTABLE_MODELS = [
    m.strip()
    for m in os.environ.get("OPENAI_MODELS", DEFAULT_MODEL).split(",")
    if m.strip()
]
# Model used for the consultant chat, via the Responses API's web_search tool
# (needs a model on your account that supports it). Separate from DEFAULT_MODEL
# since generate.py needs structured JSON output, not web search.
CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", DEFAULT_MODEL)

# The tag of the commit holding the pristine, un-generated section skeletons
# (see PLAN.md). Section instructions are read from this tag via `git show`
# rather than from the working tree, since the working tree gets overwritten
# with generated content on every `generate` run.
TEMPLATE_TAG = "template-baseline"

# Numbered LaTeX section files that get fully rewritten by generate.py, in
# document order. The abstract (inside 0_main.tex) is handled separately.
SECTION_FILES = [
    "1_Introduction",
    "2_Background",
    "3_StudyDesign",
    "4_Results",
    "5_Discussion",
    "6_RelatedWork",
    "7_Threats",
    "8_Conclusion",
]

# All editable LaTeX files (the numbered sections plus the wrapper 0_main.tex
# that holds the abstract/title/includes), in document order.
ALL_TEX_FILES = ["0_main", *SECTION_FILES]
