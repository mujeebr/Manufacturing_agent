"""
agents/visualization_subagent.py

Purpose
-------
Implements the visualisation subagent node. Only runs when the
orchestrator set needs_visualization=True. Asks the LLM to choose a
chart type and the columns to plot given the SQL deep agent's result
rows, then renders the chart with matplotlib and saves it as a PNG.
"""

import json
import uuid
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, safe for server/agent use
import matplotlib.pyplot as plt

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import VISUALIZATION_SUBAGENT_MODEL, OPENAI_API_KEY, BASE_DIR
from agents.prompts.prompts import build_visualization_subagent_prompt
from graph.state import AgentState

CHARTS_DIR = BASE_DIR / "charts"

_PLAN_INSTRUCTION = (
    "\n\n## Response format\n"
    "Given the SQL result rows below, respond with valid JSON only:\n"
    '{"chart_type": "line" | "bar" | "pie" | "scatter" | "none", '
    '"x_column": "<column name or null>", "y_column": "<column name or null>", '
    '"caption": "<one sentence insight, or reason none applies>"}'
)


def _parse_chart_plan(raw_output: str) -> dict:
    """Parse the LLM's chart plan JSON, defaulting to no chart on failure.

    A parsing failure should never crash the graph - it just means no
    chart is produced and the caption explains why.
    """
    try:
        parsed = json.loads(raw_output.strip())
        return {
            "chart_type": parsed.get("chart_type", "none"),
            "x_column": parsed.get("x_column"),
            "y_column": parsed.get("y_column"),
            "caption": parsed.get("caption", "No visualization could be determined."),
        }
    except (json.JSONDecodeError, AttributeError):
        return {"chart_type": "none", "x_column": None, "y_column": None,
                 "caption": "Could not parse a chart plan from the model output."}


def _render_chart(rows: list[dict], plan: dict) -> str:
    """Render the chosen chart type with matplotlib and save it as a PNG.

    Returns the saved file path. Assumes plan["chart_type"] is not
    "none" and plan["x_column"]/["y_column"] exist in rows[0].
    """
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    x_vals = [row[plan["x_column"]] for row in rows]
    y_vals = [row[plan["y_column"]] for row in rows] if plan.get("y_column") else None

    fig, ax = plt.subplots(figsize=(8, 5))
    if plan["chart_type"] == "line":
        ax.plot(x_vals, y_vals, marker="o")
    elif plan["chart_type"] == "bar":
        ax.bar([str(v) for v in x_vals], y_vals)
        plt.xticks(rotation=45, ha="right")
    elif plan["chart_type"] == "pie":
        ax.pie(y_vals, labels=[str(v) for v in x_vals], autopct="%1.1f%%")
    elif plan["chart_type"] == "scatter":
        ax.scatter(x_vals, y_vals)
    else:
        raise ValueError(f"Unsupported chart_type: {plan['chart_type']}")

    ax.set_title(plan.get("caption", "")[:80])
    if plan["chart_type"] != "pie":
        ax.set_xlabel(plan["x_column"])
        ax.set_ylabel(plan.get("y_column", ""))
    fig.tight_layout()

    file_path = CHARTS_DIR / f"chart_{uuid.uuid4().hex[:8]}.png"
    fig.savefig(file_path)
    plt.close(fig)
    return str(file_path)


def visualization_subagent_node(state: AgentState) -> dict:
    """Choose a chart type and render it from the SQL deep agent's results.

    Reads state["sql_result"], asks the LLM to plan an appropriate
    chart, renders it if applicable, and returns chart_path +
    chart_description for the response agent to reference.
    """
    rows = state.get("sql_result") or []
    if not rows:
        return {"chart_path": None, "chart_description": "No data was available to visualize."}

    llm = ChatOpenAI(model=VISUALIZATION_SUBAGENT_MODEL, api_key=OPENAI_API_KEY, temperature=0)
    system_prompt = build_visualization_subagent_prompt(task_context=state["user_query"]) + _PLAN_INSTRUCTION
    sample_rows = rows[:20]  # keep the prompt small; a sample is enough to pick columns

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User question: {state['user_query']}\nSample rows: {sample_rows}"),
    ])
    plan = _parse_chart_plan(response.content)

    if plan["chart_type"] == "none" or not plan.get("x_column"):
        return {"chart_path": None, "chart_description": plan["caption"],
                "messages": [AIMessage(content=response.content)]}

    try:
        chart_path = _render_chart(rows, plan)
    except (KeyError, ValueError) as exc:
        return {"chart_path": None, "chart_description": f"Chart could not be rendered: {exc}",
                "messages": [AIMessage(content=response.content)]}

    return {
        "chart_path": chart_path,
        "chart_description": plan["caption"],
        "messages": [AIMessage(content=response.content)],
    }