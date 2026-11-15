import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, copyDiagnostics } from "@/api/client";
import { AppShell } from "@/components/shell/AppShell";
import { ErrorState, Skeleton } from "@/components/ui/Card";
import { formatInr, formatQty } from "@/lib/format";

export function TaxPage() {
  const tax = useQuery({ queryKey: ["tax"], queryFn: ({ signal }) => api.tax(signal) });
  const [open, setOpen] = useState<string | null>(null);
  return (
    <AppShell title="Tax">
      <div className="mb-4 rounded-lg border border-warning/50 bg-raised p-3 text-sm">ESTIMATE, not tax advice. FIFO only. Losses are not offset against gains. Verify with a CA.</div>
      {tax.isLoading ? <Skeleton className="h-40" /> : null}
      {tax.isError ? <ErrorState message={(tax.error as Error).message} onRetry={() => void tax.refetch()} onCopy={() => void copyDiagnostics(tax.error)} /> : null}
      {tax.data ? (
        <>
          <p className="mb-3 text-sm text-muted" title="First-in, first-out cost basis. Tax is 30% of positive per-trade gains. TDS is an informational 1% of sell value.">
            Rate {tax.data.tax_rate_pct}% · TDS reference {tax.data.tds_rate_pct}% · fees as cost: {String(tax.data.fees_as_cost)}
          </p>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-muted"><th>Asset</th><th>Realized</th><th>Taxable</th><th>Estimated tax</th><th>TDS</th></tr></thead>
            <tbody>
              {tax.data.assets.map((asset) => (
                <>
                  <tr key={asset.asset} className="border-t border-line">
                    <td><button className="min-h-11" onClick={() => setOpen(open === asset.asset ? null : asset.asset)}>{asset.asset}</button></td>
                    <td className="num">{formatInr(asset.realized_gain_inr)}</td>
                    <td className="num">{formatInr(asset.taxable_gain_inr)}</td>
                    <td className="num">{formatInr(asset.estimated_tax_inr)}</td>
                    <td className="num">{formatInr(asset.tds_inr)}</td>
                  </tr>
                  {open === asset.asset ? (
                    <tr key={`${asset.asset}-lots`}>
                      <td colSpan={5}>
                        {asset.sales.map((sale) => (
                          <div key={sale.tx_id} className="py-2 text-xs">
                            Sell {formatQty(sale.qty)} gain {formatInr(sale.gain)}
                            <ul>{sale.lots.map((lot, index) => <li key={index}>Lot {lot.acquired_ts || "unknown cost"} · {formatQty(lot.qty)} @ {formatInr(lot.unit_cost)}</li>)}</ul>
                          </div>
                        ))}
                      </td>
                    </tr>
                  ) : null}
                </>
              ))}
              <tr className="border-t border-line font-medium">
                <td>Total</td>
                <td className="num">{formatInr(tax.data.totals.realized_gain_inr)}</td>
                <td className="num">{formatInr(tax.data.totals.taxable_gain_inr)}</td>
                <td className="num">{formatInr(tax.data.totals.estimated_tax_inr)}</td>
                <td className="num">{formatInr(tax.data.totals.tds_inr)}</td>
              </tr>
            </tbody>
          </table>
        </>
      ) : null}
    </AppShell>
  );
}
