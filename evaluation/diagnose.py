import json
import sys
from pathlib import Path

# Configure utf-8 encoding on standard output for Windows console
if sys.platform == "win32":
  try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
  except AttributeError:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
from agent import AppleSupportAgent

agent = AppleSupportAgent()

golden_path = ROOT_DIR / "data" / "golden_set.jsonl"
with open(golden_path, "r", encoding="utf-8") as f:
  records = [json.loads(line) for line in f if line.strip()][:15]

print("\n" + "=" * 75)
print("             MISMATCH DIAGNOSTICS (First 15 Samples)")
print("=" * 75)

mismatch_count = 0
for idx, item in enumerate(records, 1):
  text = item["customer_text"]
  gold_intent = item["gold_intent"]
  gold_routing = item["gold_routing"]

  pred = agent.process_tweet(text)

  intent_match = pred.intent.value == gold_intent
  routing_match = pred.routing.value == gold_routing

  if not intent_match or not routing_match:
    mismatch_count += 1
    print(f"\n[Case #{idx}]")
    print(f'Customer: "{text}"')
    print(f"  Gold Label:  Intent={gold_intent:<22} | Routing={gold_routing}")
    print(
        f"  Agent Pred:  Intent={pred.intent.value:<22} |"
        f" Routing={pred.routing.value} (Conf: {pred.confidence_score:.2f})"
    )
    if pred.escalation_reason:
      print(f"  Escalation Reason: {pred.escalation_reason}")
    print("-" * 75)

print(
    f"\n[+] Completed diagnostics: {mismatch_count}/{len(records)} disagreements"
    " found.\n"
)
