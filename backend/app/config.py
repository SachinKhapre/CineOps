import os

from dotenv import load_dotenv

# Load .env so `uvicorn backend.app.main:app` works without exporting vars by
# hand. Real environment variables win, so deployments are unaffected.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"), override=False)

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "mediadoc_readonly")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# §42: restricted CORS -- the frontend dev server only, not "*".
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
