"""
agents/sql_deep_agent.py

Purpose
-------
Implements the "deep agent" from the architecture diagram as two
LangGraph nodes plus a routing function:

  - sql_plan_node:    decides the next SQL query to run, or that it is
                       done and ready to summarize (plan + reflect steps)
  - sql_execute_node: runs the approved query via sql_query_tool
                       (query step), which is the "sql_query_tool" box
                       looping back to "Sql deep agent" in the diagram
  - sql_deep_agent_router: tells the graph whether to loop back to
                       sql_plan_node, stop, or force-stop at the
                       iteration cap

The human-in-the-loop pause happens *between* plan and execute: the
graph (workflow.py) interrupts before sql_execute_node so a human can
review/approve state["sql_query"] before it touches the database.
"""

import json
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import SQL_DEEP_AGENT_MODEL, OPENAI_API_KEY, SQL_DEEP_AGENT_MAX_ITERATIONS
from agents.prompts.prompts import build_sql_deep_agent_prompt
from tools.sql_query_tool import get_schema_description, run_sql_for_state
from graph.state import AgentState

_FALLBACK_SUMMARY = (
    "I was unable to fully answer this within the allowed number of "
    "query attempts. Here is the most recent data I retrieved, which "
    "may only partially answer the question."
)


def _parse_plan_decision(raw_output: str) -> dict:
    """Parse the deep agent's JSON plan step into a structured action.

    Falls back to a "final" action with a generic summary if the model
    output isn't valid JSON, so a parsing failure ends the loop safely
    instead of crashing or looping forever.
    """
    try:
        parsed = json.loads(raw_output.strip())
        if parsed.get("action") == "query" and parsed.get("sql_query"):
            return {"action": "query", "sql_query": parsed["sql_query"], "thought": parsed.get("thought", "")}
        if parsed.get("action") == "final":
            return {"action": "final", "summary": parsed.get("summary", _FALLBACK_SUMMARY)}
    except (json.JSONDecodeError, AttributeError):
        pass
    return {"action": "final", "summary": _FALLBACK_SUMMARY}


def sql_plan_node(state: AgentState) -> dict:
    """Decide the next SQL query to run, or conclude the loop.

    Calls the SQL deep agent LLM with the full conversation so far
    (original question + any prior query/result exchanges) and parses
    its JSON decision into the next state update.
    """
    llm = ChatOpenAI(model=SQL_DEEP_AGENT_MODEL, api_key=OPENAI_API_KEY, temperature=0)
    system_prompt = build_sql_deep_agent_prompt(
        task_context=state["user_query"], schema_description=get_schema_description()
    )

    response = llm.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    decision = _parse_plan_decision(response.content)

    if decision["action"] == "query":
        return {
            "sql_query": decision["sql_query"],
            "sql_query_approved": False,  # reset so the HITL gate re-checks each new query
            "sql_agent_finished": False,
            "messages": [AIMessage(content=response.content)],
        }

    return {
        "sql_agent_finished": True,
        "sql_summary": decision["summary"],
        "messages": [AIMessage(content=response.content)],
    }


def sql_execute_node(state: AgentState) -> dict:
    """Execute the approved SQL query and record the result as an observation.

    Only reached once state["sql_query_approved"] is True (enforced by
    the human-in-the-loop interrupt configured in workflow.py). Errors
    are captured as a text observation rather than raised, so the plan
    node can see and react to them on its next iteration.

    Defensively re-checks approval itself: if this node is ever reached
    with sql_query_approved False (e.g. a human rejected the query),
    it skips execution entirely rather than trusting the graph's
    control flow alone to have enforced that.
    """
    if not state.get("sql_query_approved", False):
        return {
            "sql_result": None,
            "sql_deep_agent_iterations": 1,
            "messages": [HumanMessage(content="[Tool observation] Query was not approved; execution skipped.")],
        }

    sql_query = state["sql_query"]
    try:
        rows = run_sql_for_state(sql_query)
        observation = f"Query executed successfully. Rows returned: {len(rows)}.\nSample: {rows[:5]}"
        result_update = {"sql_result": rows}
    except Exception as exc:  # noqa: BLE001 - deliberately broad; fed back to the agent as text
        observation = f"ERROR: Query failed - {exc}. Revise the query."
        result_update = {"sql_result": None}

    return {
        **result_update,
        "sql_deep_agent_iterations": 1,  # merged via operator.add reducer
        "messages": [HumanMessage(content=f"[Tool observation]\n{observation}")],
    }


def sql_deep_agent_router(state: AgentState) -> Literal["continue", "finish", "max_iterations"]:
    """Decide whether the loop continues, stops normally, or is force-stopped.

    Used by the graph's conditional edge after sql_execute_node to
    route back to sql_plan_node, or forward to the next stage.
    """
    if state["sql_agent_finished"]:
        return "finish"
    if state["sql_deep_agent_iterations"] >= SQL_DEEP_AGENT_MAX_ITERATIONS:
        return "max_iterations"
    return "continue"


def sql_force_finish_node(state: AgentState) -> dict:
    """Produce a fallback summary when the iteration cap is hit.

    Ensures the graph always has a sql_summary to hand downstream, even
    when the deep agent never emitted its own "final" action in time.
    """
    summary = state.get("sql_summary") or _FALLBACK_SUMMARY
    return {"sql_agent_finished": True, "sql_summary": summary}