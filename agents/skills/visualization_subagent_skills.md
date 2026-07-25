---
name: visualization-subagent
description: Use this skill to turn a SQL result set into a single clear chart with a one-sentence insight caption, when the orchestrator has determined a visualization is needed.
---
# visualization-subagent

## Overview
This skill explains how to turn structured SQL result rows into one
clear, correct chart plus a short caption. It is only invoked when the
orchestrator routed the request to `sql_and_visualization`.

## Instructions

### 1. Choose the chart type
Based on the user's question and the shape of `sql_result`:
- Time series / trend ("over the last 6 months") → line chart, x-axis = date/time column
- Comparison across categories ("by plant", "by machine") → bar chart, one bar per category, sorted descending by value
- Distribution / proportion ("breakdown of defect types") → pie chart if 6 or fewer categories, otherwise a horizontal bar chart
- Two numeric variables ("relationship between downtime and defects") → scatter plot
- If the result set has only one row or one number, do not force a
  chart — report that no meaningful visualization applies instead.

### 2. Validate the data before plotting
Only plot columns that are actually present in `sql_result`. If a
column needed for the requested chart type is missing, say so rather
than guessing or substituting a different column.

### 3. Render the chart
Build the chart with matplotlib: add a clear title, labeled axes, and
legible font sizes. Produce exactly one chart per request unless
explicitly asked for more. Save it as a PNG file.

### 4. Write the caption
Write one sentence describing the key insight the chart reveals (e.g.
"Plant Katowice has the highest average defect rate at 6.2%"). The
caption must stand alone and be understandable without seeing the
image, since the response agent will weave it into the final answer.

### 5. Hand off results
Return the saved chart's file path, the chart type used, and the
caption.