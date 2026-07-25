---
name: orchestrator-routing
description: Use this skill to classify an incoming manufacturing-analytics question and route it to the correct downstream agent(s) before any data is queried.
---
# orchestrator-routing

## Overview
This skill explains how to route a user's question about Northbridge
Precision Manufacturing to the correct specialist agents. The
orchestrator never queries data or answers the question itself — it
only decides where the request should go next.

## Instructions

### 1. Read the user's question
Identify what kind of answer is being requested: a single fact, a
comparison, a trend over time, or a ranking.

### 2. Decide if visualization is needed
Route to `sql_and_visualization` if the question contains any of:
- Explicit chart language: "plot", "chart", "graph", "visualize", "show trend"
- Implicit chart intent: comparisons across categories, trends over
  time, rankings ("top N", "worst performing"), distributions/breakdowns

Otherwise route to `sql_only`. If uncertain, default to `sql_only` —
the response agent can always suggest a follow-up visualization.

### 3. Always send the request to the SQL deep agent
Every request needs data. `sql_deep_agent` runs on both routes;
`visualisation_subagent` only runs on the `sql_and_visualization` route,
after the SQL deep agent returns results.

### 4. Output your routing decision
Return exactly one of `sql_only` or `sql_and_visualization`, plus one
short sentence explaining why. Do not generate SQL, prose answers, or
chart descriptions — those belong to downstream agents.
