#!/bin/sh
set -e

# Start the SAP CAP OData service in the background on port 4004 (internal only)
cd /app/cap_backend
npm run start &

# Start the FastAPI app in the foreground on the public port
cd /app/backend
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
