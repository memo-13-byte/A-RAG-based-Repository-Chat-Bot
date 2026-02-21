"""
Service Layer Exports - FIXED & ENHANCED
Centralized import location for all services with proper error handling
"""

# ============================================================================
# CORE SERVICES (Always Available)
# ============================================================================

from .chromadb_service import chroma_service
from .embedding_service import embeddings_service
from .github_service import github_service
from .gitlab_service import gitlab_service
from .git_factory import get_git_service
from .neo4j_service import neo4j_service
from .rag_service import rag_service
from .llm_service import llm_service
from .code_parser_service import code_parser_service
from .graph_populator_service import graph_populator_service
from .document_processor import document_processor

# ============================================================================
# ENHANCED SERVICES (Optional - Graceful Degradation)
# ============================================================================

# 1. Enhanced Neo4j Queries (NEW!)
try:
    from .neo4j_service_enhanced import EnhancedNeo4jQueries, get_enhanced_queries

    # Initialize enhanced queries instance
    enhanced_neo4j = get_enhanced_queries(neo4j_service)

    print("✅ Enhanced Neo4j queries loaded successfully")
    ENHANCED_QUERIES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Enhanced Neo4j queries not available: {e}")
    EnhancedNeo4jQueries = None
    get_enhanced_queries = None
    enhanced_neo4j = None
    ENHANCED_QUERIES_AVAILABLE = False

# 2. Hybrid RAG Extension
try:
    from .hybrid_rag_extension import (
        create_hybrid_rag_extension,
        HybridRAGExtension
    )
    print("✅ Hybrid RAG extension loaded")
except ImportError as e:
    print(f"⚠️ Hybrid RAG extension not available: {e}")
    create_hybrid_rag_extension = None
    HybridRAGExtension = None

# 3. Commit Indexing Services
try:
    from .commit_indexing_service import (
        create_commit_indexing_service,
        CommitIndexingService
    )
    print("✅ Commit indexing service loaded")
except ImportError as e:
    print(f"⚠️ Commit indexing service not available: {e}")
    create_commit_indexing_service = None
    CommitIndexingService = None

# 4. Enhanced Commit Indexing
try:
    from .commit_indexing_service_enhanced import (
        create_enhanced_commit_indexing_service,
        EnhancedCommitIndexingService
    )

    # Create enhanced instance if available
    if ENHANCED_QUERIES_AVAILABLE and enhanced_neo4j:
        commit_indexing_service = create_enhanced_commit_indexing_service(
            enhanced_neo4j,  # Use enhanced queries instance
            github_service
        )
        print("✅ Enhanced commit indexing service initialized")
    else:
        # Fallback to basic service
        if create_commit_indexing_service:
            commit_indexing_service = create_commit_indexing_service(
                neo4j_service,
                github_service
            )
            print("⚠️ Using basic commit indexing service (enhanced not available)")
        else:
            commit_indexing_service = None
            print("⚠️ No commit indexing service available")

except ImportError as e:
    print(f"⚠️ Enhanced commit indexing not available: {e}")
    create_enhanced_commit_indexing_service = None
    EnhancedCommitIndexingService = None

    # Try basic version
    try:
        if create_commit_indexing_service:
            commit_indexing_service = create_commit_indexing_service(
                neo4j_service,
                github_service
            )
            print("✅ Basic commit indexing service initialized")
        else:
            commit_indexing_service = None
    except Exception as e:
        print(f"❌ Failed to initialize commit indexing: {e}")
        commit_indexing_service = None

# 5. LLM Enhanced Service (if exists)
try:
    from .llm_service_enhanced import llm_service_enhanced
    print("✅ Enhanced LLM service loaded")
except ImportError:
    llm_service_enhanced = None

# 6. Memory Service (if exists)
try:
    from .memory_service import memory_service
    print("✅ Memory service loaded")
except ImportError:
    memory_service = None

# 7. Cache Service (if exists)
try:
    from .cache_service import cache_service
    print("✅ Cache service loaded")
except ImportError:
    cache_service = None

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # ===== CORE SERVICES (Always Available) =====
    "chroma_service",
    "embeddings_service",
    "github_service",
    "gitlab_service",
    "get_git_service",
    "neo4j_service",
    "rag_service",
    "llm_service",
    "code_parser_service",
    "graph_populator_service",
    "document_processor",

    # ===== ENHANCED SERVICES (May be None) =====
    # Neo4j Enhanced
    "EnhancedNeo4jQueries",
    "get_enhanced_queries",
    "enhanced_neo4j",
    "ENHANCED_QUERIES_AVAILABLE",

    # Hybrid RAG
    "create_hybrid_rag_extension",
    "HybridRAGExtension",

    # Commit Indexing
    "create_commit_indexing_service",
    "CommitIndexingService",
    "create_enhanced_commit_indexing_service",
    "EnhancedCommitIndexingService",
    "commit_indexing_service",

    # Optional Services
    "llm_service_enhanced",
    "memory_service",
    "cache_service",
]

# ============================================================================
# SERVICE STATUS REPORT
# ============================================================================

def get_service_status():
    """Get status of all services for debugging"""
    return {
        "core_services": {
            "github": github_service is not None,
            "neo4j": neo4j_service is not None,
            "rag": rag_service is not None,
            "llm": llm_service is not None,
            "chroma": chroma_service is not None,
        },
        "enhanced_services": {
            "enhanced_neo4j": enhanced_neo4j is not None,
            "commit_indexing": commit_indexing_service is not None,
            "llm_enhanced": llm_service_enhanced is not None,
            "memory": memory_service is not None,
            "cache": cache_service is not None,
        },
        "capabilities": {
            "temporal_queries": ENHANCED_QUERIES_AVAILABLE,
            "hybrid_rag": HybridRAGExtension is not None,
            "commit_tracking": commit_indexing_service is not None,
        }
    }

# Print status on import (for debugging)
if __name__ != "__main__":
    print("\n" + "="*60)
    print("SERVICE LAYER INITIALIZATION COMPLETE")
    print("="*60)
    status = get_service_status()

    print("\n✅ Core Services:")
    for name, available in status["core_services"].items():
        symbol = "✅" if available else "❌"
        print(f"  {symbol} {name}")

    print("\n🆕 Enhanced Services:")
    for name, available in status["enhanced_services"].items():
        symbol = "✅" if available else "⚠️"
        print(f"  {symbol} {name}")

    print("\n🎯 Capabilities:")
    for name, available in status["capabilities"].items():
        symbol = "✅" if available else "⚠️"
        print(f"  {symbol} {name}")

    print("="*60 + "\n")