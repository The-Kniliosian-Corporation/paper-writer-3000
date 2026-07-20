import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Every paper lives in its own project directory under here, each a separate,
# gitignored, dedicated git repo -- never pushed to this app's GitHub remote.
# See app/projects.py.
PROJECTS_ROOT = PROJECT_ROOT / "projects"
# Bundled generic IEEEtran skeleton copied into every newly-created project
# (see app/projects.py:create_project). Extracted from the pristine
# template-baseline tag of the original single-project research/ repo, minus
# setting_variable.tex (which held that paper's real macros/data and was
# replaced with an empty placeholder) -- verified generic before bundling.
STARTER_TEMPLATE_DIR = Path(__file__).resolve().parent / "starter_templates" / "ieee_default"
ROUGH_DOCS_MD = PROJECT_ROOT / "Research Rough Docs.md"

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

# Default template structure, used by manifest.py whenever a project's
# manuscript/ has no template_manifest.json of its own. This matches the
# bundled starter template's layout, so both newly-created projects (which
# get a manifest written at creation time) and the migrated legacy project
# (which predates the manifest file and relies on this fallback) resolve to
# the same structure.
DEFAULT_MAIN_FILE = "0_main"
DEFAULT_SECTION_FILES = [
    "1_Introduction",
    "2_Background",
    "3_StudyDesign",
    "4_Results",
    "5_Discussion",
    "6_RelatedWork",
    "7_Threats",
    "8_Conclusion",
]
DEFAULT_HAS_ABSTRACT = True
