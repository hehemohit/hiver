import argparse
import sys
import time
from pathlib import Path

# Configure utf-8 encoding on standard output for Windows console
if sys.platform == "win32":
  try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  except AttributeError:
    pass

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agent import AppleSupportAgent
from schemas import IntentEnum, RoutingDecision


def print_banner():
  print("\n" + "=" * 70)
  print("        @AppleSupport AI Agent — Interactive Demonstration")
  print("=" * 70)
  print("Powered by Groq LLM, ChromaDB RAG & Deterministic Safety Guardrails\n")


def display_agent_result(query: str, decision, retrieval_matches: list[dict]):
  print("\n" + "-" * 70)
  print(f"[CUSTOMER TWEET]: \"{query}\"")
  print("-" * 70)

  print("\n[1. RAG GROUNDING DEMONSTRATIONS (ChromaDB Top-2)]:")
  if retrieval_matches:
    for idx, match in enumerate(retrieval_matches[:2], 1):
      esc_flag = "ESCALATED" if match.get("historically_escalated") else "AUTO"
      print(f"  ({idx}) Sim: {match['similarity_score']:.2f} [{esc_flag}]")
      print(f"      Q: \"{match['similar_query'][:85]}...\"")
      print(f"      A: \"{match['resolved_reply'][:85]}...\"")
  else:
    print("  (No direct vector matches found; using standard system instructions)")

  print("\n[2. CLASSIFICATION & CONFIDENCE]:")
  print(f"  • Detected Intent:   {decision.intent.value}")
  print(f"  • Action Type:       {decision.action_type.value}")
  print(f"  • Model Confidence:  {decision.confidence_score * 100:.1f}%")

  print("\n[3. ROUTING & OPERATIONAL RATIONALE]:")
  print(f"  • Decision:          {decision.routing.value}")
  if decision.escalation_reason:
    print(f"  • Escalation Reason: {decision.escalation_reason}")
  else:
    print("  • Escalation Reason: None (Public Auto-Handle Safe)")

  print("\n[4. DRAFTED TWITTER REPLY]:")
  print(f"  \"{decision.draft_reply}\"")
  print(f"  (Length: {len(decision.draft_reply)}/280 characters)")
  print("-" * 70 + "\n")


def run_preset_demo(agent: AppleSupportAgent):
  presets = [
      (
          "Hardware / Physical Defect",
          "I dropped my iPhone 14 Pro on the pavement and now the screen is"
          " completely shattered and flickering green lines.",
      ),
      (
          "Billing & Refund Dispute",
          "Why was I billed $14.99 yesterday for Apple Music? I cancelled my"
          " subscription two weeks ago, I demand a refund!",
      ),
      (
          "Account Security / Lockout",
          "My Apple ID has been disabled for security reasons and the 2FA code"
          " is going to my stolen phone number!",
      ),
      (
          "Software / OS Glitch",
          "Ever since updating to iOS 17.1, my battery drops 20% in an hour"
          " while using Safari and the phone gets boiling hot.",
      ),
      (
          "Brand Vent / Rant",
          "Apple makes the absolute worst products ever. Overpriced garbage and"
          " terrible customer service.",
      ),
  ]

  print("[*] Running 5 Preset Support Demonstrations across intent spectrum...\n")
  for label, tweet in presets:
    print(f">>> Processing Preset: [{label}]")
    matches = agent.kb.query_similar(tweet, top_k=2)
    decision = agent.process_tweet(tweet)
    display_agent_result(tweet, decision, matches)
    time.sleep(0.5)


def run_interactive_mode(agent: AppleSupportAgent):
  print("[*] Interactive Mode: Type an inbound tweet or 'exit' / 'q' to quit.\n")
  while True:
    try:
      user_input = input("Enter Customer Tweet > ").strip()
    except (KeyboardInterrupt, EOFError):
      print("\nExiting.")
      break

    if not user_input:
      continue
    if user_input.lower() in ("exit", "quit", "q"):
      print("Exiting demo.")
      break

    matches = agent.kb.query_similar(user_input, top_k=2)
    decision = agent.process_tweet(user_input)
    display_agent_result(user_input, decision, matches)


def main():
  parser = argparse.ArgumentParser(description="Run Hiver Support Agent Demo")
  parser.add_argument(
      "--preset",
      action="store_true",
      help="Run predefined demonstration scenarios across 5 intents",
  )
  args = parser.parse_args()

  print_banner()
  print("[*] Initializing AppleSupportAgent and ChromaDB Knowledge Base...")
  agent = AppleSupportAgent()
  print("[+] Agent ready.\n")

  if args.preset:
    run_preset_demo(agent)
  else:
    # If no flag passed, ask user or start interactive mode
    print("Select mode:")
    print("  1. Run 5 curated preset scenarios")
    print("  2. Interactive live tweet prompt")
    choice = input("\nChoice (1 or 2, default: 1): ").strip()
    if choice == "2":
      run_interactive_mode(agent)
    else:
      run_preset_demo(agent)


if __name__ == "__main__":
  main()
