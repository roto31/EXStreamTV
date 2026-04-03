export default function SettingsPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>
      <div className="rounded-lg border border-slate-800 bg-brand-900/40 p-4 text-sm text-slate-300">
        <p>
          <strong className="text-slate-200">Persona</strong> is selected in the
          top bar and stored in <code className="text-brand-400">sessionStorage</code>{" "}
          under <code className="text-brand-400">exstreamtv.persona_id</code>.
        </p>
        <p className="mt-3">
          <strong className="text-slate-200">API base</strong> — In development,
          Vite proxies <code className="text-brand-400">/api</code> and{" "}
          <code className="text-brand-400">/iptv</code> to{" "}
          <code className="text-brand-400">127.0.0.1:8411</code>. For a split
          deployment, build with{" "}
          <code className="text-brand-400">VITE_API_BASE</code> pointing at your
          API origin (see <code className="text-brand-400">src/api/client.ts</code>
          ).
        </p>
      </div>
    </div>
  );
}
