export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type Summary = {
  total_tx: number;
  matched_pct: string;
  open_exceptions: number;
  value_at_risk_inr: string;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  holdings: { asset: string; qty: string; value_inr: string; open_exceptions: number }[];
  demo_mode: boolean;
};

export type ExceptionItem = {
  id: string;
  type: string;
  severity: string;
  asset: string | null;
  source: string | null;
  ts_utc: string | null;
  estimated_value_inr: string | null;
  explanation: string;
  suggested_fix: string;
  status: string;
  resolution_note: string | null;
  fingerprint: string;
};

export type EvidenceRow = {
  id: string;
  source: string;
  ts_utc: string;
  kind: string;
  asset: string;
  side: string | null;
  qty: string;
  price_inr: string | null;
  tx_hash: string | null;
  raw: Record<string, unknown>;
  role: string;
};

export type ExceptionDetail = ExceptionItem & {
  evidence: EvidenceRow[];
  history: { id: string; from_status: string | null; to_status: string; note: string | null; actor: string; created_at: string }[];
  details: Record<string, unknown>;
};

export type LedgerRow = {
  id: string;
  source: string;
  source_row: number;
  ts_utc: string;
  kind: string;
  asset: string;
  side: string | null;
  qty: string;
  price_inr: string | null;
  fee_qty: string;
  fee_asset: string | null;
  tx_hash: string | null;
  excluded: boolean;
  running_balance: string | null;
  matched_tx_id: string | null;
  match_note: string | null;
  raw: Record<string, unknown>;
};

export type TaxResponse = {
  assets: {
    asset: string;
    realized_gain_inr: string;
    taxable_gain_inr: string;
    estimated_tax_inr: string;
    tds_inr: string;
    sales: {
      tx_id: string;
      ts_utc: string;
      qty: string;
      proceeds: string;
      cost: string;
      gain: string;
      lots: { acquired_ts: string; qty: string; unit_cost: string; cost: string }[];
    }[];
  }[];
  totals: {
    realized_gain_inr: string;
    taxable_gain_inr: string;
    estimated_tax_inr: string;
    tds_inr: string;
  };
  tax_rate_pct: string;
  tds_rate_pct: string;
  fees_as_cost: boolean;
  disclaimer: string;
};

export type ImportIssue = {
  id: string;
  source: string;
  filename: string | null;
  row_number: number;
  severity: string;
  reason: string;
  raw_text: string;
};

export type AuditEvent = {
  id: string;
  exception_id: string;
  exception_type: string | null;
  from_status: string | null;
  to_status: string;
  note: string | null;
  actor: string;
  created_at: string;
};

export class ApiError extends Error {
  code: string;
  requestId: string;
  details: Record<string, unknown>;
  constructor(code: string, message: string, requestId: string, details: Record<string, unknown> = {}) {
    super(message);
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit & { signal?: AbortSignal }): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    signal: init?.signal,
  });
  if (!response.ok) {
    let payload: { error?: { code?: string; message?: string; request_id?: string } } = {};
    try {
      payload = (await response.json()) as typeof payload;
    } catch {
      payload = {};
    }
    throw new ApiError(
      payload.error?.code ?? "HTTP_ERROR",
      payload.error?.message ?? response.statusText,
      payload.error?.request_id ?? response.headers.get("X-Request-ID") ?? "",
      (payload.error as { details?: Record<string, unknown> } | undefined)?.details ?? {},
    );
  }
  if (response.headers.get("content-type")?.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.text()) as T;
}

export const api = {
  summary: (signal?: AbortSignal) => request<Summary>("/api/v1/summary", { signal }),
  exceptions: (query: string, signal?: AbortSignal) =>
    request<Page<ExceptionItem>>(`/api/v1/exceptions?${query}`, { signal }),
  counts: (signal?: AbortSignal) => request<Record<string, number>>("/api/v1/exceptions/counts", { signal }),
  exception: (id: string, signal?: AbortSignal) => request<ExceptionDetail>(`/api/v1/exceptions/${id}`, { signal }),
  patchException: (id: string, status: string, resolution_note: string) =>
    request<ExceptionItem>(`/api/v1/exceptions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, resolution_note }),
    }),
  bulk: (ids: string[], status: string, resolution_note: string) =>
    request<ExceptionItem[]>("/api/v1/exceptions/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, status, resolution_note }),
    }),
  ledger: (query: string, signal?: AbortSignal) => request<Page<LedgerRow>>(`/api/v1/ledger?${query}`, { signal }),
  tax: (signal?: AbortSignal) => request<TaxResponse>("/api/v1/tax", { signal }),
  issues: (signal?: AbortSignal) => request<Page<ImportIssue>>("/api/v1/import-issues?page_size=200", { signal }),
  audit: (signal?: AbortSignal) => request<Page<AuditEvent>>("/api/v1/audit-log?page_size=100", { signal }),
  loadDemo: () => request<{ job_id: string; open_exceptions: number }>("/api/v1/demo/load", { method: "POST" }),
  reset: () => request<{ status: string }>("/api/v1/reset", { method: "POST" }),
  upload: async (files: File[]) => {
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    const response = await fetch("/api/v1/imports", { method: "POST", body });
    const payload = (await response.json()) as {
      job_id?: string;
      error?: { code: string; message: string; details?: Record<string, unknown>; request_id: string };
    };
    if (!response.ok) {
      throw new ApiError(
        payload.error?.code ?? "HTTP_ERROR",
        payload.error?.message ?? "Upload failed",
        payload.error?.request_id ?? "",
        payload.error?.details ?? {},
      );
    }
    return payload as { job_id: string };
  },
  job: (id: string) =>
    request<{ status: string; progress: number; files: { filename: string; connector: string | null; rows_imported: number; rows_skipped: number }[] }>(
      `/api/v1/imports/${id}`,
    ),
  suggest: (headers: string[], sample_rows: Record<string, string>[]) =>
    request<{ suggestions: { field: string; header: string; confidence: number; source: string }[]; llm_used: boolean }>(
      "/api/v1/mapping/suggest",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ headers, sample_rows }) },
    ),
  preview: (headers: string[], rows: Record<string, string>[], mapping: Record<string, string>) =>
    request<{ rows: { asset: string; qty: string; kind: string; side: string | null }[]; issues: { reason: string }[] }>(
      "/api/v1/mapping/preview",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ headers, rows, mapping }) },
    ),
  saveProfile: (name: string, headers: string[], mapping: Record<string, string>) =>
    request<{ id: string }>("/api/v1/mapping/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, headers, mapping }),
    }),
  webhook: () => request<{ url: string; secret: string; enabled: boolean }>("/api/v1/settings/webhook"),
  saveWebhook: (body: { url: string; secret: string; enabled: boolean }) =>
    request<{ url: string; enabled: boolean }>("/api/v1/settings/webhook", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  testWebhook: () => request<{ status: string; last_error: string | null }>("/api/v1/settings/webhook/test", { method: "POST" }),
};

export async function copyDiagnostics(error: unknown): Promise<void> {
  const text = error instanceof ApiError ? `${error.code} ${error.message} request_id=${error.requestId}` : String(error);
  await navigator.clipboard.writeText(text);
}
