"""
tools/sql_query_tool.py

Purpose
-------
Defines `sql_query_tool`, the single tool the SQL deep agent calls in
its plan -> query -> reflect loop (this is the `sql_query_tool` node
looping back to "Sql deep agent" in the architecture diagram).

The tool is deliberately restricted to read-only SELECT statements
since this is an analytics workflow, not a data-entry one, and returns
either rows or a clear error string the agent can read and self-correct
from on its next iteration.
"""

import sqlite3

from langchain_core.tools import tool

from config import MANUFACTURING_DB_PATH

# Statements the agent is never allowed to run, even accidentally.
_FORBIDDEN_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE")


def get_schema_description() -> str:
    """Return a human-readable summary of every table and its columns.

    Used to build the SQL deep agent's system prompt so it knows the
    exact table/column names available without ever guessing.
    """
    conn = sqlite3.connect(MANUFACTURING_DB_PATH)
    cursor = conn.cursor()
    tables = [row[0] for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )]

    lines = []
    for table in tables:
        columns = cursor.execute(f"PRAGMA table_info({table})").fetchall()
        col_desc = ", ".join(f"{col[1]} ({col[2]})" for col in columns)
        lines.append(f"- {table}: {col_desc}")

    conn.close()
    return "\n".join(lines)


def _is_read_only(sql: str) -> bool:
    """Check that a SQL statement contains no write/DDL keywords.

    A simple keyword scan is sufficient here because the agent only
    ever needs SELECT statements for analytics; anything else is
    rejected before it reaches the database.
    """
    upper_sql = sql.upper()
    return not any(keyword in upper_sql for keyword in _FORBIDDEN_KEYWORDS)


@tool
def sql_query_tool(sql_query: str) -> str:
    """Execute a read-only SQL SELECT query against the manufacturing database.

    Args:
        sql_query: A single SQLite SELECT statement. Must reference only
            tables/columns that exist in the manufacturing schema.

    Returns:
        A formatted string of the result rows (max 50 shown), or a
        descriptive error message if the query is invalid/rejected so
        the calling agent can revise and retry.
    """
    if not _is_read_only(sql_query):
        return (
            "ERROR: Only read-only SELECT queries are permitted. "
            "Rewrite the query without INSERT/UPDATE/DELETE/DROP/ALTER/CREATE."
        )

    try:
        conn = sqlite3.connect(MANUFACTURING_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        return f"ERROR: SQL execution failed - {exc}. Revise the query and try again."

    if not rows:
        return "Query executed successfully but returned no rows."

    columns = rows[0].keys()
    preview = [dict(row) for row in rows[:50]]
    result_lines = [", ".join(columns)]
    for row in preview:
        result_lines.append(", ".join(str(row[col]) for col in columns))

    footer = f"\n({len(rows)} row(s) total, showing up to 50)" if len(rows) > 50 else f"\n({len(rows)} row(s))"
    return "\n".join(result_lines) + footer


def run_sql_for_state(sql_query: str) -> list[dict]:
    """Execute a SELECT query and return raw rows as a list of dicts.

    Used internally by the SQL deep agent node (not the LLM-facing tool
    above) to store structured results in AgentState.sql_result for the
    visualisation and response agents to consume downstream.
    """
    if not _is_read_only(sql_query):
        raise ValueError("Only read-only SELECT queries are permitted.")

    conn = sqlite3.connect(MANUFACTURING_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(sql_query)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows
