"""
Hybrid RAG Extension - Extends existing RAGService
Adds vector + graph fusion, intent detection, and context enhancement
Compatible with existing RepoWise RAGService
"""

from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class HybridRAGExtension:
    """
    Extension to existing RAG service adding:
    - Query intent detection
    - Vector + Graph fusion
    - Context enhancement with graph traversal
    - Multi-source retrieval
    
    Use this alongside your existing RAGService
    """

    def __init__(
        self,
        chroma_service,
        neo4j_service,
        llm_service,
        embeddings_service
    ):
        """
        Initialize with existing services
        
        Args:
            chroma_service: Your existing ChromaDB service
            neo4j_service: Your enhanced Neo4j service
            llm_service: Your LLM service
            embeddings_service: Your embedding service
        """
        self.chroma = chroma_service
        self.neo4j = neo4j_service
        self.llm = llm_service
        self.embeddings = embeddings_service
        
        logger.info("Hybrid RAG Extension initialized")

    # ============================================================================
    # QUERY INTENT DETECTION
    # ============================================================================

    def detect_query_intent(self, query: str) -> str:
        """
        Detect query intent to route retrieval strategy
        
        Intents:
        - 'structure': Architecture/organization questions
        - 'dependency': Dependencies/relationships
        - 'history': Version history/changes
        - 'usage': How to use
        - 'implementation': How code works (default)
        - 'comparison': Compare entities
        """
        query_lower = query.lower()
        
        # Structure queries
        if any(word in query_lower for word in [
            'architecture', 'structure', 'organized', 'layout', 'hierarchy',
            'organization', 'design pattern'
        ]):
            return 'structure'
        
        # Dependency queries
        if any(word in query_lower for word in [
            'depend', 'import', 'require', 'use', 'call', 'inherit',
            'relationship', 'connected', 'link'
        ]):
            return 'dependency'
        
        # History queries
        if any(word in query_lower for word in [
            'when', 'who changed', 'history', 'modified', 'updated',
            'commit', 'author', 'contributor', 'wrote'
        ]):
            return 'history'
        
        # Usage queries
        if any(word in query_lower for word in [
            'how to use', 'example', 'usage', 'tutorial', 'guide',
            'how do i', 'how can i'
        ]):
            return 'usage'
        
        # Comparison queries
        if any(word in query_lower for word in [
            'difference', 'compare', 'versus', 'vs', 'between',
            'similar', 'different'
        ]):
            return 'comparison'
        
        # Default: implementation
        return 'implementation'

    # ============================================================================
    # HYBRID SEARCH
    # ============================================================================

    def hybrid_search(
        self,
        query: str,
        repo_name: str,
        top_k: int = 5,
        use_graph: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector and graph retrieval
        
        Args:
            query: User question
            repo_name: Repository name (owner/repo)
            top_k: Number of results
            use_graph: Whether to use graph search
            
        Returns:
            Ranked list of contexts
        """
        intent = self.detect_query_intent(query)
        logger.info(f"Query intent detected: {intent}")
        
        # 1. Vector Search (always)
        vector_results = self._vector_search(query, repo_name, top_k * 2)
        
        # 2. Graph Search (conditional)
        graph_results = []
        if use_graph and intent in ['structure', 'dependency', 'history']:
            graph_results = self._graph_search(query, repo_name, intent)
        
        # 3. Fusion
        if graph_results:
            combined = self._reciprocal_rank_fusion(
                [vector_results, graph_results]
            )
        else:
            combined = vector_results
        
        return combined[:top_k]

    def _vector_search(
        self,
        query: str,
        repo_name: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Vector search using ChromaDB"""
        try:
            collection_name = repo_name.replace("/", "_").replace("-", "_").lower()
            
            # Generate query embedding
            query_embedding = self.embeddings.encode_single(query)
            
            # Search in ChromaDB
            results = self.chroma.query(
                collection_name=collection_name,
                query_texts=[query],
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            
            # Format results
            formatted = []
            if results and results['documents'] and len(results['documents'][0]) > 0:
                for i, (doc, meta, dist) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # Convert distance to similarity (cosine distance to similarity)
                    similarity = 1.0 - (dist / 2.0)  # Approximate conversion
                    
                    formatted.append({
                        'content': doc,
                        'metadata': meta,
                        'similarity': similarity,
                        'source': 'vector',
                        'rank': i + 1
                    })
            
            return formatted
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    def _graph_search(
        self,
        query: str,
        repo_name: str,
        intent: str
    ) -> List[Dict[str, Any]]:
        """Graph search using Neo4j"""
        try:
            results = []
            entity_name = self._extract_entity_name(query)
            
            if intent == 'structure':
                structure = self._get_repository_structure(repo_name)
                if structure:
                    results.append({
                        'content': structure,
                        'metadata': {'source': 'graph', 'type': 'structure'},
                        'similarity': 1.0,
                        'source': 'graph',
                        'rank': 1
                    })
            
            elif intent == 'dependency' and entity_name:
                deps = self._get_entity_dependencies(repo_name, entity_name)
                if deps:
                    results.append({
                        'content': deps,
                        'metadata': {'source': 'graph', 'type': 'dependencies'},
                        'similarity': 0.9,
                        'source': 'graph',
                        'rank': 1
                    })
            
            elif intent == 'history':
                if entity_name:
                    history = self._get_entity_history(entity_name)
                else:
                    # General repository history
                    history = self._get_repository_activity(repo_name)
                
                if history:
                    results.append({
                        'content': history,
                        'metadata': {'source': 'graph', 'type': 'history'},
                        'similarity': 0.9,
                        'source': 'graph',
                        'rank': 1
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Graph search error: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        result_lists: List[List[Dict]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF) algorithm
        
        Formula: score = Σ(1 / (k + rank))
        """
        doc_scores = {}
        
        for result_list in result_lists:
            if not result_list:
                continue
            
            for rank, doc in enumerate(result_list, start=1):
                doc_key = doc['content'][:100]  # Use first 100 chars as key
                score = 1.0 / (k + rank)
                
                if doc_key in doc_scores:
                    doc_scores[doc_key]['score'] += score
                else:
                    doc_scores[doc_key] = {
                        'doc': doc,
                        'score': score
                    }
        
        # Sort by score
        ranked = sorted(
            doc_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )
        
        return [item['doc'] for item in ranked]

    # ============================================================================
    # CONTEXT ENHANCEMENT
    # ============================================================================

    def enhance_context_with_graph(
        self,
        contexts: List[Dict],
        repo_name: str
    ) -> List[Dict[str, Any]]:
        """
        Enhance contexts with graph information
        
        Adds:
        - File dependencies
        - Commit history
        - Code owners
        """
        enhanced = []
        
        for ctx in contexts:
            enhanced_ctx = ctx.copy()
            file_path = ctx['metadata'].get('source', '')
            
            if file_path and file_path != 'graph':
                # Add commit history
                try:
                    history = self.neo4j.get_file_commit_history(file_path, limit=3)
                    if history:
                        enhanced_ctx['commit_history'] = history
                except Exception as e:
                    logger.debug(f"Could not get history: {e}")
                
                # Add code owners
                try:
                    owners = self.neo4j.find_code_owners(file_path)
                    if owners and owners.get('primary_owner'):
                        enhanced_ctx['code_owner'] = owners['primary_owner']
                except Exception as e:
                    logger.debug(f"Could not get owners: {e}")
            
            enhanced.append(enhanced_ctx)
        
        return enhanced

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _extract_entity_name(self, query: str) -> Optional[str]:
        """Extract class/function name from query"""
        # CamelCase pattern
        camel_match = re.search(r'\b([A-Z][a-zA-Z0-9]*(?:[A-Z][a-zA-Z0-9]*)+)\b', query)
        if camel_match:
            return camel_match.group(1)
        
        # Quoted/backticked
        quoted_match = re.search(r'[`"\'](\w+)[`"\']', query)
        if quoted_match:
            return quoted_match.group(1)
        
        # After keywords
        func_match = re.search(
            r'(?:function|method|class|file)\s+(\w+)',
            query,
            re.IGNORECASE
        )
        if func_match:
            return func_match.group(1)
        
        return None

    def _get_repository_structure(self, repo_name: str) -> str:
        """Get repository structure summary"""
        try:
            stats = self.neo4j.get_repository_statistics(repo_name)
            
            structure = f"""Repository Structure: {repo_name}

Files: {stats.get('files', 0)}
Classes: {stats.get('classes', 0)}
Functions: {stats.get('functions', 0)}
Total Commits: {stats.get('total_commits', 0)}
Contributors: {stats.get('authors', 0)}

Languages:
"""
            languages = stats.get('languages', {})
            for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                structure += f"  - {lang}: {count} files\n"
            
            return structure
            
        except Exception as e:
            logger.error(f"Error getting structure: {e}")
            return ""

    def _get_entity_dependencies(self, repo_name: str, entity_name: str) -> str:
        """Get entity dependency information"""
        try:
            # This would use your existing Neo4j queries
            # Placeholder implementation
            deps_text = f"Dependencies for {entity_name}:\n"
            deps_text += "  (Graph query would go here)\n"
            
            return deps_text
            
        except Exception as e:
            logger.error(f"Error getting dependencies: {e}")
            return ""

    def _get_entity_history(self, entity_name: str) -> str:
        """Get commit history for entity"""
        try:
            # Find file containing entity and get its history
            # Placeholder implementation
            history_text = f"Recent changes to {entity_name}:\n"
            history_text += "  (History query would go here)\n"
            
            return history_text
            
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return ""

    def _get_repository_activity(self, repo_name: str) -> str:
        """Get recent repository activity"""
        try:
            # Get recent commits
            activity = f"Recent activity in {repo_name}:\n"
            activity += "  (Activity query would go here)\n"
            
            return activity
            
        except Exception as e:
            logger.error(f"Error getting activity: {e}")
            return ""

    # ============================================================================
    # MAIN QUERY METHOD
    # ============================================================================

    def query_with_hybrid_rag(
        self,
        question: str,
        repo_name: str,
        top_k: int = 5,
        use_graph: bool = True,
        enhance: bool = True
    ) -> Dict[str, Any]:
        """
        Main hybrid RAG query method
        
        Args:
            question: User question
            repo_name: Repository name
            top_k: Number of contexts
            use_graph: Use graph search
            enhance: Enhance with graph info
            
        Returns:
            Complete answer with metadata
        """
        try:
            logger.info(f"Hybrid RAG query: {question}")
            
            # 1. Retrieve contexts
            contexts = self.hybrid_search(question, repo_name, top_k, use_graph)
            
            if not contexts:
                return {
                    'answer': "I couldn't find relevant information.",
                    'contexts': [],
                    'sources': [],
                    'intent': 'unknown'
                }
            
            # 2. Enhance contexts (optional)
            if enhance:
                contexts = self.enhance_context_with_graph(contexts, repo_name)
            
            # 3. Generate answer
            answer = self._generate_answer_with_llm(question, contexts)
            
            # 4. Format response
            return {
                'answer': answer,
                'contexts': [c['content'] for c in contexts],
                'sources': self._format_sources(contexts),
                'intent': self.detect_query_intent(question),
                'num_contexts': len(contexts),
                'used_graph': any(c['source'] == 'graph' for c in contexts)
            }
            
        except Exception as e:
            logger.error(f"Hybrid RAG error: {e}")
            return {
                'answer': f"Error: {str(e)}",
                'contexts': [],
                'sources': [],
                'intent': 'error'
            }

    def _generate_answer_with_llm(
        self,
        question: str,
        contexts: List[Dict]
    ) -> str:
        """Generate answer using LLM"""
        try:
            # Build context string
            context_str = "\n\n".join([
                f"[{c['source']}] {c['content'][:500]}"  # Limit context length
                for c in contexts
            ])
            
            # Build prompt
            prompt = f"""Based on the repository code context below, answer the question.

Context:
{context_str}

Question: {question}

Provide a clear answer based on the context above."""
            
            # Generate with LLM
            response = self.llm.generate(prompt, max_tokens=500)
            
            return response
            
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return "Unable to generate answer."

    def _format_sources(self, contexts: List[Dict]) -> List[Dict]:
        """Format sources for display"""
        sources = []
        
        for ctx in contexts:
            source = {
                'type': ctx['source'],
                'similarity': f"{ctx.get('similarity', 0):.2%}"
            }
            
            if 'metadata' in ctx:
                meta = ctx['metadata']
                source['file'] = meta.get('source', 'Unknown')
                source['language'] = meta.get('language', 'Unknown')
            
            # Add commit history if available
            if 'commit_history' in ctx and ctx['commit_history']:
                source['last_modified'] = ctx['commit_history'][0]['date']
                source['last_author'] = ctx['commit_history'][0]['author']
            
            sources.append(source)
        
        return sources


# Factory function
def create_hybrid_rag_extension(
    chroma_service,
    neo4j_service,
    llm_service,
    embeddings_service
):
    """Create Hybrid RAG Extension instance"""
    return HybridRAGExtension(
        chroma_service,
        neo4j_service,
        llm_service,
        embeddings_service
    )
