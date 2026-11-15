# 0003 Stable exception fingerprints

Context: a re-run must not reopen a decision a person already made.
Decision: fingerprint = hash(type + sorted stable keys). Resolved and ignored rows stay in that status.
Consequences: explanation text can refresh. A new row is a new fingerprint.
