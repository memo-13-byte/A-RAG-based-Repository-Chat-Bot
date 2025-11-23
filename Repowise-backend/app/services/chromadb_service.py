"""
ChromaDB Service - Fixed Version for ChromaDB 0.4.22
Extensive metadata validation to prevent empty dict errors
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Any
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ChromaDBService:
    """Service for managing ChromaDB vector database operations"""

    def __init__(self, persist_directory: str = "./chroma_db"):
        """Initialize ChromaDB client with persistent storage"""

        # Disable telemetry
        os.environ["ANONYMIZED_TELEMETRY"] = "False"
        os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        logger.info(f"ChromaDB initialized at {self.persist_directory}")

    def create_collection(
            self,
            collection_name: str,
            metadata: Optional[Dict[str, Any]] = None
    ) -> chromadb.Collection:
        """Create or get a collection"""
        try:
            collection = self.client.get_collection(name=collection_name)
            logger.info(f"Retrieved existing collection: {collection_name}")
        except Exception:
            collection = self.client.create_collection(
                name=collection_name,
                metadata=metadata or {}
            )
            logger.info(f"Created new collection: {collection_name}")

        return collection

    def get_or_create_collection(self, repo_name: str) -> chromadb.Collection:
        """Get or create a collection for a repository"""
        collection_name = repo_name.replace("/", "_").replace("-", "_").lower()
        return self.create_collection(collection_name)

    def _validate_metadata(
            self,
            metadatas: List[Dict[str, Any]],
            ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        CRITICAL: Validate and fix all metadata before ChromaDB
        NEVER returns None - always returns valid dict to avoid ChromaDB 0.4.22 bug

        Args:
            metadatas: List of metadata dicts
            ids: List of document IDs

        Returns:
            List of validated metadata dicts (NEVER None)
        """
        validated = []

        for i, (meta, doc_id) in enumerate(zip(metadatas, ids)):
            # Check if completely empty or None
            if meta is None or not isinstance(meta, dict) or len(meta) == 0:
                print(f"WARNING: Empty/invalid metadata at index {i}, id: {doc_id}")

                # CRITICAL FIX: NEVER use None! Create minimal valid metadata
                meta = {
                    "source": doc_id.split("_chunk_")[0] if "_chunk_" in doc_id else "unknown",
                    "type": "document"
                }
                print(f"  Using minimal metadata: {meta}")

            # CRITICAL: Convert ALL values to proper types for ChromaDB
            clean_meta = {}

            for key, value in meta.items():
                # ChromaDB supported types: str, int, float, bool
                # But for safety, converting all to strings
                if value is None:
                    clean_meta[key] = "null"
                elif isinstance(value, bool):
                    clean_meta[key] = "true" if value else "false"
                elif isinstance(value, (int, float)):
                    # CRITICAL: Convert int/float to string!
                    clean_meta[key] = str(value)
                elif isinstance(value, str):
                    clean_meta[key] = value
                else:
                    # Convert other types to string too
                    clean_meta[key] = str(value)

            # Final validation: Still empty after cleaning? (should never happen now)
            if not clean_meta or len(clean_meta) == 0:
                print(f"CRITICAL: Metadata became empty after cleaning at index {i}")
                clean_meta = {"source": "emergency_default", "type": "document"}

            # Debug: show what we're adding
            if i == 0:  # First item debug
                print(f"  Cleaned metadata sample: {clean_meta}")

            validated.append(clean_meta)

        return validated

    def add_documents(
            self,
            collection_name: str,
            documents: List[str],
            metadatas: List[Dict[str, Any]],
            ids: List[str],
            embeddings: Optional[List[List[float]]] = None
    ) -> bool:
        """Add documents to a collection with extensive validation"""
        try:
            print(f"\nChromaDB add_documents called:")
            print(f"  Collection: {collection_name}")
            print(f"  Documents: {len(documents)}")
            print(f"  Metadatas: {len(metadatas)}")
            print(f"  IDs: {len(ids)}")
            print(f"  Embeddings: {len(embeddings) if embeddings else 'None'}")

            print(f"  Sample (BEFORE validation): {metadatas[0]}")

            # CRITICAL: Validate all metadata - NEVER returns None now!
            validated_metadatas = self._validate_metadata(metadatas, ids)

            print(f"  Sample (AFTER validation): {validated_metadatas[0]}")
            print(f"  chunk_index type: {type(validated_metadatas[0].get('chunk_index'))}")

            print(f"  Metadata validated: {len(validated_metadatas)} items")

            try:
                collection = self.client.get_collection(name=collection_name)
                print(f"  Using existing collection: {collection_name}")
            except:
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "l2"}  # Never use empty dict!
                )
                print(f"  Created new collection: {collection_name}")

            # Add documents in batches
            batch_size = 500
            total_batches = (len(documents) + batch_size - 1) // batch_size

            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(documents))

                batch_docs = documents[start_idx:end_idx]
                # CRITICAL FIX: Deep copy metadata! ChromaDB mutates the list!
                batch_metas = [meta.copy() for meta in validated_metadatas[start_idx:end_idx]]
                batch_ids = ids[start_idx:end_idx]
                batch_embeddings = embeddings[start_idx:end_idx] if embeddings else None

                print(f"  Batch {batch_num + 1}/{total_batches}: {len(batch_docs)} docs")

                # Final safety check - should never have None/empty now
                for idx, meta in enumerate(batch_metas):
                    if not meta or len(meta) == 0:
                        print(f"    CRITICAL: Empty metadata found at {idx}!")
                        batch_metas[idx] = {"source": "emergency", "type": "document"}

                # DEBUG: Log exactly what we're sending to ChromaDB
                if batch_num == 0:
                    print(f"    FINAL CHECK before ChromaDB:")
                    print(f"       First metadata: {batch_metas[0]}")
                    print(f"       Type: {type(batch_metas[0])}")
                    print(f"       Is dict: {isinstance(batch_metas[0], dict)}")
                    print(f"       Length: {len(batch_metas[0])}")

                try:
                    print(f"    ENTERING TRY BLOCK")
                    print(f"    batch_metas length: {len(batch_metas)}")
                    print(f"    batch_metas[0]: {batch_metas[0]}")
                    print(f"    batch_metas type: {type(batch_metas)}")
                    # WORKAROUND: ChromaDB 0.4.22 bug - store in variables first!
                    _docs = list(batch_docs)
                    _metas = [dict(m) for m in batch_metas]  # Deep copy each dict!
                    _ids = list(batch_ids)
                    _embs = [list(e) for e in batch_embeddings] if batch_embeddings else None

                    # Send to ChromaDB - guaranteed no None or {} now!
                    # LAST RESORT: Add one by one (bypass ChromaDB batch bug)
                    if _embs:
                        for i in range(len(_docs)):
                            try:
                                collection.add(
                                    documents=[_docs[i]],
                                    metadatas=[_metas[i]],
                                    ids=[_ids[i]],
                                    embeddings=[_embs[i]]
                                )
                                print(f"          Item {i + 1} added")
                            except Exception as e:
                                print(f"          Item {i + 1} FAILED: {e}")
                                print(f"          Metadata: {_metas[i]}")
                                raise
                    else:
                        for i in range(len(_docs)):
                            try:
                                collection.add(
                                    documents=[_docs[i]],
                                    metadatas=[_metas[i]],
                                    ids=[_ids[i]]
                                )
                                print(f"          Item {i + 1} added")
                            except Exception as e:
                                print(f"          Item {i + 1} FAILED: {e}")
                                print(f"          Metadata: {_metas[i]}")
                                raise

                    print(f"Batch {batch_num + 1} added successfully")
                    logger.info(f"Added batch {batch_num + 1} ({len(batch_docs)} documents)")

                except Exception as batch_error:
                    print(f"Batch error: {batch_error}")
                    print(f"First 3 metadata for debugging:")
                    for i, meta in enumerate(batch_metas[:3]):
                        print(f"       [{i}]: {meta} (type: {type(meta)}, len: {len(meta)})")
                    logger.error(f"Error adding batch {batch_num + 1}: {batch_error}")
                    raise

            print(f"All {len(documents)} documents added successfully!\n")
            return True

        except Exception as e:
            print(f"ChromaDB add_documents failed: {e}\n")
            logger.error(f"Error adding documents to {collection_name}: {e}")
            return False

    def query(
            self,
            collection_name: str,
            query_texts: List[str],
            n_results: int = 5,
            where: Optional[Dict[str, Any]] = None,
            query_embeddings: Optional[List[List[float]]] = None
    ) -> Dict[str, Any]:
        """Query the collection for similar documents"""
        try:
            collection = self.client.get_collection(name=collection_name)

            if collection.count() == 0:
                logger.warning(f"Collection {collection_name} is empty")
                return {
                    "documents": [[]],
                    "metadatas": [[]],
                    "distances": [[]],
                    "ids": [[]]
                }

            if query_embeddings:
                results = collection.query(
                    query_embeddings=query_embeddings,
                    n_results=min(n_results, collection.count()),
                    where=where,
                    include=["documents", "metadatas", "distances"]
                )
            else:
                results = collection.query(
                    query_texts=query_texts,
                    n_results=min(n_results, collection.count()),
                    where=where,
                    include=["documents", "metadatas", "distances"]
                )

            logger.info(f"Query returned {len(results['ids'][0])} results")
            return results

        except Exception as e:
            logger.error(f"Error querying {collection_name}: {e}")
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
                "ids": [[]]
            }

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics about a collection"""
        try:
            collection = self.client.get_collection(name=collection_name)
            count = collection.count()

            return {
                "name": collection_name,
                "count": count,
                "metadata": collection.metadata
            }
        except Exception as e:
            logger.error(f"Error getting stats for collection {collection_name}: {e}")
            return {
                "name": collection_name,
                "count": 0,
                "error": str(e)
            }

    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection"""
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False

    def list_collections(self) -> List[str]:
        """List all collections"""
        collections = self.client.list_collections()
        return [col.name for col in collections]


# Singleton
_chroma_service: Optional[ChromaDBService] = None

def get_chroma_service() -> ChromaDBService:
    global _chroma_service
    if _chroma_service is None:
        _chroma_service = ChromaDBService()
    return _chroma_service

chroma_service = get_chroma_service()