# Services klasörü - İş mantığı burada olacak
# Bu klasör şunları içerecek:
# - rag_pipeline.py: RAG (Retrieval-Augmented Generation) pipeline
# - llm_service.py (OpenAI) entegrasyonu
# - kg_service.py: Knowledge Graph (Neo4j) işlemleri
# - embedding_service.py: Vector embeddings (CodeBERT, DPR)
# - github_service.py: GitHub API entegrasyonu
# * code_analysis.py: Code parsing ve entity extraction

# Core services
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

# Enhanced services (NEW)
from .neo4j_service_enhanced import (
    neo4j_service_enhanced,
    create_enhanced_neo4j_service
)
from .hybrid_rag_extension import (
    create_hybrid_rag_extension,
    HybridRAGExtension
)
from .commit_indexing_service import (
    create_commit_indexing_service,
    CommitIndexingService
)
from .commit_indexing_service_enhanced import (
    create_enhanced_commit_indexing_service,
    EnhancedCommitIndexingService
)

# Export all
__all__ = [
    # Core
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
    # Enhanced
    "neo4j_service_enhanced",
    "create_enhanced_neo4j_service",
    "create_hybrid_rag_extension",
    "HybridRAGExtension",
    "create_commit_indexing_service",
    "CommitIndexingService"
]

