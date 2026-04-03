import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, fetchJson } from "../api/client";

type HealthPayload = Record<string, unknown>;

export default function Dashboard() {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await fetchJson<HealthPayload>("/api/health");
        if (!cancelled) {
          setHealth(h);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) {
          setHealth(null);
          setErr(e instanceof ApiError ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="mt-2 text-slate-400">
          React console for EXStreamTV. Start the API on port{" "}
          <code className="rounded bg-slate-800 px-1">8411</code> and run{" "}
          <code className="rounded bg-slate-800 px-1">npm run dev</code> here.
        </p>
      </div>

      <section className="rounded-lg border border-slate-800 bg-brand-900/50 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          API health
        </h2>
        {err ? (
          <p className="mt-2 text-amber-400">{err}</p>
        ) : health ? (
          <pre className="mt-2 overflow-x-auto text-xs text-slate-300">
            {JSON.stringify(health, null, 2)}
          </pre>
        ) : (
          <p className="mt-2 text-slate-500">Loading…</p>
        )}
      </section>

      <ul className="flex flex-wrap gap-3 text-sm">
        <li>
          <Link
            className="text-brand-400 hover:underline"
            to="/channels"
          >
            Channels
          </Link>
        </li>
        <li>
          <Link
            className="text-brand-400 hover:underline"
            to="/schedules"
          >
            Schedules
          </Link>
        </li>
        <li>
          <Link
            className="text-brand-400 hover:underline"
            to="/schedule-history"
          >
            Schedule history (memento)
          </Link>
        </li>
      </ul>
    </div>
  );
}
