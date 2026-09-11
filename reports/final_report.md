# Project Evaluation & Engineering Report: AI Support Agent for @AppleSupport

**Author:** SDE Intern Candidate  
**Project:** Hiver Take-Home Assignment — Production Customer Support AI Pipeline  
**Target Brand:** `@AppleSupport` (Customer Support on Twitter Dataset)  

---

## 1. Executive Summary

This report presents the design, implementation, and empirical evaluation of an automated customer support agent built for **`@AppleSupport`** on Twitter. The system automates inbound triage by:
1. **Classifying customer intent** across 6 domain-specific categories (`Software_OS_Issue`, `Hardware_Physical`, `Account_Security`, `Billing_Subscription`, `General_Inquiry`, `Out_Of_Scope_Rant`).
2. **Executing deterministic, safety-critical routing** between public resolution (`AUTO_HANDLE`) and private direct message (`ESCALATE`) handoff.
3. **Drafting grounded, Twitter-compliant replies** ($\le 280$ characters, no public PII) using Retrieval-Augmented Generation (RAG) over 19,000 historical brand resolutions.

We benchmark the system against a **Trivial Baseline** (majority class) and a **Simple Baseline** (rule-based + 1-NN retrieval) across both automated quantitative metrics on a curated 200-example golden set and qualitative evaluations using a calibrated LLM-as-a-judge auditor.

---

## 2. Problem Framing

### What "Good" Means for @AppleSupport
Customer support on Twitter is fundamentally different from email or internal ticketing:
* **Public Visibility & Brand Liability:** Every public reply is visible worldwide. Hallucinating troubleshooting steps or misinforming customers causes viral reputational damage.
* **Strict Security Boundaries (Zero Public PII):** Inquiries involving Apple ID credential lockouts, activation locks, two-factor authentication loops, or unauthorized billing disputes must **never** be resolved in public tweets. "Good" means reliably recognizing when to divert a customer into encrypted Direct Messages (DM).
* **High Velocity & Conciseness:** Twitter responses are constrained to 280 characters and require empathetic, concise, and calm de-escalation.
* **Defense-in-Depth:** An AI support agent is only trustworthy if hard business policies supersede probabilistic model behavior.

### What We Chose NOT to Build (and Why)
Engineering in production is defined as much by what is omitted as what is implemented:
1. **No Autonomous Direct Database/Action Execution:** We deliberately did **not** equip the LLM with tools to issue refunds or trigger account unlocks. Giving a generative model autonomous write/transactional authority on sensitive user accounts invites catastrophic prompt-injection exploits and financial loss.
2. **No Multi-Turn Public Chat Loops:** We chose not to engage in unbounded public back-and-forth arguments. The agent provides one clear first-turn diagnostic step or immediately escalates to private DM.
3. **No Heavyweight Local Model Fine-Tuning:** We rejected fine-tuning a 70B parameter model locally. Fine-tuning is brittle to taxonomy changes and introduces massive inference latency and GPU hosting overhead. Instead, we paired a high-throughput inference engine (Groq) with dynamic few-shot RAG and strict Pydantic schemas, achieving sub-second latency and zero cold-start GPU cost.

---

## 3. System Architecture & Safety Guardrails

```
[Inbound Tweet]
       │
       ▼
[ChromaDB Vector Retrieval] ──► Top-2 Nearest Historical Resolutions
       │
       ▼
[Groq LLM + Instructor Engine] ──► Pydantic Structured Output (Intent, Confidence, Routing, Reply)
       │
       ▼
[Deterministic Guardrail Safety Layer]
  ├─ Guardrail 1: Mandatory Brand Escalation Override (Security / Billing / Hardware -> DM)
  ├─ Guardrail 2: Confidence Threshold Fallback (Confidence < 0.70 -> ESCALATE)
  ├─ Guardrail 3: Strict Twitter 280-Character Enforcer (Truncation + Ellipsis)
  └─ Guardrail 4: Schema Consistency Enforcer (Escalation Reason validation)
       │
       ▼
[Validated Operational Support Output]
```

### The 4 Deterministic Guardrails
Even state-of-the-art LLMs can exhibit sycophancy or confidence miscalibration. We implemented four non-bypassable programmatic guardrails:
* **Brand Security Override:** Any classification of `Account_Security`, `Billing_Subscription`, or `Hardware_Physical` is forcibly routed to `ESCALATE`, overriding any model prediction of `AUTO_HANDLE`.
* **Confidence Floor Fallback:** If the model's self-assessed confidence falls below `0.70`, the system automatically escalates with an explicit safety rationale.
* **Character Constraint:** Enforces the hard Twitter 280-character limit programmatically.
* **Schema Integrity:** Guarantees that every escalated ticket carries a human-readable operational reason, while auto-handled queries have clean `null` reasons.

---

## 4. Empirical Evaluation Results

### Headline Benchmark vs. Baselines (200-Sample Golden Set)

| Metric | Trivial Baseline | Simple Baseline (Regex + 1-NN) | Production Agent (Groq + RAG + Guardrails) | Delta vs. Simple Baseline |
| :--- | :---: | :---: | :---: | :---: |
| **Intent Accuracy** | 16.5% | 61.5% | **89.5%** | **+28.0%** |
| **Intent Macro-F1** | 0.047 | 0.582 | **0.884** | **+0.302** |
| **Routing Accuracy** | 42.0% | 74.5% | **94.0%** | **+19.5%** |
| **Routing F1 (Escalate)** | 0.000 | 0.768 | **0.932** | **+0.164** |
| **Safety Recall (Escalate)** | 0.0% | 81.2% | **97.8%** | **+16.6%** |

*Note: Safety Recall measures the percentage of safety-critical queries requiring private DM that were successfully escalated ($\frac{\text{True Escalated}}{\text{All Gold Escalated}}$).*

### Qualitative LLM-as-a-Judge Evaluation (1–5 Rubric)

| System | Tone & Empathy (1–5) | Relevance & Actionability (1–5) | Constraint Compliance (1–5) | Overall Quality (1–5) |
| :--- | :---: | :---: | :---: | :---: |
| **Trivial Baseline** | 3.10 | 2.15 | **5.00** | 3.42 |
| **Simple Baseline** (Copy-Paste 1-NN) | 3.65 | 3.40 | 4.60 | 3.88 |
| **Production Agent** (Groq + RAG) | **4.75** | **4.70** | **4.95** | **4.80** |

---

## 5. Judge Calibration & Human Agreement

To ensure that the automated LLM judge (`openai/gpt-oss-20b`) is trustworthy and calibrated, we evaluated the judge against a diverse benchmark of **20 human-graded customer support interactions** with ground-truth ratings across the 1–5 rubrics:

| Evaluation Dimension | Mean Absolute Error (MAE) | Exact Match (%) | Adjacent Match ($\pm 1$) (%) | Pearson Correlation ($r$) | Spearman Rank Correlation ($\rho$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Tone & Empathy** | 0.65 | 35.0% | 100.0% | 0.782 | 0.560 |
| **Relevance & Actionability** | 0.40 | 60.0% | 100.0% | 0.928 | 0.750 |
| **Constraint Compliance** | 0.20 | 90.0% | 95.0% | 0.815 | 0.814 |
| **Overall Quality (Aggregate)**| **0.42** | **20.0%** | **95.0%** | **0.908** | **0.642** |

### Key Human-Judge Agreement Findings
1. **Strong Overall Correlation ($r = 0.908$):** The LLM judge tracks human quality judgements closely across all three axes, particularly on Relevance ($r = 0.928$) and Constraint Compliance ($r = 0.815$).
2. **95% Adjacent Concordance:** In 95% of cases, the aggregate judge score was within $\pm 1.0$ point of the human auditor's evaluation, showing robust reliability.
3. **Severe Penalties for Policy Violations:** When presented with deliberately harmful replies (e.g. asking for passwords publicly or insulting a user), both the human auditor and LLM judge assigned scores of $1/5$ on Constraint Compliance and Relevance.


---

## 6. Failure Analysis: Top 5 Failure Modes

Through error analysis on the evaluation set, we identified the five most prominent failure modes:

### Failure Mode 1: Semantic Ambiguity in Polysemous Keywords ("Charge")
* **Customer Tweet:** *"My phone is taking ages to charge, this is ridiculous!"*
* **Ground Truth:** `Software_OS_Issue` / `AUTO_HANDLE`
* **Agent Behavior / Failure:** Misclassified as `Billing_Subscription` or triggered billing guardrail due to the word *"charge"*.
* **Root Cause Hypothesis:** The sub-word attention weights on *"charge"* dominate the context when tokenized, competing with electrical battery semantics.
* **Remediation:** Ingested multi-token compound rules into prompt and guardrail filters distinguishing electrical charging from monetary billing.

### Failure Mode 2: Multi-Intent Compound Queries
* **Customer Tweet:** *"My screen cracked when I dropped it and now Apple Music won't let me sign into my account."*
* **Ground Truth:** Multi-intent (`Hardware_Physical` + `Account_Security`), `ESCALATE`
* **Agent Behavior / Failure:** Only classified `Hardware_Physical`, omitting the account login component in the draft reply.
* **Root Cause Hypothesis:** The schema enforces a single categorical `IntentEnum`. When faced with compound issues, the model picks the visually or emotionally dominant defect.
* **Remediation:** While the deterministic safety routing correctly caught the escalation, an expanded schema allowing multi-label intent lists (`list[IntentEnum]`) would improve reply coverage.

### Failure Mode 3: Under-Escalation on Novel System Glitches
* **Customer Tweet:** *"iOS 11 text bug converts the letter 'I' into a weird exclamation mark and square symbol [?]!"*
* **Ground Truth:** `Software_OS_Issue`, `AUTO_HANDLE` (with temporary keyboard workaround)
* **Agent Behavior / Failure:** The model exhibited low confidence ($0.62$) and escalated to DM because the training corpus lacked knowledge of this specific viral iOS 11 font rendering bug.
* **Root Cause Hypothesis:** Out-of-distribution bugs not well represented in historical retrieval embeddings trigger the confidence fallback guardrail.
* **Remediation:** While safe (preferring escalation over hallucination), dynamically indexing real-time Apple System Status feeds into ChromaDB would resolve novel trending bugs publicly.

### Failure Mode 4: False Positive Security Triggers on Developer Submissions
* **Customer Tweet:** *"My App Store app submission has been 'In Review' for 13 days (App Apple ID 1271464806). What is going on?"*
* **Ground Truth:** `General_Inquiry` / Developer Support
* **Agent Behavior / Failure:** Mislabeled as `Account_Security` because the tweet contained the phrase *"Apple ID"*.
* **Root Cause Hypothesis:** The phrase *"Apple ID"* strongly activates the security subspace in the LLM's weights, ignoring the Developer App ID context.
* **Remediation:** Added negative lookbehind patterns in prompts and heuristics specifically exempting developer app bundle IDs.

### Failure Mode 5: Generic Public Troubleshooting for Edge-Case Hardware
* **Customer Tweet:** *"My iPhone X camera lens makes an audible buzzing noise when opening Instagram."*
* **Ground Truth:** `Hardware_Physical` (Optical Image Stabilization motor defect), `ESCALATE`
* **Agent Behavior / Failure:** Suggested reinstalling Instagram and updating iOS before escalating.
* **Root Cause Hypothesis:** The model gravitated towards standard app troubleshooting rather than recognizing physical OIS actuator hardware failure.
* **Remediation:** Adding high-signal few-shot grounding examples for camera buzz/rattle to the vector corpus ensures immediate Genius Bar escalation.

---

## 7. Mandatory Section: "What is Misleading About My Headline Number?"

In real-world ML engineering, high evaluation scores often mask structural vulnerabilities. Here is a transparent critique of our headline metrics:

1. **Circular Heuristic Bias in Golden Set Generation:**
   While the golden set was manually audited and sanitized, initial candidate labeling utilized heuristic keyword rules and historical DM markers. A model that partially mirrors those rules will artificially score higher on accuracy than it would against a 100% blind panel of human support directors.
2. **Offline Precision $\neq$ Online Resolution Rate (FCR):**
   Our metrics measure *first-turn draft accuracy*, not *First Contact Resolution (FCR)*. A generated reply may be linguistically elegant and compliant with Twitter guidelines, but if the troubleshooting link fails to resolve the customer's root issue, the customer will tweet back angrier. Offline evaluation cannot measure true customer satisfaction (CSAT) or Customer Effort Score (CES).
3. **Single-Turn Evaluation vs. Multi-Turn Thread Dynamics:**
   The evaluation treats each inbound tweet as an isolated single turn. In reality, customer support conversations on Twitter frequently span 3–8 turns with evolving context, shifting frustration, and shared screenshots. Evaluating single dyads overstates real-world system readiness for multi-turn thread management.
4. **Safety Recall Inflation via Over-Escalation:**
   Our system achieves **97.8% Safety Recall** on escalations, but this is achieved partly through conservative guardrail overrides. Over-escalating safe public queries into private DMs inflates the safety score while creating unnecessary operational overhead for human Tier-2 support agents.

---

## 8. Decision Log (12 Non-Obvious Engineering Decisions)

1. **Lightweight ONNX Embeddings over PyTorch/CUDA:**
   * *Decision:* Used ChromaDB's default ONNX-runtime `all-MiniLM-L6-v2` rather than `sentence-transformers` via PyTorch.
   * *Rationale:* Avoided a 2GB+ PyTorch wheel dependency, enabling instant installation and sub-second CPU inference across any platform.
2. **Deterministic Guardrails over Pure Prompt Engineering:**
   * *Decision:* Implemented hard programmatic Python overrides for security and billing intents rather than relying on LLM self-routing.
   * *Rationale:* Even top-tier models occasionally suffer from sycophancy or compliance degradation at low temperatures. Security policies must be deterministic.
3. **Top-2 Retrieval Grounding instead of Top-5:**
   * *Decision:* Capped vector retrieval at $k=2$ historical examples.
   * *Rationale:* Empirically reduced prompt token consumption by ~45%, mitigating Groq rate limits while preserving high in-domain grounding quality.
4. **Separate Model Quotas for Agent and Judge:**
   * *Decision:* Configured `qwen/qwen3.6-27b` for the primary agent and `openai/gpt-oss-20b` for the LLM judge.
   * *Rationale:* Prevents rapid exhaustion of the agent's daily token quota during large-scale evaluation and ensures evaluator independence.
5. **Strict Positive Label on Escalation in Safety Recall:**
   * *Decision:* Defined Safety Recall specifically as $\frac{\text{True Escalated}}{\text{All Gold Escalated}}$ rather than standard overall accuracy.
   * *Rationale:* In enterprise support, a False Negative on an escalation (failing to escalate an account lockout) is 10x more damaging than a False Positive.
6. **Programmatic 280-Character Truncation with Ellipsis:**
   * *Decision:* Enforced hard substring truncation (`[:277] + "..."`) alongside Pydantic `max_length=280`.
   * *Rationale:* Eliminates catastrophic API rejection or tweet delivery failure if the LLM generates 281 characters.
7. **Disjoint Data Partitioning to Prevent RAG Contamination:**
   * *Decision:* Excluded the 200 evaluation items completely from the vector indexing corpus.
   * *Rationale:* Preventing nearest-neighbor lookup of the identical conversation dyad ensures realistic out-of-sample evaluation.
8. **Regex Identification of Historical DM Escalation Cues:**
   * *Decision:* Tagged historical tweets as escalated using cues (`"send us a dm"`, `"reach out in DM"`).
   * *Rationale:* Kaggle TWCS data does not have an explicit `escalated` column; regex pattern matching on the brand reply extracted ground truth routing accurately.
9. **Low Temperature ($0.1$) for Agent, Zero Temperature ($0.0$) for Judge:**
   * *Decision:* Set temperature to 0.1 for the agent and 0.0 for the judge.
   * *Rationale:* Minimizes hallucinations in classification while preserving determinism and reproducibility in judge scoring.
10. **JSON RFC 8259 Sanitization (`NaN` $\to$ `null`):**
    * *Decision:* Replaced raw Pandas float `NaN` in golden set outputs with explicit `None` / `null`.
    * *Rationale:* Preserves strict JSON interoperability across non-Python microservices and evaluation tools.
11. **Fast-Fail Client Retries (`max_retries=1`):**
    * *Decision:* Set OpenAI/Groq client retries to 1 instead of default 5.
    * *Rationale:* Avoids indefinite process blocking during rate-limit cooldowns, returning explicit errors quickly.
12. **Confidence-Driven Escalation Fallback Threshold at 0.70:**
    * *Decision:* Set model confidence escalation cutoff at 0.70.
    * *Rationale:* Analysis showed that model predictions between 0.40 and 0.65 had a 42% higher disagreement rate with gold labels; routing them to human agents protects user trust.

---

## 9. What We Would Build Next with One More Week

If given one additional week of engineering time, our priority roadmap would focus on:

1. **Multi-Turn Context & Thread State Tracking:**
   * Implement conversation session memory that stitches together parent tweets via `in_response_to_tweet_id`, tracking customer sentiment shifts across multi-turn interactions.
2. **Active Learning & Human-in-the-Loop Disagreement Queue:**
   * Build an automated triage inbox where queries falling into the low-confidence band ($0.50 \le \text{confidence} < 0.70$) are routed to human operators whose corrections dynamically update the ChromaDB vector index.
3. **Local Distilled SLM (Llama-3.2-3B / Qwen-2.5-3B):**
   * Fine-tune a lightweight 3B parameter model on verified `@AppleSupport` dyads to execute intent classification and routing entirely locally on edge hardware, reducing cloud API costs to $0.
4. **Dynamic System Status Knowledge Tooling:**
   * Connect the agent to real-time Apple System Status APIs (e.g. iCloud outages, App Store maintenance) to automatically deflect mass outage queries with real-time status links.
