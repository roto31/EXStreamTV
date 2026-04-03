import { fetchJson } from "./client";

export interface ScheduleRow {
  id: number;
  name?: string;
  channel_id?: number | null;
  keep_multi_part_episodes_together?: boolean;
  treat_collections_as_shows?: boolean;
  shuffle_schedule_items?: boolean;
  random_start_point?: boolean;
  is_yaml_source?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export async function listSchedules(): Promise<ScheduleRow[]> {
  return fetchJson<ScheduleRow[]>("/api/schedules");
}

export async function getSchedule(id: number): Promise<ScheduleRow> {
  return fetchJson<ScheduleRow>(`/api/schedules/${id}`);
}
