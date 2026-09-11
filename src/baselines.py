from schemas import IntentEnum, RoutingDecision, SupportAgentOutput
from retrieval import SupportKnowledgeBase


class TrivialBaseline:
  """Baseline 1: Predicts majority class, never escalates, and uses a generic reply."""

  def __init__(self, majority_intent: IntentEnum = IntentEnum.OUT_OF_SCOPE):
    self.majority_intent = majority_intent

  def process_tweet(self, customer_text: str) -> SupportAgentOutput:
    return SupportAgentOutput(
        intent=self.majority_intent,
        confidence_score=0.50,
        routing=RoutingDecision.AUTO_HANDLE,
        escalation_reason=None,
        draft_reply=(
            "Thanks for reaching out to Apple Support. We're here to help!"
            " Please reply with more details."
        ),
    )


class SimpleBaseline:
  """Baseline 2: Regex keyword matching for intent and routing,

  with 1-shot nearest-neighbor copy-paste for replies.
  """

  def __init__(self, knowledge_base: SupportKnowledgeBase = None):
    self.kb = knowledge_base or SupportKnowledgeBase()

  def process_tweet(self, customer_text: str) -> SupportAgentOutput:
    lower = customer_text.lower()

    # Rule-based intent and escalation triggers
    if any(
        k in lower
        for k in [
            "apple id",
            "password",
            "passcode",
            "locked",
            "2fa",
            "stolen",
            "hacked",
        ]
    ):
      intent = IntentEnum.ACCOUNT_SECURITY
      routing = RoutingDecision.ESCALATE
      reason = "Security keyword detected."
    elif any(
        k in lower
        for k in ["charge", "charged", "refund", "subscription", "bill"]
    ):
      intent = IntentEnum.BILLING_SUBSCRIPTION
      routing = RoutingDecision.ESCALATE
      reason = "Billing/refund keyword detected."
    elif any(
        k in lower
        for k in ["screen", "cracked", "broken", "port", "speaker", "camera"]
    ):
      intent = IntentEnum.HARDWARE_PHYSICAL
      routing = RoutingDecision.ESCALATE
      reason = "Hardware damage keyword detected."
    elif any(
        k in lower
        for k in ["update", "ios", "battery", "freeze", "crash", "bug"]
    ):
      intent = IntentEnum.SOFTWARE_OS
      routing = RoutingDecision.AUTO_HANDLE
      reason = None
    elif any(k in lower for k in ["price", "trade", "compatible", "store"]):
      intent = IntentEnum.GENERAL_INQUIRY
      routing = RoutingDecision.AUTO_HANDLE
      reason = None
    else:
      intent = IntentEnum.OUT_OF_SCOPE
      routing = RoutingDecision.AUTO_HANDLE
      reason = None

    # Nearest neighbor copy-paste reply
    matches = self.kb.query_similar(customer_text, top_k=1)
    if matches:
      reply = matches[0]["resolved_reply"]
      if len(reply) > 280:
        reply = reply[:277] + "..."
    else:
      reply = "Please DM us with your serial number and iOS version."

    return SupportAgentOutput(
        intent=intent,
        confidence_score=0.75,
        routing=routing,
        escalation_reason=reason,
        draft_reply=reply,
    )