import os
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import instructor

from schemas import IntentEnum, RoutingDecision, SupportAgentOutput, ActionType
from retrieval import SupportKnowledgeBase
from security import SecurityScanner

load_dotenv()


class AppleSupportAgent:

  def __init__(
      self,
      model_name: str | None = None,
      confidence_threshold: float = 0.70,
      knowledge_base: SupportKnowledgeBase = None,
  ):
    # Support either GROQ_API_KEY or XAI_API_KEY
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("XAI_API_KEY")
    if not api_key:
      raise ValueError(
          "API key not found. Please set GROQ_API_KEY in your .env file."
      )

    # Defaults to qwen/qwen3.6-27b to avoid hitting separate daily token ceilings
    self.model = (
        model_name
        or os.getenv("GROQ_MODEL")
        or "qwen/qwen3.6-27b"
    )
    self.confidence_threshold = confidence_threshold
    self.kb = knowledge_base or SupportKnowledgeBase()

    # Point OpenAI client to Groq's high-speed endpoint
    raw_client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        max_retries=1,  # Fails fast instead of hanging on long TPD cooldowns
    )

    # Wrap client with Instructor in TOOLS mode for strict Pydantic JSON validation
    self.client = instructor.from_openai(
        raw_client, mode=instructor.Mode.TOOLS
    )

  def _build_system_prompt(self, historical_context: list[dict]) -> str:
    # Token-optimized system instructions to minimize TPD usage while preserving precision
    prompt = """You are the official automated AI customer support agent for @AppleSupport on Twitter.

Your task is to analyze an incoming customer tweet and return a structured JSON response matching the required schema:

1. Classify Intent into exactly one category:
   - Software_OS_Issue: iOS/macOS update glitches, battery drain, crashes, lag, connectivity (Wi-Fi/Bluetooth).
   - Hardware_Physical: Cracked screens, broken ports, physical defects, audio distortion, camera rattle, liquid damage, battery swelling.
   - Account_Security: Locked Apple ID, 2FA loops, forgotten passcodes/passwords, stolen device lockouts, disabled accounts.
   - Billing_Subscription: Unexpected charges, App Store refunds, iCloud subscription inquiries, payment disputes.
   - General_Inquiry: Trade-in policies, device compatibility, public release dates, Apple Store retail policies.
   - Out_Of_Scope_Rant: Brand venting, non-actionable insults, subjective complaints with no specific technical bug.

2. Action Type & Routing Decision:
   - INFORMATIONAL_SELF_SERVICE: If the user is asking where/how to book an appointment (e.g. Genius Bar reservation, store hours, trade-in links, or public documentation), route as AUTO_HANDLE with verified links (e.g. apple.co/geniusbar).
   - DIAGNOSTIC_DM_ESCALATION: Any query requiring private diagnostic triage, serial numbers, account unlock, billing refunds, or hardware inspection -> route as ESCALATE to DM.
   - escalation_reason: Required if ESCALATE; must be null/None if AUTO_HANDLE.

3. Draft Reply:
   - Strict Twitter limit: Under 280 characters.
   - Tone: Professional, empathetic, concise, and helpful. Never ask for passwords publicly.

GROUNDING EXAMPLES:
"""
    for idx, match in enumerate(historical_context[:2], 1):
      escalated_tag = (
          "[DM ESCALATION]"
          if match.get("historically_escalated")
          else "[PUBLIC AUTO-HANDLE]"
      )
      prompt += f"""
Example {idx} {escalated_tag}:
Customer: "{match['similar_query'][:120]}"
Apple Support: "{match['resolved_reply'][:140]}"
"""
    return prompt

  def process_tweet(
      self, customer_text: str, top_k: int = 2
  ) -> SupportAgentOutput:
    """Processes an inbound tweet through ChromaDB retrieval, Groq reasoning,
    and deterministic guardrail validation.
    """
    # Guardrail 0: Adversarial Prompt Injection & Exfiltration Defense
    is_threat, threat_reason = SecurityScanner.scan_input(customer_text)
    if is_threat:
      return SupportAgentOutput(
          intent=IntentEnum.OUT_OF_SCOPE,
          confidence_score=1.0,
          routing=RoutingDecision.ESCALATE,
          action_type=ActionType.DIAGNOSTIC_DM_ESCALATION,
          escalation_reason=f"Security Alert: {threat_reason}",
          draft_reply=(
              "Thanks for reaching out to Apple Support. For assistance with"
              " Apple devices and services, please visit support.apple.com."
          ),
      )

    # 1. Retrieve top-k nearest neighbor historical resolutions (top_k=2 saves ~45% prompt tokens)
    grounding_matches = self.kb.query_similar(customer_text, top_k=top_k)


    # 2. Assemble system instructions with retrieved demonstrations
    system_prompt = self._build_system_prompt(grounding_matches)

    # 3. Call LLM with Instructor schema parsing
    result: SupportAgentOutput = self.client.chat.completions.create(
        model=self.model,
        response_model=SupportAgentOutput,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Incoming Customer Tweet: {customer_text}",
            },
        ],
        temperature=0.1,
    )

    # 4. Deterministic Guardrail Layer

    # Guardrail A: Smart Action Dispatcher & Mandatory Escalation Policy
    # Check if this is an informational self-service request (e.g. Genius Bar reservation, appointment booking)
    is_booking_faq = bool(
        re.search(
            r"(book|schedule|make|set up|need)\s+(an?\s+)?(appointment|reservation|slot)|genius bar (appointment|reservation|link|booking)|where can i (repair|fix|book)",
            customer_text.lower(),
        )
    )

    if is_booking_faq:
      # Bypass blunt DM escalation and provide immediate self-service reservation link
      result.action_type = ActionType.INFORMATIONAL_SELF_SERVICE
      result.routing = RoutingDecision.AUTO_HANDLE
      result.escalation_reason = None
      if "apple.co/geniusbar" not in result.draft_reply and "getsupport.apple.com" not in result.draft_reply:
        result.draft_reply = (
            "We're sorry to hear about your device. You can easily schedule an"
            " appointment at your nearest Genius Bar directly at"
            " apple.co/geniusbar to have a technician inspect it."
        )
    else:
      # Brand security policy mandates DM escalation for account locks, billing disputes, and physical hardware triage
      mandatory_escalate_intents = {
          IntentEnum.ACCOUNT_SECURITY,
          IntentEnum.BILLING_SUBSCRIPTION,
          IntentEnum.HARDWARE_PHYSICAL,
      }
      if (
          result.intent in mandatory_escalate_intents
          and result.routing != RoutingDecision.ESCALATE
      ):
        result.action_type = ActionType.DIAGNOSTIC_DM_ESCALATION
        result.routing = RoutingDecision.ESCALATE
        result.escalation_reason = (
            f"Brand Policy Override: {result.intent.value} requires secure DM"
            " routing."
        )

    # Guardrail B: Confidence Threshold Fallback
    if result.confidence_score < self.confidence_threshold:
      if result.routing != RoutingDecision.ESCALATE:
        result.routing = RoutingDecision.ESCALATE
        result.escalation_reason = (
            f"Safety Override: Model confidence ({result.confidence_score:.2f})"
            f" is below operating threshold ({self.confidence_threshold:.2f})."
        )

    # Guardrail C: Strict Twitter 280-Character Limit
    if len(result.draft_reply) > 280:
      result.draft_reply = result.draft_reply[:277] + "..."

    # Guardrail D: Escalation Reason Schema Consistency
    if (
        result.routing == RoutingDecision.ESCALATE
        and not result.escalation_reason
    ):
      result.escalation_reason = (
          "Escalated to DM according to brand support protocol."
      )
    elif (
        result.routing == RoutingDecision.AUTO_HANDLE
        and result.escalation_reason
    ):
      result.escalation_reason = None

    # Guardrail E: Output Quarantine Defense
    is_safe, sanitized_reply = SecurityScanner.verify_output(result.draft_reply)
    if not is_safe:
      result.draft_reply = sanitized_reply
      result.routing = RoutingDecision.ESCALATE
      result.escalation_reason = (
          "Security Alert: Generated draft quarantined due to unauthorized policy violation."
      )

    return result




if __name__ == "__main__":
  agent = AppleSupportAgent()

  test_cases = [
      (
          "My iPhone 14 screen turned completely black after dropping it on"
          " concrete."
      ),
      (
          "I was charged $14.99 for Apple Music yesterday but I cancelled my"
          " subscription last week!"
      ),
      (
          "iOS 17 battery drain is so annoying, my phone heats up when browsing"
          " Safari."
      ),
      "You guys make the worst products ever, totally useless.",
  ]

  print(f"\n================ GROQ AGENT TEST ({agent.model}) ================\n")
  for query in test_cases:
    print(f"Customer Tweet: '{query}'")
    decision = agent.process_tweet(query)
    print(f"  -> Intent:            {decision.intent.value}")
    print(f"  -> Confidence:        {decision.confidence_score:.2f}")
    print(f"  -> Routing:           {decision.routing.value}")
    print(f"  -> Escalation Reason: {decision.escalation_reason}")
    print(f"  -> Draft Reply ({len(decision.draft_reply)} chars):")
    print(f'     "{decision.draft_reply}"')
    print("-" * 55)