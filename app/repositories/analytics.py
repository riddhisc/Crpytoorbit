"""Running balances and summary aggregates. Window functions live here on purpose."""

from decimal import Decimal

from sqlalchemy import text
from sqlmodel import Session

# Indexes used by these queries:
# ix_canonical_tx_asset_ts (asset, ts_utc) supports the window partition and ledger range filters.
# ix_canonical_tx_hash supports transfer matching.
# ix_exception_fingerprint keeps resolution stable across re-runs.


def running_balances(session: Session) -> dict[str, Decimal]:
    """Map canonical tx id -> balance of that asset AFTER the row. Excluded rows are omitted."""
    statement = text(
        """
        SELECT id,
               SUM(
                 CASE
                   WHEN kind = 'TRADE' AND side = 'BUY' THEN qty
                   WHEN kind = 'TRANSFER_IN' THEN qty
                   WHEN kind = 'TRADE' AND side = 'SELL' THEN -qty
                   WHEN kind = 'TRANSFER_OUT' THEN -qty
                   ELSE 0
                 END
               ) OVER (
                 PARTITION BY asset
                 ORDER BY ts_utc, source_row
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
               ) AS balance
        FROM canonical_tx
        WHERE NOT excluded
        """
    )
    rows = session.execute(statement).mappings().all()
    return {str(row["id"]): Decimal(str(row["balance"])) for row in rows}


def holdings(session: Session) -> list[dict[str, object]]:
    statement = text(
        """
        SELECT asset,
               SUM(
                 CASE
                   WHEN kind = 'TRADE' AND side = 'BUY' THEN qty
                   WHEN kind = 'TRANSFER_IN' THEN qty
                   WHEN kind = 'TRADE' AND side = 'SELL' THEN -qty
                   WHEN kind = 'TRANSFER_OUT' THEN -qty
                   ELSE 0
                 END
               ) AS qty
        FROM canonical_tx
        WHERE NOT excluded
        GROUP BY asset
        ORDER BY asset
        """
    )
    return [dict(row) for row in session.execute(statement).mappings().all()]
