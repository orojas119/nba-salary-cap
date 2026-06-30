# NBA Salary Cap & Luxury Tax Engine

![Daily Validation](https://github.com/orojas119/nba-salary-cap/actions/workflows/daily-validate.yml/badge.svg)

A salary cap, luxury tax, and apron engine for the NBA, built around the CBA's
incremental tax bracket system. Ships with seed data for all 30 teams (2026-27)
and a FastAPI layer for a frontend.

## Layout

```
backend/
  engine/
    constants.py      league thresholds + projected future seasons
    tax_engine.py     pure calculation functions (cap, tax, apron, financials)
    test_engine.py    unit tests proving the bracket math
  data/
    teams_2026_27.json  30-team seed rosters
    team_meta.json      per-team colors/divisions for frontend theming
  scripts/
    validate_data.py    data-integrity gate (run in CI before deploy)
  main.py             FastAPI app
```

## Run locally

```bash
cd backend
pip install -r requirements.txt
python scripts/validate_data.py
python -m pytest engine/test_engine.py -v
uvicorn main:app --reload --port 8000
```

## Key endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /teams?sort=payroll&order=desc&conference=East&tier=second_apron` | Team financials with sorting + filtering |
| `GET /teams/{id}` | Single team's financial summary |
| `GET /teams/{id}/projection?seasons=3` | Multi-season projection (future thresholds estimated) |
| `GET /league/summary` | League-wide aggregates |
| `GET /meta` | Team colors/divisions for theming |
| `POST /calculate` | Tax + apron status for an arbitrary payroll |
| `GET`/`POST` `/refresh` | Clear the in-memory cache (called daily by CI) |

## CI

[`daily-validate.yml`](.github/workflows/daily-validate.yml) runs at 08:00 UTC
daily (and on demand): it validates the seed data, runs the engine tests, then
refreshes the deployed cache. Bad data fails the run before anything deploys.
