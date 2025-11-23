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
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Query repository using RAG (Retrieve + Generate)
        """
        try:
            logger.info(f"RAG Query: {question[:50]}...")

            # Step 1: Retrieve relevant context (semantic search)
            search_results = self.search(question, repo_name, n_results=n_results)

            if search_results["status"] != "success":
                return {
                    "answer": "I don't have enough information about this repository to answer your question.",
                    "context": [],
                    "sources": []
                }

            contexts = search_results["results"]

            if not contexts:
                logger.warning("No context found")
                return {
                    "answer": "I couldn't find relevant information to answer your question.",
                    "context": [],
                    "sources": []
                }

            logger.info(f"Retrieved {len(contexts)} context chunks")

            # Step 2: Build context string
            context_str = "\n\n---\n\n".join([
                f"**Source: {ctx['metadata']['source']}**\n{ctx['content']}"
                for ctx in contexts
            ])

            # Step 3: Generate answer
            if use_llm:
                # Use LLM
                system_message = f"""You are a helpful AI assistant that answers questions about the {repo_name} repository.

You have access to relevant documentation and code from the repository. Use this context to provide accurate, specific answers.

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

            # Step 4: Format response
            sources = [
                {
                    "file_path": ctx['metadata']['source'],
                    "language": ctx['metadata'].get('language', 'unknown'),
                    "similarity": f"{ctx['similarity']:.2%}"
                }
                for ctx in contexts
            ]

            return {
                "answer": answer,
                "context": [ctx['content'] for ctx in contexts],
                "sources": sources,
                "relevance_scores": [ctx['similarity'] for ctx in contexts],
                "confidence": contexts[0]['similarity'] if contexts else 0.0
            }

        except Exception as e:
            logger.error(f"Error in RAG query: {e}")
            return {
                "answer": f"Error processing query: {str(e)}",
                "context": [],
                "sources": []
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