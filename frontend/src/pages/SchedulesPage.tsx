import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { listSchedules, type ScheduleRow } from "../api/schedules";

export default function SchedulesPage() {
  const [rows, setRows] = useState<ScheduleRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await listSchedules();
        if (!cancelled) {
          setRows(data);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) {
          setRows(null);
          setErr(e instanceof ApiError ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (err) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-white">Schedules</h1>
        <p className="mt-4 text-amber-400">{err}</p>
      </div>
    );
  }

  if (!rows) {
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
