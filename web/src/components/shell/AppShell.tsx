import { NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useUi } from "@/stores/ui";
import { Toasts } from "@/components/ui/Toast";
import { Kbd } from "@/components/ui/FileDropzone";
import { CommandPalette } from "@/features/command/CommandPalette";
import { useEffect } from "react";

const links = [
  ["/", "Overview"],
  ["/exceptions", "Exceptions"],
  ["/ledger", "Ledger"],
  ["/tax", "Tax"],
  ["/import", "Import"],
  ["/audit", "Audit log"],
  ["/settings", "Settings"],
] as const;

export function AppShell({ children, title }: { children: React.ReactNode; title: string }) {
  const theme = useUi((state) => state.theme);
  const toggleTheme = useUi((state) => state.toggleTheme);
  const sidebar = useUi((state) => state.sidebar);
  const toggleSidebar = useUi((state) => state.toggleSidebar);
  const setPalette = useUi((state) => state.setPalette);
  const setHelp = useUi((state) => state.setHelp);
  const help = useUi((state) => state.help);
  const summary = useQuery({ queryKey: ["summary"], queryFn: ({ signal }) => api.summary(signal) });
  const navigate = useNavigate();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPalette(true);
      }
      if (event.key === "?" && !(event.target instanceof HTMLInputElement) && !(event.target instanceof HTMLTextAreaElement)) {
        setHelp(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setHelp, setPalette]);

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <div className="md:flex">
        <aside className={`hidden border-r border-line bg-surface md:block ${sidebar ? "w-60" : "w-16"}`}>
          <div className="flex items-center justify-between px-4 py-5">
            <span className="font-semibold">{sidebar ? "Crypto Orbit" : "CO"}</span>
            <button className="min-h-11 min-w-11" aria-label="Collapse sidebar" onClick={toggleSidebar}>
              {sidebar ? "«" : "»"}
            </button>
          </div>
          <nav aria-label="Primary" className="flex flex-col gap-1 px-2">
            {links.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `min-h-11 rounded-md px-3 py-2 text-sm ${isActive ? "bg-raised" : ""}`}>
                {sidebar ? label : label.slice(0, 1)}
                {to === "/exceptions" && summary.data ? (
                  <span className="ml-2 rounded-md bg-danger/20 px-1.5 text-xs text-danger">{summary.data.open_exceptions}</span>
                ) : null}
              </NavLink>
            ))}
          </nav>
        </aside>
        <div className="min-w-0 flex-1 pb-24 md:pb-0">
          <header className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
            <h1 className="text-lg">{title}</h1>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              {summary.data?.total_tx === 0 ? (
                <button className="min-h-11 rounded-md bg-accent px-3 text-sm text-accent-ink" onClick={() => void api.loadDemo().then(() => navigate("/exceptions"))}>
                  Load sample data
                </button>
              ) : null}
              <button className="min-h-11 rounded-md border border-line px-3 text-sm" onClick={toggleTheme}>
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <span className="rounded-md border border-line px-2 py-1 text-xs" title="Crypto Orbit never asks for private keys or exchange API secrets.">
                Public addresses & CSV only
              </span>
            </div>
          </header>
          {summary.data?.demo_mode ? (
            <p className="border-b border-line bg-raised px-4 py-2 text-xs text-muted">Demo mode is on. Write endpoints do not require an API key. Reset is enabled.</p>
          ) : null}
          <main id="main" className="p-4">
            {children}
          </main>
        </div>
      </div>
      <nav aria-label="Mobile" className="fixed inset-x-0 bottom-0 z-40 flex gap-1 overflow-x-auto border-t border-line bg-surface p-1 md:hidden">
        {links.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"} className="min-h-11 min-w-11 shrink-0 px-2 py-1 text-center text-xs">
            {label.split(" ")[0]}
          </NavLink>
        ))}
      </nav>
      <CommandPalette />
      {help ? (
        <div role="dialog" aria-label="Keyboard shortcuts" className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-line bg-surface p-4">
            <h2 className="text-lg">Shortcuts</h2>
            <ul className="mt-3 space-y-2 text-sm">
              <li><Kbd>Ctrl</Kbd> + <Kbd>K</Kbd> command palette</li>
              <li><Kbd>?</Kbd> this help</li>
              <li>On Exceptions: arrows, Enter, <Kbd>r</Kbd> resolve, <Kbd>i</Kbd> ignore</li>
            </ul>
            <button className="mt-4 min-h-11 rounded-md border border-line px-3" onClick={() => setHelp(false)}>Close</button>
          </div>
        </div>
      ) : null}
      <Toasts />
    </div>
  );
}
