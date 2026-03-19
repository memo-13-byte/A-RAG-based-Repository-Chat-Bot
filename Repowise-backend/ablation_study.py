"""
RepoWise Ablation Study Script
Gerçek ablation: Vector-only vs Graph-only vs Hybrid

Kullanım:
  .venv\Scripts\python.exe ablation_study.py

Çıktı: ablation_results.json + ablation_results.xlsx
"""
import requests
import json
import time
import os
from collections import defaultdict
from dotenv import load_dotenv
import openai

load_dotenv()

BASE_URL    = "http://localhost:8000"
OPENAI_KEY  = os.getenv("OPENAI_API_KEY")
JUDGE_MODEL = "gpt-4o"
DELAY       = 2.0   # saniye, rate limit için

# ── 20 temsili soru ──────────────────────────────────────────────────────────
ABLATION_QS = [
    # METADATA (4) — Neo4j aggregate sorgular
    {"id":"META-001","category":"METADATA","repo":"https://github.com/psf/requests",
     "question":"How many files are in the requests repository?",
     "hint":"Should provide a specific file count (total files in the repository)",
     "criteria":"Must provide a specific number of files"},
    {"id":"META-002","category":"METADATA","repo":"https://github.com/psf/requests",
     "question":"Who are the top 5 contributors to the requests library?",
     "hint":"Names of top contributors ranked by commit count",
     "criteria":"Must name at least 3 contributors with commit counts"},
    {"id":"META-003","category":"METADATA","repo":"https://github.com/psf/requests",
     "question":"What programming languages are used in the requests repository?",
     "hint":"Python is primary; may also include YAML, RST, Makefile",
     "criteria":"Must mention Python; bonus for other languages"},
    {"id":"META-004","category":"METADATA","repo":"https://github.com/psf/requests",
     "question":"How many total commits does the requests repository have?",
     "hint":"Should provide a specific commit count number",
     "criteria":"Must provide a specific number"},

    # SEMANTIC (4) — ChromaDB vector sorguları
    {"id":"SEM-001","category":"SEMANTIC","repo":"https://github.com/psf/requests",
     "question":"How does the Session class handle cookies?",
     "hint":"Session persists cookies across requests using RequestsCookieJar; cookies merged per-request",
     "criteria":"Must mention cookie persistence and RequestsCookieJar or cookie merging"},
    {"id":"SEM-002","category":"SEMANTIC","repo":"https://github.com/psf/requests",
     "question":"What does the PreparedRequest class do in the requests library?",
     "hint":"PreparedRequest represents a fully mutable PreparedRequest with encoded body and headers",
     "criteria":"Must explain PreparedRequest's role in preparing/encoding HTTP requests"},
    {"id":"SEM-003","category":"SEMANTIC","repo":"https://github.com/psf/requests",
     "question":"How does retry logic work in the requests library?",
     "hint":"HTTPAdapter uses urllib3 Retry object; max_retries parameter; backoff",
     "criteria":"Must mention HTTPAdapter, Retry or urllib3, and retry configuration"},
    {"id":"SEM-004","category":"SEMANTIC","repo":"https://github.com/psf/requests",
     "question":"Explain how authentication works in the requests library.",
     "hint":"AuthBase base class; HTTPBasicAuth, HTTPDigestAuth; auth= parameter on requests",
     "criteria":"Must mention AuthBase or HTTPBasicAuth and how auth is applied to requests"},

    # STRUCTURAL (4) — Neo4j graph + entity extraction
    {"id":"STR-001","category":"STRUCTURAL","repo":"https://github.com/psf/requests",
     "question":"What files depend on sessions.py in the requests library?",
     "hint":"Files importing sessions: api.py, adapters.py, __init__.py",
     "criteria":"Must list at least 2 files that import from sessions.py"},
    {"id":"STR-002","category":"STRUCTURAL","repo":"https://github.com/psf/requests",
     "question":"What classes does models.py define in the requests library?",
     "hint":"PreparedRequest, Request, Response, RequestEncodingMixin, RequestHooksMixin",
     "criteria":"Must name at least 3 classes defined in models.py"},
    {"id":"STR-003","category":"STRUCTURAL","repo":"https://github.com/psf/requests",
     "question":"What external libraries does the requests library import?",
     "hint":"urllib3, chardet/charset_normalizer, certifi, idna are key dependencies",
     "criteria":"Must list at least 3 specific external libraries"},
    {"id":"STR-004","category":"STRUCTURAL","repo":"https://github.com/psf/requests",
     "question":"How is the requests library structured? Give me an overview of its modules.",
     "hint":"Key modules: api.py, sessions.py, models.py, adapters.py, auth.py, exceptions.py",
     "criteria":"Must describe at least 3 key modules and their roles"},

    # HISTORICAL (4) — Commit history, Neo4j graph
    {"id":"HIST-001","category":"HISTORICAL","repo":"https://github.com/psf/requests",
     "question":"Who last modified sessions.py in the requests library?",
     "hint":"Should name the most recent contributor to sessions.py with commit info",
     "criteria":"Must name a specific contributor and recent commit"},
    {"id":"HIST-002","category":"HISTORICAL","repo":"https://github.com/psf/requests",
     "question":"What changes were made to the requests library in its most recent commits?",
     "hint":"Recent commits include CI fixes, dependency updates, and bug fixes by Nate Prewitt",
     "criteria":"Must describe at least 2 recent changes with commit context"},
    {"id":"HIST-003","category":"HISTORICAL","repo":"https://github.com/psf/requests",
     "question":"Which contributor has made the most changes to models.py?",
     "hint":"Nate Prewitt has made the most modifications to models.py",
     "criteria":"Must name a specific contributor for models.py changes"},
    {"id":"HIST-004","category":"HISTORICAL","repo":"https://github.com/psf/requests",
     "question":"How has the requests library evolved over its recent commits?",
     "hint":"Recent focus on CI/CD improvements, dependency updates, and bug fixes",
     "criteria":"Must describe evolution trends from recent commit history"},

    # HYBRID (4) — Hem graph hem vector
    {"id":"HYB-001","category":"HYBRID","repo":"https://github.com/psf/requests",
     "question":"Who wrote the Session class and how does it work?",
     "hint":"Should combine: who authored sessions.py (graph) + how Session works (vector)",
     "criteria":"Must answer BOTH parts: author/contributor AND functional explanation"},
    {"id":"HYB-002","category":"HYBRID","repo":"https://github.com/psf/requests",
     "question":"Which files depend on models.py and what are the key classes in it?",
     "hint":"Dependencies (graph) + class explanations (vector)",
     "criteria":"Must list dependent files AND explain at least 2 classes"},
    {"id":"HYB-003","category":"HYBRID","repo":"https://github.com/pallets/flask",
     "question":"What recently changed in app.py and what does the Flask class do?",
     "hint":"Recent commits to app.py (graph) + Flask class explanation (vector)",
     "criteria":"Must include both recent change info AND functional description"},
    {"id":"HYB-004","category":"HYBRID","repo":"https://github.com/psf/requests",
     "question":"Give me a complete overview of adapters.py: its structure, what it does, and who contributes to it.",
     "hint":"Structure/classes (graph) + functionality (vector) + contributor history (graph)",
     "criteria":"Must cover all three aspects: structure, functionality, and contribution info"},
]

JUDGE_SYSTEM = """You are an expert evaluator for a software repository Q&A system.
Score the system response against the ground truth hint.
Respond ONLY with valid JSON, no markdown."""

JUDGE_PROMPT = """QUESTION: {question}
GROUND TRUTH HINT: {hint}
EVALUATION CRITERIA: {criteria}

Key principles:
- Hint is the MINIMUM bar; extra correct info is NOT penalized
- Correct = covers ALL key points without major errors
- Partial = covers SOME but not all key points
- Incorrect = completely misses or mostly wrong

SYSTEM RESPONSE:
{response}

Respond ONLY with JSON:
{{"manual_label":"<Correct|Partial|Incorrect>","notes":"<one sentence>"}}"""

FRAMINGS = [
    "Evaluate the following response carefully:",
    "Please assess the quality of this response:",
    "Review and score this response objectively:",
]

def judge(question, hint, criteria, response):
    """3-round majority voting judge"""
    if not OPENAI_KEY:
        return {"manual_label": "NOT_SCORED", "notes": "No API key"}
    client = openai.OpenAI(api_key=OPENAI_KEY)
    labels = []
    prompt = JUDGE_PROMPT.format(
        question=question, hint=hint, criteria=criteria,
        response=response[:2000]
    )
    for framing in FRAMINGS:
        try:
            r = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role":"system","content":JUDGE_SYSTEM},
                    {"role":"user","content":framing+"\n\n"+prompt}
                ],
                temperature=0, max_tokens=150
            )
            raw = r.choices[0].message.content.strip()
            raw = raw.replace("```json","").replace("```","").strip()
            result = json.loads(raw)
            labels.append(result.get("manual_label","?"))
        except Exception as e:
            print(f"    Judge error: {e}")
    if not labels:
        return {"manual_label":"JUDGE_ERROR","notes":"All judge calls failed"}
    majority = max(set(labels), key=labels.count)
    return {"manual_label":majority, "notes":f"majority {labels.count(majority)}/{len(labels)}"}

def ask(question, repo_url, mode):
    """Send question to RepoWise in specified mode"""
    params = {
        "hybrid":      {"use_rag": True,  "use_graph": True},
        "vector_only": {"use_rag": True,  "use_graph": False},
        "graph_only":  {"use_rag": False, "use_graph": True},
        "llm_only":    {"use_rag": False, "use_graph": False},
    }[mode]

    payload = {
        "message": question,
        "repository_url": repo_url,
        **params
    }
    try:
        r = requests.post(f"{BASE_URL}/api/chat/send", json=payload, timeout=60)
        return r.json().get("message","")
    except Exception as e:
        return f"ERROR: {e}"

def clear_cache():
    try:
        requests.delete(f"{BASE_URL}/api/chat/cache", timeout=5)
        print("Cache cleared")
    except:
        pass

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*60)
    print("REPOWISE ABLATION STUDY")
    print(f"Questions: {len(ABLATION_QS)}")
    print(f"Modes: vector_only, graph_only, hybrid")
    print(f"Judge: {JUDGE_MODEL} (3-round majority)")
    print("="*60)

    results = []
    modes = ["vector_only", "graph_only", "hybrid"]

    for i, q in enumerate(ABLATION_QS):
        print(f"\n[{i+1}/{len(ABLATION_QS)}] {q['id']} — {q['question'][:55]}")

        q_results = {"id": q["id"], "category": q["category"],
                     "question": q["question"]}

        for mode in modes:
            clear_cache()
            time.sleep(0.5)

            print(f"  [{mode}] ", end="", flush=True)
            response = ask(q["question"], q["repo"], mode)
            print(f"got {len(response)} chars", end="", flush=True)

            verdict = judge(q["question"], q["hint"], q["criteria"], response)
            label = verdict["manual_label"]
            print(f" → {label}")

            q_results[mode] = {
                "response": response[:500],
                "label": label,
                "notes": verdict["notes"]
            }
            time.sleep(DELAY)

        results.append(q_results)
        print(f"  vector={q_results['vector_only']['label']} | "
              f"graph={q_results['graph_only']['label']} | "
              f"hybrid={q_results['hybrid']['label']}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("ABLATION RESULTS SUMMARY")
    print("="*60)

    label_score = {"Correct":1, "Partial":0.5, "Incorrect":0, "NOT_SCORED":0}
    totals = {m:{"C":0,"P":0,"I":0} for m in modes}
    cat_totals = defaultdict(lambda: {m:{"C":0,"P":0,"I":0} for m in modes})

    for r in results:
        for m in modes:
            lbl = r[m]["label"]
            if lbl == "Correct":    totals[m]["C"] += 1
            elif lbl == "Partial":  totals[m]["P"] += 1
            elif lbl == "Incorrect":totals[m]["I"] += 1
            cat_totals[r["category"]][m][lbl[0] if lbl in ("Correct","Partial","Incorrect") else "I"] += 1

    print(f"\n{'Mode':15} {'Correct':>8} {'Partial':>8} {'Incorrect':>10} {'Accuracy':>10}")
    print("-"*55)
    for m in modes:
        n = len(ABLATION_QS)
        c,p,i = totals[m]["C"], totals[m]["P"], totals[m]["I"]
        acc = c/n*100
        print(f"{m:15} {c:>8} {p:>8} {i:>10}   {acc:>8.1f}%")

    print("\nPer-category accuracy:")
    print(f"{'Category':12}", end="")
    for m in modes:
        print(f" {m[:12]:>14}", end="")
    print()
    print("-"*60)

    cats_order = ["METADATA","SEMANTIC","STRUCTURAL","HISTORICAL","HYBRID"]
    n_per = 4
    for cat in cats_order:
        print(f"{cat:12}", end="")
        for m in modes:
            c = cat_totals[cat][m]["C"]
            print(f"  {c}/{n_per} ({c/n_per*100:.0f}%)", end="")
        print()

    # Save
    with open("ablation_results.json","w") as f:
        json.dump({"results":results,"totals":totals}, f, indent=2)

    # Excel
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ablation"
        ws.append(["ID","Category","Question","Vector-only","Graph-only","Hybrid",
                   "V-notes","G-notes","H-notes"])
        for r in results:
            ws.append([
                r["id"], r["category"], r["question"],
                r["vector_only"]["label"], r["graph_only"]["label"], r["hybrid"]["label"],
                r["vector_only"]["notes"], r["graph_only"]["notes"], r["hybrid"]["notes"],
            ])
        wb.save("ablation_results.xlsx")
        print("\nResults saved to ablation_results.json + ablation_results.xlsx")
    except ImportError:
        print("\nResults saved to ablation_results.json (openpyxl not installed for xlsx)")
