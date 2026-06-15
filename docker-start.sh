#!/bin/sh
set -e

# Start the SAP CAP OData service in the background on port 4004 (internal only).
# Force PORT=4004 here so it doesn't pick up the host platform's PORT (e.g. Render sets PORT=10000).
cd /app/cap_backend
PORT=4004 npm run start &

# Start the FastAPI app in the foreground on the public port
cd /app/backend
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
