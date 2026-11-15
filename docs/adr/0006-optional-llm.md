# 0006 Optional LLM, always validated

Context: an unseen CSV should import, and a model must not invent transactions.
Decision: fuzzy matching is the default. Anthropic runs only with a key, and only on the header plus five sample rows. Mapped rows use the same validation as every other connector.
Consequences: the demo needs no key. A bad suggestion becomes an import issue.
