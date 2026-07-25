---
name: sql-deep-agent
description: Use this skill to answer questions about Northbridge Precision Manufacturing's operational data by iteratively planning, generating, and executing read-only SQL against the manufacturing SQLite database.
---
# sql-deep-agent

## Overview
This skill explains how to act as a "deep agent" for SQL analytics:
instead of writing one query and stopping, work in a loop — plan,
query, observe, reflect, and retry if needed — until the question is
answered with real data from the manufacturing database, or the
iteration limit is reached.

## Instructions

### 1. Plan
Restate what data is needed and which tables/columns/joins will
provide it, using the schema description provided in context. Never
guess a table or column name that "sounds right" — only use names that
appear in the schema.

### 2. Query
Call `sql_query_tool` with one precise, read-only SELECT statement.
- Never write INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
- Use explicit JOINs with ON clauses.
- Prefer aggregates (COUNT, AVG, SUM, GROUP BY) for totals/trends/comparisons.
- Add LIMIT clauses for "top N" or "worst performing" style rankings.
- Dates are stored as ISO strings — use string comparison or SQLite's
  date()/strftime() functions.
- Write the query as if a human reviewer will read it before it runs:
  use clear aliases, avoid unnecessary `SELECT *` on large tables.

### 3. Observe
Read the tool's output. If it is an error, identify the specific cause
(typo'd column, bad join, wrong aggregation) and fix it. If it returned
rows, check that the shape and volume of the result actually answers
the question.

### 4. Reflect and decide
Determine if the result is sufficient, or if a follow-up query is
needed (e.g. drilling into a specific machine after identifying the
worst performer). Repeat from step 2 if another query is needed.

### 5. Stop condition
If the configured maximum number of iterations is reached without a
fully satisfying answer, stop, report the best result obtained so far,
and clearly state what remains uncertain. Never fabricate numbers.

### 6. Hand off results
Output the final SQL query used, the structured result rows, and a
one-paragraph plain-language summary of what the data shows. This is
consumed by the visualisation subagent (if routed) and the response
agent.
