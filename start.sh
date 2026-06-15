#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Stop any previously running servers to avoid port conflicts
echo "Stopping processes on ports 8000 and 4004 if present..."
for port in 8000 4004; do
  pids=$(lsof -tiTCP:${port} -sTCP:LISTEN || true)
  if [ -n "$pids" ]; then
    echo "Killing processes on port $port: $pids"
    kill -9 $pids || true
  fi
done

echo "Also attempting to kill uvicorn and npm dev processes by name..."
pkill -f uvicorn || true
pkill -f "npm run dev" || true


if [ -s "$HOME/.nvm/nvm.sh" ]; then
  . "$HOME/.nvm/nvm.sh"
  nvm use 22.22.3 >/dev/null 2>&1 || nvm install 22.22.3 >/dev/null 2>&1 && nvm use 22.22.3 >/dev/null 2>&1
fi

if [ ! -f backend/.env ]; then
  echo "Missing backend/.env. Copy backend/.env.example and add GEMINI_API_KEY."
  exit 1
fi

cd backend
pip3 install -r requirements.txt

cd ../cap_backend
npm install
npm rebuild
npm run deploy:sqlite
npm run dev > ../cap_backend.log 2>&1 &
CAP_PID=$!

sleep 2

cd ../backend
uvicorn main:app --reload --port 8000 > ../backend.log 2>&1 &
PYTHON_PID=$!

printf "\nPython: http://localhost:8000\n"
printf "CAP:    http://localhost:4004\n"
printf "UI:     http://localhost:8000/ui\n"
printf "Docs:   http://localhost:8000/docs\n"
printf "\nStop with Ctrl+C\n"

trap 'kill "$CAP_PID" "$PYTHON_PID" 2>/dev/null || true' INT TERM
wait
