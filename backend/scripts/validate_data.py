#!/usr/bin/env python3
"""Validate teams_2026_27.json before computing financials or deploying.

Checks:
  - exactly 30 teams
  - no duplicate team_ids
  - each team has 5-20 players (signed rosters run thin during the offseason)
  - every player salary value is a positive number
  - conference is "East" or "West"
  - 15 teams per conference (sanity check on league structure)

Exits 1 on any failure so a CI step can block a bad deploy.

Run:
    cd backend && python scripts/validate_data.py
"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "teams_2026_27.json"
SALARY_FIELDS = ("salary_2026_27", "salary_2027_28", "salary_2028_29")


def main() -> int:
    errors: list[str] = []

    if not DATA.exists():
        print(f"FAIL: data file not found: {DATA}")
        return 1

    teams = json.loads(DATA.read_text())

    # ── 30 teams ──
    if len(teams) != 30:
        errors.append(f"expected 30 teams, found {len(teams)}")

    # ── duplicate team_ids ──
    ids = [t.get("team_id") for t in teams]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        errors.append(f"duplicate team_ids: {sorted(dupes)}")

    conf_counts = {"East": 0, "West": 0}

    for t in teams:
        tid = t.get("team_id", "<missing>")

        # ── conference ──
        conf = t.get("conference")
        if conf not in ("East", "West"):
            errors.append(f"{tid}: conference must be 'East' or 'West', got {conf!r}")
        else:
            conf_counts[conf] += 1

        # ── roster size ──
        players = t.get("players", [])
        if not (5 <= len(players) <= 20):
            errors.append(f"{tid}: roster size {len(players)} not in 5-20")

        # ── salaries positive numbers ──
        for p in players:
            name = p.get("name", "<unnamed>")
            for field in SALARY_FIELDS:
                if field not in p:
                    continue
                val = p[field]
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    errors.append(f"{tid}/{name}: {field} is not a number ({val!r})")
                elif val <= 0:
                    errors.append(f"{tid}/{name}: {field} must be positive ({val})")

    # ── conference balance ──
    if conf_counts != {"East": 15, "West": 15} and not errors:
        errors.append(f"conference split should be 15/15, got {conf_counts}")

    if errors:
        print(f"VALIDATION FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    approx = [t["team_id"] for t in teams if t.get("data_confidence") == "approximate"]
    print(f"VALIDATION PASSED: {len(teams)} teams, "
          f"{conf_counts['East']} East / {conf_counts['West']} West")
    print(f"  Verified data:    {30 - len(approx)} teams")
    print(f"  Approximate data: {len(approx)} teams -> {', '.join(approx)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
