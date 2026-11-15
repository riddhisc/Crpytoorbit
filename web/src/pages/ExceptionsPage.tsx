import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api, copyDiagnostics, type ExceptionItem } from "@/api/client";
import { AppShell } from "@/components/shell/AppShell";
import { DataTable, Pagination } from "@/components/ui/DataTable";
import { Drawer } from "@/components/ui/Drawer";
import { SeverityBadge, StatusPill } from "@/components/ui/Badge";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { formatInr, formatLocal, formatUtc } from "@/lib/format";
import { useUi } from "@/stores/ui";

const TYPES = ["UNMATCHED_WITHDRAWAL", "UNMATCHED_DEPOSIT", "DUPLICATE_TRADE", "NEGATIVE_BALANCE", "PRICE_DEVIATION", "MISSING_FEE", "LARGE_TRANSFER_UNEXPLAINED"];

export function ExceptionsPage() {
  const [params, setParams] = useSearchParams();
  const [draftQuery, setDraftQuery] = useState(params.get("q") ?? "");
  const [selected, setSelected] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const client = useQueryClient();
  const toast = useUi((state) => state.pushToast);
  const status = params.get("status") ?? "open";
  const openId = params.get("open");

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = new URLSearchParams(params);
      if (draftQuery) next.set("q", draftQuery);
      else next.delete("q");
      setParams(next, { replace: true });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [draftQuery]);

  const queryString = params.toString() || `status=${status}`;
  const list = useQuery({
    queryKey: ["exceptions", queryString],
    queryFn: ({ signal }) => api.exceptions(queryString.includes("status=") ? queryString : `${queryString}&status=${status}`, signal),
  });
  const counts = useQuery({ queryKey: ["counts"], queryFn: ({ signal }) => api.counts(signal) });
  const detail = useQuery({
    queryKey: ["exception", openId],
    queryFn: ({ signal }) => api.exception(openId ?? "", signal),
    enabled: Boolean(openId),
  });

  const rows = list.data?.items ?? [];
  const activeFilters = useMemo(() => Array.from(params.entries()).filter(([key]) => !["page", "open"].includes(key)), [params]);

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (!value) next.delete(key);
    else next.set(key, value);
    next.delete("page");
    setParams(next);
  }

  async function changeStatus(id: string, nextStatus: string, resolutionNote: string) {
    const previous = rows.find((row) => row.id === id);
    await api.patchException(id, nextStatus, resolutionNote);
    await client.invalidateQueries({ queryKey: ["exceptions"] });
    await client.invalidateQueries({ queryKey: ["counts"] });
    await client.invalidateQueries({ queryKey: ["summary"] });
    toast(`Marked ${nextStatus}`, () => {
      if (previous) void api.patchException(id, previous.status, "Reopened from undo").then(() => client.invalidateQueries());
    });
  }

  return (
    <AppShell title="Exceptions">
      <div className="sticky top-0 z-10 mb-3 space-y-2 bg-bg py-2">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Status">
          {["open", "resolved", "ignored"].map((value) => (
            <button key={value} role="tab" aria-selected={status === value} className={`min-h-11 rounded-md border px-3 text-sm ${status === value ? "border-accent" : "border-line"}`} onClick={() => setParam("status", value)}>
              {value} {counts.data ? `(${counts.data[value] ?? 0})` : ""}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="text-sm">Type
            <select className="ml-2 min-h-11 rounded-md border border-line bg-bg px-2" value={params.get("type") ?? ""} onChange={(event) => setParam("type", event.target.value || null)}>
              <option value="">All</option>
              {TYPES.map((type) => <option key={type}>{type}</option>)}
            </select>
          </label>
          {["high", "medium", "low"].map((level) => (
            <button key={level} className="min-h-11 rounded-md border border-line px-3 text-sm" onClick={() => setParam("severity", params.get("severity") === level ? null : level)}>
              <SeverityBadge severity={level} />
            </button>
          ))}
          <input aria-label="Asset" placeholder="Asset" className="min-h-11 rounded-md border border-line bg-bg px-3" value={params.get("asset") ?? ""} onChange={(event) => setParam("asset", event.target.value.toUpperCase() || null)} />
          <input aria-label="Search exceptions" placeholder="Search" className="min-h-11 rounded-md border border-line bg-bg px-3" value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} />
        </div>
        <div className="flex flex-wrap gap-2 text-xs" aria-live="polite">
          {activeFilters.map(([key, value]) => (
            <button key={key} className="rounded-md border border-line px-2 py-1" onClick={() => setParam(key, null)}>{key}: {value} ×</button>
          ))}
          {activeFilters.length ? <button className="min-h-11 px-2" onClick={() => setParams(new URLSearchParams())}>Clear all</button> : null}
          <span>{list.data ? `${list.data.total} results` : ""}</span>
        </div>
      </div>
      {selected.length ? (
        <div className="mb-3 flex flex-wrap items-end gap-2 rounded-lg border border-line p-3">
          <label className="text-sm">Note
            <input className="ml-2 min-h-11 rounded-md border border-line bg-bg px-2" value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <Button disabled={!note.trim()} onClick={() => void api.bulk(selected, "resolved", note).then(() => client.invalidateQueries())}>Resolve selected</Button>
          <Button variant="ghost" disabled={!note.trim()} onClick={() => void api.bulk(selected, "ignored", note).then(() => client.invalidateQueries())}>Ignore selected</Button>
        </div>
      ) : null}
      {list.isLoading ? <Skeleton className="h-40" /> : null}
      {list.isError ? <ErrorState message={(list.error as Error).message} onRetry={() => void list.refetch()} onCopy={() => void copyDiagnostics(list.error)} /> : null}
      {list.data ? (
        <DataTable
          rows={rows}
          empty={<EmptyState title="No exceptions in this view" body="Try another status, or load the sample if the desk is empty." />}
          onRow={(row) => setParam("open", row.id)}
          columns={[
            { key: "pick", header: "", render: (row) => <input aria-label={`Select ${row.type}`} type="checkbox" checked={selected.includes(row.id)} onClick={(event) => event.stopPropagation()} onChange={() => setSelected((current) => current.includes(row.id) ? current.filter((id) => id !== row.id) : [...current, row.id])} /> },
            { key: "severity", header: "Severity", render: (row) => <SeverityBadge severity={row.severity} /> },
            { key: "type", header: "Type", render: (row) => row.type },
            { key: "asset", header: "Asset", render: (row) => <span className="num">{row.asset}</span> },
            { key: "value", header: "Value", render: (row) => <span className="num">{formatInr(row.estimated_value_inr)}</span> },
            { key: "date", header: "Date", render: (row) => <span title={formatUtc(row.ts_utc)}>{formatLocal(row.ts_utc)}</span> },
            { key: "explanation", header: "What happened", render: (row) => row.explanation.slice(0, 90) },
            { key: "status", header: "Status", render: (row) => <StatusPill status={row.status} /> },
          ]}
        />
      ) : null}
      <div
        onKeyDown={(event) => {
          if (!openId) return;
          if (event.key === "r") void changeStatus(openId, "resolved", note || "Resolved from keyboard");
          if (event.key === "i") void changeStatus(openId, "ignored", note || "Ignored from keyboard");
        }}
      >
        <Pagination page={Number(params.get("page") ?? 1)} pageSize={list.data?.page_size ?? 50} total={list.data?.total ?? 0} onPage={(page) => setParam("page", String(page))} />
      </div>
      <Drawer open={Boolean(openId)} onOpenChange={(open) => !open && setParam("open", null)} title={detail.data?.type ?? "Exception"}>
        {detail.data ? <Detail body={detail.data} onStatus={(statusName, resolutionNote) => void changeStatus(detail.data.id, statusName, resolutionNote)} /> : <Skeleton className="h-24" />}
      </Drawer>
    </AppShell>
  );
}

function Detail({ body, onStatus }: { body: ExceptionItem & { evidence: { source: string; kind: string; qty: string; asset: string; role: string; raw: Record<string, unknown> }[]; suggested_fix: string; history: { to_status: string; note: string | null; actor: string }[] }; onStatus: (status: string, note: string) => void }) {
  const [note, setNote] = useState("");
  return (
    <div className="space-y-4 text-sm">
      <p>{body.explanation}</p>
      <p><strong>Suggested fix.</strong> {body.suggested_fix}</p>
      <div className="grid gap-2 md:grid-cols-2">
        {body.evidence.map((row, index) => (
          <article key={`${row.role}-${index}`} className="rounded-md border border-line p-3">
            <div className="text-xs uppercase text-muted">{row.role}</div>
            <div className="num">{row.source} {row.kind} {row.qty} {row.asset}</div>
          </article>
        ))}
      </div>
      <ul className="text-xs text-muted">
        {body.history.map((event, index) => <li key={index}>{event.actor}: {event.to_status} {event.note}</li>)}
      </ul>
      <label className="block">Note
        <textarea className="mt-1 w-full rounded-md border border-line bg-bg p-2" value={note} onChange={(event) => setNote(event.target.value)} />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => onStatus("resolved", note)} disabled={!note.trim()}>Resolve</Button>
        <Button variant="ghost" onClick={() => onStatus("ignored", note)} disabled={!note.trim()}>Ignore</Button>
        <Button variant="ghost" onClick={() => onStatus("open", note || "Reopened")}>Reopen</Button>
      </div>
    </div>
  );
}
