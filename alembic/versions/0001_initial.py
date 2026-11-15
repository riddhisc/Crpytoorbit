"""Baseline schema.

Indexes:
- canonical_tx (asset, ts_utc) serves ledger filters and the running-balance window.
- canonical_tx.tx_hash serves transfer matching.
- exception_record.fingerprint is unique so a resolved exception survives the next reconcile.
"""

from alembic import op
from sqlmodel import SQLModel

from app import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind)
