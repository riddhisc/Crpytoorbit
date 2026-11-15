"""Write the FastAPI OpenAPI document for the frontend type generator."""

import json
from pathlib import Path

from app.main import app

target = Path("docs/openapi.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(target)
