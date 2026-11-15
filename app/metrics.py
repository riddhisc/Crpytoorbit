"""In-process counters rendered as Prometheus text. Durable totals are read from SQL."""

from sqlmodel import Session, func, select

from app.models import ExceptionRecord, ImportBatch, WebhookDelivery

_reconcile_seconds = 0.0


def record_reconcile_duration(seconds: float) -> None:
    global _reconcile_seconds
    _reconcile_seconds = seconds


def render_metrics(session: Session) -> str:
    imports_total = session.exec(select(func.count()).select_from(ImportBatch)).one()
    failures = session.exec(
        select(func.count()).select_from(WebhookDelivery).where(WebhookDelivery.status == "failed")
    ).one()
    grouped = session.exec(
        select(ExceptionRecord.type, func.count()).group_by(ExceptionRecord.type)
    ).all()
    lines = [
        "# HELP orbit_imports_total Import batches stored.",
        "# TYPE orbit_imports_total counter",
        f"orbit_imports_total {imports_total}",
        "# HELP orbit_webhook_failures_total Webhook deliveries that failed.",
        "# TYPE orbit_webhook_failures_total counter",
        f"orbit_webhook_failures_total {failures}",
        "# HELP orbit_reconcile_duration_seconds Duration of the latest reconcile run.",
        "# TYPE orbit_reconcile_duration_seconds gauge",
        f"orbit_reconcile_duration_seconds {_reconcile_seconds}",
        "# HELP orbit_exceptions Exceptions by type.",
        "# TYPE orbit_exceptions gauge",
    ]
    if not grouped:
        lines.append('orbit_exceptions{type="none"} 0')
    for exc_type, count in grouped:
        lines.append(f'orbit_exceptions{{type="{exc_type}"}} {count}')
    return "\n".join(lines) + "\n"
