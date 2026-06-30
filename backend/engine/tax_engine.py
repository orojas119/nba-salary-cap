from engine.constants import SEASONS


def total_payroll(salaries: list[float]) -> float:
    return sum(salaries)


def cap_space(payroll: float, season: str) -> float:
    """Returns cap minus payroll. Negative means the team is over the cap."""
    return SEASONS[season]["SALARY_CAP"] - payroll


def luxury_tax_bill(payroll: float, season: str, repeater: bool = False) -> float:
    """
    Apply incremental CBA bracket rates to every dollar above the luxury tax line.

    Repeater teams (paid tax in 3 of the prior 4 seasons) pay an extra $1.00 per
    dollar in every bracket.  The open-ended bracket ($20M+ over the line) starts
    at $3.75/$1 and escalates +$0.50 for each additional $5M chunk of overage.

    Returns 0 if payroll is at or below the tax line.
    """
    s = SEASONS[season]
    tax_line = s["LUXURY_TAX"]

    if payroll <= tax_line:
        return 0.0

    amount_over = payroll - tax_line
    repeater_adder = 1.0 if repeater else 0.0
    total_tax = 0.0

    # ── Fixed brackets 1–4 ──────────────────────────────────────────────────
    fixed_brackets = [
        (0,           5_000_000, 1.50),
        (5_000_000,  10_000_000, 1.75),
        (10_000_000, 15_000_000, 2.50),
        (15_000_000, 20_000_000, 3.25),
    ]

    for lower, upper, rate in fixed_brackets:
        if amount_over <= lower:
            break
        # Dollars of payroll that fall within this bracket
        bracket_dollars = min(amount_over, upper) - lower
        total_tax += bracket_dollars * (rate + repeater_adder)

    # ── Open-ended bracket: $20M+ above the tax line ─────────────────────────
    # Rate begins at $3.75/$1 for the first $5M chunk and climbs +$0.50 per
    # subsequent $5M chunk.  Repeater adder applies here too.
    if amount_over > 20_000_000:
        remaining = amount_over - 20_000_000
        base_rate = 3.75 + repeater_adder
        chunk = 0
        while remaining > 0:
            # Each $5M chunk has its own escalated rate
            chunk_rate = base_rate + (chunk * 0.50)
            chunk_dollars = min(remaining, 5_000_000)
            total_tax += chunk_dollars * chunk_rate
            remaining -= chunk_dollars
            chunk += 1

    return round(total_tax, 2)


def apron_status(payroll: float, season: str) -> dict:
    """
    Return a dictionary describing which thresholds the team has crossed
    and how far they are from each apron.  amount_to_* is negative when over.
    """
    s = SEASONS[season]
    tax_line = s["LUXURY_TAX"]
    first_apron = s["FIRST_APRON"]
    second_apron = s["SECOND_APRON"]

    over_tax = payroll > tax_line
    over_first = payroll > first_apron
    over_second = payroll > second_apron

    if over_second:
        tier = "Second Apron"
    elif over_first:
        tier = "First Apron"
    elif over_tax:
        tier = "Luxury Tax"
    else:
        tier = "Under Tax"

    return {
        "over_tax": over_tax,
        "over_first_apron": over_first,
        "over_second_apron": over_second,
        "amount_over_tax": round(max(0.0, payroll - tax_line), 2),
        "amount_to_first_apron": round(first_apron - payroll, 2),  # negative if over
        "amount_to_second_apron": round(second_apron - payroll, 2),
        "tier": tier,
    }


def team_financials(team: dict, season: str) -> dict:
    """
    Top-level function.  Takes a team dict from the seed JSON and returns a
    complete financial snapshot: payroll, cap space, tax bill, apron tier,
    floor status, and the list of roster-construction restrictions the team faces.
    """
    season_key = f"salary_{season.replace('-', '_')}"

    salaries = [
        p[season_key]
        for p in team["players"]
        if season_key in p and p.get("guaranteed", True)
    ]
    dead_cap_total = sum(d.get("amount", 0) for d in team.get("dead_cap", []))

    payroll = total_payroll(salaries) + dead_cap_total
    space = cap_space(payroll, season)
    tax_bill = luxury_tax_bill(payroll, season, team.get("repeater", False))
    apron = apron_status(payroll, season)

    s = SEASONS[season]
    floor = s["SALARY_CAP"] * s["TAX_FLOOR"]  # teams must spend to 90 % of cap

    # ── Restrictions by tier ──────────────────────────────────────────────────
    restrictions: list[str] = []

    if apron["tier"] in ("First Apron", "Second Apron"):
        restrictions += [
            "Cannot use bi-annual exception",
            "Cannot acquire players via sign-and-trade",
            "Cannot use full mid-level exception",
        ]

    if apron["tier"] == "Second Apron":
        restrictions += [
            "Cannot aggregate salaries in trades",
            "Cannot send cash in trades",
            "Frozen first-round pick (7 years out)",
            "Cannot use taxpayer mid-level exception",
        ]

    return {
        "team_id": team["team_id"],
        "team_name": team["team_name"],
        "season": season,
        "roster_count": len(team["players"]),
        "payroll": round(payroll, 2),
        "cap_space": round(space, 2),
        "below_floor": payroll < floor,
        "floor_deficit": round(max(0.0, floor - payroll), 2),
        "luxury_tax_bill": tax_bill,
        "apron_status": apron,
        "restrictions": restrictions,
    }
