"""CSV and PDF downloads."""

from fastapi import APIRouter
from fastapi.responses import Response

from app.deps import DbSession
from app.services.export import exceptions_csv, ledger_csv, report_pdf
from app.services.read import summary

router = APIRouter(prefix="/api/v1/export", tags=["export"])


@router.get("/ledger.csv", summary="Download the ledger as CSV")
def export_ledger(session: DbSession) -> Response:
    return Response(
        content=ledger_csv(session),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ledger.csv"},
    )


@router.get("/exceptions.csv", summary="Download exceptions as CSV")
def export_exceptions(session: DbSession) -> Response:
    return Response(
        content=exceptions_csv(session),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=exceptions.csv"},
    )


@router.get("/report.pdf", summary="Download a PDF reconciliation report")
def export_pdf(session: DbSession) -> Response:
    payload = report_pdf(session, summary(session))
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=crypto-orbit-report.pdf"},
    )
