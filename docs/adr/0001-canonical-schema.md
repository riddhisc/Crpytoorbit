# 0001 Canonical schema, per-source adapters

Context: exchange files do not share columns or clocks.
Decision: one CanonicalTx and one connector module per source.
Consequences: a new exchange is a new file. The reconcile engine stays source-agnostic.
