FROM nikolaik/python-nodejs:python3.12-nodejs22-slim

WORKDIR /app

# --- CAP backend (Node.js / SAP CAP / SQLite) ---
COPY cap_backend/package*.json cap_backend/
RUN cd cap_backend && npm install

COPY cap_backend cap_backend
RUN cd cap_backend && npm run deploy:sqlite

# --- Python backend (FastAPI) ---
COPY backend/requirements.txt backend/
RUN cd backend && pip install --no-cache-dir -r requirements.txt

COPY backend backend

# --- Frontend (served by FastAPI) ---
COPY frontend frontend

COPY docker-start.sh /app/docker-start.sh
RUN chmod +x /app/docker-start.sh

ENV PORT=8000 \
    CAP_BASE_URL=http://localhost:4004

EXPOSE 8000

CMD ["/app/docker-start.sh"]
