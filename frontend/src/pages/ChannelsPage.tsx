import { Link } from "react-router-dom";
import { listChannels, type ChannelRow } from "../api/channels";
import { useAsync } from "../hooks/useAsync";

export default function ChannelsPage() {
  const { data: rows, error: err, loading } = useAsync<ChannelRow[]>(
    () => listChannels(),
    []
  );

  if (err) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-white">Channels</h1>
        <p className="mt-4 text-amber-400">{err}</p>
      </div>
    );
  }

  if (loading || !rows) {
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
