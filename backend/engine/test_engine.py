"""
Unit tests for the NBA salary cap and luxury tax engine.
All expected values are derived from the CBA bracket math — no magic numbers.

Run from the backend/ directory:
    python -m pytest engine/test_engine.py -v
"""

import pytest
from engine.constants import SEASONS
from engine.tax_engine import (
    cap_space,
    luxury_tax_bill,
    apron_status,
    team_financials,
    total_payroll,
)

SEASON = "2026-27"
CAP = SEASONS[SEASON]["SALARY_CAP"]          # 165_000_000
TAX_LINE = SEASONS[SEASON]["LUXURY_TAX"]     # 201_048_000
FIRST_APRON = SEASONS[SEASON]["FIRST_APRON"] # 209_661_000
SECOND_APRON = SEASONS[SEASON]["SECOND_APRON"]  # 222_372_000
FLOOR = CAP * SEASONS[SEASON]["TAX_FLOOR"]   # 148_500_000


# ─────────────────────────── total_payroll ───────────────────────────────────

class TestTotalPayroll:
    def test_sums_salaries(self):
        assert total_payroll([10_000_000, 20_000_000, 5_000_000]) == 35_000_000

    def test_empty_roster(self):
        assert total_payroll([]) == 0


# ────────────────────────────── cap_space ────────────────────────────────────

class TestCapSpace:
    def test_under_cap_returns_positive_space(self):
        assert cap_space(150_000_000, SEASON) == 15_000_000

    def test_over_cap_returns_negative(self):
        assert cap_space(200_000_000, SEASON) == -35_000_000


# ────────────────────────── luxury_tax_bill ──────────────────────────────────

class TestLuxuryTaxBill:

    # ── Under / at the line ──────────────────────────────────────────────────

    def test_at_tax_line_pays_zero(self):
        # Exactly at the line: no tax owed
        assert luxury_tax_bill(TAX_LINE, SEASON) == 0.0

    def test_below_tax_line_pays_zero(self):
        assert luxury_tax_bill(TAX_LINE - 1, SEASON) == 0.0

    # ── Standard (non-repeater) bracket checks ───────────────────────────────

    def test_5m_over_standard(self):
        # $5M over → all in bracket 1 @ $1.50/$1
        # 5_000_000 × 1.50 = $7,500,000
        assert luxury_tax_bill(TAX_LINE + 5_000_000, SEASON) == 7_500_000.0

    def test_12m_over_standard(self):
        # $12M over spans brackets 1–3:
        #   bracket 1:  5M × 1.50 =  7,500,000
        #   bracket 2:  5M × 1.75 =  8,750,000
        #   bracket 3:  2M × 2.50 =  5,000,000
        #   total                  = 21,250,000
        assert luxury_tax_bill(TAX_LINE + 12_000_000, SEASON) == 21_250_000.0

    def test_20m_over_standard(self):
        # $20M over — exactly fills the four fixed brackets:
        #   5M×1.50 + 5M×1.75 + 5M×2.50 + 5M×3.25
        #   = 7.5M + 8.75M + 12.5M + 16.25M = 45,000,000
        assert luxury_tax_bill(TAX_LINE + 20_000_000, SEASON) == 45_000_000.0

    def test_25m_over_enters_escalating_bracket(self):
        # $25M over: fixed 4 brackets (45M) + first $5M chunk @ $3.75
        #   45,000,000 + 5M×3.75 = 45,000,000 + 18,750,000 = 63,750,000
        assert luxury_tax_bill(TAX_LINE + 25_000_000, SEASON) == 63_750_000.0

    def test_27m_over_straddles_two_escalating_chunks(self):
        # $27M over: fixed (45M) + 5M@3.75 + 2M@4.25
        #   45,000,000 + 18,750,000 + 8,500,000 = 72,250,000
        assert luxury_tax_bill(TAX_LINE + 27_000_000, SEASON) == 72_250_000.0

    # ── Repeater brackets (add $1.00 to every rate) ──────────────────────────

    def test_5m_over_repeater(self):
        # $5M over repeater: 5M × (1.50 + 1.00) = 5M × 2.50 = 12,500,000
        assert luxury_tax_bill(TAX_LINE + 5_000_000, SEASON, repeater=True) == 12_500_000.0

    def test_12m_over_repeater(self):
        # $12M over repeater:
        #   bracket 1:  5M × 2.50 = 12,500,000
        #   bracket 2:  5M × 2.75 = 13,750,000
        #   bracket 3:  2M × 3.50 =  7,000,000
        #   total                  = 33,250,000
        assert luxury_tax_bill(TAX_LINE + 12_000_000, SEASON, repeater=True) == 33_250_000.0

    def test_25m_over_repeater(self):
        # $25M over repeater: fixed 4 brackets (repeater) + first chunk @ 4.75
        #   5M×2.50 + 5M×2.75 + 5M×3.50 + 5M×4.25 = 12.5+13.75+17.5+21.25 = 65M
        #   + 5M × 4.75 = 23,750,000
        #   total = 88,750,000
        assert luxury_tax_bill(TAX_LINE + 25_000_000, SEASON, repeater=True) == 88_750_000.0


# ─────────────────────────── apron_status ────────────────────────────────────

class TestApronStatus:

    def test_under_tax_tier(self):
        result = apron_status(TAX_LINE - 1_000_000, SEASON)
        assert result["tier"] == "Under Tax"
        assert not result["over_tax"]
        assert not result["over_first_apron"]
        assert not result["over_second_apron"]
        assert result["amount_over_tax"] == 0.0

    def test_luxury_tax_tier(self):
        result = apron_status(TAX_LINE + 1_000_000, SEASON)
        assert result["tier"] == "Luxury Tax"
        assert result["over_tax"]
        assert not result["over_first_apron"]
        assert result["amount_over_tax"] == 1_000_000.0

    def test_first_apron_tier(self):
        result = apron_status(FIRST_APRON + 500_000, SEASON)
        assert result["tier"] == "First Apron"
        assert result["over_first_apron"]
        assert not result["over_second_apron"]

    def test_second_apron_tier(self):
        result = apron_status(SECOND_APRON + 1_000_000, SEASON)
        assert result["tier"] == "Second Apron"
        assert result["over_second_apron"]

    def test_amount_to_first_apron_is_negative_when_over(self):
        result = apron_status(FIRST_APRON + 5_000_000, SEASON)
        assert result["amount_to_first_apron"] == -5_000_000.0

    def test_amount_to_second_apron_positive_when_under(self):
        result = apron_status(FIRST_APRON + 1_000_000, SEASON)
        expected = SECOND_APRON - (FIRST_APRON + 1_000_000)
        assert result["amount_to_second_apron"] == pytest.approx(expected)


# ──────────────────────────── salary floor ───────────────────────────────────

class TestFloor:
    """Teams must spend to 90 % of the salary cap ($148,500,000 in 2026-27)."""

    def _make_team(self, payroll: float, repeater: bool = False) -> dict:
        return {
            "team_id": "TST",
            "team_name": "Test Team",
            "repeater": repeater,
            "players": [{"name": "Player A", "salary_2026_27": payroll, "guaranteed": True}],
            "dead_cap": [],
        }

    def test_below_floor_is_flagged(self):
        # floor = 0.90 × 165_000_000 = 148_500_000
        result = team_financials(self._make_team(100_000_000), SEASON)
        assert result["below_floor"] is True
        assert result["floor_deficit"] == pytest.approx(48_500_000.0)

    def test_above_floor_not_flagged(self):
        result = team_financials(self._make_team(160_000_000), SEASON)
        assert result["below_floor"] is False
        assert result["floor_deficit"] == 0.0

    def test_exactly_at_floor_not_flagged(self):
        result = team_financials(self._make_team(FLOOR), SEASON)
        assert result["below_floor"] is False


# ────────────────────────── restrictions ─────────────────────────────────────

class TestRestrictions:

    def _make_team(self, payroll: float, repeater: bool = False) -> dict:
        return {
            "team_id": "TST",
            "team_name": "Test Team",
            "repeater": repeater,
            "players": [{"name": "P", "salary_2026_27": payroll, "guaranteed": True}],
            "dead_cap": [],
        }

    def test_under_tax_has_no_restrictions(self):
        result = team_financials(self._make_team(TAX_LINE - 1_000_000), SEASON)
        assert result["restrictions"] == []

    def test_luxury_tax_tier_has_no_restrictions(self):
        result = team_financials(self._make_team(TAX_LINE + 1_000_000), SEASON)
        assert result["restrictions"] == []

    def test_first_apron_restrictions(self):
        result = team_financials(self._make_team(FIRST_APRON + 1_000_000), SEASON)
        assert "Cannot use bi-annual exception" in result["restrictions"]
        assert "Cannot use full mid-level exception" in result["restrictions"]
        assert "Cannot acquire players via sign-and-trade" in result["restrictions"]
        # Second-apron-only restrictions must NOT appear
        assert "Cannot aggregate salaries in trades" not in result["restrictions"]
        assert "Frozen first-round pick (7 years out)" not in result["restrictions"]

    def test_second_apron_restrictions_include_first_apron(self):
        result = team_financials(self._make_team(SECOND_APRON + 1_000_000), SEASON)
        # All first-apron restrictions present
        assert "Cannot use bi-annual exception" in result["restrictions"]
        # Plus second-apron-only restrictions
        assert "Cannot aggregate salaries in trades" in result["restrictions"]
        assert "Cannot send cash in trades" in result["restrictions"]
        assert "Frozen first-round pick (7 years out)" in result["restrictions"]
        assert "Cannot use taxpayer mid-level exception" in result["restrictions"]
