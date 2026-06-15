#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

BACKEND_LOG="backend.log"
CAP_LOG="cap_backend.log"
COMBINED_LOG="server_combined.log"

if [ ! -f "$BACKEND_LOG" ] && [ ! -f "$CAP_LOG" ]; then
  echo "No server logs found. Run ./start.sh first so backend.log and cap_backend.log are created."
  exit 1
fi

rm -f "$COMBINED_LOG"

echo "Combining logs into $COMBINED_LOG"
if [ -f "$CAP_LOG" ]; then
  printf "===== CAP BACKEND LOG =====\n" >> "$COMBINED_LOG"
  cat "$CAP_LOG" >> "$COMBINED_LOG"
  printf "\n" >> "$COMBINED_LOG"
fi
if [ -f "$BACKEND_LOG" ]; then
  printf "===== PYTHON BACKEND LOG =====\n" >> "$COMBINED_LOG"
  cat "$BACKEND_LOG" >> "$COMBINED_LOG"
  printf "\n" >> "$COMBINED_LOG"
fi

printf "\nCombined log written to %s\n" "$COMBINED_LOG"
printf "\n=== Last 80 lines of combined log ===\n"
tail -n 80 "$COMBINED_LOG" || true

printf "\n=== Error / warning summary ===\n"
grep -Eni 'error|warn|fail|forbidden|traceback|exception' "$COMBINED_LOG" | tail -n 80 || true
