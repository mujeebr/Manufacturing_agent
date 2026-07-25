"""
agents/orchestrator_agent.py

Purpose
-------
Defines the orchestrator node: the first agent in the graph, invoked
right after the user's message. It calls an OpenAI model with the
orchestrator's system prompt and parses the model's JSON routing
decision into AgentState fields that the graph's conditional edge
(built in graph/workflow.py) uses to pick the next node.
"""

import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import ORCHESTRATOR_MODEL, OPENAI_API_KEY
from agents.prompts.prompts import build_orchestrator_prompt
from graph.state import AgentState

_DEFAULT_ROUTE = "sql_only"  # safe fallback if the model output can't be parsed


def _parse_routing_decision(raw_output: str) -> dict:
    """Parse the orchestrator's JSON response into a route + reason.

    Falls back to `sql_only` if the model didn't return valid JSON, so
    a single malformed response never crashes the whole graph run.
    """
    try:
        parsed = json.loads(raw_output.strip())
        route = parsed.get("route", _DEFAULT_ROUTE)
        reason = parsed.get("reason", "")
        if route not in ("sql_only", "sql_and_visualization"):
            route = _DEFAULT_ROUTE
        return {"route": route, "reason": reason}
    except (json.JSONDecodeError, AttributeError):
        return {"route": _DEFAULT_ROUTE, "reason": "Could not parse routing decision; defaulted to sql_only."}


def orchestrator_node(state: AgentState) -> dict:
    """Classify the user's query and decide the routing path.

    Reads state["user_query"], calls the orchestrator LLM, and returns
    a partial state update setting "route" and "needs_visualization".
    This is the graph entry node right after the user's message.
    """
    llm = ChatOpenAI(model=ORCHESTRATOR_MODEL, api_key=OPENAI_API_KEY, temperature=0)

    system_prompt = build_orchestrator_prompt(task_context=state["user_query"])
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["user_query"]),
    ])

    decision = _parse_routing_decision(response.content)

    return {
        "route": decision["route"],
        "needs_visualization": decision["route"] == "sql_and_visualization",
        "messages": [HumanMessage(content=state["user_query"])],
    }