import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { getChannel, type ChannelRow } from "../api/channels";
import {
  getNowPlaying,
  listChannelPlayouts,
  listPlayoutItems,
  type ChannelPlayoutRow,
  type NowPlayingResponse,
  type PlayoutItemsResponse,
} from "../api/playouts";

function pickPrimaryPlayout(rows: ChannelPlayoutRow[]): ChannelPlayoutRow | null {
  if (!rows.length) return null;
  const active = rows.find((p) => p.is_active);
  return active ?? rows[0];
}

export default function ChannelDetailPage() {
  const { id } = useParams<{ id: string }>();
  const numId = id ? Number.parseInt(id, 10) : NaN;
  const [row, setRow] = useState<ChannelRow | null>(null);
  const [playouts, setPlayouts] = useState<ChannelPlayoutRow[] | null>(null);
  const [nowPlaying, setNowPlaying] = useState<NowPlayingResponse | null>(null);
  const [timeline, setTimeline] = useState<PlayoutItemsResponse | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [subErr, setSubErr] = useState<{
    playouts?: string;
    now?: string;
    items?: string;
  }>({});

  const primaryPlayout = useMemo(
    () => (playouts ? pickPrimaryPlayout(playouts) : null),
    [playouts]
  );

  useEffect(() => {
    if (!Number.isFinite(numId)) {
      setErr("Invalid channel id");
      return;
    }
    let cancelled = false;
    setErr(null);
    (async () => {
      try {
        const data = await getChannel(numId);
        if (!cancelled) setRow(data);
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

  useEffect(() => {
    if (!Number.isFinite(numId) || !row) return;
    let cancelled = false;
    setSubErr((s) => ({ ...s, playouts: undefined }));
    (async () => {
      try {
        const list = await listChannelPlayouts(numId);
        if (!cancelled) setPlayouts(list);
      } catch (e) {
        if (!cancelled) {
          setPlayouts([]);
          setSubErr((s) => ({
            ...s,
            playouts: e instanceof ApiError ? e.message : String(e),
          }));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [numId, row]);

  useEffect(() => {
    if (!primaryPlayout) {
      setNowPlaying(null);
      setTimeline(null);
      return;
    }
    let cancelled = false;
    setSubErr((s) => ({ ...s, now: undefined, items: undefined }));
    (async () => {
      try {
        const np = await getNowPlaying(primaryPlayout.id);
        if (!cancelled) setNowPlaying(np);
      } catch (e) {
        if (!cancelled) {
          setNowPlaying(null);
          setSubErr((s) => ({
            ...s,
            now: e instanceof ApiError ? e.message : String(e),
          }));
        }
      }
      try {
        const items = await listPlayoutItems(primaryPlayout.id, 15, 0);
        if (!cancelled) setTimeline(items);
      } catch (e) {
        if (!cancelled) {
          setTimeline(null);
          setSubErr((s) => ({
            ...s,
            items: e instanceof ApiError ? e.message : String(e),
          }));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [primaryPlayout]);

  if (!Number.isFinite(numId)) {
    return <p className="text-amber-400">Invalid channel id.</p>;
  }

  if (err) {
    return (
      <div>
        <Link to="/channels" className="text-brand-400 hover:underline">
          ← Channels
        </Link>
        <h1 className="mt-4 text-2xl font-bold text-white">Channel</h1>
        <p className="mt-4 text-amber-400">{err}</p>
      </div>
    );
  }

  if (!row) {
    return (
      <div>
        <Link to="/channels" className="text-brand-400 hover:underline">
          ← Channels
        </Link>
        <p className="mt-4 text-slate-500">Loading…</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <Link to="/channels" className="text-brand-400 hover:underline">
          ← Channels
        </Link>
        <h1 className="mt-4 text-2xl font-bold text-white">
          {row.name ?? `Channel ${row.id}`}
        </h1>
        <p className="mt-2 text-slate-400">
          Number {row.number ?? "—"} · id {row.id}
          {row.enabled === false ? " · disabled" : ""}
        </p>
      </div>

      <section className="rounded-lg border border-slate-800 bg-brand-900/40 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Playouts
        </h2>
        {subErr.playouts ? (
          <p className="mt-2 text-amber-400 text-sm">{subErr.playouts}</p>
        ) : playouts === null ? (
          <p className="mt-2 text-slate-500">Loading…</p>
        ) : playouts.length === 0 ? (
          <p className="mt-2 text-slate-500">No playouts for this channel.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead>
                <tr className="border-b border-slate-700 text-slate-500">
                  <th className="py-2 pr-4">ID</th>
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Active</th>
                  <th className="py-2">Schedule</th>
                </tr>
              </thead>
              <tbody>
                {playouts.map((p) => (
                  <tr
                    key={p.id}
                    className={
                      primaryPlayout?.id === p.id
                        ? "border-l-2 border-brand-500 bg-slate-900/30"
                        : ""
                    }
                  >
                    <td className="py-2 pr-4 font-mono">{p.id}</td>
                    <td className="py-2 pr-4">{p.playout_type ?? "—"}</td>
                    <td className="py-2 pr-4">
                      {p.is_active ? "yes" : "no"}
                    </td>
                    <td className="py-2">
                      {p.program_schedule_id ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {primaryPlayout ? (
              <p className="mt-2 text-xs text-slate-500">
                Using playout {primaryPlayout.id}
                {primaryPlayout.is_active ? " (active)" : ""} for now-playing
                and timeline.
              </p>
            ) : null}
          </div>
        )}
      </section>

      {primaryPlayout ? (
        <section className="rounded-lg border border-slate-800 bg-brand-900/40 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Now playing
          </h2>
          {subErr.now ? (
            <p className="mt-2 text-amber-400 text-sm">{subErr.now}</p>
          ) : nowPlaying === null ? (
            <p className="mt-2 text-slate-500">Loading…</p>
          ) : !nowPlaying.current && !nowPlaying.next ? (
            <p className="mt-2 text-slate-500">
              Nothing scheduled at server time{" "}
              <span className="font-mono text-slate-400">
                {nowPlaying.current_time}
              </span>
              .
            </p>
          ) : (
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div className="rounded-md border border-slate-700 bg-slate-900/40 p-3">
                <div className="text-xs uppercase text-slate-500">Current</div>
                {nowPlaying.current ? (
                  <>
                    <div className="mt-1 font-medium text-white">
                      {nowPlaying.current.title ?? "Untitled"}
                    </div>
                    {nowPlaying.current.episode_title ? (
                      <div className="text-sm text-slate-400">
                        {nowPlaying.current.episode_title}
                      </div>
                    ) : null}
                    <div className="mt-2 text-xs text-slate-500">
                      {nowPlaying.current.progress_seconds != null &&
                      nowPlaying.current.duration_seconds != null
                        ? `${Math.round(nowPlaying.current.progress_seconds)}s / ${Math.round(nowPlaying.current.duration_seconds)}s`
                        : null}
                    </div>
                  </>
                ) : (
                  <p className="mt-1 text-slate-500">—</p>
                )}
              </div>
              <div className="rounded-md border border-slate-700 bg-slate-900/40 p-3">
                <div className="text-xs uppercase text-slate-500">Next</div>
                {nowPlaying.next ? (
                  <>
                    <div className="mt-1 font-medium text-white">
                      {nowPlaying.next.title ?? "Untitled"}
                    </div>
                    {nowPlaying.next.starts_in_seconds != null ? (
                      <div className="mt-1 text-xs text-slate-500">
                        in {Math.round(nowPlaying.next.starts_in_seconds)}s
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="mt-1 text-slate-500">—</p>
                )}
              </div>
            </div>
          )}
        </section>
      ) : null}

      {primaryPlayout && timeline ? (
        <section className="rounded-lg border border-slate-800 bg-brand-900/40 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Upcoming (first {timeline.count} items)
          </h2>
          {subErr.items ? (
            <p className="mt-2 text-amber-400 text-sm">{subErr.items}</p>
          ) : (
            <ul className="mt-3 max-h-64 space-y-2 overflow-y-auto text-sm">
              {timeline.items.map((it) => (
                <li
                  key={it.id}
                  className="rounded border border-slate-800/80 bg-slate-900/30 px-2 py-1"
                >
                  <span className="text-slate-200">
                    {it.title ?? it.custom_title ?? `Item ${it.id}`}
                  </span>
                  <span className="ml-2 text-xs text-slate-500 font-mono">
                    {it.start_time}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      <div>
        <button
          type="button"
          onClick={() => setShowRaw((v) => !v)}
          className="text-sm text-brand-400 hover:underline"
        >
          {showRaw ? "Hide" : "Show"} raw channel JSON
        </button>
        {showRaw ? (
          <pre className="mt-2 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-xs text-slate-300">
            {JSON.stringify(row, null, 2)}
          </pre>
        ) : null}
      </div>
    </div>
  );
}
