"""Tests for the NBA Salary Cap MCP server.

Run:  .venv/bin/python -m pytest -q
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from engine.constants import SEASONS  # noqa: E402
from engine.tax_engine import luxury_tax_bill  # noqa: E402

S = "2026-27"
LINE = SEASONS[S]["LUXURY_TAX"]


# ── the bracket breakdown must always reconcile with the engine ──────────────

@pytest.mark.parametrize("over", [0, 1, 4_999_999, 5_000_000, 7_500_000, 12_345_678, 19_999_999, 20_000_000, 22_500_000, 41_000_001, 80_000_000])
@pytest.mark.parametrize("repeater", [False, True])
def test_breakdown_matches_engine(over, repeater):
    payroll = LINE + over
    out = server.luxury_tax_breakdown(payroll, S, repeater)
    assert out["total_tax"] == luxury_tax_bill(payroll, S, repeater)
    assert round(sum(r["tax"] for r in out["brackets"]), 2) == pytest.approx(out["total_tax"], abs=0.05)


def test_known_values():
    # $10M over: 5M * 1.50 + 5M * 1.75 = 16.25M
    assert server.luxury_tax_breakdown(LINE + 10_000_000, S)["total_tax"] == 16_250_000
    # Repeater adds $1.00 in every bracket: 5M * 2.50 + 5M * 2.75 = 26.25M
    assert server.luxury_tax_breakdown(LINE + 10_000_000, S, True)["total_tax"] == 26_250_000
    # Exactly at the line owes nothing and says so.
    out = server.luxury_tax_breakdown(LINE, S)
    assert out["total_tax"] == 0 and out["brackets"] == [] and "no tax owed" in out["summary"]


def test_open_ended_bracket_escalates():
    out = server.luxury_tax_breakdown(LINE + 30_000_000, S)
    rates = [r["rate_per_dollar"] for r in out["brackets"]]
    assert rates == [1.5, 1.75, 2.5, 3.25, 3.75, 4.25]


# ── team tools ───────────────────────────────────────────────────────────────

def test_team_lookup_by_id_and_name():
    a = server.get_team_financials("PHX", S)
    b = server.get_team_financials("Phoenix Suns", S)
    assert a["team_id"] == b["team_id"] == "PHX"
    assert a["basis"] == "published" and "summary" in a


def test_projected_season_is_labelled():
    assert server.get_team_financials("BOS", "2027-28")["basis"] == "projected"


def test_list_teams_filters_and_sorts():
    out = server.list_teams(S, tier="second_apron", limit=30)
    assert out["matching_teams"] == len(out["teams"])
    assert all(t["tier"] == "Second Apron" for t in out["teams"])
    payrolls = [t["payroll"] for t in out["teams"]]
    assert payrolls == sorted(payrolls, reverse=True)
    assert server.list_teams(S, limit=3)["returned"] == 3
    east = server.list_teams(S, conference="East", limit=30)
    assert all(t["conference"] == "East" for t in east["teams"])


def test_simulate_payroll_change():
    base = server.get_team_financials("PHX", S)
    up = server.simulate_payroll_change("PHX", S, add_salary_usd=20_000_000)
    assert up["after"]["payroll"] == base["payroll"] + 20_000_000
    assert up["tax_change"] >= 0
    assert up["before"]["luxury_tax_bill"] == base["luxury_tax_bill"]

    roster = server._get_team("PHX", S)["players"]
    top = max(roster, key=lambda p: p.get("salary_2026_27", 0))
    down = server.simulate_payroll_change("PHX", S, remove_player=top["name"])
    assert down["after"]["payroll"] == base["payroll"] - top["salary_2026_27"]
    assert down["tax_change"] <= 0
    # Nothing is mutated between calls.
    assert server.get_team_financials("PHX", S)["payroll"] == base["payroll"]


# ── errors must be useful to an agent ────────────────────────────────────────

def test_errors_guide_the_agent():
    with pytest.raises(ValueError, match="Valid seasons"):
        server.get_team_financials("PHX", "1999-00")
    with pytest.raises(ValueError, match="Valid ids"):
        server.get_team_financials("XYZ", S)
    with pytest.raises(ValueError, match="Roster"):
        server.simulate_payroll_change("PHX", S, remove_player="Nobody Atall")
    with pytest.raises(ValueError, match="limit"):
        server.list_teams(S, limit=0)
    with pytest.raises(ValueError, match="payroll_usd"):
        server.luxury_tax_breakdown(-1, S)


# ── end to end over the real MCP protocol (stdio) ────────────────────────────

def test_end_to_end_over_stdio():
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(command=sys.executable, args=[str(Path(server.__file__))])

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {t.name for t in (await session.list_tools()).tools}
                assert tools == {"luxury_tax_breakdown", "get_team_financials", "list_teams", "simulate_payroll_change"}
                result = await session.call_tool("luxury_tax_breakdown", {"payroll_usd": LINE + 10_000_000})
                assert not result.is_error
                assert result.structured_content["total_tax"] == 16_250_000
                bad = await session.call_tool("get_team_financials", {"team_id": "XYZ"})
                assert bad.is_error
                res = await session.read_resource("nba-cap://thresholds/2026-27")
                assert str(LINE) in res.contents[0].text

    asyncio.run(asyncio.wait_for(run(), timeout=60))
