"""
agents/response_agent.py

Purpose
-------
Implements the final node in the graph: synthesizes the SQL deep
agent's summary/results and (if present) the visualisation subagent's
chart into one direct natural-language answer for the user. This is
the "response agent -> answer" edge in the architecture diagram.
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import RESPONSE_AGENT_MODEL, OPENAI_API_KEY
from agents.prompts.prompts import build_response_agent_prompt
from graph.state import AgentState


def _build_context_message(state: AgentState) -> str:
    """Assemble the upstream results into one context block for the LLM.

    Keeps response_agent_node itself simple by isolating the string
    formatting of sql_summary/sql_result/chart info into one place.
    """
    parts = [f"Original question: {state['user_query']}"]

    if state.get("sql_summary"):
        parts.append(f"SQL deep agent summary: {state['sql_summary']}")
    if state.get("sql_result"):
        parts.append(f"Result rows (sample): {state['sql_result'][:10]}")
    if state.get("chart_path"):
        parts.append(
            f"A chart was generated at {state['chart_path']} with insight: {state['chart_description']}"
        )
    elif state.get("chart_description"):
        parts.append(f"Visualization note: {state['chart_description']}")

    return "\n\n".join(parts)


def response_agent_node(state: AgentState) -> dict:
    """Produce the final answer shown to the user.

    Reads all upstream results from state, calls the response agent
    LLM with the assembled context, and stores the result in
    state["final_answer"].
    """
    llm = ChatOpenAI(model=RESPONSE_AGENT_MODEL, api_key=OPENAI_API_KEY, temperature=0.3)
    system_prompt = build_response_agent_prompt(task_context=state["user_query"])
    context = _build_context_message(state)

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=context),
    ])

    return {
        "final_answer": response.content,
        "messages": [AIMessage(content=response.content)],
    }