"""
RepoWise Intent Router
======================
Embedding-based intent classification using sentence-transformers.
No LLM dependency — runs locally, sub-millisecond after warmup.

Intents:
    - analytics   : file history, contributor stats, who modified
    - commit      : recent commits, commit diff, what changed
    - structural  : imports, class hierarchy, functions in file
    - semantic    : how does X work, explain code, architecture
    - metadata    : file count, language stats, repo size
    - hybrid      : questions combining code meaning + history
"""

import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Training examples — add more to improve accuracy
# ---------------------------------------------------------------------------

INTENT_EXAMPLES = {
    "analytics": [
        "Who last modified sessions.py?",
        "Which contributor has made the most changes to models.py?",
        "Who are the top contributors to this repository?",
        "What files have been changed the most?",
        "Who last changed exceptions.py?",
        "Which developer modified utils.py the most?",
        "Who is the primary maintainer of adapters.py?",
        "Show me the commit history for sessions.py",
        "Which files were changed in the last 20 commits?",
        "What percentage of commits did davidism make?",
        "How many lines were added in recent commits?",
        "Who has contributed the most to this project?",
        "Show me file history for models.py",
        "Who made changes to the helpers file?",
        "What is the commit history for exceptions.py?",
        "Which contributor owns the most files?",
    ],
    "commit": [
        "Show me the most recent commits",
        "What changed in the last commit?",
        "Show commit diff between two versions",
        "List the latest commits in the repository",
        "What was committed yesterday?",
        "Show me recent commit messages",
        "What are the last 5 commits?",
        "Show me what changed in commit abc123",
        "List commits from last week",
        "What did the latest commit change?",
    ],
    "structural": [
        "What functions are defined in helpers.py?",
        "Which files import from flask/app.py?",
        "What is the class hierarchy in Flask?",
        "What does sessions.py depend on?",
        "Which modules does requests import?",
        "What classes are defined in models.py?",
        "What files depend on sessions.py?",
        "Show me the imports in adapters.py?",
        "What external libraries does requests use?",
        "How is the requests library organized?",
        "What is the inheritance structure of Flask?",
        "Which files import from utils.py?",
        "What functions are in ctx.py?",
        "What exceptions are defined in exceptions.py?",
        "Show the module structure of the Flask project",
        "What does app.py export?",
        "What files import from flask/app.py?",
        "Which files depend on sessions.py?",
        "What imports from utils.py?",
        # X defined in which file patterns
        "What exceptions are defined in the requests library and in which file?",
        "Where are the exceptions defined in requests?",
        "In which file are the exceptions declared?",
        "What errors are defined and in which file?",
        "Which file contains the exception classes?",
        "What classes are defined and where are they located?",
        "In which file are the models defined?",
        "Where are handlers declared in Flask?",
        "What is defined in ctx.py and what does it import?",
        "What does auth.py define and what does it depend on?",
    ],
    "semantic": [
        "How does the Session class work?",
        "Explain the request context in Flask",
        "What is the difference between before_request and before_first_request?",
        "How does Flask handle request routing?",
        "What is Flask's application context?",
        "How does the requests library handle authentication?",
        "Explain how sessions work in the requests library",
        "How does Flask's url_for function work?",
        "What is the purpose of the adapters module?",
        "How does retry logic work in requests?",
        "Explain Flask's blueprint system",
        "How does cookie handling work?",
        "What is the difference between request context and application context?",
        "How does Flask handle errors and exceptions?",
        "Explain how middleware works in Flask",
        "How does the requests library manage connection pooling?",
        "What is the role of the PreparedRequest class?",
    ],
    "metadata": [
    "How many files are in the Flask repository?",
    "What programming languages are used in this project?",
    "How many Python files does requests have?",
    "What is the size of this repository?",
    "How many stars does this repo have?",
    "What is the total number of commits?",
    "How many contributors does Flask have?",
    "What is the license of this project?",
    "When was this repository created?",
    "How many open issues are there?",
    "What version of Python does this support?",
    "How large is the codebase?",
    # ── YENİ EKLE ──
    "How many classes are defined in the requests library?",
    "How many functions are in the Flask codebase?",
    "How many classes does Flask have in total?",
    "What is the total number of classes defined?",
    "How many total functions are defined in requests?",
    "How many commits does the repository have?",
    "How many total commits are in Flask?",
],
    "hybrid": [
        "Who recently modified the authentication logic in requests?",
        "What changes were made to the routing system in Flask last month?",
        "Which developer added the retry functionality and how does it work?",
        "Who wrote the session management code and what does it do?",
        "What recent commits affected the error handling in requests?",
        "Who last changed the blueprint system and why?",
        "Which contributor modified the connection pooling and what changed?",
        "What commits introduced the current middleware architecture?",
        "Who implemented url_for and how does it work internally?",
    ],
}

# ---------------------------------------------------------------------------
# Router class
# ---------------------------------------------------------------------------

class IntentRouter:
    """
    Lightweight semantic intent classifier.
    Uses sentence-transformers to embed queries and compare
    against prototype vectors for each intent category.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.prototype_vectors: dict[str, np.ndarray] = {}
        self._ready = False

    def load(self):
        """Load model and compute prototype vectors. Call once at startup."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"[IntentRouter] Loading model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)

            logger.info("[IntentRouter] Computing prototype vectors...")
            for intent, examples in INTENT_EXAMPLES.items():
                embeddings = self.model.encode(examples, show_progress_bar=False)
                self.prototype_vectors[intent] = embeddings.mean(axis=0)
                logger.info(f"  ✅ {intent}: {len(examples)} examples")

            self._ready = True
            logger.info("[IntentRouter] ✅ Ready")
        except Exception as e:
            logger.error(f"[IntentRouter] Failed to load: {e}")
            self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    def classify(self, query: str, threshold: float = 0.25) -> tuple[str, float]:
        """
        Classify a query into an intent.

        Args:
            query: User message
            threshold: Minimum cosine similarity to accept classification.
                       Below this → falls back to 'semantic' (RAG handles it).

        Returns:
            (intent_name, confidence_score)
        """
        if not self._ready:
            return "semantic", 0.0

        query_vec = self.model.encode([query], show_progress_bar=False)[0]
        query_norm = np.linalg.norm(query_vec)

        scores = {}
        for intent, proto_vec in self.prototype_vectors.items():
            cosine = np.dot(query_vec, proto_vec) / (query_norm * np.linalg.norm(proto_vec))
            scores[intent] = float(cosine)

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # Log scores for debugging
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        logger.debug(f"[IntentRouter] Query: '{query[:60]}'")
        logger.debug(f"[IntentRouter] Scores: {sorted_scores}")

        if best_score < threshold:
            logger.info(f"[IntentRouter] Low confidence ({best_score:.3f}), falling back to 'semantic'")
            return "semantic", best_score

        logger.info(f"[IntentRouter] → {best_intent} (score={best_score:.3f})")
        return best_intent, best_score

    def classify_detailed(self, query: str) -> dict:
        """Returns all scores for debugging/analysis."""
        if not self._ready:
            return {"error": "Router not ready"}

        query_vec = self.model.encode([query], show_progress_bar=False)[0]
        query_norm = np.linalg.norm(query_vec)

        scores = {}
        for intent, proto_vec in self.prototype_vectors.items():
            cosine = np.dot(query_vec, proto_vec) / (query_norm * np.linalg.norm(proto_vec))
            scores[intent] = round(float(cosine), 4)

        best = max(scores, key=scores.get)
        return {
            "query": query,
            "prediction": best,
            "confidence": scores[best],
            "all_scores": dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)),
        }


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

_router: Optional[IntentRouter] = None


def get_router() -> IntentRouter:
    """Get or create the singleton router instance."""
    global _router
    if _router is None:
        _router = IntentRouter()
        _router.load()
    return _router


def classify(query: str, threshold: float = 0.25) -> tuple[str, float]:
    """Convenience function — classify a query using the singleton router."""
    return get_router().classify(query, threshold)


def classify_detailed(query: str) -> dict:
    """Convenience function — get detailed scores."""
    return get_router().classify_detailed(query)


# ---------------------------------------------------------------------------
# CLI test — python intent_router.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    router = IntentRouter()
    router.load()

    test_queries = [
        "Who last modified sessions.py?",
        "What functions are defined in helpers.py?",
        "How does Flask handle request routing?",
        "How many files are in the repository?",
        "Show me recent commits",
        "Which contributor modified the connection pooling and what changed?",
        "What is the difference between before_request and before_first_request?",
        "Which files import from flask/app.py?",
        "Who has made the most changes to models.py?",
        "What external libraries does requests use?",
    ]

    print("\n" + "="*65)
    print("REPOWISE INTENT ROUTER — TEST")
    print("="*65)

    for q in test_queries:
        result = router.classify_detailed(q)
        print(f"\nQ: {q}")
        print(f"→  {result['prediction'].upper()} (confidence: {result['confidence']:.4f})")
        print(f"   All: {result['all_scores']}")

    if len(sys.argv) > 1:
        custom = " ".join(sys.argv[1:])
        print(f"\n--- Custom query ---")
        result = router.classify_detailed(custom)
        print(f"Q: {custom}")
        print(f"→  {result['prediction'].upper()} (confidence: {result['confidence']:.4f})")
        print(f"   All: {result['all_scores']}")