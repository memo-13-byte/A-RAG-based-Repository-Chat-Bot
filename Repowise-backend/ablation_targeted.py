"""
RepoWise Targeted Ablation Study
Direct pipeline testing: Graph-only vs Vector-only
Usage: .venv\Scripts\python.exe ablation_targeted.py
"""
import sys
import os
import json, time
from dotenv import load_dotenv
load_dotenv()
import openai

sys.path.insert(0, '.')
os.environ.setdefault('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', ''))



OPENAI_KEY  = os.getenv("OPENAI_API_KEY")
JUDGE_MODEL = "gpt-4o"

# ── Test Questions — her kategori için 3 soru, clean separation ──────────────
# Bu sorular pipeline'ların gerçek farkını gösterir

METADATA_QS = [
    {"q": "How many Python files are in the requests repository?",
     "hint": "Should provide a specific file count (e.g. 53 Python files)",
     "why": "Requires COUNT query — vector embeddings cannot count files"},
    {"q": "Who are the top 3 contributors to the requests library by commit count?",
     "hint": "Top contributors: Nate Prewitt, Kenneth Reitz with commit counts",
     "why": "Requires aggregate graph query — RAG cannot rank contributors"},
    {"q": "How many total commits does the requests repository have?",
     "hint": "Should provide a specific number (around 6000+ commits)",
     "why": "Requires COUNT — not embeddable"},
]

SEMANTIC_QS = [
    {"q": "How does the Session class persist cookies across requests?",
     "hint": "Session uses RequestsCookieJar; cookies are merged per-request from session and request-level cookies",
     "why": "Requires code reading — graph has no code content"},
    {"q": "How does retry logic work in the requests library?",
     "hint": "HTTPAdapter uses urllib3 Retry object; max_retries on mount; backoff_factor",
     "why": "Implementation detail — only in ChromaDB chunks"},
    {"q": "How does Flask handle circular imports using LocalProxy?",
     "hint": "Flask uses werkzeug.local.LocalProxy with ContextVar for current_app, request, session, g",
     "why": "Semantic implementation question — needs code chunks"},
]

# STRUCTURAL: Graph wins (Neo4j DEFINES/IMPORTS), Vector cannot answer precisely
STRUCTURAL_QS = [
    {"q": "What classes does models.py define in the requests library?",
     "hint": "PreparedRequest, Request, Response, RequestEncodingMixin, RequestHooksMixin",
     "repo": "psf/requests",
     "why": "Requires DEFINES graph traversal — vector search gives vague answers"},
    {"q": "What files import from sessions.py in the requests library?",
     "hint": "Files importing sessions: api.py, adapters.py, __init__.py",
     "repo": "psf/requests",
     "why": "Requires IMPORTS graph traversal — vector cannot enumerate importers"},
    {"q": "What is the class hierarchy in the Flask application object?",
     "hint": "Flask inherits from App which inherits from Scaffold; Blueprint also inherits from Scaffold",
     "repo": "pallets/flask",
     "why": "Requires INHERITS_FROM graph traversal — vector cannot traverse inheritance"},
]

# HISTORICAL: Graph wins (commit data in Neo4j), Vector cannot answer
HISTORICAL_QS = [
    {"q": "Who last modified sessions.py in the requests library and what did they change?",
     "hint": "Nate Prewitt made the most recent modification with a CI/build related commit",
     "repo": "psf/requests",
     "why": "Requires commit history graph — vector chunks have no commit metadata"},
    {"q": "What are the most recently modified files in the Flask repository?",
     "hint": "Recent commits modified app.py, ctx.py, uv.lock and related files",
     "repo": "pallets/flask",
     "why": "Requires commit graph ordering — vector has no temporal information"},
    {"q": "Which contributor has made the most commits to the Flask repository?",
     "hint": "davidism (@davidism) has made the most commits to the Flask repository",
     "repo": "pallets/flask",
     "why": "Requires aggregate commit count per author — not in vector embeddings"},
]

def judge_response(question, hint, response):
    """Simple judge"""
    if not OPENAI_KEY or OPENAI_KEY == 'x':
        return "NOT_SCORED"
    client = openai.OpenAI(api_key=OPENAI_KEY)
    prompt = f"""QUESTION: {question}
HINT: {hint}
RESPONSE: {response[:1500]}

Is the response Correct (covers hint), Partial (covers some), or Incorrect?
Reply ONLY with JSON: {{"label":"<Correct|Partial|Incorrect>","note":"<10 words>"}}"""
    labels = []
    for framing in ["Evaluate:", "Assess:", "Score:"]:
        try:
            r = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role":"user","content":framing+"\n"+prompt}],
                temperature=0, max_tokens=80
            )
            raw = r.choices[0].message.content.strip().replace("```json","").replace("```","")
            labels.append(json.loads(raw)["label"])
        except: pass
    return max(set(labels), key=labels.count) if labels else "ERROR"

def test_rag_only(question, repo="psf/requests"):
    """ChromaDB vector search without Neo4j graph context"""
    from app.services.rag_service import rag_service
    repo_name = "pallets/flask" if "flask" in question.lower() else repo
    result = rag_service.query(
        repo_name=repo_name,
        question=question,
        n_results=10,
        use_llm=True,
        use_graph=False,   # ← No Neo4j context
        intent="semantic"
    )
    return result.get("answer", "")

def test_graph_only(question, repo="psf/requests"):
    """Neo4j analytics without ChromaDB"""
    import asyncio
    from app.services.entity_extractor import get_extractor
    from app.services import query_planner, neo4j_service
    from app.services import enhanced_neo4j as enhanced
    from app.services.query_executor import QueryExecutor, format_result
    from app.services.intent_router import classify
    from app.services.git_factory import get_git_service

    full_repo = "pallets/flask" if "flask" in question.lower() else repo
    repo_url  = f"https://github.com/{full_repo}"

    async def _run():
        intent, _ = classify(question)
        entities = get_extractor().extract(question)
        strategy = query_planner.plan(intent, entities)
        executor = QueryExecutor(neo4j_service, enhanced, get_git_service)
        result = await executor.execute(strategy, entities, full_repo, repo_url)
        response, sources, conf = format_result(result, entities, intent)
        return response or "[GRAPH-ONLY: pipeline returned no answer for this query type]"
    result = asyncio.run(_run())
    return result

if __name__ == "__main__":
    print("="*60)
    print("TARGETED ABLATION: Direct pipeline testing")
    print("="*60)

    results = {"metadata": [], "semantic": [], "structural": [], "historical": []}

    # ── METADATA: Graph-only (Neo4j aggregate) vs Vector-only ────────────────
    print("\n[METADATA] — Graph-only should win, Vector-only should fail")
    print("-"*60)
    for tq in METADATA_QS:
        print(f"\nQ: {tq['q'][:70]}")
        print(f"Why: {tq['why']}")

        # Graph-only (Neo4j direct)
        try:
            g_resp = test_graph_only(tq['q'])
            g_label = judge_response(tq['q'], tq['hint'], g_resp)
            print(f"  Graph-only:  {g_label:10} | {g_resp[:80]}")
        except Exception as e:
            g_resp, g_label = f"ERROR: {e}", "ERROR"
            print(f"  Graph-only:  ERROR — {e}")

        time.sleep(1)

        # Vector-only (ChromaDB direct)
        try:
            v_resp = test_rag_only(tq['q'])
            v_label = judge_response(tq['q'], tq['hint'], v_resp)
            print(f"  Vector-only: {v_label:10} | {v_resp[:80]}")
        except Exception as e:
            v_resp, v_label = f"ERROR: {e}", "ERROR"
            print(f"  Vector-only: ERROR — {e}")

        results["metadata"].append({
            "q": tq['q'], "hint": tq['hint'],
            "graph": {"label": g_label, "resp": g_resp[:300]},
            "vector": {"label": v_label, "resp": v_resp[:300]},
        })
        time.sleep(2)

    # ── SEMANTIC: Vector-only should win, Graph-only should fail ─────────────
    print("\n\n[SEMANTIC] — Vector-only should win, Graph-only should fail")
    print("-"*60)
    for tq in SEMANTIC_QS:
        print(f"\nQ: {tq['q'][:70]}")
        print(f"Why: {tq['why']}")

        try:
            repo = "pallets/flask" if "flask" in tq['q'].lower() else "psf/requests"
            v_resp = test_rag_only(tq['q'], repo=repo)
            v_label = judge_response(tq['q'], tq['hint'], v_resp)
            print(f"  Vector-only: {v_label:10} | {v_resp[:80]}")
        except Exception as e:
            v_resp, v_label = f"ERROR: {e}", "ERROR"
            print(f"  Vector-only: ERROR — {e}")

        time.sleep(1)

        try:
            g_resp = test_graph_only(tq['q'], repo=repo)
            g_label = judge_response(tq['q'], tq['hint'], g_resp)
            print(f"  Graph-only:  {g_label:10} | {g_resp[:80]}")
        except Exception as e:
            g_resp, g_label = f"ERROR: {e}", "ERROR"
            print(f"  Graph-only:  ERROR — {e}")

        results["semantic"].append({
            "q": tq['q'], "hint": tq['hint'],
            "graph": {"label": g_label, "resp": g_resp[:300]},
            "vector": {"label": v_label, "resp": v_resp[:300]},
        })
        time.sleep(2)

    # ── STRUCTURAL: Graph-only should win, Vector-only should fail ──────────
    print("\n\n[STRUCTURAL] — Graph-only should win (DEFINES/IMPORTS graph)")
    print("-"*60)
    for tq in STRUCTURAL_QS:
        print(f"\nQ: {tq['q'][:70]}")
        print(f"Why: {tq['why']}")

        try:
            g_resp = test_graph_only(tq["q"], repo=tq["repo"])
            g_label = judge_response(tq["q"], tq["hint"], g_resp)
            print(f"  Graph-only:  {g_label:10} | {g_resp[:100]}")
        except Exception as e:
            g_resp, g_label = f"ERROR: {e}", "ERROR"
            print(f"  Graph-only:  ERROR — {e}")

        time.sleep(1)

        try:
            v_resp = test_rag_only(tq["q"], repo=tq["repo"])
            v_label = judge_response(tq["q"], tq["hint"], v_resp)
            print(f"  Vector-only: {v_label:10} | {v_resp[:100]}")
        except Exception as e:
            v_resp, v_label = f"ERROR: {e}", "ERROR"
            print(f"  Vector-only: ERROR — {e}")

        results["structural"].append({
            "q": tq["q"], "hint": tq["hint"],
            "graph": {"label": g_label, "resp": g_resp[:300]},
            "vector": {"label": v_label, "resp": v_resp[:300]},
        })
        time.sleep(2)

    # ── HISTORICAL: Graph-only should win, Vector-only should fail ───────────
    print("\n\n[HISTORICAL] — Graph-only should win (commit graph)")
    print("-"*60)
    for tq in HISTORICAL_QS:
        print(f"\nQ: {tq['q'][:70]}")
        print(f"Why: {tq['why']}")

        try:
            g_resp = test_graph_only(tq["q"], repo=tq["repo"])
            g_label = judge_response(tq["q"], tq["hint"], g_resp)
            print(f"  Graph-only:  {g_label:10} | {g_resp[:100]}")
        except Exception as e:
            g_resp, g_label = f"ERROR: {e}", "ERROR"
            print(f"  Graph-only:  ERROR — {e}")

        time.sleep(1)

        try:
            v_resp = test_rag_only(tq["q"], repo=tq["repo"])
            v_label = judge_response(tq["q"], tq["hint"], v_resp)
            print(f"  Vector-only: {v_label:10} | {v_resp[:100]}")
        except Exception as e:
            v_resp, v_label = f"ERROR: {e}", "ERROR"
            print(f"  Vector-only: ERROR — {e}")

        results["historical"].append({
            "q": tq["q"], "hint": tq["hint"],
            "graph": {"label": g_label, "resp": g_resp[:300]},
            "vector": {"label": v_label, "resp": v_resp[:300]},
        })
        time.sleep(2)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("FULL ABLATION SUMMARY (12 questions, 4 categories)")
    print("="*60)

    label_val = {"Correct": 1.0, "Partial": 0.5, "Incorrect": 0.0,
                 "ERROR": 0.0, "NOT_SCORED": 0.0}

    cat_order = ["metadata", "semantic", "structural", "historical"]
    cat_names = {"metadata":"METADATA", "semantic":"SEMANTIC",
                 "structural":"STRUCTURAL", "historical":"HISTORICAL"}
    cat_expected = {
        "metadata":   "Graph >> Vector",
        "semantic":   "Vector >> Graph",
        "structural": "Graph >> Vector",
        "historical": "Graph >> Vector",
    }

    print(f"\n{'Category':12} {'Graph-only':>14} {'Vector-only':>14}  Expected")
    print("-"*65)

    grand_g, grand_v = 0, 0
    for cat in cat_order:
        qs = results[cat]
        g_score = sum(label_val.get(r["graph"]["label"],0) for r in qs)
        v_score = sum(label_val.get(r["vector"]["label"],0) for r in qs)
        n = len(qs)
        g_pct = g_score/n*100
        v_pct = v_score/n*100
        winner = "✅ as expected" if (
            (cat in ["metadata","structural","historical"] and g_pct > v_pct) or
            (cat == "semantic" and v_pct > g_pct)
        ) else "⚠️  unexpected"
        print(f"{cat_names[cat]:12}  {g_score:.1f}/{n} ({g_pct:.0f}%)   "
              f"{v_score:.1f}/{n} ({v_pct:.0f}%)   {winner}")
        grand_g += g_score
        grand_v += v_score

    n_total = sum(len(results[c]) for c in cat_order)
    print("-"*65)
    print(f"{'TOTAL':12}  {grand_g:.1f}/{n_total} ({grand_g/n_total*100:.0f}%)   "
          f"{grand_v:.1f}/{n_total} ({grand_v/n_total*100:.0f}%)")

    print(f"\n→ Full Hybrid system (60-Q eval): 47/60 = 78.3%")
    print(f"→ Hybrid gain over Graph-only:  +{(47/60 - grand_g/n_total)*100:.0f}pp")
    print(f"→ Hybrid gain over Vector-only: +{(47/60 - grand_v/n_total)*100:.0f}pp")

    with open("ablation_targeted_results.json","w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved: ablation_targeted_results.json")