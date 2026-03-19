"""
Embedding Service - Code Embeddings Generation
Uses CodeBERT or sentence-transformers for semantic code understanding
"""

from typing import List, Optional, Dict, Any
import logging
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating code embeddings using pre-trained models"""

    # Available models
    MODELS = {
        "codebert": "microsoft/codebert-base",
        "unixcoder": "microsoft/unixcoder-base",
        "graphcodebert": "microsoft/graphcodebert-base",
        "mpnet": "sentence-transformers/all-mpnet-base-v2",  # General purpose
        "minilm": "sentence-transformers/all-MiniLM-L6-v2"  # Faster, smaller
    }

    def __init__(self, model_name: str = "minilm"):
        """
        Initialize embedding service with a specific model

        Args:
            model_name: Name of the model to use (see MODELS dict)
        """
        self.model_name = model_name
        self.model_path = self.MODELS.get(model_name, self.MODELS["minilm"])

        logger.info(f"Loading embedding model: {self.model_path}")

        try:
            # Load model using sentence-transformers
            # This handles both code models and general NLP models
            self.model = SentenceTransformer(self.model_path)
            self.embedding_dimension = self.model.get_sentence_embedding_dimension()

            logger.info(f"Model loaded successfully. Embedding dimension: {self.embedding_dimension}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            # Fallback to smaller model
            logger.info("Falling back to MiniLM model...")
            self.model = SentenceTransformer(self.MODELS["minilm"])
            self.embedding_dimension = self.model.get_sentence_embedding_dimension()

    def encode(
            self,
            texts: List[str],
            batch_size: int = 32,
            show_progress: bool = False,
            normalize: bool = True
    ) -> np.ndarray:
        """
        Encode texts into embeddings

        Args:
            texts: List of text strings (code snippets, queries)
            batch_size: Batch size for encoding
            show_progress: Show progress bar
            normalize: Normalize embeddings to unit length

        Returns:
            NumPy array of embeddings (shape: [num_texts, embedding_dim])
        """
        if not texts:
            return np.array([])

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                normalize_embeddings=normalize,
                convert_to_numpy=True
            )

            logger.info(f"Encoded {len(texts)} texts into embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Error encoding texts: {e}")
            # Return zero embeddings as fallback
            return np.zeros((len(texts), self.embedding_dimension))

    def encode_single(self, text: str) -> List[float]:
        """
        Encode a single text into embedding

        Args:
            text: Single text string

        Returns:
            List of floats (embedding vector)
        """
        embedding = self.encode([text], show_progress=False)[0]
        return embedding.tolist()

    def encode_batch(
            self,
            texts: List[str],
            metadata: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Encode a batch of texts with optional metadata

        Args:
            texts: List of text strings
            metadata: Optional list of metadata dicts

        Returns:
            Dictionary with embeddings and metadata
        """
        embeddings = self.encode(texts, show_progress=True)

        result = {
            "embeddings": embeddings.tolist(),
            "count": len(texts),
            "dimension": self.embedding_dimension
        }

        if metadata:
            result["metadata"] = metadata

        return result

    def compute_similarity(
            self,
            query_embedding: np.ndarray,
            document_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute cosine similarity between query and documents

        Args:
            query_embedding: Single query embedding (shape: [embedding_dim])
            document_embeddings: Multiple document embeddings (shape: [num_docs, embedding_dim])

        Returns:
            Similarity scores (shape: [num_docs])
        """
        # Normalize embeddings
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        docs_norm = document_embeddings / np.linalg.norm(document_embeddings, axis=1, keepdims=True)

        # Compute cosine similarity
        similarities = np.dot(docs_norm, query_norm)

        return similarities

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model

        Returns:
            Dictionary with model information
        """
        return {
            "model_name": self.model_name,
            "model_path": self.model_path,
            "embedding_dimension": self.embedding_dimension,
            "max_sequence_length": self.model.max_seq_length
        }


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(model_name: str = "minilm") -> EmbeddingService:
    """
    Get or create embedding service singleton instance

    Args:
        model_name: Name of the model to use

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(model_name)
    return _embedding_service


# Export singleton for easy import (for RAG service compatibility)
embeddings_service = get_embedding_service("mpnet")


# Utility functions for code preprocessing
def preprocess_code(code: str) -> str:
    """
    Preprocess code for better embedding quality

    Args:
        code: Raw code string

    Returns:
        Preprocessed code string
    """
    # Remove excessive whitespace
    lines = [line.rstrip() for line in code.split('\n')]
    code = '\n'.join(line for line in lines if line.strip())

    # Remove comments (simple approach - can be improved)
    # This is language-specific, here's a basic Python example
    lines = []
    for line in code.split('\n'):
        # Remove inline comments
        if '#' in line:
            line = line[:line.index('#')]
        if line.strip():
            lines.append(line)

    return '\n'.join(lines)


def chunk_code(
        code: str,
        max_length: int = 512,
        overlap: int = 50
) -> List[str]:
    """
    Split code into overlapping chunks for embedding

    Args:
        code: Code string
        max_length: Maximum characters per chunk
        overlap: Overlap between chunks

    Returns:
        List of code chunks
    """
    if len(code) <= max_length:
        return [code]

    chunks = []
    start = 0

    while start < len(code):
        end = start + max_length
        chunk = code[start:end]

        # Try to break at newline
        if end < len(code):
            last_newline = chunk.rfind('\n')
            if last_newline > max_length // 2:
                end = start + last_newline
                chunk = code[start:end]

        chunks.append(chunk)
        start = end - overlap

    return chunks


# Test function
def test_embedding_service():
    """Test embedding service with code examples"""
    print("Testing Embedding Service...")

    service = get_embedding_service("minilm")
    print(f"\nModel Info: {service.get_model_info()}")

    # Test code snippets
    code_snippets = [
        "def add(a, b): return a + b",
        "def multiply(x, y): return x * y",
        "class Calculator: pass"
    ]

    # Generate embeddings
    embeddings = service.encode(code_snippets, show_progress=True)
    print(f"\nGenerated embeddings shape: {embeddings.shape}")

    # Test similarity
    query = "function for addition"
    query_emb = service.encode([query])[0]

    similarities = service.compute_similarity(query_emb, embeddings)
    print(f"\nSimilarities to '{query}':")
    for i, (snippet, sim) in enumerate(zip(code_snippets, similarities)):
        print(f"{i + 1}. {snippet[:30]}... - Similarity: {sim:.4f}")

    print("\nTest completed!")


if __name__ == "__main__":
    test_embedding_service()