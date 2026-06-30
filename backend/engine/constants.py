# CBA-defined incremental luxury tax rates — verify against the current CBA each season.

# Estimated annual growth of cap/tax thresholds, used to project future seasons
# when no published figures exist. The CBA caps year-over-year cap growth at 10%;
# ~5% is a conservative middle estimate.
PROJECTED_CAP_GROWTH = 0.05

SEASONS: dict[str, dict] = {
    "2026-27": {
        "SALARY_CAP": 165_000_000,
        "LUXURY_TAX": 201_048_000,
        "FIRST_APRON": 209_661_000,
        "SECOND_APRON": 222_372_000,
        "TAX_FLOOR": 0.90,
        # Incremental tax rate per dollar above the luxury tax line.
        # Tuple: (band_low, band_high, rate_per_dollar).
        # The final band is open-ended; the rate escalates +$0.50 per additional $5M chunk.
        # Repeater tax adds $1.00 to each rate (team paid tax in 3 of prior 4 seasons).
        "STANDARD_BRACKETS": [
            (0,           5_000_000, 1.50),   # $0–5M over the line:   $1.50/$1
            (5_000_000,  10_000_000, 1.75),   # $5–10M over the line:  $1.75/$1
            (10_000_000, 15_000_000, 2.50),   # $10–15M over the line: $2.50/$1
            (15_000_000, 20_000_000, 3.25),   # $15–20M over the line: $3.25/$1
            (20_000_000, float("inf"), 3.75), # $20M+ over: $3.75/$1, then +$0.50 per $5M chunk
        ],
    }
}

# The seasons published in the CBA / NBA releases. Anything not in this set is a
# model projection (see PROJECTED_SEASONS below) and should be labelled as such.
PUBLISHED_SEASONS = frozenset(SEASONS)

# ── Projected future seasons ─────────────────────────────────────────────────
# Grow the cap, tax, and apron thresholds by PROJECTED_CAP_GROWTH per year off the
# most recent published season. Tax bracket *bands* are CBA-fixed dollar amounts,
# so they carry over unchanged; only the thresholds move.
def _project(base: dict, years_ahead: int) -> dict:
    factor = (1 + PROJECTED_CAP_GROWTH) ** years_ahead
    return {
        "SALARY_CAP": round(base["SALARY_CAP"] * factor),
        "LUXURY_TAX": round(base["LUXURY_TAX"] * factor),
        "FIRST_APRON": round(base["FIRST_APRON"] * factor),
        "SECOND_APRON": round(base["SECOND_APRON"] * factor),
        "TAX_FLOOR": base["TAX_FLOOR"],
        "STANDARD_BRACKETS": base["STANDARD_BRACKETS"],
    }


# Maps a future season label -> (base_season, years_ahead) used to derive it.
PROJECTED_SEASONS = {
    "2027-28": ("2026-27", 1),
    "2028-29": ("2026-27", 2),
}

for _label, (_base, _yrs) in PROJECTED_SEASONS.items():
    if _label not in SEASONS:
        SEASONS[_label] = _project(SEASONS[_base], _yrs)

