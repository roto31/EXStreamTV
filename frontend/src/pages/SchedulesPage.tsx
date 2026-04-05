import { Link } from "react-router-dom";
import { listSchedules, type ScheduleRow } from "../api/schedules";
import { useAsync } from "../hooks/useAsync";

export default function SchedulesPage() {
  const { data: rows, error: err, loading } = useAsync<ScheduleRow[]>(
    () => listSchedules(),
    []
  );

  if (err) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-white">Schedules</h1>
        <p className="mt-4 text-amber-400">{err}</p>
      </div>
    );
  }

  if (loading || !rows) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-white">Schedules</h1>
        <p className="mt-4 text-slate-500">Loading…</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Schedules</h1>
      <p className="mt-2 text-slate-400">{rows.length} schedule(s)</p>
      <ul className="mt-6 space-y-2">
        {rows.map((s) => (
          <li key={s.id}>
            <Link
              to={`/schedules/${s.id}`}
              className="block rounded-lg border border-slate-800 bg-brand-900/40 px-4 py-3 transition hover:border-brand-500/50"
            >
              <span className="font-medium text-white">
                {s.name ?? `Schedule ${s.id}`}
              </span>
              <span className="ml-2 text-slate-500">id {s.id}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
