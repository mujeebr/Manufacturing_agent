"""
config.py

Purpose
-------
Single source of truth for configuration used across the whole
Manufacturing Multi-Agent System: API keys, which OpenAI model each
agent uses, and the file paths of the two SQLite databases:

  1. manufacturing.db  -> business data the SQL deep agent queries
  2. checkpoints.db     -> LangGraph's persistence layer (used for
                            resuming runs and human-in-the-loop pauses)

Every other module imports from here instead of reading os.environ
directly, so there is exactly one place to change models or paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables from a local .env file (OPENAI_API_KEY=...) if present.
load_dotenv()

# --- Project paths -----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"

MANUFACTURING_DB_PATH = str(DATABASE_DIR / "manufacturing.db")
CHECKPOINT_DB_PATH = str(DATABASE_DIR / "checkpoints.db")

# --- OpenAI credentials --------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Model assignment per agent ------------------------------------------
# Different agents can use different model sizes to balance cost/latency.
# The orchestrator and deep agent do the most reasoning, so they get the
# stronger model; the response agent just needs to write clean prose.
ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "gpt-4o")
SQL_DEEP_AGENT_MODEL = os.getenv("SQL_DEEP_AGENT_MODEL", "gpt-4o")
VISUALIZATION_SUBAGENT_MODEL = os.getenv("VISUALIZATION_SUBAGENT_MODEL", "gpt-4o-mini")
RESPONSE_AGENT_MODEL = os.getenv("RESPONSE_AGENT_MODEL", "gpt-4o-mini")

# Cheap/fast model used only to pick which skill(s) apply to a task when an
# agent has more than one candidate skill registered (see skill_registry.py).
SKILL_SELECTOR_MODEL = os.getenv("SKILL_SELECTOR_MODEL", "gpt-4o-mini")

# --- Human-in-the-loop toggle ---------------------------------------------
# When True, the graph pauses before the SQL deep agent executes a
# generated query so a human can approve/edit/reject it. Set to False
# for fully autonomous runs (e.g. automated testing).
HUMAN_IN_THE_LOOP_ENABLED = os.getenv("HUMAN_IN_THE_LOOP_ENABLED", "true").lower() == "true"

# --- Deep agent behavior -----------------------------------------------
# Max number of plan -> query -> reflect loops the SQL deep agent may take
# before it is forced to give up and report what it has.
SQL_DEEP_AGENT_MAX_ITERATIONS = int(os.getenv("SQL_DEEP_AGENT_MAX_ITERATIONS", "4"))


def validate_config() -> None:
    """Raise a clear error early if required configuration is missing.

    Called once at program startup (main.py) so failures happen before
    any graph nodes run, instead of deep inside an agent call.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a .env file with "
            "OPENAI_API_KEY=sk-... or export it in your shell."
        )
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)