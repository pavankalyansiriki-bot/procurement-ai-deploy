import logging
import re
import time
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from schemas import ProcurementRequest
from cap_client import fetch_vendors_from_cap
from agents import (
    build_adk_agents,
    _tool_find_vendors,
    _tool_check_financial_sufficiency,
    _tool_make_budget_decision,
)

log = logging.getLogger("procurement-ai.orchestrator")


async def _run_adk_agent(agent, session_id: str, prompt_text: str) -> str:
    runner = Runner(
        session_service=InMemorySessionService(),
        agent=agent,
        app_name=getattr(agent, "name", "ADKAgent"),
        auto_create_session=True,
    )
    response_text = ""
    prompt = Content(parts=[Part(text=prompt_text)], role="user")

    async for event in runner.run_async(
        user_id="procurement_user",
        session_id=session_id,
        new_message=prompt,
    ):
        if event.message is not None:
            message = event.message
            for part in getattr(message, "parts", []) or []:
                if getattr(part, "text", None):
                    response_text = f"{response_text} {part.text}".strip()

    return response_text.strip()


async def run_multi_agent_pipeline(request: ProcurementRequest) -> dict:
    start_time = time.time()
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    agent_steps = []

    log.info(f"[Orchestrator] Starting pipeline | Session: {session_id}")
    log.info(f"[Orchestrator] Request: '{request.request_text}' | Dept: {request.department}")

    text = request.request_text.lower()
    qty_match = re.search(r"\b(\d+)\b", text)
    quantity = int(qty_match.group(1)) if qty_match else 1

    item_keywords = ["laptop", "desktop", "monitor", "tablet", "printer",
                     "computer", "server", "phone", "chair", "desk"]
    item = next((kw for kw in item_keywords if kw in text), "equipment")
    
    # Extract vendor preference if mentioned
    vendor_keywords = ["dell", "hp", "apple", "lenovo", "asus", "samsung", "sony", 
                       "microsoft", "cisco", "netapp", "oracle", "ibm"]
    vendor_preference = next((vendor for vendor in vendor_keywords if vendor in text), None)

    log.info(f"[Orchestrator] Parsed → item: {item}, qty: {quantity}, vendor: {vendor_preference}")

    # 🚨 GUARDRAIL: If no vendor is specified, reject early and ask the user to specify
    if not vendor_preference:
        processing_ms = int((time.time() - start_time) * 1000)
        feedback_msg = "Please specify a preferred vendor (e.g., Dell, HP, Apple) to process this procurement request."
        
        log.warning(f"[Orchestrator] Pipeline halted: No vendor specified.")
        
        return {
            "session_id": session_id,
            "decision": "REJECTED",
            "summary": "Request rejected due to missing information.",
            "vendor_name": "Unknown",
            "vendor_id": "N/A",
            "quantity": quantity,
            "unit_price": 0.0,
            "total_amount": 0.0,
            "budget_available": 0.0,
            "rejection_reason": feedback_msg,
            "confidence": 1.0,
            "processing_ms": processing_ms,
            "guardrail_hit": True,
            "guardrail_reason": "Missing Vendor Specification",
            "agent_steps": [{
                "agent": "OrchestratorGuardrail",
                "result": "REJECTED",
                "details": feedback_msg
            }],
        }

    # Proceed with the 3-Agent pipeline if vendor is present
    procurement_agent, financial_agent, budget_agent = build_adk_agents()

    log.info("[Orchestrator] → Running ProcurementAgent")
    procurement_prompt = (
        f"Procurement request: {request.request_text}\n"
        f"Department: {request.department}\n"
        f"Quantity: {quantity}\n"
        f"Item: {item}\n"
        f"Preferred Vendor: {vendor_preference}\n"
        "Use the find_vendors tool and provide a concise procurement recommendation."
    )
    procurement_adk_text = await _run_adk_agent(procurement_agent, session_id, procurement_prompt)
    
    # Pass the validated vendor_preference to the backend database/SAP tool
    vendor_data = await _tool_find_vendors(item, quantity, vendor_preference=vendor_preference)

    proc_step = {
        "agent": "ProcurementAgent",
        "result": "COMPLETED",
        "details": (
            f"Found {vendor_data['vendors_found']} vendors. "
            f"Best match: {vendor_data['best_vendor_name']} @ ${vendor_data['unit_price']:,.2f}/unit. "
            f"Total for {quantity} units: ${vendor_data['total_amount']:,.2f}. "
            f"Lead time: {vendor_data['lead_time_days']} days. "
            f"Rating: {vendor_data['rating']}/5.0"
        )
    }
    agent_steps.append(proc_step)
    log.info(f"[ProcurementAgent] ✓ {proc_step['details']}")

    log.info("[Orchestrator] → Running FinancialAgent")
    financial_prompt = (
        f"Verify financial sufficiency for department {request.department} "
        f"with required amount ${vendor_data['total_amount']:,.2f}. "
        "Use the check_financial_sufficiency tool and return a precise verdict."
    )
    financial_adk_text = await _run_adk_agent(financial_agent, session_id, financial_prompt)
    financial_data = await _tool_check_financial_sufficiency(request.department, vendor_data["total_amount"])

    fin_step = {
        "agent": "FinancialAgent",
        "result": financial_data["financial_verdict"],
        "details": (
            f"Budget check for {request.department}: "
            f"Total ${financial_data['total_budget']:,.2f} | "
            f"Spent ${financial_data['spent_amount']:,.2f} | "
            f"Available ${financial_data['budget_remaining']:,.2f} | "
            f"Required ${financial_data['required_amount']:,.2f} | "
            f"Utilization: {financial_data['budget_utilization_pct']}% | "
            f"Verdict: {financial_data['financial_verdict']}. "
            f"ADK: {financial_adk_text}"
        )
    }
    agent_steps.append(fin_step)
    log.info(f"[FinancialAgent] ✓ {fin_step['details']}")

    log.info("[Orchestrator] → Running BudgetAgent")
    budget_prompt = (
        f"Make a final approval decision for purchasing {quantity}x {item} "
        f"from {vendor_data['best_vendor_name']} at ${vendor_data['total_amount']:,.2f}. "
        "Use the make_budget_decision tool and explain the final decision."
    )
    budget_adk_text = await _run_adk_agent(budget_agent, session_id, budget_prompt)
    budget_data = await _tool_make_budget_decision(
        vendor_name=vendor_data["best_vendor_name"],
        item_description=item,
        quantity=quantity,
        total_amount=vendor_data["total_amount"],
        budget_sufficient=financial_data["sufficient"],
        budget_remaining=financial_data["budget_remaining"],
        budget_utilization_pct=financial_data["budget_utilization_pct"],
        needs_escalation=financial_data["needs_escalation"]
    )

    budget_step = {
        "agent": "BudgetAgent",
        "result": budget_data["decision"],
        "details": (
            f"{budget_data['summary']} "
            f"ADK: {budget_adk_text}"
        )
    }
    agent_steps.append(budget_step)
    log.info(f"[BudgetAgent] ✓ Decision: {budget_data['decision']}")

    processing_ms = int((time.time() - start_time) * 1000)

    return {
        "session_id": session_id,
        "decision": budget_data["decision"],
        "summary": budget_data["summary"],
        "vendor_name": vendor_data["best_vendor_name"],
        "vendor_id": vendor_data["best_vendor_id"],
        "quantity": quantity,
        "unit_price": vendor_data["unit_price"],
        "total_amount": vendor_data["total_amount"],
        "budget_available": financial_data["budget_remaining"],
        "rejection_reason": budget_data["feedback"] if budget_data["decision"] == "REJECTED" else "",
        "confidence": 0.92,
        "processing_ms": processing_ms,
        "guardrail_hit": False,
        "guardrail_reason": "",
        "agent_steps": agent_steps,
    }