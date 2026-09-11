import json
import os
import sys
import time
from pathlib import Path
import numpy as np
from scipy.stats import pearsonr, spearmanr
from tabulate import tabulate

# Add src and evaluation to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm_judge import SupportReplyJudge


def run_judge_calibration(
    benchmark_path: str = "evaluation/human_benchmark_sample.json",
    delay: float = 0.5,
):
  with open(benchmark_path, "r", encoding="utf-8") as f:
    benchmark_cases = json.load(f)

  print(
      f"[*] Starting Judge Calibration against {len(benchmark_cases)} human-graded benchmark cases..."
  )

  judge = SupportReplyJudge()

  human_empathy, judge_empathy = [], []
  human_relevance, judge_relevance = [], []
  human_constraints, judge_constraints = [], []
  human_overall, judge_overall = [], []

  detailed_records = []

  for idx, item in enumerate(benchmark_cases, 1):
    case_id = item["case_id"]
    tweet = item["customer_tweet"]
    reply = item["generated_reply"]
    h_scores = item["human_scores"]

    try:
      eval_res = judge.evaluate_reply(tweet, reply)
      j_emp = eval_res.empathy_tone_score
      j_rel = eval_res.relevance_actionability_score
      j_con = eval_res.constraint_compliance_score
      j_crit = eval_res.critique
    except Exception as e:
      print(f"    [!] Judge scoring error on {case_id}: {e}")
      j_emp, j_rel, j_con, j_crit = 3, 3, 3, "Scoring error default fallback."

    h_emp = h_scores["empathy_tone"]
    h_rel = h_scores["relevance_actionability"]
    h_con = h_scores["constraint_compliance"]

    h_avg = round((h_emp + h_rel + h_con) / 3.0, 2)
    j_avg = round((j_emp + j_rel + j_con) / 3.0, 2)

    human_empathy.append(h_emp)
    judge_empathy.append(j_emp)
    human_relevance.append(h_rel)
    judge_relevance.append(j_rel)
    human_constraints.append(h_con)
    judge_constraints.append(j_con)
    human_overall.append(h_avg)
    judge_overall.append(j_avg)

    detailed_records.append({
        "case_id": case_id,
        "human_overall": h_avg,
        "judge_overall": j_avg,
        "diff": round(abs(h_avg - j_avg), 2),
        "h_scores": (h_emp, h_rel, h_con),
        "j_scores": (j_emp, j_rel, j_con),
        "judge_critique": j_crit,
    })

    print(
        f"  [{idx}/{len(benchmark_cases)}] {case_id}: Human Avg={h_avg} | Judge Avg={j_avg} (Diff: {abs(h_avg - j_avg):.2f})"
    )
    if delay > 0:
      time.sleep(delay)

  # Compute statistical metrics
  def compute_metrics(y_true, y_pred):
    mae = float(np.mean(np.abs(np.array(y_true) - np.array(y_pred))))
    exact_acc = float(np.mean(np.array(y_true) == np.array(y_pred))) * 100
    adj_acc = (
        float(np.mean(np.abs(np.array(y_true) - np.array(y_pred)) <= 1.0)) * 100
    )

    if len(set(y_true)) > 1 and len(set(y_pred)) > 1:
      p_corr, _ = pearsonr(y_true, y_pred)
      s_corr, _ = spearmanr(y_true, y_pred)
    else:
      p_corr, s_corr = 0.0, 0.0

    return {
        "MAE": f"{mae:.2f}",
        "Exact Match": f"{exact_acc:.1f}%",
        "Adjacent (+-1)": f"{adj_acc:.1f}%",
        "Pearson r": f"{p_corr:.3f}",
        "Spearman rho": f"{s_corr:.3f}",
    }

  metrics_table = [
      {"Dimension": "Empathy & Tone (1-5)", **compute_metrics(human_empathy, judge_empathy)},
      {"Dimension": "Relevance & Actionability (1-5)", **compute_metrics(human_relevance, judge_relevance)},
      {"Dimension": "Constraint Compliance (1-5)", **compute_metrics(human_constraints, judge_constraints)},
      {"Dimension": "Overall Quality (Aggregate)", **compute_metrics(human_overall, judge_overall)},
  ]

  # Save output to json first
  output_path = "evaluation/calibration_results.json"
  with open(output_path, "w", encoding="utf-8") as f:
    json.dump(
        {
            "summary_metrics": metrics_table,
            "detailed_cases": detailed_records,
        },
        f,
        indent=2,
    )
  print(f"[+] Calibration results saved to '{output_path}'")

  print("\n" + "=" * 85)
  print("            HUMAN-JUDGE ALIGNMENT & CALIBRATION BENCHMARK")
  print("=" * 85)
  headers = [
      "Dimension",
      "MAE",
      "Exact Match",
      "Adjacent (+-1)",
      "Pearson r",
      "Spearman rho",
  ]
  try:
    print(
        tabulate(
            [[row[h] for h in headers] for row in metrics_table],
            headers=headers,
            tablefmt="github",
        )
    )
  except Exception as e:
    for row in metrics_table:
      print(row)
  print("=" * 85 + "\n")



if __name__ == "__main__":
  run_judge_calibration()
