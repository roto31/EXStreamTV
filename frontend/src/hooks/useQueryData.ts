import { useQuery } from "@tanstack/react-query";
import { listChannels, getChannel } from "../api/channels";
import { listSchedules, getSchedule } from "../api/schedules";
import { listChannelPlayouts, getNowPlaying, listPlayoutItems } from "../api/playouts";
import { fetchJson } from "../api/client";

export function useChannels() {
  return useQuery({ queryKey: ["channels"], queryFn: listChannels });
}
export function useChannel(id: number) {
  return useQuery({ queryKey: ["channels", id], queryFn: () => getChannel(id), enabled: Number.isFinite(id) });
}
export function useSchedules() {
  return useQuery({ queryKey: ["schedules"], queryFn: listSchedules });
}
export function useSchedule(id: number) {
  return useQuery({ queryKey: ["schedules", id], queryFn: () => getSchedule(id), enabled: Number.isFinite(id) });
}
export function useChannelPlayouts(channelId: number) {
  return useQuery({ queryKey: ["playouts", channelId], queryFn: () => listChannelPlayouts(channelId), enabled: Number.isFinite(channelId) });
}
export function useNowPlaying(playoutId: number | undefined) {
  return useQuery({ queryKey: ["now-playing", playoutId], queryFn: () => getNowPlaying(playoutId!), enabled: playoutId != null, refetchInterval: 15000 });
}
export function usePlayoutItems(playoutId: number | undefined, limit = 15) {
  return useQuery({ queryKey: ["playout-items", playoutId, limit], queryFn: () => listPlayoutItems(playoutId!, limit, 0), enabled: playoutId != null });
}
export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: () => fetchJson<Record<string, unknown>>("/api/health"), refetchInterval: 30000 });
}
