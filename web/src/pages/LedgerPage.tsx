import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useState } from "react";
import { api, copyDiagnostics } from "@/api/client";
import { AppShell } from "@/components/shell/AppShell";
import { DataTable, Pagination } from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Drawer";
import { CopyButton } from "@/components/ui/FileDropzone";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/Card";
import { formatInr, formatLocal, formatQty, formatUtc } from "@/lib/format";

export function LedgerPage() {
  const [params, setParams] = useSearchParams();
  const [raw, setRaw] = useState<string | null>(null);
  const [density, setDensity] = useState<"compact" | "comfortable">("comfortable");
  const query = params.toString();
  const list = useQuery({ queryKey: ["ledger", query], queryFn: ({ signal }) => api.ledger(query, signal) });
  return (
    <AppShell title="Ledger">
      <div className="mb-3 flex flex-wrap gap-2">
        <input aria-label="Filter asset" className="min-h-11 rounded-md border border-line bg-bg px-3" placeholder="Asset" value={params.get("asset") ?? ""} onChange={(event) => {
          const next = new URLSearchParams(params);
          if (event.target.value) next.set("asset", event.target.value.toUpperCase());
          else next.delete("asset");
          setParams(next);
        }} />
        <button className="min-h-11 rounded-md border border-line px-3 text-sm" onClick={() => setDensity(density === "compact" ? "comfortable" : "compact")}>Density</button>
      </div>
      {list.isLoading ? <Skeleton className="h-40" /> : null}
      {list.isError ? <ErrorState message={(list.error as Error).message} onRetry={() => void list.refetch()} onCopy={() => void copyDiagnostics(list.error)} /> : null}
      {list.data ? (
        <DataTable
          density={density}
          rows={list.data.items}
          empty={<EmptyState title="Ledger is empty" body="Load the sample or import a file." />}
          columns={[
            { key: "when", header: "When", render: (row) => <span title={formatUtc(row.ts_utc)}>{formatLocal(row.ts_utc)}</span> },
            { key: "source", header: "Source", render: (row) => <Badge>{row.source}</Badge> },
            { key: "kind", header: "Kind", render: (row) => row.kind },
            { key: "asset", header: "Asset", render: (row) => <span className="num">{row.asset}</span> },
            { key: "qty", header: "Qty", render: (row) => <span className={`num ${row.excluded ? "line-through" : ""}`}>{formatQty(row.qty)} {row.excluded ? "duplicate" : ""}</span> },
            { key: "price", header: "Price", render: (row) => <span className="num">{formatInr(row.price_inr)}</span> },
            { key: "match", header: "Match", render: (row) => row.match_note ? <span title={row.matched_tx_id ?? ""}>⛓ {row.match_note}</span> : "—" },
            { key: "raw", header: "Raw", render: (row) => <button className="min-h-11 text-sm underline" onClick={(event) => { event.stopPropagation(); setRaw(JSON.stringify(row.raw, null, 2)); }}>View raw</button> },
          ]}
        />
      ) : null}
      <Pagination page={list.data?.page ?? 1} pageSize={list.data?.page_size ?? 50} total={list.data?.total ?? 0} onPage={(page) => {
        const next = new URLSearchParams(params);
        next.set("page", String(page));
        setParams(next);
      }} />
      <Modal open={raw !== null} onOpenChange={(open) => !open && setRaw(null)} title="Original row">
        <pre className="max-h-80 overflow-auto text-xs">{raw}</pre>
        {raw ? <CopyButton text={raw} /> : null}
      </Modal>
    </AppShell>
  );
}
