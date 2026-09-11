import os
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

# Add src and evaluation to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))

from schemas import IntentEnum, RoutingDecision, SupportAgentOutput
from data_processor import clean_text, sanitize_id, detect_historical_escalation


def test_clean_text():
  dirty = "@AppleSupport @user123 My screen cracked! Check http://test.com &amp; help"
  cleaned = clean_text(dirty)
  assert "@AppleSupport" not in cleaned
  assert "http://test.com" not in cleaned
  assert "&amp;" not in cleaned
  assert "&" in cleaned
  assert "My screen cracked!" in cleaned


def test_sanitize_id():
  assert sanitize_id("12345.0") == "12345"
  assert sanitize_id("98765") == "98765"
  assert sanitize_id(None) is None
  assert sanitize_id("nan") is None


def test_detect_historical_escalation():
  assert detect_historical_escalation("Please send us a DM so we can look into this.") is True
  assert detect_historical_escalation("Reach out via DM with your serial number.") is True
  assert detect_historical_escalation("Try force restarting your device using these steps.") is False


def test_support_agent_output_schema_valid():
  output = SupportAgentOutput(
      intent=IntentEnum.SOFTWARE_OS,
      confidence_score=0.92,
      routing=RoutingDecision.AUTO_HANDLE,
      escalation_reason=None,
      draft_reply="Try restarting your iPhone to fix this glitch.",
  )
  assert output.confidence_score == 0.92
  assert output.routing == RoutingDecision.AUTO_HANDLE
  assert len(output.draft_reply) <= 280


def test_support_agent_output_schema_invalid_confidence():
  with pytest.raises(ValidationError):
    SupportAgentOutput(
        intent=IntentEnum.SOFTWARE_OS,
        confidence_score=1.5,  # Exceeds max 1.0
        routing=RoutingDecision.AUTO_HANDLE,
        draft_reply="Invalid confidence test",
    )


def test_mandatory_escalation_guardrail_logic():
  # Simulating Guardrail A behavior
  mandatory_intents = {
      IntentEnum.ACCOUNT_SECURITY,
      IntentEnum.BILLING_SUBSCRIPTION,
      IntentEnum.HARDWARE_PHYSICAL,
  }

  def apply_guardrails(intent, routing, confidence, reply):
    reason = None
    if intent in mandatory_intents and routing != RoutingDecision.ESCALATE:
      routing = RoutingDecision.ESCALATE
      reason = f"Brand Policy Override: {intent.value} requires secure DM routing."
    if confidence < 0.70 and routing != RoutingDecision.ESCALATE:
      routing = RoutingDecision.ESCALATE
      reason = "Safety Override: Low confidence."
    if len(reply) > 280:
      reply = reply[:277] + "..."
    return routing, reason, reply

  # Hardware should always escalate even if model predicted AUTO_HANDLE
  routing, reason, _ = apply_guardrails(
      IntentEnum.HARDWARE_PHYSICAL, RoutingDecision.AUTO_HANDLE, 0.95, "Screen broken"
  )
  assert routing == RoutingDecision.ESCALATE
  assert "Brand Policy Override" in reason

  # Low confidence should escalate even for general inquiry
  routing, reason, _ = apply_guardrails(
      IntentEnum.GENERAL_INQUIRY, RoutingDecision.AUTO_HANDLE, 0.45, "Maybe trade in?"
  )
  assert routing == RoutingDecision.ESCALATE
  assert "Safety Override: Low confidence." in reason
