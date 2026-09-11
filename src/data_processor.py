import os
import re
from pathlib import Path
import pandas as pd


def clean_text(text: str) -> str:
  """Cleans tweet text by stripping handles, URLs, and extra whitespaces."""
  if not isinstance(text, str):
    return ""
  # Strip user mentions (@AppleSupport, @115108, etc.)
  text = re.sub(r"@\w+", "", text)
  # Strip URLs
  text = re.sub(r"https?://\S+|www\.\S+", "", text)
  # Unescape HTML entities & clean whitespace
  text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
  return re.sub(r"\s+", " ", text).strip()


def sanitize_id(val) -> str | None:
  """Ensures tweet IDs are clean integer strings without float '.0' artifacts."""
  if pd.isna(val):
    return None
  val_str = str(val).strip()
  if val_str.lower() in ("nan", "none", ""):
    return None
  # Strip .0 if loaded as float string
  if val_str.endswith(".0"):
    val_str = val_str[:-2]
  return val_str


def detect_historical_escalation(text: str) -> bool:
  """Identifies if the historical agent escalated to DM / human verification."""
  lower = text.lower()
  escalation_cues = [
      "send us a dm",
      "send a dm",
      "reach out via dm",
      "direct message",
      "in our dms",
      "private message",
      "pm us",
  ]
  return any(phrase in lower for phrase in escalation_cues)


def process_brand_conversations(
    raw_csv_path: str = "data/raw/twcs.csv",
    output_path: str = "data/processed/apple_support_threads.parquet",
    target_brand: str = "AppleSupport",
    chunk_size: int = 100_000,
    max_pairs: int = 20_000,
    min_word_count: int = 5,
):
  raw_path = Path(raw_csv_path)
  if not raw_path.exists():
    raise FileNotFoundError(
        f"Raw dataset not found at '{raw_csv_path}'. "
        f"Download twcs.csv from Kaggle and place it in data/raw/"
    )

  print(f"[*] Streaming {raw_csv_path} in chunks of {chunk_size}...")

  needed_cols = [
      "tweet_id",
      "author_id",
      "inbound",
      "in_response_to_tweet_id",
      "text",
      "created_at",
  ]
  # Force ID columns as strings during read to prevent float coercion
  dtypes = {
      "tweet_id": str,
      "author_id": str,
      "in_response_to_tweet_id": str,
      "text": str,
  }

  brand_chunks = []

  for chunk in pd.read_csv(
      raw_csv_path,
      usecols=needed_cols,
      dtype=dtypes,
      chunksize=chunk_size,
      low_memory=False,
  ):
    mask = (chunk["author_id"] == target_brand) | (
        chunk["text"].str.contains(f"@{target_brand}", case=False, na=False)
    )
    filtered = chunk[mask]
    if not filtered.empty:
      brand_chunks.append(filtered)

  df_brand = pd.concat(brand_chunks, ignore_index=True)
  print(f"[*] Extracted {len(df_brand):,} brand-related records.")

  # Clean and normalize ID formats
  df_brand["tweet_id"] = df_brand["tweet_id"].apply(sanitize_id)
  df_brand["in_response_to_tweet_id"] = df_brand[
      "in_response_to_tweet_id"
  ].apply(sanitize_id)

  # Standardize inbound boolean
  is_inbound = df_brand["inbound"].astype(str).str.lower().isin(["true", "1"])

  # 1. Inbound root questions: customer inquiries starting a conversation
  inbounds = df_brand[
      is_inbound & df_brand["in_response_to_tweet_id"].isna()
  ][["tweet_id", "text", "created_at"]]
  print(f"[*] Inbound root queries found: {len(inbounds):,}")

  # 2. First outbound replies by AppleSupport
  outbounds = df_brand[df_brand["author_id"] == target_brand][
      ["in_response_to_tweet_id", "text"]
  ]
  print(f"[*] Outbound replies authored by {target_brand}: {len(outbounds):,}")

  # 3. Merge Q&A dyads
  print("[*] Merging conversational pairs on Tweet ID...")
  threads = inbounds.merge(
      outbounds,
      left_on="tweet_id",
      right_on="in_response_to_tweet_id",
      suffixes=("_customer", "_agent"),
  )
  print(f"[*] Merged conversation pairs: {len(threads):,}")

  # 4. Clean text
  threads["text_customer"] = threads["text_customer"].apply(clean_text)
  threads["text_agent"] = threads["text_agent"].apply(clean_text)

  # 5. Filter out empty or ultra-short noise
  threads["len_customer"] = threads["text_customer"].str.split().apply(len)
  threads["len_agent"] = threads["text_agent"].str.split().apply(len)

  clean_threads = threads[
      (threads["len_customer"] >= min_word_count)
      & (threads["len_agent"] >= min_word_count)
  ].copy()

  # 6. Flag historical routing for grounding & analysis
  clean_threads["historically_escalated"] = clean_threads["text_agent"].apply(
      detect_historical_escalation
  )

  # Deduplicate on customer query text
  clean_threads = clean_threads.drop_duplicates(subset=["text_customer"])

  if len(clean_threads) > max_pairs:
    clean_threads = clean_threads.sample(n=max_pairs, random_state=42)

  export_df = clean_threads[
      [
          "tweet_id",
          "text_customer",
          "text_agent",
          "historically_escalated",
          "created_at",
      ]
  ]

  os.makedirs(Path(output_path).parent, exist_ok=True)
  export_df.to_parquet(output_path, index=False)

  escalation_ratio = (
      export_df["historically_escalated"].mean() * 100
      if len(export_df) > 0
      else 0
  )
  print(
      f"[+] Successfully exported {len(export_df):,} clean pairs to"
      f" '{output_path}'"
  )
  print(f"[+] Historical DM Escalation Ratio: {escalation_ratio:.1f}%")


if __name__ == "__main__":
  process_brand_conversations()