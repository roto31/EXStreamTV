import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { getSchedule, type ScheduleRow } from "../api/schedules";

export default function ScheduleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const numId = id ? Number.parseInt(id, 10) : NaN;
  const [row, setRow] = useState<ScheduleRow | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(numId)) {
      setErr("Invalid schedule id");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await getSchedule(numId);
        if (!cancelled) {
          setRow(data);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) {
          setRow(null);
          setErr(e instanceof ApiError ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [numId]);

  if (!Number.isFinite(numId)) {
    return <p className="text-amber-400">Invalid schedule id.</p>;
  }

  if (err) {
    return (
      <div>
        <Link to="/schedules" className="text-brand-400 hover:underline">
          ← Schedules
        </Link>
        <h1 className="mt-4 text-2xl font-bold text-white">Schedule</h1>
        <p className="mt-4 text-amber-400">{err}</p>
      </div>
    );
  }

  if (!row) {
    return (
      <div>
        <Link to="/schedules" className="text-brand-400 hover:underline">
          ← Schedules
        </Link>
        <p className="mt-4 text-slate-500">Loading…</p>
      </div>
    );
  }

  const flags = [
    ["Multi-part episodes together", row.keep_multi_part_episodes_together],
    ["Treat collections as shows", row.treat_collections_as_shows],
    ["Shuffle items", row.shuffle_schedule_items],
    ["Random start point", row.random_start_point],
  ] as const;

  return (
    <div className="space-y-6">
      <Link to="/schedules" className="text-brand-400 hover:underline">
        ← Schedules
      </Link>
      <h1 className="text-2xl font-bold text-white">
        {row.name ?? `Schedule ${row.id}`}
      </h1>
      <p className="text-slate-400">id {row.id}</p>

      <section className="rounded-lg border border-slate-800 bg-brand-900/40 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Flags
        </h2>
        <ul className="mt-3 space-y-1 text-sm text-slate-300">
          {flags.map(([label, v]) => (
            <li key={label}>
              {label}:{" "}
              <span className={v ? "text-emerald-400" : "text-slate-500"}>
                {v ? "on" : "off"}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {(row.created_at || row.updated_at) && (
        <section className="text-xs text-slate-500">
          {row.created_at ? <div>Created {row.created_at}</div> : null}
          {row.updated_at ? <div>Updated {row.updated_at}</div> : null}
        </section>
      )}

      <details className="rounded-lg border border-slate-800 bg-slate-900/30 p-3">
        <summary className="cursor-pointer text-sm text-brand-400">
          Raw JSON
        </summary>
        <pre className="mt-2 overflow-x-auto text-xs text-slate-400">
          {JSON.stringify(row, null, 2)}
        </pre>
      </details>
    </div>
  );
}
