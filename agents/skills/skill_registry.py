"""
agents/skills/skill_registry.py

Purpose
-------
Implements progressive disclosure for skills: agents see only cheap
name+description "menu" entries for their candidate skills by default,
and only the full body of a skill is loaded once it's actually selected
as relevant to the current task.

The extensibility point is SKILL_REGISTRY below: each agent maps to a
LIST of candidate skill filenames. Today every agent has exactly one
skill, so selection is free (no ambiguity, no LLM call). Add a second
filename to any agent's list later and selection automatically starts
doing real work - no other code needs to change.
"""

import json
import re
from pathlib import Path

from config import SKILL_SELECTOR_MODEL, OPENAI_API_KEY

SKILLS_DIR = Path(__file__).resolve().parent

# Agent key -> candidate skill filenames. Add more filenames per agent
# here as new skills are written; nothing else needs to change.
SKILL_REGISTRY: dict[str, list[str]] = {
    "orchestrator": ["orchestrator_skills.md"],
    "sql_deep_agent": ["sql_deep_agent_skills.md"],
    "visualization_subagent": ["visualization_subagent_skills.md"],
    "response_agent": ["response_agent_skills.md"],
}

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def _read_skill_file(filename: str) -> tuple[dict, str]:
    """Read one skill file and split it into (frontmatter dict, body).

    Cheap by design: callers that only need the menu (name/description)
    never have to touch the body text.
    """
    content = (SKILLS_DIR / filename).read_text()
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError(f"{filename} is missing valid '---' frontmatter.")

    frontmatter_raw, body = match.group(1), match.group(2)
    frontmatter = {}
    for line in frontmatter_raw.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()
    return frontmatter, body.strip()


def list_candidate_skills(agent_key: str) -> list[dict]:
    """Return cheap metadata (filename, name, description) for an agent's candidates.

    This is what gets shown to the agent/selector every time - never
    the full skill body - so the "menu" stays small regardless of how
    many skills exist.
    """
    candidates = []
    for filename in SKILL_REGISTRY.get(agent_key, []):
        frontmatter, _ = _read_skill_file(filename)
        candidates.append({
            "filename": filename,
            "name": frontmatter.get("name", filename),
            "description": frontmatter.get("description", ""),
        })
    return candidates


def format_skill_menu(agent_key: str) -> str:
    """Format an agent's candidate skills as a readable bullet list.

    Used both for the LLM-based selection prompt and, if useful, for
    logging/debugging which skills were even considered.
    """
    candidates = list_candidate_skills(agent_key)
    return "\n".join(f"- {c['name']}: {c['description']}" for c in candidates)


def load_skill_body(filename: str) -> str:
    """Load the full body (Overview + Instructions) of one skill file.

    Only called for skills that survived selection - this is the
    "expensive" step that progressive disclosure is designed to avoid
    doing unnecessarily.
    """
    _, body = _read_skill_file(filename)
    return body


def select_relevant_skills(agent_key: str, task_context: str) -> list[str]:
    """Decide which of an agent's candidate skills apply to this task.

    Returns a list of filenames to fully load. If there is only one
    candidate, it's returned immediately with no LLM call - selection
    only costs anything once an agent actually has multiple skills to
    choose between. On any parsing failure, falls back to returning
    ALL candidates (safe default: never silently drop a possibly-needed
    skill).
    """
    candidates = list_candidate_skills(agent_key)
    if len(candidates) <= 1:
        return [c["filename"] for c in candidates]

    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage

    menu = format_skill_menu(agent_key)
    selector_prompt = (
        "You are selecting which skills are relevant to a task. "
        "Respond with valid JSON only: {\"skill_names\": [\"<name>\", ...]}\n\n"
        f"Available skills:\n{menu}"
    )
    llm = ChatOpenAI(model=SKILL_SELECTOR_MODEL, api_key=OPENAI_API_KEY, temperature=0)
    response = llm.invoke([
        SystemMessage(content=selector_prompt),
        HumanMessage(content=f"Task: {task_context}"),
    ])

    try:
        selected_names = set(json.loads(response.content.strip())["skill_names"])
        matched = [c["filename"] for c in candidates if c["name"] in selected_names]
        return matched or [c["filename"] for c in candidates]  # never return empty
    except (json.JSONDecodeError, KeyError, AttributeError):
        return [c["filename"] for c in candidates]  # fail safe: load everything


def load_relevant_skills(agent_key: str, task_context: str) -> str:
    """End-to-end helper: select relevant skills and return their bodies, concatenated.

    This is the single function prompts.py calls per agent - it hides
    the select-then-load two-step behind one call.
    """
    selected_filenames = select_relevant_skills(agent_key, task_context)
    sections = []
    for filename in selected_filenames:
        frontmatter, _ = _read_skill_file(filename)
        body = load_skill_body(filename)
        sections.append(f"## Skill: {frontmatter.get('name', filename)}\n{body}")
    return "\n\n".join(sections)