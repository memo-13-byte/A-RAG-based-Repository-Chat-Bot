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
        self.llm = llm_service

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
        n_results: int = 3,
        use_llm: bool = True,
        use_graph: bool = True  # ← ADD THIS PARAMETER
    ) -> Dict[str, Any]:
        """
        Query repository using RAG (Retrieve + Generate)
        """
        try:
            logger.info(f"RAG Query: {question[:50]}...")

            # Step 1: Retrieve relevant context (semantic search)
            search_results = self.search(question, repo_name, n_results=n_results)

            # ADD THESE LINES AFTER logger.info, BEFORE search:

            # Check if this is a graph-related query
            is_graph_query = use_graph and self._detect_graph_query(question)

            # Get graph context if applicable
            graph_context = None
            if is_graph_query:
                graph_context = self._get_graph_context(repo_name, question)
                if graph_context:
                    logger.info("Graph context retrieved successfully")

            # Step 1: Retrieve relevant context (semantic search)
            search_results = self.search(question, repo_name, n_results=n_results)


            if search_results["status"] != "success":
                return {
                    "answer": "I don't have enough information about this repository to answer your question.",
                    "context": [],
                    "sources": [],
                    "graph_used": False  # ← ADD THIS
                }

            contexts = search_results["results"]

            if not contexts and not graph_context:  # ← UPDATE CONDITION
                logger.warning("No context found")
                return {
                    "answer": "I couldn't find relevant information to answer your question.",
                    "context": [],
                    "sources": [],
                    "graph_used": False  # ← ADD THIS
                }

            logger.info(f"Retrieved {len(contexts)} context chunks")

            # Step 2: Build combined context (graph + vector)
            context_parts = []

            # Add graph knowledge first (structure)
            if graph_context:
                context_parts.append(f"**Graph Knowledge (Code Structure):**\n{graph_context}")

            # Add vector search results (code content)
            if contexts:
                vector_context = "\n\n---\n\n".join([
                    f"**Source: {ctx['metadata']['source']}**\n{ctx['content']}"
                    for ctx in contexts
                ])
                context_parts.append(f"**Code Context:**\n{vector_context}")

            context_str = "\n\n" + "=" * 50 + "\n\n".join(context_parts) if context_parts else ""

            # Step 3: Generate answer
            if use_llm:
                # Use LLM
                system_message = f"""You are a helpful AI assistant that answers questions about the {repo_name} repository.

                You have access to:
                1. **Graph Knowledge**: Code structure, class hierarchies, and relationships
                2. **Code Context**: Actual implementation from relevant files

                Use this combined knowledge to provide accurate, specific answers.

                Context from repository:
                {context_str}
Instructions:
- Answer based on the provided context
- Be specific and cite sources when possible
- If the context doesn't contain relevant information, say so
- Keep answers concise but informative"""

                answer = self.llm.generate(
                    prompt=question,
                    system_message=system_message,
                    max_tokens=500
                )
            else:
                # Fallback to template
                answer = self._generate_template_answer(question, contexts)

            logger.info("Answer generated")

            # Step 4: Format response with graph information
            sources = []

            # Add graph source if used
            if graph_context:
                sources.append({
                    "file_path": "Knowledge Graph",
                    "language": "graph",
                    "similarity": "100%"
                })

            # Add vector search sources
            for ctx in contexts:
                sources.append({
                    "file_path": ctx['metadata']['source'],
                    "language": ctx['metadata'].get('language', 'unknown'),
                    "similarity": f"{ctx['similarity']:.2%}"
                })

            return {
                "answer": answer,
                "context": [ctx['content'] for ctx in contexts],
                "sources": sources,
                "relevance_scores": [ctx['similarity'] for ctx in contexts],
                "confidence": contexts[0]['similarity'] if contexts else 0.0,
                "graph_used": graph_context is not None,  # ← NEW FIELD
                "graph_context": graph_context  # ← NEW FIELD
            }

        except Exception as e:
            logger.error(f"Error in RAG query: {e}")
            return {
                "answer": f"Error processing query: {str(e)}",
                "context": [],
                "sources": [],
                "graph_used": False  # ← ADD THIS
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
                from .neo4j_service_enhanced import neo4j_service_enhanced

                logger.info("Initializing Hybrid RAG extension...")

                self._hybrid_rag = create_hybrid_rag_extension(
                    chroma_service=self.chroma,
                    neo4j_service=neo4j_service_enhanced,
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

            from .commit_indexing_service import create_commit_indexing_service
            from .neo4j_service_enhanced import neo4j_service_enhanced
            from .git_factory import get_git_service

            git_service = get_git_service(repo_url)

            commit_indexer = create_commit_indexing_service(
                neo4j_service=neo4j_service_enhanced,
                git_service=git_service
            )

            commit_result = commit_indexer.index_commits(
                repo_url=repo_url,
                max_commits=max_commits,
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
        """
        Detect if question needs graph knowledge

        Returns True if question contains graph-related keywords
        """
        graph_keywords = [
            "inherit", "extends", "subclass", "parent", "child",
            "depends", "dependency", "imported by", "imports",
            "calls", "called by", "relationship", "structure"
        ]
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in graph_keywords)

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
        """
        Get graph knowledge for the question

        Returns formatted string with graph context or None
        """
        try:
            owner, name = repo_name.split("/")
            context_parts = []

            # Get repository structure overview
            structure = neo4j_service.query_repository_structure(owner, name)
            if structure:
                context_parts.append(
                    f"Repository Structure:\n"
                    f"- Files: {structure.get('files', 0)}\n"
                    f"- Classes: {structure.get('classes', 0)}\n"
                    f"- Functions: {structure.get('functions', 0)}\n"
                    f"- Modules: {structure.get('modules', 0)}"
                )

            # Try to extract entity name and get its dependencies
            entity_name = self._extract_entity_name(question)
            if entity_name:
                # Try as Class first
                deps = neo4j_service.find_entity_dependencies(
                    owner, name, entity_name, "Class"
                )

                if deps:
                    dep_list = []
                    for dep in deps[:5]:  # Limit to 5
                        rel_type = dep.get('relationship', 'RELATED')
                        dep_list.append(f"  - {rel_type}: {dep['name']}")

                    if dep_list:
                        context_parts.append(
                            f"\n'{entity_name}' Relationships:\n" +
                            "\n".join(dep_list)
                        )

            if context_parts:
                return "\n\n".join(context_parts)

            return None

        except Exception as e:
            logger.warning(f"Could not fetch graph context: {e}")
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