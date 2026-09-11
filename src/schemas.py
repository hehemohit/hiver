from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class IntentEnum(str, Enum):
    SOFTWARE_OS = "Software_OS_Issue"
    HARDWARE_PHYSICAL = "Hardware_Physical"
    ACCOUNT_SECURITY = "Account_Security"
    BILLING_SUBSCRIPTION = "Billing_Subscription"
    GENERAL_INQUIRY = "General_Inquiry"
    OUT_OF_SCOPE = "Out_Of_Scope_Rant"


class RoutingDecision(str, Enum):
    AUTO_HANDLE = "AUTO_HANDLE"
    ESCALATE = "ESCALATE"


class SupportAgentOutput(BaseModel):
    intent: IntentEnum = Field(description="Classified customer intent")
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Model certainty score between 0 and 1"
    )
    routing: RoutingDecision = Field(
        description="Routing outcome: AUTO_HANDLE or ESCALATE"
    )
    escalation_reason: Optional[str] = Field(
        default=None,
        description="Explicit operational rationale if escalated; None otherwise",
    )
    draft_reply: str = Field(
        max_length=280,
        description="Grounded, Twitter-compliant reply under 280 characters",
    )


class GoldenExample(BaseModel):
    id: str
    customer_text: str
    gold_intent: IntentEnum
    gold_routing: RoutingDecision
    gold_escalation_reason: Optional[str] = None
    reference_agent_reply: str