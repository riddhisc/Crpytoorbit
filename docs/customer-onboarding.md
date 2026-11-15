# Customer onboarding

1. Inventory: which exchanges, which wallets, which financial year.
2. Access: CSV exports and a wallet JSON. No API secrets, no private keys.
3. Sample file: one month from each source, plus the unknown-format file if a new exchange shows up.
4. Success metric: every high-severity exception is resolved or ignored with a note, and the FIFO estimate is reviewed by a CA.
5. UAT: load the sample, confirm the six seeded exceptions, resolve one, re-run, confirm it stays resolved, export CSV and PDF.
6. Go-live: demo mode off, API key set, webhook pointed at a public HTTPS URL, Postgres in `DATABASE_URL`.
