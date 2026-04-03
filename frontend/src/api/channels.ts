import { fetchJson } from "./client";

export interface ChannelRow {
  id: number;
  number?: number;
  name?: string;
  group?: string;
  enabled?: boolean;
  logo_url?: string;
}

export async function listChannels(): Promise<ChannelRow[]> {
  return fetchJson<ChannelRow[]>("/api/channels");
}

export async function getChannel(id: number): Promise<ChannelRow> {
  return fetchJson<ChannelRow>(`/api/channels/${id}`);
}
