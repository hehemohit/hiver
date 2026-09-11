import os
from openai import OpenAI
import instructor
from pydantic import BaseModel, Field

from schemas import IntentEnum, RoutingDecision


class DraftReplyOutput(BaseModel):
  draft_reply: str = Field(
      max_length=280,
      description="Grounded, Twitter-compliant reply under 280 characters",
  )


class ResponseGenerator:
  """Modular draft response generator grounded in historical brand resolutions."""

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

  def generate_reply(
      self,
      customer_text: str,
      intent: IntentEnum,
      routing: RoutingDecision,
      grounding_examples: list[dict],
  ) -> str:
    prompt = f"""You are the official automated AI customer support agent for @AppleSupport on Twitter.
Write a concise, helpful, empathetic, and professional reply strictly under 280 characters.
Never ask for passwords, credit card numbers, or sensitive credentials in public.
Intent: {intent.value}
Routing Decision: {routing.value}

Historical resolutions for reference:
"""
    for ex in grounding_examples[:2]:
      prompt += f"- Similar: \"{ex.get('similar_query', '')[:80]}\" -> Agent: \"{ex.get('resolved_reply', '')[:100]}\"\n"

    res = self.client.chat.completions.create(
        model=self.model,
        response_model=DraftReplyOutput,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Customer Tweet: {customer_text}"},
        ],
        temperature=0.2,
    )
    reply = res.draft_reply
    if len(reply) > 280:
      reply = reply[:277] + "..."
    return reply
