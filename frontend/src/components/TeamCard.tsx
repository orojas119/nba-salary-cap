import { Link } from "react-router-dom";
import type { Team, Tier } from "../types";
import CapThresholdBar from "./CapThresholdBar";

const TIER_COLORS: Record<Tier, string> = {
  "Under Tax": "bg-green-600",
  "Luxury Tax": "bg-blue-600",
  "First Apron": "bg-orange-600",
  "Second Apron": "bg-red-600",
};

function fmtMillions(n: number): string {
  return `$${(n / 1_000_000).toFixed(1)}M`;
}

export default function TeamCard({ team }: { team: Team }) {
  return (
    <Link
      to={`/team/${team.team_id}`}
      className="block rounded-lg border border-slate-700 bg-slate-800 p-4 transition hover:border-slate-500 hover:bg-slate-700"
    >
      <div className="mb-2 flex items-center justify-between">
        <div>
          <span className="text-sm font-mono text-slate-400">{team.team_id}</span>
          <h3 className="text-lg font-semibold text-white">{team.team_name}</h3>
        </div>
        <span
          className={`rounded-full px-2 py-1 text-xs font-medium text-white ${TIER_COLORS[team.apron_status.tier]}`}
        >
          {team.apron_status.tier}
        </span>
      </div>

      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-2xl font-bold text-white">{fmtMillions(team.payroll)}</span>
        {team.luxury_tax_bill > 0 && (
          <span className="text-sm text-amber-400">
            Tax {fmtMillions(team.luxury_tax_bill)}
          </span>
        )}
        {team.below_floor && (
          <span className="text-sm text-red-400">Below floor</span>
        )}
      </div>

      <CapThresholdBar payroll={team.payroll} height={16} />
    </Link>
  );
}
