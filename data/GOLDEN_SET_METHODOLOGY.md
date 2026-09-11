# Golden Evaluation Set Methodology

## 1. Overview
The golden evaluation set ([data/golden_set.jsonl](file:///c:/projects/Hiver/hiver-support-agent/data/golden_set.jsonl)) consists of **200 hand-curated and audited evaluation examples** extracted from the Kaggle Twitter Customer Support dataset (`twcs.csv`) for `@AppleSupport`.

This dataset serves as the ground truth benchmark for evaluating:
1. **Intent Classification Accuracy & Macro-F1** across 6 domain-specific intents.
2. **Routing Decision Accuracy & F1** (`AUTO_HANDLE` vs. `ESCALATE`).
3. **Safety Recall** (ensuring critical customer queries requiring privacy/repairs are escalated).
4. **Draft Reply Quality** against historical brand responses.

---

## 2. Sampling Strategy

### Strict Disjoint Split (Zero Leakage)
To prevent data contamination and overly optimistic retrieval benchmarks, the data is partitioned into two completely non-overlapping subsets:
* **Retrieval Corpus (`data/processed/retrieval_corpus.parquet`)**: 19,000 historical Q&A dyads indexed in the ChromaDB vector database.
* **Golden Evaluation Set (`data/golden_set.jsonl`)**: 200 distinct test conversation dyads completely excluded from the vector database.

### Stratification
To avoid class imbalance skewing the evaluation, candidate inbound tweets are sampled across diverse customer scenarios to represent the operating distribution:
* `Software_OS_Issue` (~25%): Battery drain, iOS updates, Wi-Fi/Bluetooth glitches, app crashes.
* `Hardware_Physical` (~15%): Cracked screens, physical button failures, liquid damage, camera lens defects.
* `Account_Security` (~15%): Apple ID lockouts, 2FA issues, forgotten passcodes, suspected hacking.
* `Billing_Subscription` (~15%): Unexpected charges, App Store refund disputes, subscription renewals.
* `General_Inquiry` (~15%): Trade-in policies, developer app submission inquiries, release dates, store hours.
* `Out_Of_Scope_Rant` (~15%): General venting, brand complaints without actionable bug details.

---

## 3. Labeling Taxonomy & Guidelines

Each sample contains:
* `id`: Unique identifier referencing the originating Twitter thread (`gold_<tweet_id>`).
* `customer_text`: The inbound tweet text cleaned of Twitter handles, excessive whitespace, and raw URLs.
* `gold_intent`: The primary functional intent.
* `gold_routing`: Operational routing (`AUTO_HANDLE` or `ESCALATE`).
* `gold_escalation_reason`: Explicit rationale explaining why escalation is necessary (e.g., identity verification, Genius Bar hardware repair, private billing lookup), or `null` if auto-handled.
* `reference_agent_reply`: The historical ground-truth reply authored by the verified `@AppleSupport` agent.

---

## 4. Edge Cases & Curation Rules

During manual auditing, several subtle linguistic ambiguities were disambiguated:
1. **"Charge" Ambiguity**:
   * *Financial*: `"charged me $9.99"` $\to$ `Billing_Subscription` + `ESCALATE`.
   * *Electrical*: `"my phone takes ages to charge"` $\to$ `Software_OS_Issue` or `Hardware_Physical` depending on context.
2. **"Password" Ambiguity**:
   * *Apple ID Credentials*: `"forgot my Apple ID password"` $\to$ `Account_Security` + `ESCALATE`.
   * *Wi-Fi Password*: `"iPhone forgot my home Wi-Fi password after iOS 11"` $\to$ `Software_OS_Issue` + `AUTO_HANDLE` / `ESCALATE`.
3. **Developer / App Store Submissions**:
   * App developer queries citing `"In Review for 13 days"` with an App Apple ID $\to$ `General_Inquiry` rather than account security.
4. **Siri & Voice Recognition**:
   * `"Hey Siri is broken after update"` $\to$ `Software_OS_Issue` (software glitch) rather than hardware microphone defect unless physical damage is cited.
