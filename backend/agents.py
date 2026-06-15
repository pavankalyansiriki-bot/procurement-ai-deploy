import logging
import os
from typing import Any

from cap_client import fetch_vendors_from_cap, fetch_budget_from_cap
from config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger("procurement-ai.agents")

from google.adk.agents import Agent
from google.adk.tools import FunctionTool


async def find_vendors(item_keyword: str, quantity: int, vendor_preference: str = None) -> dict[str, Any]:
    log.info(f"[ProcurementAgent] Finding vendors for: {item_keyword} x{quantity} (preferred: {vendor_preference})")
    vendors = await fetch_vendors_from_cap()

    keyword_lower = item_keyword.lower()
    relevant = []
    for v in vendors:
        cat = v.get("category", "").lower()
        name = v.get("name", "").lower()
        if any(w in keyword_lower for w in ["laptop", "computer", "desktop", "monitor", "tablet"]):
            if "electronics" in cat:
                relevant.append(v)
        elif keyword_lower in name or keyword_lower in cat:
            relevant.append(v)

    if not relevant:
        relevant = [v for v in vendors if v.get("isActive")][:5]

    # Prioritize vendor preference if specified
    if vendor_preference:
        preferred_vendors = [v for v in relevant if vendor_preference.lower() in v.get("name", "").lower()]
        if preferred_vendors:
            relevant = preferred_vendors

    relevant.sort(key=lambda x: x.get("rating", 0), reverse=True)
    best = relevant[0] if relevant else None
    total = (best["unitPrice"] * quantity) if best else 0

    result = {
        "vendors_found": len(relevant),
        "best_vendor_id": best["ID"] if best else "",
        "best_vendor_name": best["name"] if best else "Not found",
        "unit_price": best["unitPrice"] if best else 0,
        "total_amount": total,
        "quantity": quantity,
        "lead_time_days": best.get("leadTimeDays", 7) if best else 0,
        "rating": best.get("rating", 0) if best else 0,
        "all_vendors": [
            {
                "name": v["name"],
                "price": v["unitPrice"],
                "rating": v.get("rating", 0),
                "lead_days": v.get("leadTimeDays", 7)
            }
            for v in relevant[:5]
        ]
    }
    log.info(f"[ProcurementAgent] Best vendor: {result['best_vendor_name']} @ ${result['unit_price']}")
    return result


async def check_financial_sufficiency(department: str, required_amount: float) -> dict[str, Any]:
    log.info(f"[FinancialAgent] Checking ${required_amount} for {department}")
    budget = await fetch_budget_from_cap(department)

    total = float(budget.get("totalBudget", 0))
    spent = float(budget.get("spentAmount", 0))
    reserved = float(budget.get("reservedAmount", 0))
    remaining = total - spent - reserved
    utilization = ((spent + required_amount) / total * 100) if total > 0 else 100

    sufficient = remaining >= required_amount
    approval_limit = float(budget.get("approvalLimit", 15000))
    needs_escalation = required_amount > approval_limit

    result = {
        "sufficient": sufficient,
        "total_budget": total,
        "spent_amount": spent,
        "reserved_amount": reserved,
        "budget_remaining": remaining,
        "required_amount": required_amount,
        "shortfall": max(0, required_amount - remaining),
        "budget_utilization_pct": round(utilization, 1),
        "needs_escalation": needs_escalation,
        "approval_limit": approval_limit,
        "financial_verdict": "SUFFICIENT" if sufficient else "INSUFFICIENT",
        "message": (
            f"Budget sufficient. ${remaining:,.2f} available, ${required_amount:,.2f} required."
            if sufficient else
            f"Insufficient budget. Need ${required_amount:,.2f}, only ${remaining:,.2f} available. Shortfall: ${required_amount - remaining:,.2f}"
        )
    }
    log.info(f"[FinancialAgent] Verdict: {result['financial_verdict']}, Remaining: ${remaining:,.2f}")
    return result


async def make_budget_decision(
    vendor_name: str,
    item_description: str,
    quantity: int,
    total_amount: float,
    budget_sufficient: bool,
    budget_remaining: float,
    budget_utilization_pct: float,
    needs_escalation: bool
) -> dict[str, Any]:
    log.info(f"[BudgetAgent] Making decision for ${total_amount} via {vendor_name}")

    reasons_approve = []
    reasons_reject = []

    if not budget_sufficient:
        reasons_reject.append(
            f"Insufficient budget. Required ${total_amount:,.2f} but only ${budget_remaining:,.2f} available."
        )

    if budget_utilization_pct > 90:
        reasons_reject.append(
            f"Budget utilization critically high at {budget_utilization_pct}%. Cannot approve additional expenditure."
        )
    elif budget_utilization_pct > 80:
        reasons_reject.append(
            f"Budget utilization is {budget_utilization_pct}% — over the 80% warning threshold."
        )

    if total_amount > 500000:
        reasons_reject.append(
            f"Amount ${total_amount:,.2f} exceeds maximum single-PO limit of $500,000. Requires board approval."
        )

    if needs_escalation and total_amount > 50000:
        reasons_reject.append(
            f"Amount ${total_amount:,.2f} exceeds departmental approval limit. Requires CFO sign-off."
        )

    if budget_sufficient:
        reasons_approve.append(f"Budget available: ${budget_remaining:,.2f} remaining.")
    if budget_utilization_pct <= 80:
        reasons_approve.append(f"Budget utilization healthy at {budget_utilization_pct}%.")
    if not needs_escalation:
        reasons_approve.append("Amount within departmental approval limit.")

    if reasons_reject:
        decision = "REJECTED"
        feedback = " | ".join(reasons_reject)
        summary = (
            f"Purchase of {quantity}x {item_description} from {vendor_name} "
            f"for ${total_amount:,.2f} has been REJECTED. Reasons: {feedback}"
        )
    else:
        decision = "APPROVED"
        feedback = " | ".join(reasons_approve)
        summary = (
            f"Purchase of {quantity}x {item_description} from {vendor_name} "
            f"for ${total_amount:,.2f} has been APPROVED. {feedback}"
        )

    result = {
        "decision": decision,
        "feedback": feedback,
        "summary": summary,
        "approve_reasons": reasons_approve,
        "reject_reasons": reasons_reject,
        "po_recommended": decision == "APPROVED"
    }
    log.info(f"[BudgetAgent] Decision: {decision}")
    return result


def build_adk_agents():
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is required to run the Google ADK agent pipeline. "
            "Set GEMINI_API_KEY in backend/.env."
        )

    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

    procurement_agent = Agent(
        name="ProcurementAgent",
        model=GEMINI_MODEL,
        description="Finds and recommends vendors for procurement requests",
        instruction="""You are a SAP Procurement Specialist agent.
Your ONLY job: find the best vendor for the requested item.

RULES:
- Only respond to procurement/purchasing requests
- Always call find_vendors tool with the item, quantity, and vendor_preference (if specified)
- If a specific vendor is mentioned, pass it as vendor_preference to prioritize it
- Report back: vendor name, unit price, total amount, lead time
- Do NOT make financial decisions — that is FinancialAgent's job
- Do NOT make approval decisions — that is BudgetAgent's job
- If the request is not about buying/procuring something, say: 'Not a procurement request'

OUTPUT FORMAT: Always end with a clear vendor recommendation. Include the vendor name, pricing, and lead time.""",
        tools=[FunctionTool(func=find_vendors)]
    )

    financial_agent = Agent(
        name="FinancialAgent",
        model=GEMINI_MODEL,
        description="Checks financial sufficiency and budget availability",
        instruction="""You are a SAP Financial Analysis agent.
Your ONLY job: check if there is enough budget for the requested purchase.

RULES:
- Only analyze financial aspects — budget, amounts, utilization
- Always call check_financial_sufficiency with department and required amount
- Report: available budget, required amount, utilization %, verdict
- Do NOT recommend vendors — that is ProcurementAgent's job
- Do NOT make final approval — that is BudgetAgent's job
- Be precise with numbers — always show exact dollar amounts

OUTPUT FORMAT: Clear SUFFICIENT or INSUFFICIENT verdict with numbers.""",
        tools=[FunctionTool(func=check_financial_sufficiency)]
    )

    budget_agent = Agent(
        name="BudgetAgent",
        model=GEMINI_MODEL,
        description="Makes final APPROVE or REJECT decision with detailed feedback",
        instruction="""You are a SAP Budget Controller agent.
Your ONLY job: make the final APPROVE or REJECT decision.

RULES:
- Only make budget approval decisions — not vendor selection, not financial analysis
- Always call make_budget_decision tool with all parameters
- ALWAYS provide specific rejection reasons if rejecting
- Consider: budget sufficiency, utilization %, approval limits, amount thresholds
- Be transparent — explain exactly WHY you are approving or rejecting
- Rejection reasons must be actionable — what can be done to get it approved?

OUTPUT FORMAT: Start with APPROVED or REJECTED in caps, then detailed reasoning.""",
        tools=[FunctionTool(func=make_budget_decision)]
    )

    return procurement_agent, financial_agent, budget_agent
