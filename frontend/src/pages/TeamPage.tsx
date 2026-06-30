import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchTeam, fetchProjection } from "../api/client";
import type { TeamDetail, TeamProjection } from "../types";
import CapThresholdBar from "../components/CapThresholdBar";

function fmtMoney(n: number): string {
  return `$${n.toLocaleString()}`;
}

function fmtM(n: number): string {
  return `$${(n / 1_000_000).toFixed(1)}M`;
}

export default function TeamPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [projection, setProjection] = useState<TeamProjection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!teamId) return;
    let active = true;
    setLoading(true);
    Promise.all([fetchTeam(teamId), fetchProjection(teamId, 3)])
      .then(([t, p]) => {
        if (!active) return;
        setTeam(t);
        setProjection(p);
        setError(null);
      })
      .catch((e) => active && setError(e?.message ?? "Failed to load team"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [teamId]);

  if (loading) return <div className="p-8 text-slate-400">Loading…</div>;
  if (error) return <div className="p-8 text-red-400">{error}</div>;
  if (!team) return <div className="p-8 text-slate-400">No team found.</div>;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Link to="/" className="text-sm text-blue-400 hover:underline">
        ← All teams
      </Link>

      <header className="mb-6 mt-2 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">{team.team_name}</h1>
          <p className="text-slate-400">
            {team.conference} · {team.roster_count} players
            {team.repeater && " · Repeater"}
            {team.data_confidence === "approximate" && " · approx. data"}
          </p>
        </div>
        <span className="rounded-full bg-slate-700 px-3 py-1 text-sm font-medium text-white">
          {team.apron_status.tier}
        </span>
      </header>

      <section className="mb-8 rounded-lg bg-slate-800 p-5">
        <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <div className="text-xs uppercase text-slate-400">Payroll</div>
            <div className="text-xl font-bold text-white">{fmtM(team.payroll)}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-slate-400">Cap Space</div>
            <div className="text-xl font-bold text-white">{fmtM(team.cap_space)}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-slate-400">Luxury Tax</div>
            <div className="text-xl font-bold text-amber-400">{fmtM(team.luxury_tax_bill)}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-slate-400">Over Tax</div>
            <div className="text-xl font-bold text-white">{fmtM(team.apron_status.amount_over_tax)}</div>
          </div>
        </div>
        <CapThresholdBar payroll={team.payroll} height={28} showLabels />
      </section>

      {team.restrictions.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold text-white">Restrictions</h2>
          <ul className="space-y-1">
            {team.restrictions.map((r) => (
              <li key={r} className="flex items-start gap-2 text-slate-300">
                <span className="text-red-400">✕</span>
                {r}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold text-white">Roster</h2>
        <div className="overflow-x-auto rounded-lg border border-slate-700">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800 text-slate-400">
              <tr>
                <th className="px-4 py-2">Player</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2 text-right">2026-27</th>
                <th className="px-4 py-2 text-right">2027-28</th>
                <th className="px-4 py-2 text-right">2028-29</th>
                <th className="px-4 py-2">Notes</th>
              </tr>
            </thead>
            <tbody>
              {team.players.map((p) => (
                <tr key={p.name} className="border-t border-slate-800 text-slate-200">
                  <td className="px-4 py-2 font-medium">{p.name}</td>
                  <td className="px-4 py-2 text-slate-400">{p.contract_type}</td>
                  <td className="px-4 py-2 text-right">{fmtMoney(p.salary_2026_27)}</td>
                  <td className="px-4 py-2 text-right text-slate-400">
                    {p.salary_2027_28 ? fmtMoney(p.salary_2027_28) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-slate-400">
                    {p.salary_2028_29 ? fmtMoney(p.salary_2028_29) : "—"}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-500">
                    {p.player_option && "PO "}
                    {p.team_option && "TO "}
                    {!p.guaranteed && "Non-gtd"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {projection && (
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold text-white">3-Year Projection</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {projection.projection.map((s) => (
              <div key={s.season} className="rounded-lg bg-slate-800 p-4">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">{s.season}</span>
                  {s.projected && (
                    <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-300">
                      projected
                    </span>
                  )}
                </div>
                <div className="mt-2 text-lg font-bold text-white">{fmtM(s.payroll)}</div>
                <div className="text-sm text-slate-400">{s.tier}</div>
                {s.luxury_tax_bill > 0 && (
                  <div className="text-sm text-amber-400">Tax {fmtM(s.luxury_tax_bill)}</div>
                )}
                <div className="mt-1 text-xs text-slate-500">
                  {s.roster_count_with_salary} under contract
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
