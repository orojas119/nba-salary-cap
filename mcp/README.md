# NBA Salary Cap MCP server

An [MCP](https://modelcontextprotocol.io) server that lets an AI agent answer
NBA payroll questions using the same CBA luxury-tax engine that powers the
[salary cap tracker](https://nba-salary-cap.vercel.app). The server imports
`backend/engine` directly, so an agent and the web app always agree on the math.

## Tools

| Tool | What an agent uses it for |
|------|---------------------------|
| `list_teams` | Find a `team_id`, or answer league-wide questions ("who is over the second apron?", "who owes the most tax?") with filter and sort. |
| `get_team_financials` | One team's payroll, cap space, luxury tax bill, apron tier and roster restrictions. |
| `luxury_tax_breakdown` | Explain how a tax bill is calculated: every bracket, rate and dollar amount for any payroll, with repeater handling. |
| `simulate_payroll_change` | What-if without saving anything: add a salary or remove a player and see the new tax bill and tier. |

Resource: `nba-cap://thresholds/{season}` returns the cap, tax line, aprons and payroll floor.

## Design choices for agent use

- **Read-only.** Every tool is annotated `readOnlyHint`; nothing is written anywhere.
- **Structured output plus a plain-language `summary`**, so the agent can quote or reason from either.
- **Errors that tell the agent how to recover.** An unknown team lists valid ids; an unknown player lists the roster; a bad season lists valid seasons.
- **Forgiving inputs.** A team can be given as `PHX` or `Phoenix Suns`.
- **Honest about uncertainty.** Seasons after 2026-27 are model projections, and every response is labelled `"basis": "published"` or `"projected"`.
- **The breakdown is checked against the engine.** Tests assert the per-bracket rows always add up to the engine's tax bill.

## Run it

Requires Python 3.10+.

```bash
cd mcp
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q      # 30 tests, including an end-to-end run over stdio
.venv/bin/python server.py         # starts the server on stdio
```

### Use it from Claude Code

```bash
claude mcp add nba-salary-cap -- /absolute/path/to/nba-salary-cap/mcp/.venv/bin/python /absolute/path/to/nba-salary-cap/mcp/server.py
```

### Use it from Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nba-salary-cap": {
      "command": "/absolute/path/to/nba-salary-cap/mcp/.venv/bin/python",
      "args": ["/absolute/path/to/nba-salary-cap/mcp/server.py"]
    }
  }
}
```

## Example questions an agent can now answer

- "How is a $215M payroll taxed, bracket by bracket?"
- "Which teams are over the first apron, and what do they owe?"
- "If Boston signs a $30M player, what happens to its tier and tax bill?"

## What is tested

`test_server.py` covers: breakdown equals the engine for 22 payroll and repeater
combinations; known hand-computed values; the escalating open-ended bracket;
team lookup by id and by name; projected-season labelling; filtering and sorting;
what-if changes without mutation; agent-friendly error messages; and a full
client-to-server round trip over stdio.

## Limits

- Roster and salary data comes from the project's seed files (Spotrac importer), so it is only as current as the last data refresh.
- Projected seasons grow the cap by an assumed 5% per year.
- It does not model every CBA rule (trade matching, exceptions, and so on), only payroll, cap space, tax and the apron restrictions the engine implements.
- The tests are deterministic checks, not an LLM-graded evaluation.
