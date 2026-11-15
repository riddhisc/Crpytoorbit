"""India tax estimate. Every figure is an estimate, not advice."""

from fastapi import APIRouter

from app.deps import DbSession
from app.schemas import TaxResponse
from app.services.read import tax_report

router = APIRouter(prefix="/api/v1", tags=["tax"])


@router.get("/tax", response_model=TaxResponse, summary="FIFO tax estimate")
def tax(session: DbSession) -> TaxResponse:
    return TaxResponse(**tax_report(session))
