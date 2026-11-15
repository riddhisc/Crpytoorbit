import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, copyDiagnostics } from "@/api/client";
import { AppShell } from "@/components/shell/AppShell";
import { FileDropzone } from "@/components/ui/FileDropzone";
import { ErrorState } from "@/components/ui/Card";

const FIELDS = ["ts", "asset", "side", "qty", "price", "fee", "fee_asset", "tx_hash"];

export function ImportPage() {
  const issues = useQuery({ queryKey: ["issues"], queryFn: ({ signal }) => api.issues(signal) });
  const client = useQueryClient();
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<string>("");

  async function handleFiles(files: File[]) {
    setError(null);
    setStatus("uploading");
    try {
      const job = await api.upload(files);
      setStatus("parsing");
      const done = await api.job(job.job_id);
      setStatus(`done · ${done.files.map((file) => `${file.filename}: ${file.connector ?? "unknown"} (${file.rows_imported} rows)`).join(", ")}`);
      await client.invalidateQueries();
    } catch (err) {
      if (err instanceof ApiError && err.code === "UNSUPPORTED_FILE") {
        const filesMeta = (err.details.files as { headers: string[] }[] | undefined) ?? [];
        const found = filesMeta[0]?.headers ?? [];
        setHeaders(found);
        const text = await files[0].text();
        const [head, ...rest] = text.trim().split(/\r?\n/);
        const cols = head.split(",").map((cell) => cell.trim());
        const parsed = rest.filter(Boolean).slice(0, 5).map((line) => {
          const cells = line.split(",");
          return Object.fromEntries(cols.map((column, index) => [column, cells[index] ?? ""]));
        });
        setRows(parsed);
        const suggestion = await api.suggest(found.length ? found : cols, parsed);
        const next: Record<string, string> = {};
        suggestion.suggestions.forEach((item) => {
          next[item.field] = item.header;
        });
        setMapping(next);
        setStatus("Map columns — no connector recognized this file.");
      } else {
        setError(err instanceof Error ? err.message : "Upload failed");
      }
    }
  }

  return (
    <AppShell title="Import">
      <FileDropzone onFiles={(files) => void handleFiles(files)} onText={(text) => void handleFiles([new File([text], "pasted.csv", { type: "text/csv" })])} />
      {status ? <p className="mt-3 text-sm" aria-live="polite">{status}</p> : null}
      {error ? <div className="mt-3"><ErrorState message={error} onCopy={() => void copyDiagnostics(error)} /></div> : null}
      {headers.length ? (
        <section className="mt-4 rounded-lg border border-line p-4">
          <h2 className="text-lg">Map columns</h2>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {FIELDS.map((field) => (
              <label key={field} className="text-sm">{field}
                <select className="mt-1 min-h-11 w-full rounded-md border border-line bg-bg px-2" value={mapping[field] ?? ""} onChange={(event) => setMapping({ ...mapping, [field]: event.target.value })}>
                  <option value="">—</option>
                  {headers.map((header) => <option key={header}>{header}</option>)}
                </select>
              </label>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="min-h-11 rounded-md border border-line px-3" onClick={() => void api.preview(headers, rows, mapping).then((result) => setPreview(JSON.stringify(result.rows, null, 2)))}>Preview 10 rows</button>
            <button className="min-h-11 rounded-md bg-accent px-3 text-accent-ink" onClick={() => void api.saveProfile("custom", headers, mapping).then(() => setStatus("Saved connector profile. Upload the file again."))}>Save as connector profile</button>
          </div>
          {preview ? <pre className="mt-3 overflow-auto text-xs">{preview}</pre> : null}
        </section>
      ) : null}
      <section className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h2>Import issues</h2>
          <a className="min-h-11 text-sm underline" href="/api/v1/import-issues.csv">Download issues as CSV</a>
        </div>
        <ul className="space-y-2 text-sm">
          {issues.data?.items.map((issue) => (
            <li key={issue.id} className="rounded-md border border-line p-2">
              <span className="text-muted">{issue.filename} row {issue.row_number} · {issue.reason}</span>
              <div className="num text-xs">{issue.raw_text}</div>
            </li>
          ))}
        </ul>
      </section>
      <details className="mt-6">
        <summary className="min-h-11 cursor-pointer">Supported formats</summary>
        <p className="mt-2 text-sm text-muted">WazirX: Date, Market, Side, Price (INR), Volume, Total (INR), Fee, Fee Currency. Binance: Date(UTC), Pair, Side, Price, Executed, Amount, Fee, Fee Coin, TxHash. Wallet JSON: address + transfers.</p>
      </details>
    </AppShell>
  );
}
