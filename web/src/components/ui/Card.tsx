export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-line bg-surface p-4 shadow-soft ${className}`}>{children}</section>;
}

export function StatCard({ label, value, hint, onClick }: { label: string; value: string; hint?: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="rounded-lg border border-line bg-surface p-4 text-left shadow-soft min-h-11">
      <div className="text-xs text-muted">{label}</div>
      <div className="num mt-1 text-xl">{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted">{hint}</div> : null}
    </button>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-line/60 ${className}`} />;
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line p-8 text-center">
      <h2 className="text-lg">{title}</h2>
      <p className="mt-2 text-sm text-muted">{body}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry, onCopy }: { message: string; onRetry?: () => void; onCopy?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-danger/40 p-4">
      <p>{message}</p>
      <div className="mt-3 flex gap-2">
        {onRetry ? <button className="min-h-11 rounded-md border border-line px-3" onClick={onRetry}>Retry</button> : null}
        {onCopy ? <button className="min-h-11 rounded-md border border-line px-3" onClick={onCopy}>Copy diagnostic info</button> : null}
      </div>
    </div>
  );
}
