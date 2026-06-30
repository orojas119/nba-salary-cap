export type Tier = "Under Tax" | "Luxury Tax" | "First Apron" | "Second Apron";

export interface ApronStatus {
  over_tax: boolean;
  over_first_apron: boolean;
  over_second_apron: boolean;
  amount_over_tax: number;
  amount_to_first_apron: number;
  amount_to_second_apron: number;
  tier: Tier;
}

export interface Team {
  team_id: string;
  team_name: string;
  season: string;
  roster_count: number;
  payroll: number;
  cap_space: number;
  below_floor: boolean;
  floor_deficit: number;
  luxury_tax_bill: number;
  apron_status: ApronStatus;
  restrictions: string[];
}

export interface Player {
  name: string;
  salary_2026_27: number;
  salary_2027_28?: number;
  salary_2028_29?: number;
  contract_type: string;
  player_option: boolean;
  team_option: boolean;
  guaranteed: boolean;
}

export interface DeadCap {
  player?: string;
  amount?: number;
}

export interface DraftPick {
  year: number;
  round: number;
  to: string;
  protected: string | null;
}

export interface TeamDetail extends Team {
  conference: string;
  repeater: boolean;
  data_confidence?: string;
  players: Player[];
  dead_cap: DeadCap[];
  draft_picks_owed: DraftPick[];
}

export interface LeagueSummary {
  season: string;
  projected: boolean;
  team_count: number;
  total_league_payroll: number;
  total_tax_collected: number;
  average_payroll: number;
  teams_over_cap: number;
  teams_over_tax: number;
  teams_over_first_apron: number;
  teams_over_second_apron: number;
  teams_below_floor: number;
  highest_payroll_team: { team_name: string; payroll: number };
  lowest_payroll_team: { team_name: string; payroll: number };
}

export interface ProjectionSeason {
  season: string;
  projected: boolean;
  payroll: number;
  cap_space: number;
  luxury_tax_bill: number;
  tier: Tier;
  roster_count_with_salary: number;
}

export interface TeamProjection {
  team_id: string;
  team_name: string;
  base_season: string;
  seasons_projected: number;
  projection: ProjectionSeason[];
}

// 2026-27 league thresholds (mirror of backend/engine/constants.py) used by the
// CapThresholdBar to position zones and the payroll marker.
export const THRESHOLDS = {
  SALARY_CAP: 165_000_000,
  LUXURY_TAX: 201_048_000,
  FIRST_APRON: 209_661_000,
  SECOND_APRON: 222_372_000,
};
