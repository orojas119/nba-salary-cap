import { useEffect, useMemo, useState } from "react";
import { fetchTeams, fetchLeagueSummary } from "../api/client";
import type { Team, LeagueSummary } from "../types";
import TeamCard from "../components/TeamCard";

type SortKey = "payroll" | "tax_bill" | "cap_space" | "team_name";
type ConfFilter = "All" | "East" | "West";
type TierFilter = "" | "under_tax" | "luxury_tax" | "first_apron" | "second_apron";

const TIER_LABELS: Record<Exclude<TierFilter, "">, string> = {
  under_tax: "Under Tax",
  luxury_tax: "Luxury Tax",
  first_apron: "First Apron",
  second_apron: "Second Apron",
};

function fmtMoney(n: number): string {
  return `$${(n / 1_000_000).toFixed(1)}M`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-xl font-bold text-white">{value}</div>
    </div>
  );
}

export default function Home() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [summary, setSummary] = useState<LeagueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sort, setSort] = useState<SortKey>("payroll");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [conference, setConference] = useState<ConfFilter>("All");
  const [tier, setTier] = useState<TierFilter>("");

  // Conference filter is applied server-side (the /teams list payload doesn't
  // carry a conference field). Sort + tier are applied client-side for snappiness.
  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchTeams(conference === "All" ? {} : { conference })
      .then((t) => {
        if (active) {
          setTeams(t);
          setError(null);
        }
      })
      .catch((e) => active && setError(e?.message ?? "Failed to load teams"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [conference]);

  useEffect(() => {
    let active = true;
    fetchLeagueSummary()
      .then((s) => active && setSummary(s))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const visibleTeams = useMemo(() => {
    let list = [...teams];
    if (tier) {
      list = list.filter((t) => t.apron_status.tier === TIER_LABELS[tier]);
    }
    const dir = order === "desc" ? -1 : 1;
    list.sort((a, b) => {
      switch (sort) {
        case "team_name":
          return a.team_name.localeCompare(b.team_name) * dir;
        case "tax_bill":
          return (a.luxury_tax_bill - b.luxury_tax_bill) * dir;
        case "cap_space":
          return (a.cap_space - b.cap_space) * dir;
        default:
          return (a.payroll - b.payroll) * dir;
      }
    });
    return list;
  }, [teams, sort, order, tier]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white">NBA Salary Cap Tracker</h1>
        <p className="text-slate-400">
          2026-27 season · cap, luxury tax, and apron status for all 30 teams
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-700 bg-red-950 p-4 text-red-300">
          {error}
        </div>
      )}

      {summary && (
        <section className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat label="Total Payroll" value={fmtMoney(summary.total_league_payroll)} />
          <Stat label="Total Tax" value={fmtMoney(summary.total_tax_collected)} />
          <Stat label="Over Tax" value={String(summary.teams_over_tax)} />
          <Stat label="Over 2nd Apron" value={String(summary.teams_over_second_apron)} />
        </section>
      )}

      <section className="mb-6 flex flex-wrap items-center gap-3">
        <label className="text-sm text-slate-400">
          Sort
          <select
            className="ml-2 rounded bg-slate-800 px-2 py-1 text-white"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
          >
            <option value="payroll">Payroll</option>
            <option value="tax_bill">Tax Bill</option>
            <option value="cap_space">Cap Space</option>
            <option value="team_name">Name</option>
          </select>
        </label>

        <button
          className="rounded bg-slate-800 px-3 py-1 text-sm text-white hover:bg-slate-700"
          onClick={() => setOrder((o) => (o === "desc" ? "asc" : "desc"))}
        >
          {order === "desc" ? "↓ Desc" : "↑ Asc"}
        </button>

        <label className="text-sm text-slate-400">
          Conference
          <select
            className="ml-2 rounded bg-slate-800 px-2 py-1 text-white"
            value={conference}
            onChange={(e) => setConference(e.target.value as ConfFilter)}
          >
            <option value="All">All</option>
            <option value="East">East</option>
            <option value="West">West</option>
          </select>
        </label>

        <label className="text-sm text-slate-400">
          Tier
          <select
            className="ml-2 rounded bg-slate-800 px-2 py-1 text-white"
            value={tier}
            onChange={(e) => setTier(e.target.value as TierFilter)}
          >
            <option value="">All</option>
            <option value="under_tax">Under Tax</option>
            <option value="luxury_tax">Luxury Tax</option>
            <option value="first_apron">First Apron</option>
            <option value="second_apron">Second Apron</option>
          </select>
        </label>
      </section>

      {loading ? (
        <p className="text-slate-400">Loading teams…</p>
      ) : (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visibleTeams.map((t) => (
            <TeamCard key={t.team_id} team={t} />
          ))}
        </section>
      )}
    </div>
  );
}
