"""NBA Salary Cap MCP server.

Exposes the project's CBA luxury-tax engine to AI agents over the Model Context
Protocol. The engine (backend/engine) is imported directly, so an agent and the
web app always agree on the math.

Design notes for agent use:
- Every tool is read-only and takes plain, self-describing arguments.
- Errors are written for the agent: they say what was wrong and list valid values.
- Money is always whole US dollars. Responses include a short "summary" string
  in plain language alongside the structured numbers.
- Seasons beyond the published one are projections; responses say so.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Literal, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from engine.constants import PROJECTED_SEASONS, PUBLISHED_SEASONS, SEASONS  # noqa: E402
from engine.tax_engine import luxury_tax_bill, team_financials  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

DATA_DIR = ROOT / "backend" / "data"
DEFAULT_SEASON = "2026-27"

mcp = MCPServer(
    "nba-salary-cap",
    instructions=(
        "Answer questions about NBA team payrolls, cap space, luxury tax bills and "
        "apron restrictions. Start with list_teams to find a team_id, then use "
        "get_team_financials, simulate_payroll_change, or luxury_tax_breakdown. "
        "All amounts are whole US dollars. Seasons after 2026-27 are projections."
    ),
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)

Tier = Literal["under_tax", "luxury_tax", "first_apron", "second_apron"]
TIER_LABELS = {
    "under_tax": "Under Tax",
    "luxury_tax": "Luxury Tax",
    "first_apron": "First Apron",
    "second_apron": "Second Apron",
}


# ───────────────────────────── helpers ───────────────────────────────────────

def _check_season(season: str) -> None:
    if season not in SEASONS:
        raise ValueError(f"Unsupported season {season!r}. Valid seasons: {sorted(SEASONS)}.")


def _basis(season: str) -> str:
    return "published" if season in PUBLISHED_SEASONS else "projected"


def _load_teams(season: str) -> dict[str, dict]:
    file_season = PROJECTED_SEASONS[season][0] if season in PROJECTED_SEASONS else season
    path = DATA_DIR / f"teams_{file_season.replace('-', '_')}.json"
    if not path.exists():
        raise ValueError(f"No roster data for season {season!r}.")
    with open(path) as f:
        return {t["team_id"]: t for t in json.load(f)}


def _get_team(team_id: str, season: str) -> dict[str, Any]:
    teams = _load_teams(season)
    key = team_id.strip().upper()
    if key in teams:
        return teams[key]
    # Be forgiving: allow a team name such as "Phoenix Suns" or just "suns".
    needle = team_id.strip().lower()
    matches = [t for t in teams.values() if needle and needle in t["team_name"].lower()]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(
        f"Unknown team {team_id!r}. Use a team_id such as 'PHX' or 'BOS'. "
        f"Valid ids: {sorted(teams)}. Call list_teams to browse."
    )


def _bracket_rows(amount_over: float, repeater: bool) -> list[dict]:
    """Per-bracket tax rows that mirror engine.tax_engine.luxury_tax_bill."""
    adder = 1.0 if repeater else 0.0
    rows: list[dict] = []
    fixed = [
        (0, 5_000_000, 1.50),
        (5_000_000, 10_000_000, 1.75),
        (10_000_000, 15_000_000, 2.50),
        (15_000_000, 20_000_000, 3.25),
    ]
    for lower, upper, rate in fixed:
        if amount_over <= lower:
            break
        dollars = min(amount_over, upper) - lower
        rows.append(
            {
                "band": f"${lower / 1e6:g}M to ${upper / 1e6:g}M over the tax line",
                "dollars_in_band": round(dollars, 2),
                "rate_per_dollar": rate + adder,
                "tax": round(dollars * (rate + adder), 2),
            }
        )
    if amount_over > 20_000_000:
        remaining = amount_over - 20_000_000
        chunk = 0
        while remaining > 0:
            rate = 3.75 + adder + chunk * 0.50
            dollars = min(remaining, 5_000_000)
            start = 20 + chunk * 5
            rows.append(
                {
                    "band": f"${start}M to ${start + 5}M over the tax line",
                    "dollars_in_band": round(dollars, 2),
                    "rate_per_dollar": rate,
                    "tax": round(dollars * rate, 2),
                }
            )
            remaining -= dollars
            chunk += 1
    return rows


def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x) / 1e6:,.1f}M"


# ───────────────────────────── tools ─────────────────────────────────────────

@mcp.tool(annotations=READ_ONLY)
def luxury_tax_breakdown(payroll_usd: float, season: str = DEFAULT_SEASON, repeater: bool = False) -> dict[str, Any]:
    """Compute an NBA luxury tax bill for any payroll, with every bracket shown.

    Use this to explain HOW a tax bill is calculated. The luxury tax works like
    income tax: each rate applies only to the dollars inside its band. Repeater
    teams (taxpayers in 3 of the prior 4 seasons) pay an extra $1.00 per dollar
    in every band.

    Args:
        payroll_usd: Total team payroll in whole US dollars, e.g. 215000000.
        season: Season label such as "2026-27". Later seasons are projections.
        repeater: True if the team is a repeat taxpayer.
    """
    _check_season(season)
    if payroll_usd < 0:
        raise ValueError("payroll_usd must be zero or positive (whole US dollars).")
    line = SEASONS[season]["LUXURY_TAX"]
    over = max(0.0, payroll_usd - line)
    rows = _bracket_rows(over, repeater)
    bill = luxury_tax_bill(payroll_usd, season, repeater)
    return {
        "season": season,
        "basis": _basis(season),
        "payroll": payroll_usd,
        "luxury_tax_line": line,
        "amount_over_tax_line": round(over, 2),
        "repeater": repeater,
        "brackets": rows,
        "total_tax": bill,
        "summary": (
            f"Payroll {_money(payroll_usd)} is {_money(over)} over the {_money(line)} tax line, "
            f"so the {'repeater ' if repeater else ''}tax bill is {_money(bill)}."
            if over > 0
            else f"Payroll {_money(payroll_usd)} is at or below the {_money(line)} tax line: no tax owed."
        ),
    }


@mcp.tool(annotations=READ_ONLY)
def get_team_financials(team_id: str, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """Get one team's payroll, cap space, luxury tax bill, apron tier and restrictions.

    Args:
        team_id: Three-letter team id such as "PHX" (a team name like "Phoenix Suns" also works).
        season: Season label such as "2026-27". Later seasons are projections.
    """
    _check_season(season)
    team = _get_team(team_id, season)
    fin = team_financials(team, season)
    fin["basis"] = _basis(season)
    fin["repeater"] = team.get("repeater", False)
    fin["summary"] = (
        f"{fin['team_name']} ({season}): payroll {_money(fin['payroll'])}, "
        f"tier '{fin['apron_status']['tier']}', luxury tax {_money(fin['luxury_tax_bill'])}, "
        f"cap space {_money(fin['cap_space'])}."
    )
    return fin


@mcp.tool(annotations=READ_ONLY)
def list_teams(
    season: str = DEFAULT_SEASON,
    tier: Optional[Tier] = None,
    conference: Optional[Literal["East", "West"]] = None,
    sort_by: Literal["payroll", "luxury_tax_bill", "cap_space", "team_name"] = "payroll",
    descending: bool = True,
    limit: int = 10,
) -> dict[str, Any]:
    """List teams with their key financials, optionally filtered and sorted.

    Use this to find a team_id or answer league-wide questions such as "which
    teams are over the second apron?" or "who owes the most luxury tax?".

    Args:
        season: Season label such as "2026-27".
        tier: Only teams in this tier: under_tax, luxury_tax, first_apron, second_apron.
        conference: "East" or "West".
        sort_by: payroll, luxury_tax_bill, cap_space or team_name.
        descending: Sort high to low when true.
        limit: Maximum number of teams to return (1 to 30).
    """
    _check_season(season)
    if not 1 <= limit <= 30:
        raise ValueError("limit must be between 1 and 30.")
    teams = _load_teams(season)
    rows = []
    for t in teams.values():
        if conference and t.get("conference") != conference:
            continue
        f = team_financials(t, season)
        if tier and f["apron_status"]["tier"] != TIER_LABELS[tier]:
            continue
        rows.append(
            {
                "team_id": f["team_id"],
                "team_name": f["team_name"],
                "conference": t.get("conference"),
                "payroll": f["payroll"],
                "cap_space": f["cap_space"],
                "luxury_tax_bill": f["luxury_tax_bill"],
                "tier": f["apron_status"]["tier"],
            }
        )
    rows.sort(key=lambda r: r[sort_by], reverse=descending)
    total = len(rows)
    return {
        "season": season,
        "basis": _basis(season),
        "matching_teams": total,
        "returned": min(limit, total),
        "teams": rows[:limit],
    }


@mcp.tool(annotations=READ_ONLY)
def simulate_payroll_change(
    team_id: str,
    season: str = DEFAULT_SEASON,
    add_salary_usd: float = 0,
    remove_player: Optional[str] = None,
) -> dict[str, Any]:
    """Preview what happens to a team's tax bill and tier if it adds or drops salary.

    Nothing is saved. Use it for questions like "what if the Suns trade away
    Devin Booker?" or "how much tax would Boston owe after signing a $30M player?".

    Args:
        team_id: Three-letter team id such as "BOS".
        season: Season label such as "2026-27".
        add_salary_usd: Salary of a hypothetical new player, in whole US dollars (0 for none).
        remove_player: Exact or partial name of a current player to remove (optional).
    """
    _check_season(season)
    if add_salary_usd < 0:
        raise ValueError("add_salary_usd must be zero or positive.")
    team = _get_team(team_id, season)
    before = team_financials(team, season)

    modified = copy.deepcopy(team)
    removed = None
    season_key = f"salary_{season.replace('-', '_')}"
    if remove_player:
        needle = remove_player.strip().lower()
        hits = [p for p in modified["players"] if needle in p["name"].lower()]
        if not hits:
            names = sorted(p["name"] for p in modified["players"])
            raise ValueError(f"No player matching {remove_player!r} on {team['team_name']}. Roster: {names}.")
        if len(hits) > 1:
            raise ValueError(
                f"{remove_player!r} matches several players: {[p['name'] for p in hits]}. Use the full name."
            )
        removed = hits[0]["name"]
        modified["players"] = [p for p in modified["players"] if p is not hits[0]]
    if add_salary_usd:
        modified["players"].append({"name": "Hypothetical player", season_key: add_salary_usd, "guaranteed": True})

    after = team_financials(modified, season)
    return {
        "team_id": team["team_id"],
        "season": season,
        "basis": _basis(season),
        "change": {"added_salary": add_salary_usd, "removed_player": removed},
        "before": {"payroll": before["payroll"], "luxury_tax_bill": before["luxury_tax_bill"], "tier": before["apron_status"]["tier"]},
        "after": {"payroll": after["payroll"], "luxury_tax_bill": after["luxury_tax_bill"], "tier": after["apron_status"]["tier"], "restrictions": after["restrictions"]},
        "tax_change": round(after["luxury_tax_bill"] - before["luxury_tax_bill"], 2),
        "summary": (
            f"{team['team_name']}: payroll {_money(before['payroll'])} to {_money(after['payroll'])}; "
            f"tier {before['apron_status']['tier']} to {after['apron_status']['tier']}; "
            f"luxury tax {_money(before['luxury_tax_bill'])} to {_money(after['luxury_tax_bill'])}."
        ),
    }


# ───────────────────────────── resources ─────────────────────────────────────

@mcp.resource("nba-cap://thresholds/{season}", mime_type="application/json")
def thresholds(season: str) -> str:
    """League thresholds (cap, tax line, aprons, floor) for a season."""
    _check_season(season)
    s = SEASONS[season]
    return json.dumps(
        {
            "season": season,
            "basis": _basis(season),
            "salary_cap": s["SALARY_CAP"],
            "luxury_tax_line": s["LUXURY_TAX"],
            "first_apron": s["FIRST_APRON"],
            "second_apron": s["SECOND_APRON"],
            "payroll_floor": s["SALARY_CAP"] * s["TAX_FLOOR"],
        }
    )


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
