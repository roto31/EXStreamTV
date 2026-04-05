import { Link } from "react-router-dom";
import { fetchJson } from "../api/client";
import { useAsync } from "../hooks/useAsync";

type HealthPayload = Record<string, unknown>;

export default function Dashboard() {
  const { data: health, error: err, loading } = useAsync(
    () => fetchJson<HealthPayload>("/api/health"),
    []
  );

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
        ) : loading ? (
          <p className="mt-2 text-slate-500">Loading…</p>
        ) : null}
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
