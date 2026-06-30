import json
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.constants import PROJECTED_SEASONS, PUBLISHED_SEASONS, SEASONS
from engine.tax_engine import apron_status, luxury_tax_bill, team_financials

app = FastAPI(title="NBA Salary Cap Engine", version="0.2.0")

# Allow a frontend (any origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"

# Map the API's tier filter values to the engine's tier strings.
TIER_FILTERS = {
    "under_tax": "Under Tax",
    "luxury_tax": "Luxury Tax",
    "first_apron": "First Apron",
    "second_apron": "Second Apron",
}
SORT_KEYS = {
    "payroll": lambda f: f["payroll"],
    "tax_bill": lambda f: f["luxury_tax_bill"],
    "cap_space": lambda f: f["cap_space"],
    "team_name": lambda f: f["team_name"],
}


# ─────────────────────────────── caching ─────────────────────────────────────
# This data changes at most once daily, so we cache computed responses in-memory
# for 24h. A daily GitHub Action calls GET /refresh after updating the JSON.
CACHE_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value):
    _cache[key] = (time.time(), value)


def _load_teams_raw(season: str) -> dict[str, dict]:
    """Load and index the seed JSON for a season (file load is itself cached)."""
    cache_key = f"raw:{season}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Future/projected seasons reuse the base season's roster file.
    file_season = season
    if season in PROJECTED_SEASONS:
        file_season = PROJECTED_SEASONS[season][0]

    path = DATA_DIR / f"teams_{file_season.replace('-', '_')}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No data for season {season!r}")
    with open(path) as f:
        indexed = {t["team_id"]: t for t in json.load(f)}
    _cache_set(cache_key, indexed)
    return indexed


def _all_financials(season: str) -> list[dict]:
    cache_key = f"financials:{season}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    teams = _load_teams_raw(season)
    result = [team_financials(t, season) for t in teams.values()]
    _cache_set(cache_key, result)
    return result


def _require_season(season: str):
    if season not in SEASONS:
        raise HTTPException(
            status_code=400,
            detail=f"Season {season!r} not supported. Valid: {sorted(SEASONS)}",
        )


# ─────────────────────────────── routes ──────────────────────────────────────

@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "nba-salary-cap-engine",
        "published_seasons": sorted(PUBLISHED_SEASONS),
        "projected_seasons": sorted(PROJECTED_SEASONS),
    }


@app.get("/refresh")
def refresh():
    """Clear all cached responses. Called by the daily data-update Action."""
    count = len(_cache)
    _cache.clear()
    return {"status": "cache cleared", "entries_cleared": count}


@app.get("/meta")
def team_meta():
    """Team logos/colors/divisions for frontend theming."""
    with open(DATA_DIR / "team_meta.json") as f:
        return json.load(f)


@app.get("/teams")
def list_teams(
    season: str = "2026-27",
    sort: Optional[str] = Query(None, description="payroll | tax_bill | cap_space | team_name"),
    order: str = Query("desc", description="asc | desc"),
    conference: Optional[str] = Query(None, description="East | West"),
    tier: Optional[str] = Query(None, description="under_tax | luxury_tax | first_apron | second_apron"),
):
    _require_season(season)
    financials = list(_all_financials(season))

    # ── filtering ──
    if conference is not None:
        conf = conference.strip().title()
        if conf not in ("East", "West"):
            raise HTTPException(status_code=400, detail="conference must be 'East' or 'West'")
        raw = _load_teams_raw(season)
        financials = [f for f in financials if raw[f["team_id"]]["conference"] == conf]

    if tier is not None:
        if tier not in TIER_FILTERS:
            raise HTTPException(status_code=400, detail=f"tier must be one of {sorted(TIER_FILTERS)}")
        wanted = TIER_FILTERS[tier]
        financials = [f for f in financials if f["apron_status"]["tier"] == wanted]

    # ── sorting ──
    if sort is not None:
        if sort not in SORT_KEYS:
            raise HTTPException(status_code=400, detail=f"sort must be one of {sorted(SORT_KEYS)}")
        if order not in ("asc", "desc"):
            raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")
        financials.sort(key=SORT_KEYS[sort], reverse=(order == "desc"))

    return financials


@app.get("/teams/{team_id}")
def get_team(team_id: str, season: str = "2026-27"):
    _require_season(season)
    teams = _load_teams_raw(season)
    tid = team_id.upper()
    if tid not in teams:
        raise HTTPException(status_code=404, detail=f"Team {team_id!r} not found for season {season!r}")
    return team_financials(teams[tid], season)


@app.get("/teams/{team_id}/projection")
def team_projection(
    team_id: str,
    seasons: int = Query(3, ge=1, le=3, description="Number of seasons to project (1-3)"),
    season: str = "2026-27",
):
    """Project a team's financials across consecutive seasons using each year's
    salary fields. Future-season thresholds are model estimates (see constants).
    Note: future payrolls reflect only players with guaranteed salary figures for
    that year — expiring contracts and cap holds are not modeled."""
    _require_season(season)
    teams = _load_teams_raw(season)
    tid = team_id.upper()
    if tid not in teams:
        raise HTTPException(status_code=404, detail=f"Team {team_id!r} not found")

    # Ordered season labels starting from the requested base season.
    ordered = sorted(SEASONS)
    if season not in ordered:
        raise HTTPException(status_code=400, detail=f"Season {season!r} not available")
    start = ordered.index(season)
    window = ordered[start:start + seasons]

    projection = []
    for s in window:
        fin = team_financials(teams[tid], s)
        projection.append({
            "season": s,
            "projected": s not in PUBLISHED_SEASONS,
            "payroll": fin["payroll"],
            "cap_space": fin["cap_space"],
            "luxury_tax_bill": fin["luxury_tax_bill"],
            "tier": fin["apron_status"]["tier"],
            "roster_count_with_salary": len([
                p for p in teams[tid]["players"]
                if f"salary_{s.replace('-', '_')}" in p and p.get("guaranteed", True)
            ]),
        })

    return {
        "team_id": tid,
        "team_name": teams[tid]["team_name"],
        "base_season": season,
        "seasons_projected": len(window),
        "projection": projection,
    }


@app.get("/league/summary")
def league_summary(season: str = "2026-27"):
    _require_season(season)
    cache_key = f"summary:{season}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    financials = _all_financials(season)
    s = SEASONS[season]

    payrolls = [(f["team_name"], f["payroll"]) for f in financials]
    total_payroll = sum(p for _, p in payrolls)
    total_tax = sum(f["luxury_tax_bill"] for f in financials)

    highest = max(payrolls, key=lambda x: x[1])
    lowest = min(payrolls, key=lambda x: x[1])

    summary = {
        "season": season,
        "projected": season not in PUBLISHED_SEASONS,
        "team_count": len(financials),
        "total_league_payroll": round(total_payroll, 2),
        "total_tax_collected": round(total_tax, 2),
        "average_payroll": round(total_payroll / len(financials), 2),
        "teams_over_cap": sum(1 for f in financials if f["payroll"] > s["SALARY_CAP"]),
        "teams_over_tax": sum(1 for f in financials if f["apron_status"]["over_tax"]),
        "teams_over_first_apron": sum(1 for f in financials if f["apron_status"]["over_first_apron"]),
        "teams_over_second_apron": sum(1 for f in financials if f["apron_status"]["over_second_apron"]),
        "teams_below_floor": sum(1 for f in financials if f["below_floor"]),
        "highest_payroll_team": {"team_name": highest[0], "payroll": round(highest[1], 2)},
        "lowest_payroll_team": {"team_name": lowest[0], "payroll": round(lowest[1], 2)},
    }
    _cache_set(cache_key, summary)
    return summary


class PayrollQuery(BaseModel):
    payroll: float
    season: str = "2026-27"
    repeater: bool = False


@app.post("/calculate")
def calculate(q: PayrollQuery):
    _require_season(q.season)
    return {
        "payroll": q.payroll,
        "season": q.season,
        "repeater": q.repeater,
        "luxury_tax_bill": luxury_tax_bill(q.payroll, q.season, q.repeater),
        "apron_status": apron_status(q.payroll, q.season),
    }
