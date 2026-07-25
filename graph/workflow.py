"""
graph/workflow.py

Purpose
-------
Wires every agent node into the actual LangGraph StateGraph, matching
the architecture diagram:

    user -> orchestrator agent -> Sql deep agent <-> sql_query_tool
         -> (visualisation sub agent, if routed) -> response agent -> answer

Two production concerns are configured here:
  - Checkpointing: a SqliteSaver persists graph state after every node,
    so a run can be resumed (e.g. after a crash, or after a human
    approves a paused query) instead of starting over.
  - Human-in-the-loop: the graph is compiled with
    interrupt_before=["sql_execute"] (when enabled in config), so it
    pauses right before any SQL touches the database, letting a human
    inspect/approve state["sql_query"] first.
"""

import sqlite3
from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from config import CHECKPOINT_DB_PATH, HUMAN_IN_THE_LOOP_ENABLED
from graph.state import AgentState
from agents.orchestrator_agent import orchestrator_node
from agents.sql_deep_agent import (
    sql_plan_node,
    sql_execute_node,
    sql_force_finish_node,
    sql_deep_agent_router,
)
from agents.visualization_subagent import visualization_subagent_node
from agents.response_agent import response_agent_node


def route_after_plan(state: AgentState) -> Literal["sql_execute", "visualization_subagent", "response_agent"]:
    """Decide the next node right after the plan step.

    If the deep agent isn't finished, the next SQL query needs to run
    (via sql_execute, which is where the HITL interrupt sits). If it
    is finished, branch straight to visualization or response based on
    the orchestrator's earlier decision.
    """
    if not state["sql_agent_finished"]:
        return "sql_execute"
    return "visualization_subagent" if state["needs_visualization"] else "response_agent"


def route_after_execute(state: AgentState) -> Literal["sql_plan", "sql_force_finish", "visualization_subagent", "response_agent"]:
    """Decide the next node right after a query executes.

    Delegates the continue/finish/max_iterations decision to
    sql_deep_agent_router, then resolves "finish" the same way
    route_after_plan does (visualize vs respond).
    """
    decision = sql_deep_agent_router(state)
    if decision == "continue":
        return "sql_plan"
    if decision == "max_iterations":
        return "sql_force_finish"
    return "visualization_subagent" if state["needs_visualization"] else "response_agent"


def route_after_force_finish(state: AgentState) -> Literal["visualization_subagent", "response_agent"]:
    """Decide the next node after the iteration cap forces a stop."""
    return "visualization_subagent" if state["needs_visualization"] else "response_agent"


def build_graph() -> StateGraph:
    """Assemble the full StateGraph: nodes, edges, and conditional routing.

    Returns the uncompiled graph so build_app() can attach a
    checkpointer and HITL interrupt configuration separately - keeping
    "what the graph looks like" separate from "how it's run".
    """
    graph = StateGraph(AgentState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("sql_plan", sql_plan_node)
    graph.add_node("sql_execute", sql_execute_node)
    graph.add_node("sql_force_finish", sql_force_finish_node)
    graph.add_node("visualization_subagent", visualization_subagent_node)
    graph.add_node("response_agent", response_agent_node)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "sql_plan")  # every request always goes through the SQL deep agent

    graph.add_conditional_edges("sql_plan", route_after_plan, {
        "sql_execute": "sql_execute",
        "visualization_subagent": "visualization_subagent",
        "response_agent": "response_agent",
    })
    graph.add_conditional_edges("sql_execute", route_after_execute, {
        "sql_plan": "sql_plan",
        "sql_force_finish": "sql_force_finish",
        "visualization_subagent": "visualization_subagent",
        "response_agent": "response_agent",
    })
    graph.add_conditional_edges("sql_force_finish", route_after_force_finish, {
        "visualization_subagent": "visualization_subagent",
        "response_agent": "response_agent",
    })

    graph.add_edge("visualization_subagent", "response_agent")
    graph.add_edge("response_agent", END)

    return graph


# All agent nodes — used by the Streamlit UI for step-by-step resume.
ALL_AGENT_NODES = [
    "orchestrator",
    "sql_plan",
    "sql_execute",
    "sql_force_finish",
    "visualization_subagent",
    "response_agent",
]


def build_app(interrupt_before: list[str] | None = None):
    """Compile the graph with a SQLite checkpointer and optional interrupts.

    Args:
        interrupt_before: Nodes to pause before. When None (CLI default),
            pauses only before sql_execute if HUMAN_IN_THE_LOOP_ENABLED.
            Pass ALL_AGENT_NODES for Streamlit step-by-step execution.
    """
    graph = build_graph()

    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    if interrupt_before is None:
        interrupt_before = ["sql_execute"] if HUMAN_IN_THE_LOOP_ENABLED else []
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)