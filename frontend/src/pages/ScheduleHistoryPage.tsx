import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { captureSnapshot, revertSnapshot } from "../api/scheduleHistory";
import { usePersona } from "../context/PersonaContext";

export default function ScheduleHistoryPage() {
  const { personaId } = usePersona();
  const isViewer = personaId === "viewer";
  const [idsText, setIdsText] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [revertId, setRevertId] = useState("");

  async function onCapture(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    const parts = idsText
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const channel_ids = parts.map((p) => Number.parseInt(p, 10));
    if (channel_ids.some((n) => !Number.isFinite(n))) {
      setMsg("Enter numeric channel ids separated by commas or spaces.");
      return;
    }
    setBusy(true);
    try {
      const res = await captureSnapshot({
        channel_ids,
        persona_id: personaId,
        label: label.trim() || null,
      });
      setMsg(`Captured snapshot id=${res.id}`);
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRevert(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    const hid = Number.parseInt(revertId, 10);
    if (!Number.isFinite(hid)) {
      setMsg("Enter a numeric history id to revert.");
      return;
    }
    setBusy(true);
    try {
      const res = await revertSnapshot(hid, personaId);
      setMsg(
        `Reverted: ${res.status}${res.items_restored != null ? ` (${res.items_restored} items)` : ""}`
      );
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (isViewer) {
    return (
      <div className="max-w-xl space-y-4">
        <h1 className="text-2xl font-bold text-white">Schedule history</h1>
        <p className="text-slate-400">
          The <strong>viewer</strong> persona is read-only. Snapshot capture and
          revert are hidden. Switch to <strong>operator</strong> or{" "}
          <strong>curator</strong> in{" "}
          <Link to="/settings" className="text-brand-400 hover:underline">
            Settings
          </Link>{" "}
          (persona selector in the header).
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Schedule history</h1>
        <p className="mt-2 text-slate-400">
          Memento capture uses the current <strong>Persona</strong> from the
          header ({personaId}).
        </p>
      </div>

      <form
        onSubmit={onCapture}
        className="space-y-4 rounded-lg border border-slate-800 bg-brand-900/40 p-4"
      >
        <h2 className="text-sm font-semibold text-slate-300">Capture snapshot</h2>
        <label className="block text-sm">
          <span className="text-slate-400">Channel ids</span>
          <input
            className="mt-1 w-full rounded-md border border-slate-700 bg-brand-950 px-3 py-2 text-slate-100"
            value={idsText}
            onChange={(e) => setIdsText(e.target.value)}
            placeholder="e.g. 1, 2, 3"
            disabled={busy}
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-400">Label (optional)</span>
          <input
            className="mt-1 w-full rounded-md border border-slate-700 bg-brand-950 px-3 py-2 text-slate-100"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            disabled={busy}
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-400 disabled:opacity-50"
        >
          POST /api/schedule-history/capture
        </button>
      </form>

      <form
        onSubmit={onRevert}
        className="space-y-4 rounded-lg border border-slate-800 bg-brand-900/40 p-4"
      >
        <h2 className="text-sm font-semibold text-slate-300">Revert</h2>
        <label className="block text-sm">
          <span className="text-slate-400">History id</span>
          <input
            className="mt-1 w-full rounded-md border border-slate-700 bg-brand-950 px-3 py-2 text-slate-100"
            value={revertId}
            onChange={(e) => setRevertId(e.target.value)}
            placeholder="id from capture response"
            disabled={busy}
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md border border-slate-600 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          POST /api/schedule-history/…/revert
        </button>
      </form>

      {msg ? (
        <p className="rounded-md border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-200">
          {msg}
        </p>
      ) : null}
    </div>
  );
}
