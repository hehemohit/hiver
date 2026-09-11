# Hiver Support Agent (@AppleSupport)

An automated AI customer support agent and evaluation pipeline for `@AppleSupport` on Twitter, built with **Groq LLMs**, **Instructor** (structured outputs), **ChromaDB** (retrieval-augmented grounding), and a deterministic **guardrail safety layer**.

---

## Overview & System Capabilities

The agent automates the triage, routing, and response drafting for inbound customer support queries:

1. **Intent Classification**:
   Categorizes customer queries into one of 6 operational intents:
   * `Software_OS_Issue`
   * `Hardware_Physical`
   * `Account_Security`
   * `Billing_Subscription`
   * `General_Inquiry`
   * `Out_Of_Scope_Rant`

2. **Deterministic & Safe Routing**:
   Routes queries into:
   * `AUTO_HANDLE`: Public troubleshooting advice, basic settings guidance, or official support links.
   * `ESCALATE`: Private direct message (DM) handoff with human agents for sensitive, complex, or high-risk issues.

3. **Deterministic Guardrails**:
   * **Mandatory Escalation Policy**: Hard brand override forcing `ESCALATE` for `Account_Security`, `Billing_Subscription`, and `Hardware_Physical`.
   * **Confidence Threshold Fallback**: Automatically escalates queries where model confidence falls below `0.70`.
   * **Twitter Compliance**: Enforces strict Twitter character limits ($\le 280$ characters).
   * **Schema Consistency**: Enforces explicit escalation reasons for all escalated queries.

4. **Retrieval-Augmented Grounding (RAG)**:
   * Uses **ChromaDB** with lightweight ONNX `all-MiniLM-L6-v2` embeddings (no heavy PyTorch or GPU dependencies required).
   * Injects historical verified Q&A demonstrations into the prompt context for in-domain tone and factual grounding.

5. **Evaluation Suite**:
   * Benchmarks against **Trivial** (majority-class) and **Simple** (rule/keyword + 1-NN) baselines.
   * Calculates **Intent Accuracy**, **Intent Macro-F1**, **Routing Accuracy**, **Routing F1**, and **Safety Recall** ($\frac{\text{True Escalations}}{\text{All Gold Escalations}}$).
   * Includes an **LLM-as-a-Judge** scoring engine for qualitative tone, empathy, relevance, and constraint compliance.

---

## Project Structure

```text
hiver-support-agent/
│
├── data/
│   ├── raw/
│   │   └── twcs.csv                     # Raw Kaggle Twitter Customer Support dataset
│   ├── processed/
│   │   ├── apple_support_threads.parquet # Extracted & cleaned @AppleSupport Q&A pairs
│   │   └── retrieval_corpus.parquet     # Knowledge base corpus for vector indexing
│   ├── chroma_db/                       # Persistent ChromaDB vector index
│   └── golden_set.jsonl                 # Stratified 200-sample evaluation benchmark
│
├── src/
│   ├── __init__.py
│   ├── schemas.py                       # Pydantic schemas (IntentEnum, SupportAgentOutput, etc.)
│   ├── agent.py                         # Production AppleSupportAgent with guardrails
│   ├── retrieval.py                     # SupportKnowledgeBase (ChromaDB + ONNX embeddings)
│   ├── data_processor.py                # Pipeline to parse and clean raw TWCS data
│   ├── sample_golden_set.py             # Script to generate balanced golden eval set
│   └── baselines.py                     # Trivial and Simple heuristic baselines
│
├── evaluation/
│   ├── __init__.py
│   ├── eval_metrics.py                  # Quantitative benchmark runner
│   ├── llm_judge.py                     # SupportReplyJudge rubric definition
│   └── eval_judge_benchmark.py          # Qualitative LLM judge evaluation runner
│
├── reports/
│   └── final_report.md                  # Comprehensive evaluation and architecture report
│
├── tests/                               # Unit test suite
├── diagnose.py                          # Disagreement analyzer on golden set samples
├── demo.py                              # Interactive demonstration script
├── requirements.txt                     # Project dependencies
├── .env.example                         # Environment configuration template
└── README.md
```

---

## Quickstart & Installation

### 1. Prerequisites & Environment Setup

Create and activate a virtual environment with Python 3.10+:

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python -m venv venv
source venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env` and set your Groq API credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.6-27b
GROQ_JUDGE_MODEL=openai/gpt-oss-20b
```

---

## Data Pipeline Reproduction

If you wish to re-process the raw data and rebuild the vector store from scratch:

1. **Download Raw Dataset**:
   Place `twcs.csv` into `data/raw/` (from the [Kaggle Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) dataset).

2. **Process Conversation Pairs**:
   Extracts cleaned `@AppleSupport` Q&A dyads and detects historical DM escalations:
   ```bash
   python src/data_processor.py
   ```

3. **Sample Golden Set & Split Retrieval Corpus**:
   Generates a balanced 200-sample evaluation dataset and a disjoint vector corpus:
   ```bash
   python src/sample_golden_set.py
   ```

4. **Build Vector Store Index**:
   Indexes the conversation corpus into ChromaDB:
   ```bash
   python src/retrieval.py
   ```

---

## Running the Agent & Diagnostics

### Run the Agent on Test Inquiries
Execute the agent directly to run test scenarios across different intent types:

```bash
python src/agent.py
```

### Run Golden Set Diagnostics
Inspect disagreements between agent predictions and the ground-truth golden set:

```bash
python diagnose.py
```

---

## Evaluation

### 1. Quantitative Benchmark (vs Baselines)
Evaluates the production agent against the **Trivial Baseline** and **Simple Baseline**:

```bash
# Quick run on first 30 samples
python evaluation/eval_metrics.py --limit 30

# Full run on the complete 200-sample golden set
python evaluation/eval_metrics.py --limit 200
```

**Metrics Evaluated:**
* Intent Accuracy & Macro-F1
* Routing Decision Accuracy & F1
* Safety Recall ($\frac{\text{True Escalated}}{\text{All Gold Escalated}}$)

### 2. Qualitative LLM-as-a-Judge Audit & Calibration
Evaluates generated replies using an automated LLM judge across three 1–5 scoring axes:
1. **Tone & Empathy**: Professional, empathetic, calm brand voice.
2. **Relevance & Actionability**: Technical accuracy and proper troubleshooting/DM handoff.
3. **Constraint Compliance**: Length $\le 280$ characters, no public password or sensitive credential requests.

```bash
# Run comparative LLM-as-a-judge evaluation across baselines
python evaluation/eval_judge_benchmark.py --limit 30

# Run human-judge calibration benchmark (MAE, Pearson r, Spearman rho)
python evaluation/judge_calibration.py
```

### 3. Automated Unit Tests
Run the pytest test suite to verify schemas, text cleaning, and deterministic guardrail logic:

```bash
pytest tests/test_agent.py -v
```

---

## Deliverables & Documentation Index

* **Final Engineering & Evaluation Report**: [reports/final_report.md](file:///c:/projects/Hiver/hiver-support-agent/reports/final_report.md)
  * *Problem Framing & What We Chose Not to Build*
  * *Results vs. Trivial & Simple Baselines*
  * *Empirical Human-Judge Calibration Analysis*
  * *Top 5 Failure Modes (with Real Examples & Hypotheses)*
  * *"What is Misleading About My Headline Number?" (Mandatory Section)*
  * *Decision Log (12 Non-Obvious Engineering Decisions)*
  * *1-Week Future Roadmap*
* **Golden Set Sampling & Curation Methodology**: [data/GOLDEN_SET_METHODOLOGY.md](file:///c:/projects/Hiver/hiver-support-agent/data/GOLDEN_SET_METHODOLOGY.md)
* **Interactive Agent Demonstration**: [demo.py](file:///c:/projects/Hiver/hiver-support-agent/demo.py) (`python demo.py --preset`)

---

## Deliverable Status Matrix

| Deliverable (from Take-Home Brief) | Status | Artifact / Implementation |
| :--- | :---: | :--- |
| **1. Runnable Pipeline & Demo** | **Complete** | [demo.py](file:///c:/projects/Hiver/hiver-support-agent/demo.py), [agent.py](file:///c:/projects/Hiver/hiver-support-agent/src/agent.py), [README.md](file:///c:/projects/Hiver/hiver-support-agent/README.md) (Runs in $< 15$ min) |
| **2. Golden Evaluation Set (200 items)** | **Complete** | [data/golden_set.jsonl](file:///c:/projects/Hiver/hiver-support-agent/data/golden_set.jsonl), [data/GOLDEN_SET_METHODOLOGY.md](file:///c:/projects/Hiver/hiver-support-agent/data/GOLDEN_SET_METHODOLOGY.md) |
| **3. Evaluation Harness + Human-Judge Agreement** | **Complete** | [evaluation/eval_metrics.py](file:///c:/projects/Hiver/hiver-support-agent/evaluation/eval_metrics.py), [evaluation/judge_calibration.py](file:///c:/projects/Hiver/hiver-support-agent/evaluation/judge_calibration.py) ($r = 0.908$) |
| **4. Comprehensive Report** | **Complete** | [reports/final_report.md](file:///c:/projects/Hiver/hiver-support-agent/reports/final_report.md) (All 5 mandatory sections covered) |
| **5. Decision Log (12 Decisions)** | **Complete** | Documented in Section 8 of [reports/final_report.md](file:///c:/projects/Hiver/hiver-support-agent/reports/final_report.md) |

