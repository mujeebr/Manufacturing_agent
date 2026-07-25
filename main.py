"""
main.py

Purpose
-------
CLI entry point for the Northbridge Precision Manufacturing analytics
system. Prompts the user for a question, runs it through the compiled
LangGraph app, and - when human-in-the-loop is enabled - pauses to let
the user review and approve the SQL deep agent's generated query
before it touches the database.

Run with:
    python main.py
"""

import uuid

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

from config import validate_config, HUMAN_IN_THE_LOOP_ENABLED
from graph.workflow import build_app
from graph.state import initial_state

console = Console()


def print_banner() -> None:
    """Print a short startup banner identifying the system."""
    console.print(Panel.fit(
        "[bold]Northbridge Precision Manufacturing[/bold]\nAnalytics Assistant "
        "(orchestrator -> SQL deep agent -> visualisation -> response)",
        border_style="cyan",
    ))


def handle_human_approval(app, run_config: dict, state: dict) -> dict:
    """Show the paused SQL query to the user and get approve/edit/reject.

    Called only when the graph has paused before sql_execute (HITL
    enabled). Loops until the user approves or rejects, since an
    "edit" just re-poses the same choice with the modified query.
    """
    while True:
        console.print(Panel(
            state["sql_query"], title="Generated SQL - awaiting your approval", border_style="yellow"
        ))
        choice = Prompt.ask("Approve this query?", choices=["approve", "edit", "reject"], default="approve")

        if choice == "approve":
            app.update_state(run_config, {"sql_query_approved": True})
            return app.invoke(None, run_config)

        if choice == "edit":
            edited_query = Prompt.ask("Enter the revised SQL query")
            app.update_state(run_config, {"sql_query": edited_query, "sql_query_approved": True})
            return app.invoke(None, run_config)

        # reject: end this query attempt without hitting the database, and
        # let the deep agent's own loop try a different approach next round
        app.update_state(run_config, {
            "sql_query_approved": False,
            "sql_agent_finished": True,
            "sql_summary": "The user rejected the proposed query, so no data was retrieved.",
        })
        return app.invoke(None, run_config)


def run_query(app, user_query: str) -> dict:
    """Run one user question through the graph end-to-end.

    Creates a fresh thread_id per question (so checkpoints don't bleed
    between unrelated questions), invokes the graph, and resolves any
    human-in-the-loop pause before returning the final state.
    """
    run_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    state = initial_state(user_query)

    result = app.invoke(state, run_config)

    # A paused-for-approval state has no final_answer yet; resolve it.
    while HUMAN_IN_THE_LOOP_ENABLED and result.get("final_answer") is None and result.get("sql_query"):
        result = handle_human_approval(app, run_config, result)

    return result


def print_result(result: dict) -> None:
    """Print the final answer, and the chart path if one was generated."""
    console.print(Panel(Markdown(result["final_answer"] or "No answer was produced."),
                         title="Answer", border_style="green"))
    if result.get("chart_path"):
        console.print(f"[dim]Chart saved to: {result['chart_path']}[/dim]")


def main() -> None:
    """Entry point: validate config, build the app, and loop on user input."""
    validate_config()
    print_banner()
    app = build_app()

    console.print("[dim]Type your question, or 'exit' to quit.[/dim]\n")
    while True:
        user_query = Prompt.ask("[bold cyan]Ask a question[/bold cyan]")
        if user_query.strip().lower() in ("exit", "quit"):
            break

        result = run_query(app, user_query)
        print_result(result)
        console.print()


if __name__ == "__main__":
    main()