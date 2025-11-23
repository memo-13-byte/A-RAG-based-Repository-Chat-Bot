"""
RAG Service - Complete RAG Pipeline Integration
Ultimate version combining comprehensive features with clean service architecture
"""

from typing import List, Dict, Any, Optional
import logging
from .chromadb_service import chroma_service
from .embedding_service import embeddings_service
from .document_processor import document_processor
from .github_service import github_service
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
        self.github = github_service
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

        Args:
            repo_url: GitHub repository URL
            include_readme: Whether to index README
            include_code_files: Whether to index code files
            max_files: Maximum number of code files to index
            chunk_size: Chunk size for documents
            force_reindex: Re-index even if collection exists

        Returns:
            Dictionary with indexing results
        """
        try:
            logger.info(f"Starting repository indexing: {repo_url}")

            # Get repository info
            repo_info = self.github.get_repository_info(repo_url)
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
                readme = self.github.get_readme(repo_url)

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
                    # Get file tree
                    files = self.github.get_file_tree(repo_url, path="")

                    # Filter processable files
                    processable_files = [
                        f for f in files
                        if f["type"] == "file" and self.processor.should_process_file(f["path"])
                    ][:max_files]

                    logger.info(f"Found {len(processable_files)} processable files")

                    for file_info in processable_files:
                        try:
                            # Get file content
                            content = self.github.get_file_content(repo_url, file_info["path"])

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

                # Debug log
                if not metadata or metadata == {}:
                    print(f"EMPTY METADATA at chunk {i}: {chunk.chunk_id}")

                # Ensure non-empty
                if not metadata:
                    metadata = {
                        "source": "unknown",
                        "type": "unknown",
                        "repository": repo_name
                    }

                # Ensure required fields
                if "source" not in metadata:
                    metadata["source"] = chunk.chunk_id.split("_chunk_")[
                        0] if "_chunk_" in chunk.chunk_id else "unknown"
                if "type" not in metadata:
                    metadata["type"] = "document"
                if "repository" not in metadata:
                    metadata["repository"] = repo_name

                # NEW: Convert all values to strings HERE!
                clean_metadata = {}
                for key, value in metadata.items():
                    if isinstance(value, (int, float)):
                        clean_metadata[key] = str(value)  # chunk_index: 0 -> "0"
                    else:
                        clean_metadata[key] = str(value) if value is not None else "null"

                metadata = clean_metadata

                # Double check before adding
                if not metadata or len(metadata) == 0:
                    print(f"STILL EMPTY after fixes! chunk {i}")
                    metadata = {"source": "emergency_default", "type": "document", "repository": repo_name}

                metadatas.append(metadata)

            ids = [chunk.chunk_id for chunk in all_chunks]

            # Debug: Print first metadata
            print(f"Sample metadata (first chunk): {metadatas[0]}")
            print(f"Total chunks: {len(all_chunks)}, metadatas: {len(metadatas)}")

            # Generate embeddings
            embeddings_array = self.embeddings.encode(documents, show_progress=True)
            embeddings_list = embeddings_array.tolist()

            # 5. Store in ChromaDB
            logger.info(f"Storing in ChromaDB collection: {collection_name}")
            # BEFORE sending to ChromaDB
            print("\nFINAL DEBUG BEFORE ChromaDB:")
            print(f"Documents count: {len(documents)}")
            print(f"Metadatas count: {len(metadatas)}")
            print(f"Embeddings count: {len(embeddings_list)}")

            for i in range(min(3, len(metadatas))):
                print(f"\n  Item {i}:")
                print(f"    Doc: {documents[i][:50]}...")
                print(f"    Meta: {metadatas[i]}")
                print(f"    Embedding: {embeddings_list[i][:3]}... (dim: {len(embeddings_list[i])})")

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

        Args:
            query: Search query
            repo_name: Repository name (e.g., 'langchain-ai/langchain')
            n_results: Number of results to return
            language_filter: Optional language filter (e.g., "python")

        Returns:
            Dictionary with search results
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

        Args:
            repo_name: Repository name (e.g., 'langchain-ai/langchain')
            question: User question
            n_results: Number of context chunks to retrieve
            use_llm: Use LLM for generation (fallback to template if False)

        Returns:
            Dictionary with answer, context, and sources
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

        Args:
            query: User query
            contexts: Retrieved context documents

        Returns:
            Template-based answer string
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
            answer += f"   {content_preview}...\n\n"

        answer += f"These files primarily use {', '.join(languages)} and are most relevant to your query."

        return answer

    def get_index_status(self, repo_name: str) -> Dict[str, Any]:
        """
        Get indexing status for a repository

        Args:
            repo_name: Repository name

        Returns:
            Dictionary with index status
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

        Args:
            repo_name: Repository name

        Returns:
            True if successful
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
        """
        List all indexed repositories

        Returns:
            List of collection names
        """
        return self.chroma.list_collections()

    def get_collection_info(self, repo_name: str) -> Dict[str, Any]:
        """
        Get information about an indexed repository

        Args:
            repo_name: Repository name

        Returns:
            Dictionary with collection information
        """
        collection_name = repo_name.replace("/", "_").replace("-", "_").lower()
        return self.chroma.get_collection_stats(collection_name)


# Singleton instance
rag_service = RAGService()


# Test function
def test_rag_service():
    """Test RAG service end-to-end"""
    print("=" * 80)
    print("Testing Ultimate RAG Service")
    print("=" * 80)

    # Test repository (small for quick test)
    repo_url = "https://github.com/psf/requests"

    # 1. Index repository
    print("\nIndexing repository (README only)...")
    result = rag_service.index_repository(
        repo_url=repo_url,
        include_readme=True,
        include_code_files=False
    )

    print(f"Status: {result['status']}")
    print(f"Indexed chunks: {result.get('document_count', 0)}")

    if result['status'] == 'success':
        repo_name = result['repository']

        # 2. Check status
        print("\nChecking index status...")
        status = rag_service.get_index_status(repo_name)
        print(f"Repository: {status['repository']}")
        print(f"Indexed: {status['indexed']}")
        print(f"Total chunks: {status['total_chunks']}")

        # 3. Test search
        print("\nTesting semantic search...")
        search_results = rag_service.search("HTTP requests", repo_name, n_results=3)
        print(f"Found {search_results['count']} results")
        if search_results['results']:
            print(f"Top result: {search_results['results'][0]['metadata']['source']}")

        # 4. Test RAG query
        print("\nTesting RAG query...")
        question = "What is this library used for?"

        response = rag_service.query(repo_name, question, n_results=2, use_llm=True)

        print(f"\nQuestion: {question}")
        print(f"Answer: {response['answer'][:200]}...")
        print(f"\nSources: {', '.join([s['file_path'] for s in response['sources']])}")

        # 5. Cleanup
        print("\nCleaning up...")
        rag_service.delete_index(repo_name)
        print("Test complete!")


if __name__ == "__main__":
    test_rag_service()