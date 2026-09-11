import argparse
import json
import os
import sys
import time
from pathlib import Path
from sklearn.metrics import accuracy_score, classification_report, f1_score
from tabulate import tabulate

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

if sys.platform == "win32":
  try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  except AttributeError:
    pass

from agent import AppleSupportAgent
from baselines import SimpleBaseline, TrivialBaseline
from schemas import RoutingDecision


def load_golden_set(filepath: str) -> list[dict]:
  with open(filepath, "r", encoding="utf-8") as f:
    return [json.loads(line) for line in f if line.strip()]


def evaluate_system(system, dataset: list[dict], system_name: str, delay: float = 0.5):
  print(f"\n[*] Evaluating {system_name} on {len(dataset)} examples...")
  y_true_intent = []
  y_pred_intent = []
  y_true_routing = []
  y_pred_routing = []

  for idx, sample in enumerate(dataset, 1):
    gold_intent = sample["gold_intent"]
    gold_routing = sample["gold_routing"]
    text = sample["customer_text"]

    try:
      pred = system.process_tweet(text)
      y_pred_intent.append(pred.intent.value)
      y_pred_routing.append(pred.routing.value)
    except Exception as e:
      print(f"    [!] Error on sample {idx}: {e}")
      y_pred_intent.append("Out_Of_Scope_Rant")
      y_pred_routing.append("AUTO_HANDLE")

    y_true_intent.append(gold_intent)
    y_true_routing.append(gold_routing)

    if idx % 10 == 0:
      print(f"    -> Processed {idx}/{len(dataset)} items...")
    if delay > 0:
      time.sleep(delay)

  # Intent Metrics
  intent_acc = accuracy_score(y_true_intent, y_pred_intent)
  intent_f1 = f1_score(
      y_true_intent, y_pred_intent, average="macro", zero_division=0
  )

  # Routing Metrics (Escalate = positive class)
  routing_acc = accuracy_score(y_true_routing, y_pred_routing)
  routing_f1 = f1_score(
      y_true_routing,
      y_pred_routing,
      pos_label=RoutingDecision.ESCALATE.value,
      zero_division=0,
  )

  # Safety Escalation Recall: True Escalated / All Gold Escalated
  true_escalate = sum(
      1
      for t, p in zip(y_true_routing, y_pred_routing)
      if t == RoutingDecision.ESCALATE.value
      and p == RoutingDecision.ESCALATE.value
  )
  total_gold_escalate = sum(
      1 for t in y_true_routing if t == RoutingDecision.ESCALATE.value
  )
  safety_recall = (
      (true_escalate / total_gold_escalate) if total_gold_escalate > 0 else 0.0
  )

  return {
      "System": system_name,
      "Intent Acc": f"{intent_acc * 100:.1f}%",
      "Intent Macro-F1": f"{intent_f1:.3f}",
      "Routing Acc": f"{routing_acc * 100:.1f}%",
      "Routing F1": f"{routing_f1:.3f}",
      "Safety Recall (Escalate)": f"{safety_recall * 100:.1f}%",
  }


def main():
  parser = argparse.ArgumentParser(
      description="Run Hiver benchmark evaluation against baselines."
  )
  parser.add_argument(
      "--golden_set",
      type=str,
      default="data/golden_set.jsonl",
      help="Path to golden set JSONL",
  )
  parser.add_argument(
      "--limit",
      type=int,
      default=30,
      help="Number of samples to evaluate (default 30 for <2 min test; set 200 for full set)",
  )
  parser.add_argument(
      "--delay",
      type=float,
      default=0.4,
      help="Rate-limit delay in seconds between API calls",
  )
  args = parser.parse_args()

  # Install tabulate if needed
  try:
    import tabulate
  except ImportError:
    os.system(f"{sys.executable} -m pip install tabulate")

  dataset = load_golden_set(args.golden_set)[: args.limit]
  print(f"[+] Loaded {len(dataset)} evaluation samples from {args.golden_set}")

  # 1. Evaluate Trivial Baseline
  trivial = TrivialBaseline()
  trivial_metrics = evaluate_system(
      trivial, dataset, "Trivial Baseline", delay=0.0
  )

  # 2. Evaluate Simple Baseline
  simple = SimpleBaseline()
  simple_metrics = evaluate_system(simple, dataset, "Simple Baseline", delay=0.0)

  # 3. Evaluate Production Agent
  agent = AppleSupportAgent()
  agent_metrics = evaluate_system(
      agent, dataset, "Production Agent (Groq + RAG)", delay=args.delay
  )

  # Print Comparison Table
  results = [trivial_metrics, simple_metrics, agent_metrics]
  headers = [
      "System",
      "Intent Acc",
      "Intent Macro-F1",
      "Routing Acc",
      "Routing F1",
      "Safety Recall (Escalate)",
  ]

  print("\n" + "=" * 80)
  print("             HEADLINE BENCHMARK COMPARISON TABLE")
  print("=" * 80)
  print(
      tabulate.tabulate(
          [[r[h] for h in headers] for r in results],
          headers=headers,
          tablefmt="github",
      )
  )
  print("=" * 80 + "\n")


if __name__ == "__main__":
  main()