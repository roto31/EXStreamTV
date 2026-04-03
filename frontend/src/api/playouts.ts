import { fetchJson } from "./client";

export interface ChannelPlayoutRow {
  id: number;
  channel_id: number;
  program_schedule_id?: number | null;
  template_id?: number | null;
  playout_type?: string | null;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

export async function listChannelPlayouts(
  channelId: number
): Promise<ChannelPlayoutRow[]> {
  return fetchJson<ChannelPlayoutRow[]>(
    `/api/channels/${channelId}/playouts`
  );
}

export interface NowPlayingItem {
  id: number;
  title?: string | null;
  episode_title?: string | null;
  start_time?: string;
  finish_time?: string;
  progress_seconds?: number;
  duration_seconds?: number;
}

export interface NowPlayingResponse {
  playout_id: number;
  current_time: string;
  current: NowPlayingItem | null;
  next: {
    id: number;
    title?: string | null;
    start_time?: string;
    starts_in_seconds?: number;
  } | null;
}

export async function getNowPlaying(
  playoutId: number
): Promise<NowPlayingResponse> {
  return fetchJson<NowPlayingResponse>(
    `/api/playouts/${playoutId}/now-playing`
  );
}

export interface PlayoutItemRow {
  id: number;
  media_item_id?: number | null;
  source_url?: string | null;
  title?: string | null;
  episode_title?: string | null;
  start_time: string;
  finish_time: string;
  filler_kind?: string | null;
  custom_title?: string | null;
}

export interface PlayoutItemsResponse {
  playout_id: number;
  items: PlayoutItemRow[];
  offset: number;
  limit: number;
  count: number;
}

export async function listPlayoutItems(
  playoutId: number,
  limit = 20,
  offset = 0
): Promise<PlayoutItemsResponse> {
  const q = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return fetchJson<PlayoutItemsResponse>(
    `/api/playouts/${playoutId}/items?${q}`
  );
}
