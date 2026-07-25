# Northbridge Precision Manufacturing — Multi-Agent Analytics System

A LangGraph multi-agent system that answers natural-language questions
about a manufacturing company's operations (production, quality,
suppliers, maintenance, inventory) by querying a SQLite database,
optionally generating a chart, and returning a grounded, synthesized
answer — with human approval of every SQL query before it runs.

## Architecture

```
user -> orchestrator agent -> Sql deep agent <-> sql_query_tool
                                    |
                     (human approves query here)
                                    |
              +---------------------+---------------------+
              |                                             |
     [route: sql_only]                        [route: sql_and_visualization]
              |                                             |
              |                                  visualisation sub agent
              |                                             |
              +---------------------+---------------------+
                                    |
                              response agent
                                    |
                                  answer
```

| Diagram box | Implementation |
|---|---|
| orchestrator agent | `agents/orchestrator_agent.py` — classifies the request, decides routing |
| Sql deep agent | `agents/sql_deep_agent.py` — `sql_plan_node` + `sql_execute_node`, looping plan → query → reflect |
| sql_query_tool | `tools/sql_query_tool.py` — the read-only SQL execution tool |
| visualisation sub agent | `agents/visualization_subagent.py` — only runs when routed |
| response agent | `agents/response_agent.py` — final synthesis |
| the graph itself | `graph/workflow.py` — wires all nodes, checkpointing, HITL |

## Key concepts covered

- **LangGraph workflow**: `graph/workflow.py` builds a `StateGraph` with
  conditional edges implementing the branch/loop structure above.
- **Deep agent pattern**: the SQL agent doesn't stop at one query — it
  plans, executes, observes, and reflects in a loop (capped by
  `SQL_DEEP_AGENT_MAX_ITERATIONS` in `config.py`) until it's confident
  in its answer or forced to stop.
- **Subagent**: the visualisation agent is a specialist invoked
  conditionally by the orchestrator's routing decision, not on every run.
- **Skills**: each agent's domain know-how lives in
  `agents/skills/*.md` (Anthropic Agent Skills format: YAML
  frontmatter + Overview + numbered Instructions).
- **Dynamic skill loading**: `agents/skills/skill_registry.py`
  implements progressive disclosure — agents see cheap skill
  descriptions first, and only load full skill bodies once selected
  as relevant. Today each agent has one candidate skill (instant,
  no LLM call); add more filenames to `SKILL_REGISTRY` later and
  real selection kicks in automatically.
- **Prompts**: `agents/prompts/prompts.py` assembles persona + selected
  skill(s) + graph-specific plumbing (tool names, output format
  contracts) into the final system prompt per node — kept separate
  from the reusable skill content itself.
- **Checkpointing**: `graph/workflow.py` uses `SqliteSaver`
  (`database/checkpoints.db`) so any run can be paused and resumed.
- **Human-in-the-loop**: the graph is compiled with
  `interrupt_before=["sql_execute"]`, pausing before any SQL touches
  the database. `main.py` shows the generated query and lets you
  approve, edit, or reject it.

## Project structure

```
manufacturing_agent_system/
├── requirements.txt
├── .env.example
├── config.py                          # models, paths, HITL toggle
├── main.py                            # CLI entry point
├── database/
│   ├── schema.sql                     # 11-table manufacturing schema
│   └── seed_data.py                   # generates synthetic data (Faker)
├── graph/
│   ├── state.py                       # shared AgentState schema
│   └── workflow.py                    # StateGraph + checkpointer + HITL
├── tools/
│   └── sql_query_tool.py              # read-only SQL execution tool
└── agents/
    ├── orchestrator_agent.py
    ├── sql_deep_agent.py
    ├── visualization_subagent.py
    ├── response_agent.py
    ├── prompts/
    │   └── prompts.py                 # persona + skill + plumbing assembly
    └── skills/
        ├── skill_registry.py          # dynamic skill selection/loading
        ├── orchestrator_skills.md
        ├── sql_deep_agent_skills.md
        ├── visualization_subagent_skills.md
        └── response_agent_skills.md
```

## Setup

```bash
cd manufacturing_agent_system
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set OPENAI_API_KEY

python database/seed_data.py      # builds database/manufacturing.db
python main.py                    # start the CLI
streamlit run streamlit_app.py    # step-through UI (chat + live architecture)
```

The Streamlit UI pauses **before every agent node**. Use **Run next step**
to resume one node at a time; the right-hand diagram highlights the active
path. When paused before SQL Execute, approve / edit / reject the query
first.

## Example session

```
Ask a question: Which plant has the highest average defect rate, and show a chart

[Generated SQL - awaiting your approval]
SELECT pl.plant_name, AVG(...) ...

Approve this query? [approve/edit/reject]: approve

Answer:
Plant Katowice has the highest average defect rate at 6.2%...
Chart saved to: charts/chart_a1b2c3d4.png
```

## Try these questions

Paste any of these into the CLI to exercise both the SQL deep agent and
the visualisation subagent (comparisons, rankings, and breakdowns tend
to route to `sql_and_visualization`):

1. **Which plant has the highest average defect rate? Show a bar chart comparing all plants.**
2. **Plot total maintenance cost by maintenance type (preventive, corrective, emergency).**
3. **Show a chart of units produced by product category over the last 12 months.**
4. **Which machines have the most downtime minutes? Chart the top 10.**

## Configuration

All tunable behavior lives in `config.py` / `.env`:

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | required | — |
| `ORCHESTRATOR_MODEL` | routing model | `gpt-4o` |
| `SQL_DEEP_AGENT_MODEL` | SQL reasoning model | `gpt-4o` |
| `VISUALIZATION_SUBAGENT_MODEL` | chart-planning model | `gpt-4o-mini` |
| `RESPONSE_AGENT_MODEL` | final synthesis model | `gpt-4o-mini` |
| `SKILL_SELECTOR_MODEL` | skill-selection model | `gpt-4o-mini` |
| `HUMAN_IN_THE_LOOP_ENABLED` | pause before SQL execution | `true` |
| `SQL_DEEP_AGENT_MAX_ITERATIONS` | cap on plan/query/reflect loops | `4` |

## Extending

- **New skill for an existing agent**: write a new `.md` file in
  `agents/skills/` following the frontmatter + Overview + Instructions
  format, then add its filename to that agent's list in
  `SKILL_REGISTRY` (`agents/skills/skill_registry.py`). Nothing else
  changes — selection and prompt assembly pick it up automatically.
- **New agent/subagent**: write the node function (following the
  pattern in any `agents/*.py` file), add its skill(s), register it in
  `SKILL_REGISTRY`, add a `build_*_prompt` function in `prompts.py`,
  and wire it into `graph/workflow.py`.
- **Disable human-in-the-loop** (e.g. for automated testing): set
  `HUMAN_IN_THE_LOOP_ENABLED=false` in `.env`.

## Notes

- The manufacturing data is entirely synthetic, generated by
  `database/seed_data.py` via Faker — there is no real company behind
  "Northbridge Precision Manufacturing."
- `tools/sql_query_tool.py` only permits `SELECT` statements; write/DDL
  keywords are rejected before reaching the database.