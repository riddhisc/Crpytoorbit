import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { AppShell } from "@/components/shell/AppShell";
import { formatLocal } from "@/lib/format";

export function AuditPage() {
  const audit = useQuery({ queryKey: ["audit"], queryFn: ({ signal }) => api.audit(signal) });
  return (
    <AppShell title="Audit log">
      <div className="mb-3"><a className="text-sm underline" href="/api/v1/export/exceptions.csv">Export exceptions CSV</a></div>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-muted"><th>When</th><th>Who</th><th>What</th><th>Note</th></tr></thead>
        <tbody>
          {audit.data?.items.map((event) => (
            <tr key={event.id} className="border-t border-line">
              <td>{formatLocal(event.created_at)}</td>
              <td>{event.actor}</td>
              <td>{event.exception_type}: {event.from_status} → {event.to_status}</td>
              <td>{event.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </AppShell>
  );
}
