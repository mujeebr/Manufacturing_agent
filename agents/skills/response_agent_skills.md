---
name: response-synthesis
description: Use this skill as the final step of every run to synthesize the SQL deep agent's data and any visualisation subagent output into one clear, grounded answer for the user.
---
# response-synthesis

## Overview
This skill explains how to combine everything upstream agents produced
into a single, direct, trustworthy answer to the user's original
question. There are no agents downstream to clean this up — it is
exactly what the user sees.

## Instructions

### 1. Re-read the original question
Confirm what was actually asked before writing anything, so the answer
leads with that — not with a restatement of the question or a
description of the process used to get there.

### 2. Ground the answer in upstream data
Use only the numbers and facts present in the SQL deep agent's result
data. Never add figures that were not present upstream.

### 3. Reference the chart if one was generated
If `chart_path` and `chart_description` are present, mention the chart
naturally (e.g. "As the chart shows, ...") and restate its key insight
in your own words rather than repeating the caption verbatim.

### 4. Disclose any limitations
If the SQL deep agent reported uncertainty or hit its iteration limit,
say so plainly instead of presenting the answer as fully certain.

### 5. Format for readability
Keep the tone professional and concise, like a data analyst briefing a
manufacturing operations manager. Use short paragraphs or a brief
bulleted list for multi-part answers; avoid dense walls of text.

### 6. Output
Produce the final natural-language answer only.
