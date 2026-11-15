export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "info" | "success" }) {
  const color = tone === "info" ? "text-info" : tone === "success" ? "text-success" : "text-muted";
  return <span className={`inline-flex items-center gap-1 rounded-md border border-line px-2 py-0.5 text-xs ${color}`}>{children}</span>;
}

const severityIcon = { high: "▲", medium: "●", low: "○" };

export function SeverityBadge({ severity }: { severity: string }) {
  const tone = severity === "high" ? "text-danger" : severity === "medium" ? "text-warning" : "text-info";
  const mark = severityIcon[severity as keyof typeof severityIcon] ?? "•";
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium uppercase ${tone}`}>
      <span aria-hidden="true">{mark}</span>
      {severity}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  return <span className="rounded-md border border-line px-2 py-0.5 text-xs capitalize">{status}</span>;
}
