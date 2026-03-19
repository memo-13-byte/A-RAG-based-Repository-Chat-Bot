"""
RepoWise Evaluation Script
--------------------------
Sends questions to RepoWise API, measures latency,
scores with LLM-as-judge, writes results to Excel.

Usage:
    python repowise_evaluator.py [--questions 60] [--repo psf/requests] [--dry-run]

Requirements:
    pip install openai openpyxl requests tqdm
"""

import json
import time
import argparse
import os
import statistics
from datetime import datetime
from pathlib import Path

import requests as http_requests
from tqdm import tqdm
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
import openai
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# CONFIGURATION — edit these before running
# ─────────────────────────────────────────────
REPOWISE_BASE_URL = "http://localhost:8000"   # Your backend URL
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")  # Set in .env file
JUDGE_MODEL       = "gpt-4o"             # Higher quality judge — more accurate labels
DATASET_JSON      = "repowise_eval_dataset.json"
OUTPUT_XLSX       = "repowise_eval_results.xlsx"
TEMPLATE_XLSX     = "repowise_eval_dataset.xlsx"  # The dataset Excel we created
REQUEST_TIMEOUT   = 60   # seconds per question
DELAY_BETWEEN_Q   = 1.0  # seconds between questions (avoid rate limiting)
# ─────────────────────────────────────────────


# ── LLM-as-Judge prompt (based on SWE-QA rubric) ────────────────────────────
JUDGE_SYSTEM = """You are an expert evaluator for a software repository analysis Q&A system called RepoWise.
Your job is to score a system response against a question and ground truth hint.
The GROUND TRUTH HINT lists the KEY expected elements — it is not exhaustive.
You must respond ONLY with valid JSON — no markdown, no explanation outside JSON."""

JUDGE_PROMPT = """Evaluate the following response on 5 dimensions, each scored 1-5.

QUESTION: {question}
GROUND TRUTH HINT: {ground_truth}
EVALUATION CRITERIA: {criteria}
SYSTEM RESPONSE: {response}

Scoring rubric:
5 = Excellent: all key elements from the hint are present and accurate
4 = Good: most key elements present, only minor omissions or small inaccuracies
3 = Partial: some key elements present but important ones missing, OR inaccuracies present
2 = Weak: barely addresses the hint or contains significant wrong information
1 = Incorrect: wrong, contradicts the hint, or completely off-topic

Step-by-step evaluation process:
1. Read the GROUND TRUTH HINT and identify each distinct key element (e.g., specific names, commit hashes, class names, file names, numbers).
2. For each key element, check: is it present in the SYSTEM RESPONSE? (yes/no)
3. Count how many key elements are covered.
4. Check if any covered element is stated INCORRECTLY (contradicts ground truth).
5. Assign manual_label based on the rules below.

Completeness rules:
- ALL key elements covered + no contradictions → Correct
- MOST (>50%) key elements covered + no major contradictions → Correct or Partial depending on severity
- SOME (<50%) key elements covered → Partial
- Key elements missing AND contradicted → Incorrect

Additional information rules:
- The response may contain MORE information than the hint (e.g., more commits, more files, more classes). This is expected behavior for a RAG system — evaluate only whether the HINT elements are present and accurate, not whether extra info exists.
- Do NOT penalize for additional details unless they directly contradict a hint element.
- Do NOT label additional details as "fabricated" unless they directly contradict a verifiable fact in the hint (e.g., wrong author name, wrong hash for a named commit).

MANUAL_LABEL rules:
- "Correct"   if the response covers ALL key points in the hint without major errors (extra correct info is fine)
- "Partial"   if it covers SOME but not all key points in the hint, OR contains notable inaccuracies alongside correct info
- "Incorrect" if it completely misses the point, contradicts the hint, or is mostly fabricated/wrong

Respond ONLY with this JSON:
{{
  "correctness": <1-5>,
  "completeness": <1-5>,
  "relevance": <1-5>,
  "clarity": <1-5>,
  "reasoning": <1-5>,
  "manual_label": "<Correct|Partial|Incorrect>",
  "notes": "<one sentence explaining the main strength or weakness>"
}}"""


# Track which repos have been analyzed this session
_analyzed_repos = set()


def ensure_graph_analyzed(repo_url: str):
    """Trigger graph analysis once per repo before questions."""
    try:
        print(f"\n  [Graph] Analyzing {repo_url} — this may take 1-2 min...")
        resp = http_requests.post(
            f"{REPOWISE_BASE_URL}/api/graph/analyze",
            params={"repository_url": f"https://github.com/{repo_url}"},
            timeout=300
        )
        if resp.status_code == 200:
            print(f"  [Graph] Done ✓")
        else:
            print(f"  [Graph] Warning: {resp.status_code}")
    except Exception as e:
        print(f"  [Graph] Warning: {e}")


def send_question(question: str, repo_url: str) -> dict:
    """Send question to RepoWise chat API and return response + latency."""

    # Ensure graph is analyzed once per repo
    if repo_url not in _analyzed_repos:
        # ensure_graph_analyzed(repo_url)
        _analyzed_repos.add(repo_url)

    start = time.time()
    try:
        resp = http_requests.post(
            f"{REPOWISE_BASE_URL}/api/chat/send",
            json={
                "message": question,
                "repository_url": f"https://github.com/{repo_url}",
                "use_rag": True,
                "use_graph": True,
                "use_llm": True,
                "auto_index": True,
                "stream": False
            },
            timeout=REQUEST_TIMEOUT
        )
        elapsed = round(time.time() - start, 2)

        if resp.status_code == 200:
            data = resp.json()

            # API returns "message" field (ChatResponse model)
            response_text = (
                data.get("message") or
                data.get("response") or
                data.get("content") or
                str(data)
            )

            # Routing: API returns rag_used (bool) and graph_used (bool)
            rag_used   = data.get("rag_used", False)
            graph_used = data.get("graph_used", False)

            if rag_used and graph_used:
                routing_used = "HYBRID"
            elif graph_used:
                routing_used = "GRAPH"
            elif rag_used:
                routing_used = "VECTOR"
            else:
                routing_used = "DIRECT"  # LLM only, no retrieval

            return {
                "success": True,
                "response": response_text,
                "routing": routing_used,
                "latency": elapsed,
                "status_code": resp.status_code,
                "confidence": data.get("confidence", 0),
            }
        else:
            return {
                "success": False,
                "response": f"HTTP {resp.status_code}: {resp.text[:300]}",
                "routing": "ERROR",
                "latency": elapsed,
                "status_code": resp.status_code
            }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "success": False,
            "response": f"ERROR: {str(e)}",
            "routing": "ERROR",
            "latency": elapsed,
            "status_code": 0
        }


def judge_response(question: str, ground_truth: str, criteria: str, response: str) -> dict:
    """Use LLM-as-judge to score the response. Uses majority voting (5 runs) to reduce variance."""
    if not OPENAI_API_KEY:
        return {
            "correctness": 0, "completeness": 0, "relevance": 0,
            "clarity": 0, "reasoning": 0,
            "manual_label": "NOT_SCORED",
            "notes": "No OpenAI API key — manual scoring required"
        }

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    prompt = JUDGE_PROMPT.format(
        question=question,
        ground_truth=ground_truth,
        criteria=criteria,
        response=response[:2000]
    )

    # Slightly different framings per run to bypass OpenAI prompt caching
    # (identical prompt + temperature=0 → cache hit → same result every time)
    FRAMINGS = [
        "Evaluate the following response carefully:",
        "Please assess the quality of this response:",
        "Review and score this response objectively:",
        "Analyze this response and provide your evaluation:",
        "Critically examine and score this response:",
    ]

    def single_judge(framing: str) -> dict:
        varied_prompt = framing + "\n\n" + prompt
        try:
            completion = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": varied_prompt}
                ],
                temperature=0,
                max_tokens=300
            )
            raw = completion.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception as e:
            return {
                "correctness": 0, "completeness": 0, "relevance": 0,
                "clarity": 0, "reasoning": 0,
                "manual_label": "JUDGE_ERROR",
                "notes": f"Judge error: {str(e)}"
            }

    # Majority voting: 5 runs with different framings
    results = [single_judge(f) for f in FRAMINGS]

    # Filter out errors
    valid = [r for r in results if r.get("manual_label") not in ("JUDGE_ERROR", "NOT_SCORED")]
    if not valid:
        return results[0]

    # Majority vote on manual_label
    labels = [r.get("manual_label", "Incorrect") for r in valid]
    majority_label = max(set(labels), key=labels.count)

    # Average numeric scores from valid results
    numeric_keys = ["correctness", "completeness", "relevance", "clarity", "reasoning"]
    avg = {}
    for k in numeric_keys:
        vals = [r.get(k, 0) for r in valid]
        avg[k] = round(sum(vals) / len(vals), 2)

    # Notes from majority result
    majority_result = next((r for r in valid if r.get("manual_label") == majority_label), valid[0])
    avg["manual_label"] = majority_label
    avg["notes"] = majority_result.get("notes", "") + f" [majority {labels.count(majority_label)}/{len(valid)}]"
    return avg


def routing_correct(expected: str, actual: str) -> str:
    """Check if routing matches expected.

    HYBRID is a superset of GRAPH and VECTOR — if system used both,
    it satisfies either GRAPH or VECTOR expectation.
    """
    actual_upper = actual.upper()
    expected_upper = expected.upper()

    if actual_upper == "ERROR":
        return "No"

    if expected_upper == "HYBRID":
        # Hybrid requires both mechanisms
        return "Yes" if "HYBRID" in actual_upper else "No"
    elif expected_upper == "GRAPH":
        # GRAPH or HYBRID both satisfy GRAPH expectation
        return "Yes" if "GRAPH" in actual_upper or "HYBRID" in actual_upper else "No"
    elif expected_upper == "VECTOR":
        # VECTOR or HYBRID both satisfy VECTOR expectation
        return "Yes" if "VECTOR" in actual_upper or "HYBRID" in actual_upper else "No"
    return "Unknown"


def write_results_to_excel(results: list, output_path: str, template_path: str):
    """Write evaluation results to Excel."""
    import shutil
    shutil.copy(template_path, output_path)

    wb = load_workbook(output_path)
    ws = wb["Results"]

    # Color fills for labels
    correct_fill   = PatternFill("solid", start_color="E2EFDA")
    partial_fill   = PatternFill("solid", start_color="FFEB9C")
    incorrect_fill = PatternFill("solid", start_color="FFC7CE")

    for i, r in enumerate(results, 2):
        ws.cell(row=i, column=6,  value=r.get("actual_routing", ""))
        ws.cell(row=i, column=7,  value=r.get("routing_correct", ""))
        ws.cell(row=i, column=8,  value=r.get("response", "")[:500])  # Truncate for Excel
        ws.cell(row=i, column=9,  value=r.get("latency", ""))
        ws.cell(row=i, column=10, value=r.get("correctness", ""))
        ws.cell(row=i, column=11, value=r.get("completeness", ""))
        ws.cell(row=i, column=12, value=r.get("relevance", ""))
        ws.cell(row=i, column=13, value=r.get("clarity", ""))
        ws.cell(row=i, column=14, value=r.get("reasoning", ""))
        ws.cell(row=i, column=16, value=r.get("manual_label", ""))
        ws.cell(row=i, column=17, value=r.get("notes", ""))

        # Color the manual label cell
        label = r.get("manual_label", "")
        label_cell = ws.cell(row=i, column=16)
        if label == "Correct":
            label_cell.fill = correct_fill
        elif label == "Partial":
            label_cell.fill = partial_fill
        elif label == "Incorrect":
            label_cell.fill = incorrect_fill

        # Color routing correct cell
        rc_cell = ws.cell(row=i, column=7)
        if r.get("routing_correct") == "Yes":
            rc_cell.fill = correct_fill
        elif r.get("routing_correct") == "No":
            rc_cell.fill = incorrect_fill

    wb.save(output_path)
    print(f"\nResults saved to: {output_path}")


def print_summary(results: list):
    """Print a summary table to console."""
    total = len(results)
    if total == 0:
        return

    answered = [r for r in results if r.get("success")]
    errors   = [r for r in results if not r.get("success")]

    # Accuracy
    correct  = sum(1 for r in results if r.get("manual_label") == "Correct")
    partial  = sum(1 for r in results if r.get("manual_label") == "Partial")
    incorrect= sum(1 for r in results if r.get("manual_label") == "Incorrect")

    # Routing
    routing_yes = sum(1 for r in results if r.get("routing_correct") == "Yes")
    routing_total = sum(1 for r in results if r.get("routing_correct") in ["Yes", "No"])

    # Latency
    latencies = [r["latency"] for r in results if r.get("latency") and r["latency"] > 0]

    print("\n" + "="*60)
    print("REPOWISE EVALUATION SUMMARY")
    print("="*60)
    print(f"Total questions:     {total}")
    print(f"Successfully answered: {len(answered)} / {total}")
    print(f"Errors:              {len(errors)}")
    print()
    print("ANSWER QUALITY:")
    print(f"  Correct:   {correct:3d} ({correct/total*100:.1f}%)")
    print(f"  Partial:   {partial:3d} ({partial/total*100:.1f}%)")
    print(f"  Incorrect: {incorrect:3d} ({incorrect/total*100:.1f}%)")
    print()

    if routing_total > 0:
        print("ROUTING ACCURACY:")
        print(f"  Correct routing: {routing_yes}/{routing_total} ({routing_yes/routing_total*100:.1f}%)")

    if latencies:
        print()
        print("RESPONSE LATENCY:")
        print(f"  Average: {statistics.mean(latencies):.2f}s")
        print(f"  Median:  {statistics.median(latencies):.2f}s")
        print(f"  p95:     {sorted(latencies)[int(len(latencies)*0.95)]:.2f}s")
        print(f"  Min:     {min(latencies):.2f}s")
        print(f"  Max:     {max(latencies):.2f}s")

    # Per-category breakdown
    print()
    print("BY CATEGORY:")
    cats = set(r.get("category", "") for r in results)
    for cat in sorted(cats):
        cat_results = [r for r in results if r.get("category") == cat]
        cat_correct = sum(1 for r in cat_results if r.get("manual_label") == "Correct")
        print(f"  {cat:12s}: {cat_correct}/{len(cat_results)} correct")

    print("="*60)


def run_evaluation(args):
    """Main evaluation loop."""
    # Load dataset
    with open(args.dataset, 'r') as f:
        data = json.load(f)

    questions = data["questions"]

    # Filter by repo if specified
    if args.repo:
        questions = [q for q in questions if q["repo"] == args.repo]
        print(f"Filtered to repo '{args.repo}': {len(questions)} questions")

    # Limit questions if specified
    if args.questions and args.questions < len(questions):
        questions = questions[:args.questions]
        print(f"Limited to first {args.questions} questions")

    print(f"\nStarting evaluation: {len(questions)} questions")
    print(f"RepoWise URL: {REPOWISE_BASE_URL}")
    print(f"Judge model:  {JUDGE_MODEL}")
    print(f"Dry run:      {args.dry_run}")

    if args.dry_run:
        print("\n[DRY RUN] Simulating responses without calling RepoWise...")

    results = []

    for q in tqdm(questions, desc="Evaluating"):
        result = {
            "id": q["id"],
            "repo": q["repo"],
            "category": q["category"],
            "question": q["question"],
            "expected_routing": q["expected_routing"],
        }

        if args.dry_run:
            # Simulate a response for testing the script itself
            result.update({
                "success": True,
                "response": f"[DRY RUN] Simulated response for: {q['question'][:50]}...",
                "actual_routing": q["expected_routing"],
                "routing_correct": "Yes",
                "latency": round(1.5 + (hash(q["id"]) % 30) / 10, 2),
                "correctness": 3, "completeness": 3, "relevance": 4,
                "clarity": 4, "reasoning": 3,
                "manual_label": "Partial",
                "notes": "Dry run — not a real evaluation"
            })
        else:
            # 1. Send to RepoWise
            api_result = send_question(q["question"], q["repo"])
            result.update(api_result)

            # 2. Check routing
            result["routing_correct"] = routing_correct(
                q["expected_routing"],
                api_result.get("routing", "UNKNOWN")
            )
            result["actual_routing"] = api_result.get("routing", "UNKNOWN")

            # 3. Judge the response (only if API call succeeded)
            if api_result["success"]:
                scores = judge_response(
                    question=q["question"],
                    ground_truth=q["ground_truth_hint"],
                    criteria=q["evaluation_criteria"],
                    response=api_result["response"]
                )
                result.update(scores)
            else:
                result.update({
                    "correctness": 0, "completeness": 0, "relevance": 0,
                    "clarity": 0, "reasoning": 0,
                    "manual_label": "Incorrect",
                    "notes": "API call failed"
                })

            time.sleep(DELAY_BETWEEN_Q)

        results.append(result)

        # Save intermediate results every 10 questions
        if len(results) % 10 == 0:
            interim_path = args.output.replace(".xlsx", f"_interim_{len(results)}.xlsx")
            try:
                write_results_to_excel(results, interim_path, args.template)
                tqdm.write(f"  [Checkpoint] Saved {len(results)} results to {interim_path}")
            except Exception as e:
                tqdm.write(f"  [Checkpoint] Failed to save: {e}")

    # Final save
    write_results_to_excel(results, args.output, args.template)

    # Also save raw JSON
    json_output = args.output.replace(".xlsx", ".json")
    with open(json_output, 'w') as f:
        json.dump({"metadata": data["metadata"], "results": results}, f, indent=2)
    print(f"Raw results saved to: {json_output}")

    # Print summary
    print_summary(results)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RepoWise Evaluation Script")
    parser.add_argument("--dataset",   default=DATASET_JSON,  help="Path to dataset JSON")
    parser.add_argument("--template",  default=TEMPLATE_XLSX, help="Path to Excel template")
    parser.add_argument("--output",    default=OUTPUT_XLSX,   help="Output Excel path")
    parser.add_argument("--repo",      default=None,          help="Filter by repo (e.g. psf/requests)")
    parser.add_argument("--questions", default=None, type=int,help="Limit number of questions")
    parser.add_argument("--dry-run",   action="store_true",   help="Test script without calling APIs")
    args = parser.parse_args()

    run_evaluation(args)