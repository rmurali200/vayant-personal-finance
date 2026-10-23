"""Prints the OpenAPI spec, which web/ turns into TypeScript types (npm run gen:api)."""
import json

from .main import app

print(json.dumps(app.openapi()))
