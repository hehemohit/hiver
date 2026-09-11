import json
import re
from pathlib import Path
import pandas as pd
from schemas import IntentEnum, RoutingDecision


def classify_text_heuristics(
    text: str, historical_reply: str, historically_escalated: bool
) -> tuple[IntentEnum, RoutingDecision, str | None]:
  lower = text.lower()

  # 1. Billing & Financial Transactions (Exclude electrical charging context)
  is_battery_charge = bool(
      re.search(
          r"charge\s*(my|the|it|phone|twice|2x|minimum|again|slowly|overnight)",
          lower,
      )
  )
  if not is_battery_charge and any(
      k in lower
      for k in [
          "charged",
          "refund",
          "subscription",
          "billed",
          "receipt",
          "itunes store charge",
          "unauthorized",
          "overcharged",
          "apple music sub",
          "applecare renew",
      ]
  ):
    return (
        IntentEnum.BILLING_SUBSCRIPTION,
        RoutingDecision.ESCALATE,
        "Financial billing dispute or refund request requiring private account"
        " lookup.",
    )

  # 2. Account Security & Credentials (Exclude "disabled person")
  if (
      any(
          k in lower
          for k in [
              "apple id",
              "passcode",
              "password",
              "locked out",
              "2fa",
              "two-factor",
              "stolen",
              "hacked",
              "icloud login",
              "verification code",
              "activation lock",
          ]
      )
      or "account disabled" in lower
      or "id disabled" in lower
  ):
    return (
        IntentEnum.ACCOUNT_SECURITY,
        RoutingDecision.ESCALATE,
        "Account lockout or credential security requiring identity"
        " verification.",
    )

  # 3. Hardware / Physical Damage (Exclude "lock screen" or "home screen")
  has_hardware_damage = any(
      k in lower
      for k in [
          "cracked",
          "shattered",
          "broken",
          "charging port",
          "speaker rattle",
          "camera rattle",
          "dropped",
          "water damage",
          "melted",
          "swollen",
          "bent",
      ]
  )
  has_display_damage = bool(
      re.search(
          r"(cracked|broken|shattered|lines on|black|flickering)\s*screen", lower
      )
  )
  if has_hardware_damage or has_display_damage:
    return (
        IntentEnum.HARDWARE_PHYSICAL,
        RoutingDecision.ESCALATE,
        "Physical damage or hardware component failure requiring Genius Bar"
        " repair.",
    )

  # 4. General Policy / Compatibility Inquiries
  if any(
      k in lower
      for k in [
          "trade-in",
          "trade in",
          "order online",
          "store hours",
          "release date",
          "compatibility",
          "when will",
          "returning of twitter",
      ]
  ):
    return (
        IntentEnum.GENERAL_INQUIRY,
        RoutingDecision.AUTO_HANDLE,
        None,
    )

  # 5. Software & OS Issues
  if any(
      k in lower
      for k in [
          "update",
          "ios",
          "battery",
          "drain",
          "crash",
          "freeze",
          "glitch",
          "wifi",
          "bluetooth",
          "slow",
          "lag",
          "lock screen",
          "songs",
          "app",
          "safari",
          "sync",
          "itunes",
      ]
  ) or is_battery_charge:
    if historically_escalated:
      return (
          IntentEnum.SOFTWARE_OS,
          RoutingDecision.ESCALATE,
          "Persistent OS/update glitch requiring DM diagnostics.",
      )
    return (
        IntentEnum.SOFTWARE_OS,
        RoutingDecision.AUTO_HANDLE,
        None,
    )

  # 6. Out of Scope Rants / Venting
  return (
      IntentEnum.OUT_OF_SCOPE,
      RoutingDecision.AUTO_HANDLE,
      None,
  )


def build_golden_set(
    parquet_path: str = "data/processed/apple_support_threads.parquet",
    golden_out_path: str = "data/golden_set.jsonl",
    corpus_out_path: str = "data/processed/retrieval_corpus.parquet",
    sample_size: int = 200,
):
  df = pd.read_parquet(parquet_path)
  print(f"[*] Loaded {len(df):,} total threads from {parquet_path}")

  df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
  candidates = df.iloc[:1000].copy()
  retrieval_corpus = df.iloc[1000:].copy()

  retrieval_corpus.to_parquet(corpus_out_path, index=False)
  print(f"[+] Saved {len(retrieval_corpus):,} disjoint threads for Vector DB")

  labeled = []
  for _, row in candidates.iterrows():
    intent, routing, reason = classify_text_heuristics(
        row["text_customer"],
        row["text_agent"],
        row["historically_escalated"],
    )
    labeled.append({
        "id": f"gold_{row['tweet_id']}",
        "customer_text": row["text_customer"],
        "gold_intent": intent.value,
        "gold_routing": routing.value,
        "gold_escalation_reason": reason,
        "reference_agent_reply": row["text_agent"],
    })

  cand_df = pd.DataFrame(labeled)

  stratified_samples = []
  target_per_intent = sample_size // 6

  for intent_val in cand_df["gold_intent"].unique():
    subset = cand_df[cand_df["gold_intent"] == intent_val]
    count = min(len(subset), target_per_intent)
    stratified_samples.append(subset.sample(n=count, random_state=42))

  final_df = pd.concat(stratified_samples, ignore_index=True)

  if len(final_df) < sample_size:
    remainder = cand_df[~cand_df["id"].isin(final_df["id"])]
    needed = sample_size - len(final_df)
    final_df = pd.concat(
        [final_df, remainder.head(needed)], ignore_index=True
    )

  final_df = final_df.sample(frac=1.0, random_state=1337).reset_index(
      drop=True
  )

  with open(golden_out_path, "w", encoding="utf-8") as f:
    for _, row in final_df.iterrows():
      f.write(json.dumps(row.to_dict()) + "\n")

  print(
      f"[+] Exported {len(final_df)} clean, shuffled golden evaluation cases to"
      f" '{golden_out_path}'"
  )
  print("\n[*] Intent distribution:\n", final_df["gold_intent"].value_counts())
  print(
      "\n[*] Routing distribution:\n", final_df["gold_routing"].value_counts()
  )


if __name__ == "__main__":
  build_golden_set()