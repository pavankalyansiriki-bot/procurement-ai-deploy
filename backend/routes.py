import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from cap_client import fetch_budget_from_cap, fetch_vendors_from_cap
from config import CAP_BASE_URL, FRONTEND_INDEX, GEMINI_API_KEY
from guards import check_guardrails
from orchestrator import run_multi_agent_pipeline
from schemas import ProcurementRequest, ProcurementResponse

log = logging.getLogger("procurement-ai.routes")

app = FastAPI(
    title="SAP Procurement AI Backend",
    description="Google ADK Multi-Agent Orchestration for SAP CAP",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ui", response_class=HTMLResponse)
async def ui():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX, media_type="text/html")
    raise HTTPException(status_code=404, detail="Frontend not found")


@app.get("/")
async def root():
    return {
        "service": "SAP Procurement AI Backend",
        "version": "1.0.0",
        "adk_configured": bool(GEMINI_API_KEY),
        "agents": ["ProcurementAgent", "FinancialAgent", "BudgetAgent"],
        "endpoints": ["/api/process-request", "/api/vendors", "/api/budget/{department}", "/health", "/ui"],
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "adk_configured": bool(GEMINI_API_KEY),
        "cap_backend": CAP_BASE_URL,
    }


@app.post("/api/process-request", response_model=ProcurementResponse)
async def process_procurement_request(request: ProcurementRequest):
    log.info(f"[API] /api/process-request | user: {request.user_name} | role: {request.user_role}")

    if request.user_role not in ["ProcurementOfficer", "admin"]:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{request.user_role}' is not authorized to submit procurement requests. Required: ProcurementOfficer",
        )

    blocked, reason = check_guardrails(request.request_text)
    if blocked:
        log.warning(f"[Guardrail] BLOCKED: '{request.request_text}' — {reason}")
        return ProcurementResponse(
            session_id=f"sess-blocked-{request.request_text[:6]}",
            decision="GUARDRAIL_BLOCKED",
            summary=f"Request blocked by guardrails: {reason}",
            rejection_reason=reason,
            guardrail_hit=True,
            guardrail_reason=reason,
            agent_steps=[{
                "agent": "Guardrail",
                "result": "BLOCKED",
                "details": reason,
            }],
        )

    try:
        result = await run_multi_agent_pipeline(request)
        return ProcurementResponse(**result)
    except Exception as exc:
        log.error(f"[API] Pipeline error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent pipeline failed: {str(exc)}")


@app.get("/api/vendors")
async def get_vendors(category: str = ""):
    try:
        vendors = await fetch_vendors_from_cap(category)
        return {"vendors": vendors, "count": len(vendors)}
    except Exception as exc:
        log.error("/api/vendors failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"CAP backend error: {str(exc)}")


@app.get("/api/budget/{department}")
async def get_budget(department: str):
    try:
        budget = await fetch_budget_from_cap(department)
        remaining = budget.get("totalBudget", 0) - budget.get("spentAmount", 0) - budget.get("reservedAmount", 0)
        return {
            "department": department,
            "budget": budget,
            "remaining": remaining,
        }
    except Exception as exc:
        log.error("/api/budget/%s failed: %s", department, exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"CAP backend error: {str(exc)}")


@app.post("/api/guardrail-test")
async def test_guardrail(body: dict):
    text = body.get("text", "")
    blocked, reason = check_guardrails(text)
    return {
        "text": text,
        "blocked": blocked,
        "reason": reason if blocked else "Passed all guardrails",
    }
