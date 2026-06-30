import axios from "axios";
import type {
  Team,
  TeamDetail,
  LeagueSummary,
  TeamProjection,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const api = axios.create({ baseURL: BASE_URL });

export interface TeamQuery {
  season?: string;
  sort?: "payroll" | "tax_bill" | "cap_space" | "team_name";
  order?: "asc" | "desc";
  conference?: "East" | "West";
  tier?: "under_tax" | "luxury_tax" | "first_apron" | "second_apron";
}

export async function fetchTeams(query: TeamQuery = {}): Promise<Team[]> {
  const { data } = await api.get<Team[]>("/teams", { params: query });
  return data;
}

export async function fetchTeam(
  teamId: string,
  season = "2026-27"
): Promise<TeamDetail> {
  const { data } = await api.get<TeamDetail>(`/teams/${teamId}`, {
    params: { season },
  });
  return data;
}

export async function fetchLeagueSummary(
  season = "2026-27"
): Promise<LeagueSummary> {
  const { data } = await api.get<LeagueSummary>("/league/summary", {
    params: { season },
  });
  return data;
}

export async function fetchProjection(
  teamId: string,
  seasons = 3
): Promise<TeamProjection> {
  const { data } = await api.get<TeamProjection>(
    `/teams/${teamId}/projection`,
    { params: { seasons } }
  );
  return data;
}

export { BASE_URL };
