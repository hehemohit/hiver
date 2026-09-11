import os
from openai import OpenAI
import instructor
from pydantic import BaseModel, Field

from schemas import IntentEnum, RoutingDecision


class ClassificationResult(BaseModel):
  intent: IntentEnum = Field(description="Classified customer intent")
  confidence_score: float = Field(
      ge=0.0, le=1.0, description="Model certainty score between 0 and 1"
  )
  routing: RoutingDecision = Field(
      description="Routing outcome: AUTO_HANDLE or ESCALATE"
  )
  escalation_reason: str | None = Field(
      default=None,
      description="Operational rationale if escalated; None otherwise",
  )


class IntentClassifier:
  """Modular classifier for evaluating inbound support tweet intents and routing."""

  def __init__(self, client: instructor.Instructor = None, model: str = "qwen/qwen3.6-27b"):
    self.model = model
    if client is not None:
      self.client = client
    else:
      api_key = os.getenv("GROQ_API_KEY") or os.getenv("XAI_API_KEY")
      raw_client = OpenAI(
          api_key=api_key,
          base_url="https://api.groq.com/openai/v1",
          max_retries=1,
      )
      self.client = instructor.from_openai(
          raw_client, mode=instructor.Mode.TOOLS
      )

  def classify(self, text: str) -> ClassificationResult:
    prompt = """Classify the customer's intent and routing decision for @AppleSupport on Twitter into exactly one category:
- Software_OS_Issue (iOS/macOS glitches, battery drain, crashes, lag, connectivity)
- Hardware_Physical (Cracked screens, broken ports, physical damage, speaker rattle)
- Account_Security (Locked Apple ID, 2FA loops, forgotten passwords, stolen devices)
- Billing_Subscription (Charges, App Store refunds, iCloud subscriptions)
- General_Inquiry (Trade-in policies, device compatibility, release dates)
- Out_Of_Scope_Rant (Brand venting, insults, non-actionable complaints)

Routing:
- ESCALATE: Queries requiring private DM (account security, refunds/billing, hardware repairs).
- AUTO_HANDLE: Public troubleshooting advice or basic documentation links.
"""
    return self.client.chat.completions.create(
        model=self.model,
        response_model=ClassificationResult,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Customer: {text}"},
        ],
        temperature=0.0,
    )
