import argparse
import json
from pathlib import Path
import sys
import time
from tabulate import tabulate

# Ensure src/ and evaluation/ are on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.platform == "win32":
  try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  except AttributeError:
    pass

from agent import AppleSupportAgent
from baselines import SimpleBaseline, TrivialBaseline
from llm_judge import SupportReplyJudge


def load_golden_set(filepath: str) -> list[dict]:
  with open(filepath, "r", encoding="utf-8") as f:
    return [json.loads(line) for line in f if line.strip()]


def evaluate_system_qualitative(
    system,
    judge: SupportReplyJudge,
    dataset: list[dict],
    system_name: str,
    delay: float = 0.5,
):
  print(f"\n[*] Auditing {system_name} on {len(dataset)} replies...")

  empathy_scores = []
  relevance_scores = []
  constraint_scores = []

  for idx, sample in enumerate(dataset, 1):
    tweet = sample["customer_text"]
    ref_reply = sample.get("reference_agent_reply", "")

    # 1. Generate reply from the target system
    try:
      pred = system.process_tweet(tweet)
      reply = pred.draft_reply
    except Exception as e:
      print(f"    [!] Generation error on #{idx}: {e}")
      reply = (
          "We're here to help. Please reach out to Apple Support for assistance."
      )

    # 2. Score reply using the calibrated LLM judge
    try:
      audit = judge.evaluate_reply(tweet, reply, ref_reply)
      empathy_scores.append(audit.empathy_tone_score)
      relevance_scores.append(audit.relevance_actionability_score)
      constraint_scores.append(audit.constraint_compliance_score)
    except Exception as e:
      print(f"    [!] Judge scoring error on #{idx}: {e}")
      empathy_scores.append(3)
      relevance_scores.append(3)
      constraint_scores.append(3)

    if idx % 10 == 0:
      print(f"    -> Audited {idx}/{len(dataset)} responses...")
    if delay > 0:
      time.sleep(delay)

  avg_empathy = (
      sum(empathy_scores) / len(empathy_scores) if empathy_scores else 0.0
  )
  avg_relevance = (
      sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
  )
  avg_constraint = (
      sum(constraint_scores) / len(constraint_scores)
      if constraint_scores
      else 0.0
  )
  overall_avg = (avg_empathy + avg_relevance + avg_constraint) / 3.0

  return {
      "System": system_name,
      "Tone & Empathy (1-5)": f"{avg_empathy:.2f}",
      "Relevance (1-5)": f"{avg_relevance:.2f}",
      "Constraints (1-5)": f"{avg_constraint:.2f}",
      "Overall Quality (1-5)": f"{overall_avg:.2f}",
  }


def main():
  parser = argparse.ArgumentParser(
      description="Run qualitative LLM-as-a-judge comparison."
  )
  parser.add_argument(
      "--limit",
      type=int,
      default=30,
      help="Number of samples to audit (default: 30)",
  )
  parser.add_argument(
      "--delay",
      type=float,
      default=0.5,
      help="Rate-limit sleep between API calls in seconds",
  )
  args = parser.parse_args()

  dataset = load_golden_set("data/golden_set.jsonl")[: args.limit]
  print(
      f"[+] Loaded {len(dataset)} samples from golden set for qualitative audit"
  )

  judge = SupportReplyJudge()
  trivial = TrivialBaseline()
  simple = SimpleBaseline()
  agent = AppleSupportAgent()

  results = []
  results.append(
      evaluate_system_qualitative(
          trivial, judge, dataset, "Trivial Baseline", delay=args.delay
      )
  )
  results.append(
      evaluate_system_qualitative(
          simple, judge, dataset, "Simple Baseline", delay=args.delay
      )
  )
  results.append(
      evaluate_system_qualitative(
          agent,
          judge,
          dataset,
          "Production Agent (Groq + RAG)",
          delay=args.delay,
      )
  )

  headers = [
      "System",
      "Tone & Empathy (1-5)",
      "Relevance (1-5)",
      "Constraints (1-5)",
      "Overall Quality (1-5)",
  ]

  print("\n" + "=" * 80)
  print("        QUALITATIVE LLM-AS-A-JUDGE BENCHMARK TABLE")
  print("=" * 80)
  print(
      tabulate(
          [[r[h] for h in headers] for r in results],
          headers=headers,
          tablefmt="github",
      )
  )
  print("=" * 80 + "\n")


if __name__ == "__main__":
  main()