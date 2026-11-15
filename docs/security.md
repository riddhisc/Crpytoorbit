# Security

- Untrusted files: size cap, extension and MIME allow-list, row cap, safe filenames, and CSV formula prefixing on export.
- No private keys: the UI says "Public addresses & CSV only". Connectors never ask for secrets. Etherscan uses a public address and an optional key.
- Webhook signing: outbound posts carry `X-Orbit-Signature` (HMAC-SHA256). Receivers should verify it.
- SSRF: webhook URLs must be http(s) and must not resolve to private, loopback, or link-local addresses.
- Retention: demo mode can reset the database. Production should set `DEMO_MODE=false`, require `X-API-Key` on writes, and put Postgres behind the app. Rate limits cover upload and webhook routes. CORS is the configured origin list. Responses send `X-Content-Type-Options`, a frame denial, and a content security policy.
