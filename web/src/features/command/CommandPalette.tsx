import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUi } from "@/stores/ui";
import { api } from "@/api/client";
import { useQueryClient } from "@tanstack/react-query";

const actions = [
  { id: "overview", label: "Go to Overview", to: "/" },
  { id: "exceptions", label: "Go to Exceptions", to: "/exceptions" },
  { id: "ledger", label: "Go to Ledger", to: "/ledger" },
  { id: "tax", label: "Go to Tax", to: "/tax" },
  { id: "import", label: "Go to Import", to: "/import" },
  { id: "high", label: "Filter high severity exceptions", to: "/exceptions?severity=high&status=open" },
  { id: "export", label: "Export exceptions CSV", to: "/api/v1/export/exceptions.csv" },
];

export function CommandPalette() {
  const open = useUi((state) => state.palette);
  const setOpen = useUi((state) => state.setPalette);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const client = useQueryClient();
  const filtered = useMemo(() => actions.filter((action) => action.label.toLowerCase().includes(query.toLowerCase())), [query]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-start bg-black/40 p-4 pt-24" role="dialog" aria-label="Command palette">
      <div className="mx-auto w-full max-w-lg rounded-lg border border-line bg-surface p-3 shadow-soft">
        <input autoFocus aria-label="Command" className="min-h-11 w-full rounded-md border border-line bg-bg px-3" value={query} onChange={(event) => setQuery(event.target.value)} />
        <ul className="mt-2">
          {filtered.map((action) => (
            <li key={action.id}>
              <button
                className="min-h-11 w-full rounded-md px-2 text-left text-sm hover:bg-raised"
                onClick={() => {
                  if (action.id === "export") {
                    window.location.href = action.to;
                  } else if (action.id === "sample") {
                    void api.loadDemo().then(() => client.invalidateQueries());
                  } else {
                    navigate(action.to);
                  }
                  setOpen(false);
                }}
              >
                {action.label}
              </button>
            </li>
          ))}
          <li>
            <button
              className="min-h-11 w-full rounded-md px-2 text-left text-sm"
              onClick={() => {
                void api.loadDemo().then(() => {
                  void client.invalidateQueries();
                  navigate("/exceptions");
                  setOpen(false);
                });
              }}
            >
              Load sample data
            </button>
          </li>
        </ul>
        <button className="mt-2 min-h-11 text-sm" onClick={() => setOpen(false)}>Close</button>
      </div>
    </div>
  );
}
