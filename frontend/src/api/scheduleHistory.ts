import { fetchJson } from "./client";

export interface CaptureBody {
  channel_ids: number[];
  persona_id?: string | null;
  label?: string | null;
}

export interface CaptureResponse {
  id: number;
  persona_id?: string | null;
  label?: string | null;
}

export async function captureSnapshot(
  body: CaptureBody
): Promise<CaptureResponse> {
  return fetchJson<CaptureResponse>("/api/schedule-history/capture", {
    method: "POST",
    json: body,
  });
}

export async function revertSnapshot(
  historyId: number,
  personaId?: string | null
): Promise<{ status: string; items_restored?: number }> {
  const q =
    personaId != null && personaId !== ""
      ? `?persona_id=${encodeURIComponent(personaId)}`
      : "";
  return fetchJson<{ status: string; items_restored?: number }>(
    `/api/schedule-history/${historyId}/revert${q}`,
    { method: "POST" }
  );
}
