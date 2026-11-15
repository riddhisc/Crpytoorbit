import { lazy, Suspense, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, copyDiagnostics } from "@/api/client";
import { AppShell } from "@/components/shell/AppShell";
import { ErrorState, Skeleton, StatCard } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { formatInr } from "@/lib/format";
import { SeverityBadge } from "@/components/ui/Badge";

const OrbitView = lazy(() => import("@/features/overview/OrbitView").then((mod) => ({ default: mod.OrbitView })));
const Charts = lazy(() => import("@/features/overview/Charts"));

export function OverviewPage() {
  const query = useQuery({ queryKey: ["summary"], queryFn: ({ signal }) => api.summary(signal) });
  const exceptions = useQuery({
    queryKey: ["exceptions", "top"],
    queryFn: ({ signal }) => api.exceptions("status=open&sort=value_desc&page_size=5", signal),
    enabled: (query.data?.total_tx ?? 0) > 0,
  });
  const client = useQueryClient();
  const navigate = useNavigate();
  const [list, setList] = useState(false);
  const [tour, setTour] = useState(() => localStorage.getItem("orbit-tour") !== "done");

  async function loadSample() {
    await api.loadDemo();
    await client.invalidateQueries();
    setTour(true);
  }

  return (
    <AppShell title="Overview">
      {query.isLoading ? <Skeleton className="h-40" /> : null}
      {query.isError ? <ErrorState message={(query.error as Error).message} onRetry={() => void query.refetch()} onCopy={() => void copyDiagnostics(query.error)} /> : null}
      {query.data && query.data.total_tx === 0 ? (
        <div className="mx-auto max-w-3xl text-center">
          <OrbitMark />
          <h2 className="mt-4 text-2xl">Reconcile your crypto records in minutes</h2>
          <p className="mt-2 text-muted">Upload WazirX and Binance exports plus a wallet JSON. We normalize them, match transfers, and list every exception that needs you.</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button onClick={() => void loadSample()}>Try with sample data</Button>
            <Button variant="ghost" onClick={() => navigate("/import")}>Import your files</Button>
          </div>
          <ol className="mt-8 grid gap-3 text-left md:grid-cols-3">
            {["Upload", "We normalize and match", "You resolve exceptions"].map((step, index) => (
              <li key={step} className="rounded-lg border border-line p-4">
                <span className="text-xs text-muted">0{index + 1}</span>
                <div className="mt-1">{step}</div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      {query.data && query.data.total_tx > 0 ? (
        <div className="space-y-4">
          {tour ? (
            <div className="rounded-lg border border-accent/40 bg-raised p-4" data-testid="tour">
              <p className="text-sm">Start with the summary cards, then the orbit, then open Exceptions and press Resolve on anything that is not yours.</p>
              <button className="mt-2 min-h-11 text-sm" onClick={() => { localStorage.setItem("orbit-tour", "done"); setTour(false); }}>Skip tour</button>
            </div>
          ) : null}
          <div className="grid gap-3 md:grid-cols-4" data-testid="summary-cards">
            <StatCard label="Matched %" value={`${query.data.matched_pct}%`} hint="Share of transfers with a counterpart" onClick={() => navigate("/ledger?kind=TRANSFER_OUT")} />
            <StatCard label="Open exceptions" value={String(query.data.open_exceptions)} hint="High, medium, and low — icon plus text" onClick={() => navigate("/exceptions?status=open")} />
            <StatCard label="Value at risk" value={formatInr(query.data.value_at_risk_inr)} hint="ESTIMATE, not tax advice" onClick={() => navigate("/exceptions?status=open&sort=value_desc")} />
            <StatCard label="Transactions" value={String(query.data.total_tx)} onClick={() => navigate("/ledger")} />
          </div>
          <div className="flex items-center justify-between">
            <h2 className="text-lg">Orbit</h2>
            <button className="min-h-11 rounded-md border border-line px-3 text-sm" onClick={() => setList((value) => !value)}>{list ? "Orbit view" : "List view"}</button>
          </div>
          {list ? (
            <ul>{query.data.holdings.map((holding) => <li key={holding.asset}>{holding.asset} {formatInr(holding.value_inr)}</li>)}</ul>
          ) : (
            <Suspense fallback={<Skeleton className="h-[420px]" />}>
              <OrbitView summary={query.data} />
            </Suspense>
          )}
          <section>
            <h2 className="mb-2 text-lg">Needs your attention</h2>
            <ul className="space-y-2">
              {exceptions.data?.items.map((item) => (
                <li key={item.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-line p-3">
                  <SeverityBadge severity={item.severity} />
                  <span className="text-sm">{item.explanation}</span>
                  <button className="ml-auto min-h-11 rounded-md border border-line px-3 text-sm" onClick={() => navigate(`/exceptions?status=open&open=${item.id}`)}>Review</button>
                </li>
              ))}
            </ul>
          </section>
          <Suspense fallback={<Skeleton className="h-64" />}>
            <Charts summary={query.data} />
          </Suspense>
        </div>
      ) : null}
    </AppShell>
  );
}

function OrbitMark() {
  return (
    <svg viewBox="0 0 160 100" className="mx-auto h-24 w-40" role="img" aria-label="Orbit illustration">
      <ellipse cx="80" cy="50" rx="70" ry="24" fill="none" stroke="currentColor" opacity="0.4" />
      <ellipse cx="80" cy="50" rx="46" ry="16" fill="none" stroke="currentColor" opacity="0.6" />
      <circle cx="80" cy="50" r="8" fill="currentColor" />
    </svg>
  );
}
