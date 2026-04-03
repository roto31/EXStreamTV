import { NavLink, Outlet } from "react-router-dom";
import { PERSONAS, usePersona } from "../context/PersonaContext";

const navClass = ({ isActive }: { isActive: boolean }) =>
  [
    "rounded-md px-3 py-2 text-sm font-medium transition",
    isActive
      ? "bg-brand-700 text-white"
      : "text-slate-300 hover:bg-slate-800 hover:text-white",
  ].join(" ");

export default function AppShell() {
  const { personaId, setPersonaId } = usePersona();
  const isViewer = personaId === "viewer";

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-800 bg-brand-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <NavLink to="/" className="text-lg font-semibold text-white">
              EXStreamTV
            </NavLink>
            <nav className="flex flex-wrap gap-1">
              <NavLink to="/" end className={navClass}>
                Dashboard
              </NavLink>
              <NavLink to="/channels" className={navClass}>
                Channels
              </NavLink>
              <NavLink to="/schedules" className={navClass}>
                Schedules
              </NavLink>
              {!isViewer ? (
                <NavLink to="/schedule-history" className={navClass}>
                  Schedule history
                </NavLink>
              ) : null}
              <NavLink to="/settings" className={navClass}>
                Settings
              </NavLink>
            </nav>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-400">
            <span>Persona</span>
            <select
              value={personaId}
              onChange={(e) =>
                setPersonaId(e.target.value as (typeof PERSONAS)[number])
              }
              className="rounded-md border border-slate-700 bg-brand-950 px-2 py-1 text-slate-100"
            >
              {PERSONAS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-slate-800 py-4 text-center text-xs text-slate-500">
        Track B UI — API proxy → :8411 ·{" "}
        <a
          className="text-brand-400 hover:underline"
          href="https://github.com/roto31/EXStreamTV/blob/main/docs/EXStreamTV-UI-Architecture.md"
        >
          EXStreamTV-UI-Architecture.md
        </a>
      </footer>
    </div>
  );
}
