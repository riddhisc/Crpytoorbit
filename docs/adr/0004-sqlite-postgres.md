# 0004 SQLite for the demo, Postgres for real data

Context: the demo must start with no extra services. Customer data must not live on an ephemeral disk.
Decision: SQLite by default. DATABASE_URL selects Postgres. One Alembic migration.
Consequences: SQL stays portable. The Render free disk is documented as a demo trade-off.
