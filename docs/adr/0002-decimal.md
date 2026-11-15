# 0002 Decimal arithmetic, no floats

Context: paise and 8-decimal quantities are not binary floats.
Decision: Decimal in Python, NUMERIC in the database, strings on the wire.
Consequences: no silent rounding. Display formatting happens in the UI.
