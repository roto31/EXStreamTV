import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { listChannels, type ChannelRow } from "../api/channels";

export default function ChannelsPage() {
  const [rows, setRows] = useState<ChannelRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await listChannels();
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
        <h1 className="text-2xl font-bold text-white">Channels</h1>
        <p className="mt-4 text-amber-400">{err}</p>
      </div>
    );
  }

  if (!rows) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-white">Channels</h1>
        <p className="mt-4 text-slate-500">Loading…</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Channels</h1>
      <p className="mt-2 text-slate-400">{rows.length} channel(s)</p>
      <ul className="mt-6 space-y-2">
        {rows.map((c) => (
          <li key={c.id}>
            <Link
              to={`/channels/${c.id}`}
              className="block rounded-lg border border-slate-800 bg-brand-900/40 px-4 py-3 transition hover:border-brand-500/50"
            >
              <span className="font-medium text-white">
                {c.name ?? `Channel ${c.id}`}
              </span>
              <span className="ml-2 text-slate-500">
                #{c.number ?? c.id}
                {c.enabled === false ? " · disabled" : ""}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
