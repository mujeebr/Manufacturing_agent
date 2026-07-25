"""
streamlit_app.py

Streamlit UI for the manufacturing multi-agent system:
  - Left:  chat + answers / charts + step controls / SQL approval
  - Right: live architecture diagram highlighting the active agent

Every agent node is compiled with interrupt_before, so the run pauses
after routing to the next node. Click "Run next step" to resume one node
at a time and watch the token move through the graph.

Run with:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from config import validate_config
from graph.state import initial_state
from graph.workflow import ALL_AGENT_NODES, build_app

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Northbridge Analytics",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

NODE_LABELS = {
    "orchestrator": "Orchestrator",
    "sql_plan": "SQL Plan",
    "sql_execute": "SQL Execute",
    "sql_force_finish": "Force Finish",
    "visualization_subagent": "Visualization",
    "response_agent": "Response",
}


@st.cache_resource
def get_step_app():
    """One compiled graph with interrupts before every agent node."""
    validate_config()
    return build_app(interrupt_before=list(ALL_AGENT_NODES))


def _init_session() -> None:
    defaults = {
        "thread_id": None,
        "run_active": False,
        "run_done": False,
        "visited": [],          # nodes that have finished at least once
        "next_nodes": [],       # nodes LangGraph will run on next resume
        "step_log": [],         # human-readable log of completed steps
        "chat": [],             # [{role, content, chart_path?}]
        "snapshot_values": {},
        "sql_approved": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _config() -> dict:
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _refresh_snapshot(app) -> None:
    snap = app.get_state(_config())
    st.session_state.snapshot_values = dict(snap.values or {})
    st.session_state.next_nodes = list(snap.next or [])
    st.session_state.run_done = st.session_state.run_active and not snap.next
    if st.session_state.run_done:
        st.session_state.run_active = False


def _describe_step(node: str, values: dict) -> str:
    """Short summary of what a completed node produced."""
    if node == "orchestrator":
        route = values.get("route") or "?"
        return f"Routed to **{route}**"
    if node == "sql_plan":
        if values.get("sql_agent_finished"):
            return f"Finished planning — { (values.get('sql_summary') or '')[:120] }"
        return f"Proposed SQL:\n```sql\n{values.get('sql_query') or ''}\n```"
    if node == "sql_execute":
        rows = values.get("sql_result")
        if rows is None:
            return "Execution skipped or failed"
        return f"Returned **{len(rows)}** row(s)"
    if node == "sql_force_finish":
        return f"Hit iteration cap — { (values.get('sql_summary') or '')[:120] }"
    if node == "visualization_subagent":
        path = values.get("chart_path")
        cap = values.get("chart_description") or ""
        return f"Chart: `{path}` — {cap}" if path else f"No chart — {cap}"
    if node == "response_agent":
        return values.get("final_answer") or "No answer"
    return "Done"


def _start_run(app, question: str) -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.run_active = True
    st.session_state.run_done = False
    st.session_state.visited = []
    st.session_state.step_log = []
    st.session_state.sql_approved = False
    st.session_state.chat.append({"role": "user", "content": question})

    # First invoke pauses before orchestrator (interrupt_before).
    app.invoke(initial_state(question), _config())
    _refresh_snapshot(app)


def _run_next_step(app) -> None:
    """Resume the graph so exactly one agent node executes, then pause again."""
    next_nodes = st.session_state.next_nodes
    if not next_nodes:
        return

    upcoming = next_nodes[0]

    # Gate SQL execute until the user has approved / edited the query.
    if upcoming == "sql_execute" and not st.session_state.sql_approved:
        values = st.session_state.snapshot_values
        if not values.get("sql_query_approved"):
            st.warning("Approve, edit, or reject the SQL query before running SQL Execute.")
            return

    app.invoke(None, _config())
    _refresh_snapshot(app)

    # Mark the node we just ran as visited and log its output.
    values = st.session_state.snapshot_values
    if upcoming not in st.session_state.visited:
        st.session_state.visited.append(upcoming)
    st.session_state.step_log.append(
        {"node": upcoming, "summary": _describe_step(upcoming, values)}
    )
    st.session_state.sql_approved = False  # re-approve each new query

    # When the whole run finishes, push the final answer into the chat.
    if st.session_state.run_done:
        answer = values.get("final_answer") or "No answer was produced."
        chart = values.get("chart_path")
        st.session_state.chat.append(
            {"role": "assistant", "content": answer, "chart_path": chart}
        )


def _approve_sql(app, edited: str | None = None) -> None:
    update = {"sql_query_approved": True}
    if edited is not None:
        update["sql_query"] = edited
    app.update_state(_config(), update)
    st.session_state.sql_approved = True
    _refresh_snapshot(app)


def _reject_sql(app) -> None:
    app.update_state(
        _config(),
        {
            "sql_query_approved": False,
            "sql_agent_finished": True,
            "sql_summary": "The user rejected the proposed query, so no data was retrieved.",
        },
    )
    # Still need to run sql_execute (skip path) — mark approved-for-resume
    # so the Next button can proceed; the node itself will not hit the DB.
    st.session_state.sql_approved = True
    _refresh_snapshot(app)


# ---------------------------------------------------------------------------
# Architecture diagram (right panel)
# ---------------------------------------------------------------------------

def _mermaid_diagram(visited: list[str], next_nodes: list[str], done: bool) -> str:
    active = next_nodes[0] if next_nodes else None

    def cls(node: str) -> str:
        if done and node in visited:
            return ":::done"
        if node == active:
            return ":::active"
        if node in visited:
            return ":::done"
        return ":::idle"

    # Keep topology identical to graph/workflow.py
    return f"""
flowchart TD
    START([START]) --> orch[Orchestrator]{cls("orchestrator")}
    orch --> plan[SQL Plan]{cls("sql_plan")}
    plan --> rp{{route_after_plan}}
    rp -->|query| exec[SQL Execute]{cls("sql_execute")}
    rp -->|viz| viz[Visualization]{cls("visualization_subagent")}
    rp -->|answer| resp[Response]{cls("response_agent")}
    exec --> re{{route_after_execute}}
    re -->|loop| plan
    re -->|cap| force[Force Finish]{cls("sql_force_finish")}
    re -->|viz| viz
    re -->|answer| resp
    force --> rf{{route}}
    rf -->|viz| viz
    rf -->|answer| resp
    viz --> resp
    resp --> END([END])

    classDef idle fill:#e8eef5,stroke:#7a8ea3,color:#1a2a3a,stroke-width:1px
    classDef active fill:#f5a623,stroke:#c47a00,color:#1a1200,stroke-width:3px
    classDef done fill:#2ecc71,stroke:#1e8449,color:#0b2e1a,stroke-width:2px
"""


def _render_architecture(visited: list[str], next_nodes: list[str], done: bool) -> None:
    diagram = _mermaid_diagram(visited, next_nodes, done)
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    body {{ margin: 0; background: #0f1720; font-family: ui-sans-serif, system-ui, sans-serif; }}
    .legend {{ color: #c5d0dc; font-size: 12px; padding: 8px 4px 12px; display: flex; gap: 14px; }}
    .swatch {{ display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 5px; vertical-align: middle; }}
    #graph {{ padding: 4px; }}
  </style>
</head>
<body>
  <div class="legend">
    <span><span class="swatch" style="background:#e8eef5"></span>Waiting</span>
    <span><span class="swatch" style="background:#f5a623"></span>Next / active</span>
    <span><span class="swatch" style="background:#2ecc71"></span>Completed</span>
  </div>
  <div id="graph" class="mermaid">
{diagram}
  </div>
  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "dark", securityLevel: "loose" }});
  </script>
</body>
</html>
"""
    components.html(html, height=620, scrolling=True)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_init_session()
app = get_step_app()

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
      div[data-testid="stHorizontalBlock"] > div { align-items: stretch; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Northbridge Precision Manufacturing")
st.caption("Step through the LangGraph agents — chat on the left, live architecture on the right.")

left, right = st.columns([1.15, 1], gap="large")

# ----- Left: chat + controls ----------------------------------------------
with left:
    st.subheader("Chat")

    chat_box = st.container(height=360)
    with chat_box:
        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                chart = msg.get("chart_path")
                if chart and Path(chart).exists():
                    st.image(chart, use_container_width=True)

    question = st.chat_input(
        "Ask a manufacturing analytics question…",
        disabled=st.session_state.run_active,
    )
    if question:
        _start_run(app, question)
        st.rerun()

    st.divider()
    st.subheader("Step controls")

    values = st.session_state.snapshot_values
    next_nodes = st.session_state.next_nodes
    upcoming = next_nodes[0] if next_nodes else None

    if st.session_state.run_active or st.session_state.run_done:
        if upcoming:
            st.info(f"**Next node:** `{NODE_LABELS.get(upcoming, upcoming)}`")
        elif st.session_state.run_done:
            st.success("Run complete.")

        # SQL approval gate when paused before sql_execute
        if upcoming == "sql_execute" and not st.session_state.sql_approved:
            st.markdown("#### SQL awaiting approval")
            sql = values.get("sql_query") or ""
            st.code(sql, language="sql")
            edited = st.text_area("Edit SQL (optional)", value=sql, height=100)
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Approve", type="primary", use_container_width=True):
                    _approve_sql(app)
                    st.rerun()
            with c2:
                if st.button("Approve edited", use_container_width=True):
                    _approve_sql(app, edited=edited)
                    st.rerun()
            with c3:
                if st.button("Reject", use_container_width=True):
                    _reject_sql(app)
                    st.rerun()

        cols = st.columns(2)
        with cols[0]:
            can_step = bool(upcoming) and (
                upcoming != "sql_execute" or st.session_state.sql_approved
            )
            if st.button(
                "▶ Run next step",
                type="primary",
                disabled=not can_step,
                use_container_width=True,
            ):
                with st.spinner(f"Running {NODE_LABELS.get(upcoming, upcoming)}…"):
                    _run_next_step(app)
                st.rerun()
        with cols[1]:
            if st.button("Reset run", use_container_width=True):
                for key in (
                    "thread_id", "run_active", "run_done", "visited",
                    "next_nodes", "step_log", "snapshot_values", "sql_approved",
                ):
                    st.session_state[key] = (
                        [] if key in ("visited", "next_nodes", "step_log")
                        else {} if key == "snapshot_values"
                        else False if key in ("run_active", "run_done", "sql_approved")
                        else None
                    )
                st.rerun()
    else:
        st.write("Ask a question above to start a stepped graph run.")

    if st.session_state.step_log:
        st.markdown("#### Step log")
        for i, entry in enumerate(st.session_state.step_log, 1):
            label = NODE_LABELS.get(entry["node"], entry["node"])
            with st.expander(f"{i}. {label}", expanded=(i == len(st.session_state.step_log))):
                st.markdown(entry["summary"])
                if entry["node"] == "visualization_subagent":
                    path = values.get("chart_path")
                    if path and Path(path).exists():
                        st.image(path, use_container_width=True)
                if entry["node"] == "response_agent" and values.get("chart_path"):
                    path = values["chart_path"]
                    if Path(path).exists():
                        st.image(path, use_container_width=True)

# ----- Right: live architecture -------------------------------------------
with right:
    st.subheader("Architecture — live path")
    status = (
        "complete" if st.session_state.run_done
        else ("running" if st.session_state.run_active else "idle")
    )
    st.caption(f"Status: **{status}**")
    if upcoming:
        st.caption(f"Highlighting next: **{NODE_LABELS.get(upcoming, upcoming)}**")

    _render_architecture(
        visited=st.session_state.visited,
        next_nodes=st.session_state.next_nodes,
        done=st.session_state.run_done,
    )

    if values:
        with st.expander("Current state snapshot", expanded=False):
            st.json(
                {
                    "route": values.get("route"),
                    "needs_visualization": values.get("needs_visualization"),
                    "sql_agent_finished": values.get("sql_agent_finished"),
                    "sql_deep_agent_iterations": values.get("sql_deep_agent_iterations"),
                    "sql_query": values.get("sql_query"),
                    "sql_query_approved": values.get("sql_query_approved"),
                    "chart_path": values.get("chart_path"),
                    "has_final_answer": bool(values.get("final_answer")),
                    "row_count": len(values["sql_result"]) if values.get("sql_result") else 0,
                }
            )
