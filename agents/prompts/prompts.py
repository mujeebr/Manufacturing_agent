"""
agents/prompts/prompts.py

Purpose
-------
Assembles the final system prompt sent to the LLM for each graph node.

Each build_*_prompt() function layers three things:
  1. Persona/identity   - who this node is, written here (not in a skill)
  2. Relevant skill(s)  - loaded dynamically via skill_registry, which
                           decides at call time which of the agent's
                           candidate skills actually apply to this task
                           (progressive disclosure - see skill_registry.py)
  3. Graph plumbing      - tool names, state fields, output format,
                            which only make sense inside this graph

task_context (usually the user's query) is passed into every builder
so skill selection can be task-aware once an agent has more than one
candidate skill registered.
"""

from agents.skills.skill_registry import load_relevant_skills


def build_orchestrator_prompt(task_context: str) -> str:
    """Assemble the orchestrator node's full system prompt.

    Persona + graph plumbing are written here; the routing procedure
    is dynamically loaded from the orchestrator's candidate skill(s).
    """
    persona = (
        "You are the Orchestrator node in a LangGraph multi-agent system "
        "for Northbridge Precision Manufacturing analytics. You sit "
        "directly after the user's message and before any specialist "
        "agent runs. You do not answer questions or query data yourself."
    )
    skills = load_relevant_skills("orchestrator", task_context)
    graph_plumbing = (
        "\n\n## How your output is used\n"
        "Your output is parsed programmatically by the graph to decide "
        "which node runs next (sql_deep_agent, then optionally "
        "visualisation_subagent). It is never shown to the user directly.\n\n"
        "## Response format\n"
        "Respond with valid JSON only, no other text:\n"
        '{"route": "sql_only" | "sql_and_visualization", "reason": "<one short sentence>"}'
    )
    return f"{persona}\n\n{skills}{graph_plumbing}"


def build_sql_deep_agent_prompt(task_context: str, schema_description: str) -> str:
    """Assemble the SQL deep agent node's full system prompt.

    Injects the live database schema and names the exact tool this
    node has access to; the SQL procedure itself is dynamically loaded
    from the agent's candidate skill(s).
    """
    persona = (
        "You are the SQL Deep Agent node in a LangGraph multi-agent "
        "system for Northbridge Precision Manufacturing analytics. You "
        "run after the orchestrator has routed a request to you, and "
        "your output feeds either the visualisation subagent or the "
        "response agent next."
    )
    skills = load_relevant_skills("sql_deep_agent", task_context)
    graph_plumbing = (
        "\n\n## Tool available to you\n"
        "`sql_query_tool(sql_query: str)` - executes one read-only SELECT "
        "statement against the manufacturing database and returns the "
        "result rows or an error string.\n\n"
        f"## Database schema\n{schema_description}"
        "\n\n## Response format\n"
        "At each step, respond with valid JSON only, no other text:\n"
        '{"action": "query", "sql_query": "<one SELECT statement>", "thought": "<why this query>"}\n'
        "or, once you have a fully confident answer:\n"
        '{"action": "final", "summary": "<plain-language paragraph summarizing the answer>"}'
    )
    return f"{persona}\n\n{skills}{graph_plumbing}"


def build_visualization_subagent_prompt(task_context: str) -> str:
    """Assemble the visualisation subagent node's full system prompt."""
    persona = (
        "You are the Visualisation Subagent node in a LangGraph "
        "multi-agent system for Northbridge Precision Manufacturing "
        "analytics. You are only invoked when the orchestrator routed "
        "the request to sql_and_visualization, and you receive the SQL "
        "deep agent's result rows as input."
    )
    skills = load_relevant_skills("visualization_subagent", task_context)
    graph_plumbing = (
        "\n\n## What happens to your output\n"
        "The chart file path and caption you return are passed to the "
        "response agent, which will reference them in the final answer "
        "shown to the user."
    )
    return f"{persona}\n\n{skills}{graph_plumbing}"


def build_response_agent_prompt(task_context: str) -> str:
    """Assemble the response agent node's full system prompt."""
    persona = (
        "You are the Response Agent node in a LangGraph multi-agent "
        "system for Northbridge Precision Manufacturing analytics. You "
        "are the final node before the user sees an answer - there is "
        "no further agent to clean up or correct your output."
    )
    skills = load_relevant_skills("response_agent", task_context)
    graph_plumbing = (
        "\n\n## Inputs available to you\n"
        "The SQL deep agent's data summary and result rows, and - if "
        "the visualisation subagent ran - a chart file path and caption."
    )
    return f"{persona}\n\n{skills}{graph_plumbing}"