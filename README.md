# SAP Procurement AI Agent

A simple multi-agent procurement demo using:
- Python FastAPI backend
- SAP CAP + SQLite backend
- Static frontend served from Python at `/ui`

## What this repo does
- Accepts procurement requests via `/api/process-request`
- Uses a guardrail layer to block non-procurement or unsafe inputs
- Runs a 3-step agent pipeline: Procurement → Financial → Budget via Google ADK
- Reads vendors and budgets from the CAP SQLite backend
- Returns approval/rejection reasoning and vendor recommendation

## Prerequisites
- Python 3.14+
- Node.js 22.22.3 (recommended via `nvm`)
- npm
- Required: Google Gemini API key to enable Google ADK support

## Setup

### 1. Python backend
```bash
cd backend
cp .env.example .env
# Set GEMINI_API_KEY in backend/.env to run the ADK pipeline.
python3 -m pip install -r requirements.txt
```

### 2. CAP backend
```bash
cd ../cap_backend
source ~/.nvm/nvm.sh
nvm install 22.22.3
nvm use 22.22.3
npm install
npm run deploy:sqlite
```

### 3. Start the app
Open two terminals.

Terminal 1 — Python backend:
```bash
cd /Users/rishi/Downloads/procurement_ai/backend
python3 -m uvicorn main:app --reload --port 8000
```

Terminal 2 — CAP backend:
```bash
cd /Users/rishi/Downloads/procurement_ai/cap_backend
source ~/.nvm/nvm.sh
nvm use 22.22.3
npm run dev
```

## Access the app
- Frontend UI: `http://127.0.0.1:8000/ui`
- API docs: `http://127.0.0.1:8000/docs`
- CAP service: `http://localhost:4004/odata/v4/procurement`

## Notes
- The Python backend requires `google-adk` and a valid `GEMINI_API_KEY`.
- The app does not fallback to mock mode; the ADK agent pipeline must be available.
- The frontend is served by the Python backend directly via `/ui`.

## Example requests
```bash
curl -X POST http://127.0.0.1:8000/api/process-request \
  -H "Content-Type: application/json" \
  -d '{"request_text":"buy 20 dell laptops","department":"IT Department","user_role":"ProcurementOfficer","user_name":"alice"}'
```

```bash
curl http://127.0.0.1:8000/api/vendors
```

```bash
curl "http://127.0.0.1:8000/api/budget/IT%20Department"
```
