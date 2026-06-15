from typing import List

from pydantic import BaseModel, Field


class ProcurementRequest(BaseModel):
    request_text: str
    department: str = "IT Department"
    user_role: str = "ProcurementOfficer"
    user_name: str = "user"


class AgentStep(BaseModel):
    agent: str
    result: str
    details: str


class ProcurementResponse(BaseModel):
    session_id: str
    decision: str
    summary: str
    vendor_name: str = ""
    vendor_id: str = ""
    quantity: int = 0
    unit_price: float = 0.0
    total_amount: float = 0.0
    budget_available: float = 0.0
    rejection_reason: str = ""
    confidence: float = 0.85
    processing_ms: int = 0
    guardrail_hit: bool = False
    guardrail_reason: str = ""
    agent_steps: List[AgentStep] = Field(default_factory=list)
