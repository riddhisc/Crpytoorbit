"""Background job rows and Idempotency-Key handling."""

import hashlib

from sqlmodel import Session

from app.errors import AppError
from app.models import IdempotencyKey, Job


def request_fingerprint(file_hashes: list[str]) -> str:
    return hashlib.sha256("|".join(file_hashes).encode()).hexdigest()


def start_job(
    session: Session,
    kind: str,
    file_hashes: list[str],
    idempotency_key: str | None,
) -> tuple[Job, bool]:
    digest = request_fingerprint(file_hashes)
    if idempotency_key:
        existing = session.get(IdempotencyKey, idempotency_key)
        if existing is not None:
            if existing.request_hash != digest:
                raise AppError(
                    409,
                    "CONFLICT",
                    "This Idempotency-Key was already used with a different payload.",
                )
            job = session.get(Job, existing.job_id)
            if job is None:
                raise AppError(409, "CONFLICT", "Idempotency record has no job.")
            return job, True
    job = Job(kind=kind, status="queued", progress=0, idempotency_key=idempotency_key)
    session.add(job)
    session.commit()
    session.refresh(job)
    if idempotency_key:
        session.add(IdempotencyKey(key=idempotency_key, request_hash=digest, job_id=job.id))
        session.commit()
    return job, False
