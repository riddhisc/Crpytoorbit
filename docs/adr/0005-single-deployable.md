# 0005 A single deployable

Context: two public origins complicate a free-tier deploy.
Decision: Vite builds the SPA and FastAPI serves it. Development still proxies /api to the API.
Consequences: one container. The CLI shares the Python services and does not need the UI.
