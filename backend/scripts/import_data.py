#!/usr/bin/env python3
"""Import current NBA rosters + salaries from Spotrac into teams_2026_27.json.

Source: https://www.spotrac.com/nba/<team-slug>/cap/_/year/<start_year>/
The per-team cap page renders an HTML table of the signed roster with each
player's cap hit for that league year. We read the signed-roster table (and
two-way players) for the base year, then optionally pull the next two years to
populate future-season salaries used by the projection endpoint.

NOTE ON USAGE: This scrapes Spotrac, a third-party site. Be a good citizen —
the script rate-limits between requests and sends a normal User-Agent. Spotrac's
data and markup can change without notice; re-verify the parser if a run starts
producing empty rosters. Respect Spotrac's Terms of Service for your use case.

Run:
    cd backend
    pip install -r scripts/requirements.txt
    python scripts/import_data.py            # base year only
    python scripts/import_data.py --future   # also fetch 2027-28, 2028-29
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "teams_2026_27.json"
META_FILE = BASE_DIR / "data" / "team_meta.json"

# League year that the "2026-27" season starts in.
BASE_START_YEAR = 2026
SEASON_LABEL = "2026-27"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 1.5  # seconds between requests — be polite

# team_id -> Spotrac URL slug
TEAM_SLUGS = {
    "ATL": "atlanta-hawks", "BOS": "boston-celtics", "BKN": "brooklyn-nets",
    "CHA": "charlotte-hornets", "CHI": "chicago-bulls", "CLE": "cleveland-cavaliers",
    "DAL": "dallas-mavericks", "DEN": "denver-nuggets", "DET": "detroit-pistons",
    "GSW": "golden-state-warriors", "HOU": "houston-rockets", "IND": "indiana-pacers",
    "LAC": "la-clippers", "LAL": "los-angeles-lakers", "MEM": "memphis-grizzlies",
    "MIA": "miami-heat", "MIL": "milwaukee-bucks", "MIN": "minnesota-timberwolves",
    "NOP": "new-orleans-pelicans", "NYK": "new-york-knicks", "OKC": "oklahoma-city-thunder",
    "ORL": "orlando-magic", "PHI": "philadelphia-76ers", "PHX": "phoenix-suns",
    "POR": "portland-trail-blazers", "SAC": "sacramento-kings", "SAS": "san-antonio-spurs",
    "TOR": "toronto-raptors", "UTA": "utah-jazz", "WAS": "washington-wizards",
}

# Spotrac contract "Type" codes -> our contract_type vocabulary.
TYPE_MAP = {
    "VET-EXT": "Veteran", "VET": "Veteran", "RK-EXT": "Rookie Extension",
    "RK-1ST": "Rookie Scale", "RK": "Rookie Scale", "FA": "Free Agent",
    "S&T": "Sign and Trade", "ROS": "Veteran Minimum", "2W": "Two-Way",
    "MLE": "MLE", "BAE": "BAE", "QO": "Qualifying Offer",
}

# Rows in the cap table that are not real players.
NON_PLAYER_RE = re.compile(
    r"incomplete roster|roster charge|round \d|pick #|dead|cap hold|total",
    re.IGNORECASE,
)


def fetch(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_salary(value) -> int | None:
    """'$43,902,439' -> 43902439; '-' / NaN -> None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in {"-", "nan", "NaN"}:
        return None
    digits = re.sub(r"[^0-9]", "", s)
    return int(digits) if digits else None


def clean_name(raw: str) -> str:
    """Spotrac doubles the name as '<LastName>  <Full Name>'. Keep the full name
    (the segment after the run of spaces); fall back to the whole string."""
    parts = re.split(r"\s{2,}", str(raw).strip())
    return parts[-1].strip() if parts else str(raw).strip()


def _player_col(cols: list[str]) -> str | None:
    for c in cols:
        if c.startswith("Player"):
            return c
    return None


def parse_team_page(html: str) -> dict[str, dict]:
    """Return {full_name: {salary, contract_type}} for the signed active roster.

    Spotrac renders several cap tables (active roster, free-agent holds, dead
    money, two-way). Only the active-roster table carries an 'X of 15' marker in
    its Player header — that's the one that maps to actual cap salaries. We use
    that table specifically so holds/dead money don't get counted as roster.
    """
    tables = pd.read_html(io.StringIO(html))

    roster_table = None
    fallback = None
    for t in tables:
        cols = [str(c) for c in t.columns]
        pcol = _player_col(cols)
        if pcol is None or "Cap Hit" not in cols:
            continue
        if fallback is None:
            fallback = (t, cols, pcol)
        if "of 15" in pcol:  # active-roster signature, e.g. "Player (10 of 15 ...)"
            roster_table = (t, cols, pcol)
            break

    chosen = roster_table or fallback
    if chosen is None:
        return {}

    t, cols, pcol = chosen
    t.columns = cols
    players: dict[str, dict] = {}
    for _, row in t.iterrows():
        raw_name = row[pcol]
        if not isinstance(raw_name, str) or NON_PLAYER_RE.search(raw_name):
            continue
        salary = parse_salary(row["Cap Hit"])
        if salary is None or salary <= 0:
            continue
        name = clean_name(raw_name)
        ctype = str(row["Type"]).strip() if "Type" in cols else ""
        players[name] = {
            "salary": salary,
            "contract_type": TYPE_MAP.get(ctype, ctype or "Veteran"),
        }
    return players


def team_url(slug: str, year: int) -> str:
    return f"https://www.spotrac.com/nba/{slug}/cap/_/year/{year}/"


def build_team(team_id: str, slug: str, meta: dict, existing: dict | None,
               fetch_future: bool) -> dict:
    base = parse_team_page(fetch(team_url(slug, BASE_START_YEAR)))
    time.sleep(REQUEST_DELAY)

    future_years: dict[int, dict[str, dict]] = {}
    if fetch_future:
        for yr in (BASE_START_YEAR + 1, BASE_START_YEAR + 2):
            try:
                future_years[yr] = parse_team_page(fetch(team_url(slug, yr)))
            except Exception as e:  # noqa: BLE001 — best effort, never fatal
                print(f"    warn: future year {yr} failed for {team_id}: {e}", file=sys.stderr)
                future_years[yr] = {}
            time.sleep(REQUEST_DELAY)

    players = []
    for name, info in base.items():
        p = {
            "name": name,
            "salary_2026_27": info["salary"],
            "contract_type": info["contract_type"],
            # Spotrac's cap table doesn't expose option/guarantee flags; default
            # them and refine later from the per-player contract page if needed.
            "player_option": False,
            "team_option": False,
            "guaranteed": True,
        }
        if BASE_START_YEAR + 1 in future_years and name in future_years[BASE_START_YEAR + 1]:
            p["salary_2027_28"] = future_years[BASE_START_YEAR + 1][name]["salary"]
        if BASE_START_YEAR + 2 in future_years and name in future_years[BASE_START_YEAR + 2]:
            p["salary_2028_29"] = future_years[BASE_START_YEAR + 2][name]["salary"]
        players.append(p)

    players.sort(key=lambda p: p["salary_2026_27"], reverse=True)

    return {
        "team_id": team_id,
        "team_name": meta["full_name"],
        "conference": meta["conference"],
        # repeater status isn't on the cap page — preserve prior value if we have it.
        "repeater": (existing or {}).get("repeater", False),
        "data_confidence": "verified",
        "data_source": "spotrac",
        "players": players,
        "dead_cap": [],
        "draft_picks_owed": (existing or {}).get("draft_picks_owed", []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--future", action="store_true",
                    help="also fetch 2027-28 and 2028-29 salaries")
    ap.add_argument("--only", help="comma-separated team_ids to import (testing)")
    ap.add_argument("--out", default=str(DATA_FILE), help="output JSON path")
    args = ap.parse_args()

    meta = json.loads(META_FILE.read_text())
    existing = {t["team_id"]: t for t in json.loads(DATA_FILE.read_text())} if DATA_FILE.exists() else {}

    targets = list(TEAM_SLUGS)
    if args.only:
        targets = [t.strip().upper() for t in args.only.split(",")]

    teams = []
    for i, tid in enumerate(targets, 1):
        slug = TEAM_SLUGS[tid]
        print(f"[{i}/{len(targets)}] {tid} ({slug}) …", flush=True)
        try:
            team = build_team(tid, slug, meta[tid], existing.get(tid), args.future)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR importing {tid}: {e}", file=sys.stderr)
            return 1
        print(f"    {len(team['players'])} players, "
              f"top: {team['players'][0]['name'] if team['players'] else '—'}")
        teams.append(team)

    # Preserve any teams we didn't re-import (e.g. --only runs).
    if args.only:
        merged = {t["team_id"]: t for t in json.loads(DATA_FILE.read_text())}
        for t in teams:
            merged[t["team_id"]] = t
        teams = list(merged.values())

    teams.sort(key=lambda t: t["team_id"])
    Path(args.out).write_text(json.dumps(teams, indent=2))
    print(f"\nWrote {len(teams)} teams -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
