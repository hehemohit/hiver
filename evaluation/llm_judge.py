import json
import os
from pathlib import Path
import sys
from dotenv import load_dotenv
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

load_dotenv()


class JudgeEvaluation(BaseModel):
  empathy_tone_score: int = Field(
      ...,
      ge=1,
      le=5,
      description=(
          "1-5 rating: Brand voice, calm tone, professionalism, and empathy."
      ),
  )
  relevance_actionability_score: int = Field(
      ...,
      ge=1,
      le=5,
      description=(
          "1-5 rating: Accurately addresses the defect with diagnostic guidance"
          " or DM handoff."
      ),
  )
  constraint_compliance_score: int = Field(
      ...,
      ge=1,
      le=5,
      description=(
          "1-5 rating: Under 280 characters, no sensitive PII/passwords"
          " requested publicly."
      ),
  )
  critique: str = Field(
      ...,
      description=(
          "Concise one-sentence rationale for the scores assigned."
      ),
  )


class SupportReplyJudge:

  def __init__(self, model_name: str | None = None):
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("XAI_API_KEY")
    if not api_key:
      raise ValueError(
          "API key not configured. Set GROQ_API_KEY in your .env file."
      )

    # Defaults to openai/gpt-oss-20b to isolate judge token usage from the agent's quota
    self.model = (
        model_name
        or os.getenv("GROQ_JUDGE_MODEL")
        or "openai/gpt-oss-20b"
    )

    raw_client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        max_retries=1,  # Fails fast instead of hanging on long TPD cooldowns
    )
    self.client = instructor.from_openai(
        raw_client, mode=instructor.Mode.TOOLS
    )

  def evaluate_reply(
      self,
      customer_tweet: str,
      generated_reply: str,
      reference_reply: str | None = None,
  ) -> JudgeEvaluation:
    prompt = f"""You are an expert customer experience auditor evaluating an AI support response for @AppleSupport on Twitter.

EVALUATION RUBRIC:
1. Empathy & Tone (1-5): Calm, polite, brand-aligned Apple tone.
2. Relevance & Actionability (1-5): Addresses the core technical/operational issue with appropriate troubleshooting or DM escalation.
3. Constraint Compliance (1-5): Strictly under 280 chars, no request for passwords or sensitive credentials in public.

Customer Tweet: "{customer_tweet}"
Historical Brand Reference: "{reference_reply or 'N/A'}"
Agent Draft Reply: "{generated_reply}"
"""
    return self.client.chat.completions.create(
        model=self.model,
        response_model=JudgeEvaluation,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an objective, calibrated customer support quality"
                    " auditor."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )


if __name__ == "__main__":
  judge = SupportReplyJudge()
  print(f"\n--- TESTING JUDGE ON {judge.model} ---")

  test_query = "My iPhone 14 screen cracked after dropping it!"
  test_reply = (
      "We understand how frustrating a broken screen is. Please DM us with your"
      " serial number and region so we can help you schedule a Genius Bar"
      " appointment."
  )

  evaluation = judge.evaluate_reply(test_query, test_reply)
  print(f"Tone & Empathy:             {evaluation.empathy_tone_score}/5")
  print(f"Relevance & Actionability:  {evaluation.relevance_actionability_score}/5")
  print(f"Constraint Compliance:      {evaluation.constraint_compliance_score}/5")
  print(f"Critique:                   {evaluation.critique}\n")