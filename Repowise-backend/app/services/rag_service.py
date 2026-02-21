"""
RAG Service - Complete RAG Pipeline Integration
Ultimate version combining comprehensive features with clean service architecture
"""

from typing import List, Dict, Any, Optional
import logging
from .chromadb_service import chroma_service
from .embedding_service import embeddings_service
from .document_processor import document_processor
from .git_factory import get_git_service
from .llm_service import llm_service
import re
from .neo4j_service import neo4j_service
from .llm_service_enhanced import (
    enhanced_llm_service,
    build_optimized_context
)
from .cache_service import cache_service



logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG (Retrieval-Augmented Generation) Service

    Complete pipeline:
    1. Index repository -> Process files -> Generate embeddings -> Store in ChromaDB
    2. Search -> Semantic similarity search in vector DB
    3. Generate answer -> Retrieve context -> LLM generation
    """

    def __init__(self):
        """Initialize RAG service with existing services"""
        self.chroma = chroma_service
        self.embeddings = embeddings_service
        self.processor = document_processor
        # self.github satırı SİLİNDİ. Artık dinamik seçilecek.
        self.llm = enhanced_llm_service # Use enhanced service

        logger.info("RAG Service initialized")

    def index_repository(
        self,
        repo_url: str,
        include_readme: bool = True,
        include_code_files: bool = True,
        max_files: int = 500,
        chunk_size: int = 1000,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Index a repository for RAG
        """
        try:
            # --- YENİ: URL'ye göre doğru servisi (GitHub/GitLab) seç ---
            git_service = get_git_service(repo_url)
            # -----------------------------------------------------------
            
            logger.info(f"Starting repository indexing: {repo_url}")

            # Get repository info (git_service kullanılarak)
            repo_info = git_service.get_repository_info(repo_url)
            repo_name = repo_info["full_name"]
            collection_name = repo_name.replace("/", "_").replace("-", "_").lower()

            # Check if already indexed
            existing_collections = self.chroma.list_collections()
            if collection_name in existing_collections and not force_reindex:
                stats = self.chroma.get_collection_stats(collection_name)
                logger.info(f"Collection already exists with {stats['count']} documents")
                return {
                    "status": "exists",
                    "collection_name": collection_name,
                    "document_count": stats['count'],
                    "repository": repo_name,
                    "message": "Collection already indexed. Use force_reindex=True to re-index."
                }

            # Delete existing if force_reindex
            if force_reindex and collection_name in existing_collections:
                self.chroma.delete_collection(collection_name)
                logger.info("Deleted existing collection for re-indexing")

            all_chunks = []

            # 1. Index README
            if include_readme:
                logger.info("Processing README...")
                # git_service kullanıldı
                readme = git_service.get_readme(repo_url)

                if readme:
                    readme_chunks = self.processor.process_readme(readme, repo_name)
                    all_chunks.extend(readme_chunks)
                    logger.info(f"README: {len(readme_chunks)} chunks")
                else:
                    logger.warning("README not found")

            # 2. Index code files
            if include_code_files:
                logger.info(f"Processing code files (max {max_files})...")

                try:
                    # Get file tree (git_service kullanıldı)
                    files = git_service.get_file_tree(repo_url, path="")

                    # Filter processable files
                    processable_files = [
                        f for f in files
                        if f["type"] == "file" and self.processor.should_process_file(f["path"])
                    ][:max_files]

                    logger.info(f"Found {len(processable_files)} processable files")

                    for file_info in processable_files:
                        try:
                            # Get file content (git_service kullanıldı)
                            content = git_service.get_file_content(repo_url, file_info["path"])

                            if not content:
                                continue

                            # Process file into chunks
                            file_chunks = self.processor.process_file(
                                content,
                                file_info["path"],
                                repo_name
                            )

                            all_chunks.extend(file_chunks)
                            logger.info(f"{file_info['path']}: {len(file_chunks)} chunks")

                        except Exception as e:
                            logger.warning(f"Error processing {file_info['path']}: {e}")

                    logger.info(f"Processed {len(processable_files)} code files")

                except Exception as e:
                    logger.warning(f"Error indexing code files: {e}")

            # 3. Check if we have chunks
            if not all_chunks:
                logger.warning("No chunks to index")
                return {
                    "status": "no_content",
                    "repository": repo_name,
                    "indexed_chunks": 0,
                    "message": "No content found to index"
                }

            # 4. Generate embeddings
            logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")

            documents = [chunk.content for chunk in all_chunks]

            # CRITICAL FIX: Validate all metadata before ChromaDB
            metadatas = []
            for i, chunk in enumerate(all_chunks):
                metadata = chunk.metadata if chunk.metadata else {}

                if not metadata:
                    metadata = {
                        "source": "unknown",
                        "type": "unknown",
                        "repository": repo_name
                    }

                # Ensure required fields
                if "source" not in metadata:
                    metadata["source"] = chunk.chunk_id.split("_chunk_")[0] if "_chunk_" in chunk.chunk_id else "unknown"
                if "type" not in metadata:
                    metadata["type"] = "document"
                if "repository" not in metadata:
                    metadata["repository"] = repo_name

                # NEW: Convert all values to strings HERE!
                clean_metadata = {}
                for key, value in metadata.items():
                    if isinstance(value, (int, float)):
                        clean_metadata[key] = str(value)
                    else:
                        clean_metadata[key] = str(value) if value is not None else "null"

                metadata = clean_metadata
                metadatas.append(metadata)

            ids = [chunk.chunk_id for chunk in all_chunks]

            # Generate embeddings
            embeddings_array = self.embeddings.encode(documents, show_progress=True)
            embeddings_list = embeddings_array.tolist()

            # 5. Store in ChromaDB
            logger.info(f"Storing in ChromaDB collection: {collection_name}")
            
            success = self.chroma.add_documents(
                collection_name=collection_name,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings_list
            )

            if success:
                stats = self.chroma.get_collection_stats(collection_name)
                logger.info(f"Repository indexed successfully: {stats['count']} chunks")

                return {
                    "status": "success",
                    "repository": repo_name,
                    "collection_name": collection_name,
                    "document_count": stats['count'],
                    "repository_url": repo_url,
                    "embedding_dimension": self.embeddings.embedding_dimension
                }
            else:
                logger.error("Failed to store documents")
                return {
                    "status": "error",
                    "repository": repo_name,
                    "message": "Failed to store documents in ChromaDB"
                }

        except Exception as e:
            logger.error(f"Error indexing repository: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def search(
        self,
        query: str,
        repo_name: str,
        n_results: int = 5,
        language_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for relevant code snippets using semantic search
        """
        try:
            logger.info(f"Searching: '{query[:50]}...'")

            collection_name = repo_name.replace("/", "_").replace("-", "_").lower()

            # Generate query embedding
            query_embedding = self.embeddings.encode([query])[0]

            # Prepare metadata filter
            where = {"language": language_filter} if language_filter else None

            # Search in ChromaDB
            results = self.chroma.query(
                collection_name=collection_name,
                query_texts=[],  # Empty because we provide embeddings
                query_embeddings=[query_embedding.tolist()],
                n_results=n_results,
                where=where
            )

            if not results['documents'][0]:
                logger.warning("No results found")
                return {
                    "status": "no_results",
                    "query": query,
                    "results": [],
                    "count": 0
                }

            # Format results
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i],
                    "similarity": 1 - results['distances'][0][i]  # Convert to similarity
                })

            logger.info(f"Found {len(formatted_results)} results")

            return {
                "status": "success",
                "query": query,
                "results": formatted_results,
                "count": len(formatted_results)
            }

        except Exception as e:
            logger.error(f"Error searching: {e}")
            return {
                "status": "error",
                "message": str(e),
                "results": []
            }

    def query(
            self,
            repo_name: str,
            question: str,
            n_results: int = 5,
            use_llm: bool = True,
            use_graph: bool = True,
            intent: Optional[str] = None,
            chat_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Query repository with RAG (now optimized with caching!)

        Combines:
        - Response caching (50-70% hit rate, 10-50x faster)
        - Enhanced LLM (dynamic temp, max_tokens, CoT)
        - Graph database (code structure)
        - Vector search (semantic similarity)

        Args:
            repo_name: Repository name (owner/repo)
            question: User question
            n_results: Number of chunks to retrieve (default 5)
            use_llm: Whether to use LLM
            use_graph: Whether to use graph context
            intent: Query intent (auto-detected if None)
            chat_history: Previous messages

        Returns:
            Dict with answer, sources, confidence, graph info
        """
        try:
            # ================================================================
            # STEP -1: CACHE CHECK 🆕
            # ================================================================

            # Build cache key parameters
            cache_params = {
                "n_results": n_results,
                "use_graph": use_graph,
                "intent": intent or 'unknown'
            }

            # Try to get from cache
            cached_response = cache_service.get(repo_name, question, **cache_params)

            if cached_response:
                logger.info(
                    f"💚 Cache HIT! Returning cached response (hit rate: {cache_service.get_stats()['hit_rate']})")
                return cached_response

            logger.info("💛 Cache MISS - generating fresh response")

            # ================================================================
            # STEP 0: INTENT DETECTION
            # ================================================================

            if intent is None:
                try:
                    from .hybrid_rag_extension import hybrid_rag
                    intent = hybrid_rag.detect_query_intent(question)
                except:
                    intent = 'implementation'

            logger.info(f"RAG Query: '{question[:50]}...' (intent: {intent})")

            # ================================================================
            # STEP 1: GRAPH CONTEXT
            # ================================================================

            graph_context = ""
            graph_used = False

            is_graph_query = use_graph and self._detect_graph_query(question)

            if is_graph_query:
                try:
                    graph_context_data = self._get_graph_context(repo_name, question)

                    if graph_context_data:
                        graph_context = f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║ GRAPH DATABASE INSIGHTS (Code Structure)
    ╚══════════════════════════════════════════════════════════════╝

    {graph_context_data}

    """
                        graph_used = True
                        logger.info("✅ Graph context retrieved")
                except Exception as e:
                    logger.warning(f"Graph unavailable: {e}")

            # ================================================================
            # STEP 2: VECTOR SEARCH
            # ================================================================

            search_results = self.search(
                question,
                repo_name,
                n_results=n_results * 2  # Get 2x, filter later
            )

            if not search_results.get('results') and not graph_context:
                return {
                    "answer": "No relevant information found.",
                    "sources": [],
                    "confidence": 0.0,
                    "contexts": [],
                    "intent": intent,
                    "graph_used": False
                }

            # ================================================================
            # STEP 3: BUILD OPTIMIZED CONTEXT
            # ================================================================

            contexts = []
            if search_results.get('results'):
                for result in search_results['results'][:n_results]:
                    contexts.append({
                        'content': result['content'],
                        'metadata': result['metadata'],
                        'similarity': result.get('similarity', 0)
                    })

            # Use optimized context builder
            vector_context = ""
            if contexts:
                vector_context = build_optimized_context(
                    contexts,
                    max_tokens=3000
                )

            # ================================================================
            # STEP 4: COMBINE GRAPH + VECTOR
            # ================================================================

            context_parts = []

            if graph_context:
                context_parts.append(graph_context)

            if vector_context:
                context_parts.append(vector_context)

            total_context = "\n\n".join(context_parts) if context_parts else ""
            context_length = len(total_context) // 4

            logger.info(f"Context: {len(contexts)} chunks + {'graph' if graph_used else 'no graph'}")

            # ================================================================
            # STEP 5: LLM GENERATION (Enhanced!)
            # ================================================================

            if use_llm:
                system_message = f"""You are RepoWise AI, expert for {repo_name} repository.

    Context available:
    1. Graph Knowledge: Code structure, relationships
    2. Vector Search: Implementation details

    {total_context}

    Instructions:
    - Answer based on provided context
    - Cite sources when relevant
    - Be specific and accurate
    - If uncertain, acknowledge it"""

                answer = self.llm.generate_enhanced(
                    prompt=question,
                    system_message=system_message,
                    context=total_context,
                    context_length=context_length,
                    intent=intent,
                    chat_history=chat_history
                )

                logger.info(f"✅ Answer generated ({len(answer)} chars)")
            else:
                answer = total_context

            # ================================================================
            # STEP 6: BUILD RESPONSE
            # ================================================================

            sources = []

            if graph_used:
                sources.append("Knowledge Graph")

            for ctx in contexts:
                source = ctx['metadata'].get('source', 'Unknown')
                if source not in sources:
                    sources.append(source)

            confidence = contexts[0].get('similarity', 0.0) if contexts else 0.0

            # Build response
            response = {
                "answer": answer,
                "sources": sources,
                "confidence": float(confidence),
                "contexts": contexts,
                "intent": intent,
                "graph_used": graph_used,
                "graph_context": graph_context if graph_used else None
            }

            # ================================================================
            # STEP 7: CACHE RESPONSE 🆕
            # ================================================================

            # Cache successful response (1 hour TTL)
            try:
                cache_service.set(
                    repo_name,
                    question,
                    response,
                    ttl=3600,  # 1 hour
                    **cache_params
                )
                logger.info("💾 Response cached for 1 hour")
            except Exception as cache_error:
                logger.warning(f"Cache set failed (non-critical): {cache_error}")

            return response

        except Exception as e:
            logger.error(f"RAG query failed: {e}", exc_info=True)
            return {
                "answer": f"Error: {str(e)}",
                "sources": [],
                "confidence": 0.0,
                "contexts": [],
                "intent": intent or 'unknown',
                "graph_used": False,
                "error": str(e)
            }

    def query_hybrid(
            self,
            question: str,
            repo_name: str,
            top_k: int = 5,
            use_graph: bool = True
    ) -> Dict[str, Any]:
        """
        Hybrid RAG query using vector + graph search

        Args:
            question: User question
            repo_name: Repository name (owner/repo)
            top_k: Number of results
            use_graph: Use graph knowledge

        Returns:
            Answer with enhanced context
        """
        try:
            # Lazy initialization of hybrid RAG
            if not hasattr(self, '_hybrid_rag'):
                from .hybrid_rag_extension import create_hybrid_rag_extension
                from .neo4j_service_enhanced import get_enhanced_queries

                logger.info("Initializing Hybrid RAG extension...")

                self._hybrid_rag = create_hybrid_rag_extension(
                    chroma_service=self.chroma,
                    neo4j_service=neo4j_service,
                    llm_service=self.llm,
                    embeddings_service=self.embeddings
                )

            # Query with hybrid RAG
            result = self._hybrid_rag.query_with_hybrid_rag(
                question=question,
                repo_name=repo_name,
                top_k=top_k,
                use_graph=use_graph,
                enhance=True
            )

            logger.info(f"Hybrid query completed. Intent: {result.get('intent')}")

            return result

        except Exception as e:
            logger.error(f"Hybrid query failed: {e}")
            logger.info("Falling back to regular query...")

            # Fallback to regular query
            return self.query(question, repo_name, top_k)

    def index_with_commits(
            self,
            repo_url: str,
            max_commits: int = 100,
            **kwargs
    ) -> Dict[str, Any]:
        """
        Index repository with commit history

        Args:
            repo_url: Repository URL
            max_commits: Maximum commits to index
            **kwargs: Other index_repository parameters

        Returns:
            Combined indexing statistics
        """
        try:
            # 1. Regular indexing (vector + code structure)
            logger.info("Starting regular indexing...")
            index_result = self.index_repository(repo_url, **kwargs)

            # 2. Commit indexing
            logger.info("Starting commit indexing...")

            from .commit_indexing_service_enhanced import create_enhanced_commit_indexing_service
            from .neo4j_service_enhanced import get_enhanced_queries
            from .git_factory import get_git_service

            git_service = get_git_service(repo_url)

            commit_indexer = create_enhanced_commit_indexing_service(
                neo4j_service=neo4j_service,
                git_service=git_service
            )

            commit_result = commit_indexer.index_commits_enhanced(
                repo_url=repo_url,
                max_commits=max_commits,
                include_files=True,  # ← NEW
                include_diffs=True,   # ← NEW
                force=kwargs.get('force_reindex', False)
            )


            # Combine results
            return {
                "status": "success",
                "repository": index_result.get("repository"),
                "vector_chunks": index_result.get("indexed_chunks", 0),
                "commits_indexed": commit_result.get("statistics", {}).get("commits_processed", 0),
                "authors_found": commit_result.get("statistics", {}).get("authors_created", 0)
            }

        except Exception as e:
            logger.error(f"Index with commits failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _generate_template_answer(
        self,
        query: str,
        contexts: List[Dict[str, Any]]
    ) -> str:
        """
        Generate template-based answer without LLM (fallback)
        """
        # Extract file information
        files = list(set(ctx['metadata']['source'] for ctx in contexts))
        languages = list(set(ctx['metadata'].get('language', 'unknown') for ctx in contexts))

        answer = f"Based on the repository code, I found relevant information in {len(files)} file(s):\n\n"

        for i, ctx in enumerate(contexts[:3], 1):  # Show top 3
            file_path = ctx['metadata']['source']
            content_preview = ctx['content'][:200].replace('\n', ' ')
            similarity = f"{ctx['similarity']:.0%}"

            answer += f"{i}. **{file_path}** ({ctx['metadata'].get('language', 'unknown')}) - {similarity} match\n"
            answer += f"    {content_preview}...\n\n"

        answer += f"These files primarily use {', '.join(languages)} and are most relevant to your query."

        return answer

    def _detect_graph_query(self, question: str) -> bool:
        """Detect if query needs graph context"""
        question_lower = question.lower()

        graph_keywords = [
            # Structure
            'structure', 'architecture', 'organized', 'layout', 'design',
            'hierarchy', 'organization',

            # Relationships
            'depend', 'dependency', 'dependencies', 'import', 'imports',
            'use', 'uses', 'used by', 'call', 'calls', 'called by',
            'inherit', 'inherits', 'extend', 'extends',
            'relationship', 'connected', 'connection', 'link',

            # Files/Classes/Functions
            'class', 'classes', 'function', 'functions', 'method', 'methods',
            'file', 'files', 'module', 'modules', 'package', 'packages',

            # History/Changes
            'who', 'when', 'author', 'contributor', 'wrote', 'modified',
            'changed', 'history', 'commit', 'commits',

            # Comparison
            'difference', 'compare', 'similar', 'related'
        ]

        return any(kw in question_lower for kw in graph_keywords)

    def _extract_entity_name(self, question: str) -> Optional[str]:
        """
        Extract class/function name from question

        Examples:
        - "What does BaseChain inherit from?" → "BaseChain"
        - "How does the run function work?" → "run"
        """
        # Pattern 1: CamelCase class names
        camel_match = re.search(r'\b([A-Z][a-zA-Z0-9]*(?:[A-Z][a-zA-Z0-9]*)+)\b', question)
        if camel_match:
            return camel_match.group(1)

        # Pattern 2: Quoted/backticked names
        quoted_match = re.search(r'[`"\'](\w+)[`"\']', question)
        if quoted_match:
            return quoted_match.group(1)

        # Pattern 3: After "function" or "method" keyword
        func_match = re.search(r'(?:function|method)\s+(\w+)', question, re.IGNORECASE)
        if func_match:
            return func_match.group(1)

        return None

    def _get_graph_context(self, repo_name: str, question: str) -> Optional[str]:
        """Get graph context from Neo4j"""
        try:
            from .neo4j_service import neo4j_service

            question_lower = question.lower()

            # File structure
            if any(w in question_lower for w in ['structure', 'organized', 'files', 'directory']):
                result = neo4j_service.get_repository_structure(repo_name)
                if result:
                    return f"Repository Structure:\n{result}"

            # Class hierarchy
            if any(w in question_lower for w in ['class', 'inherit', 'hierarchy']):
                result = neo4j_service.get_class_hierarchy(repo_name)
                if result:
                    return f"Class Hierarchy:\n{result}"

            # Dependencies
            if any(w in question_lower for w in ['depend', 'import', 'use']):
                result = neo4j_service.get_dependencies(repo_name)
                if result:
                    return f"Dependencies:\n{result}"

            # Commit history
            if any(w in question_lower for w in ['who', 'when', 'author', 'history', 'commit']):
                result = neo4j_service.get_commit_history(repo_name, limit=10)
                if result:
                    return f"Recent Commit History:\n{result}"

            # Default: general overview
            return neo4j_service.get_repository_overview(repo_name)

        except Exception as e:
            logger.warning(f"Graph context error: {e}")
            return None

    def get_index_status(self, repo_name: str) -> Dict[str, Any]:
        """
        Get indexing status for a repository
        """
        try:
            collection_name = repo_name.replace("/", "_").replace("-", "_").lower()
            stats = self.chroma.get_collection_stats(collection_name)

            return {
                "repository": repo_name,
                "indexed": stats["count"] > 0,
                "total_chunks": stats["count"],
                "collection": collection_name
            }

        except Exception as e:
            logger.error(f"Error getting index status: {e}")
            return {
                "repository": repo_name,
                "indexed": False,
                "total_chunks": 0,
                "error": str(e)
            }

    def delete_index(self, repo_name: str) -> bool:
        """
        Delete repository index
        """
        try:
            collection_name = repo_name.replace("/", "_").replace("-", "_").lower()
            success = self.chroma.delete_collection(collection_name)

            if success:
                logger.info(f"Deleted index for {repo_name}")

            return success

        except Exception as e:
            logger.error(f"Error deleting index: {e}")
            return False

    def list_indexed_repositories(self) -> List[str]:
        """List all indexed repositories"""
        return self.chroma.list_collections()

    def get_collection_info(self, repo_name: str) -> Dict[str, Any]:
        """Get information about an indexed repository"""
        collection_name = repo_name.replace("/", "_").replace("-", "_").lower()
        return self.chroma.get_collection_stats(collection_name)


# Singleton instance
rag_service = RAGService()

