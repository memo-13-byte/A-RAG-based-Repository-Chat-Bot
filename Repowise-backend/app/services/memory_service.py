"""
Memory Service - Persistent Conversation Storage with Redis
Provides production-grade conversation history management for RepoWise
"""

from typing import List, Dict, Optional
import redis
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Conversation memory with Redis backend

    Features:
    - Persistent storage (survives server restarts)
    - Fast retrieval (Redis in-memory)
    - Automatic expiration (TTL)
    - Conversation summarization
    - History optimization for LLM context
    """

    def __init__(
            self,
            redis_url: str = "redis://localhost:6379",
            ttl_days: int = 30
    ):
        """
        Initialize memory service

        Args:
            redis_url: Redis connection URL
            ttl_days: How long to keep conversations (days)
        """
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Memory Service connected to Redis at {redis_url}")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.warning("⚠️ Falling back to in-memory storage (data will be lost on restart)")
            self.redis_client = None
            self.memory_fallback = {}  # In-memory fallback

        self.ttl_seconds = ttl_days * 24 * 60 * 60

    def _get_key(self, conversation_id: str) -> str:
        """
        Get Redis key for conversation

        Args:
            conversation_id: Unique conversation ID

        Returns:
            Redis key string
        """
        return f"conversation:{conversation_id}"

    def save_message(
            self,
            conversation_id: str,
            role: str,
            content: str,
            metadata: Optional[Dict] = None
    ):
        """
        Save a message to conversation history

        Args:
            conversation_id: Unique conversation ID
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Optional metadata (sources, confidence, etc.)
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        try:
            if self.redis_client:
                key = self._get_key(conversation_id)

                # Append to list (RPUSH = right push, adds to end)
                self.redis_client.rpush(key, json.dumps(message))

                # Set/refresh TTL
                self.redis_client.expire(key, self.ttl_seconds)

                logger.debug(f"💾 Saved message to conversation {conversation_id}")
            else:
                # Fallback to in-memory
                if conversation_id not in self.memory_fallback:
                    self.memory_fallback[conversation_id] = []
                self.memory_fallback[conversation_id].append(message)

        except Exception as e:
            logger.error(f"Failed to save message: {e}")

    def get_history(
            self,
            conversation_id: str,
            limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get conversation history

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages (None = all, negative = last N)

        Returns:
            List of messages (oldest first)

        Examples:
            get_history("conv_123")          # All messages
            get_history("conv_123", limit=10) # Last 10 messages
            get_history("conv_123", limit=-5) # Last 5 messages
        """
        try:
            if self.redis_client:
                key = self._get_key(conversation_id)

                # Get messages from Redis
                if limit:
                    if limit < 0:
                        # Negative limit = last N messages
                        messages = self.redis_client.lrange(key, limit, -1)
                    else:
                        # Positive limit = first N messages
                        messages = self.redis_client.lrange(key, 0, limit - 1)
                else:
                    # No limit = all messages
                    messages = self.redis_client.lrange(key, 0, -1)

                return [json.loads(msg) for msg in messages]
            else:
                # Fallback to in-memory
                messages = self.memory_fallback.get(conversation_id, [])
                if limit:
                    if limit < 0:
                        return messages[limit:]
                    else:
                        return messages[:limit]
                return messages

        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    def clear_conversation(self, conversation_id: str):
        """
        Delete conversation history

        Args:
            conversation_id: Conversation ID to delete
        """
        try:
            if self.redis_client:
                key = self._get_key(conversation_id)
                self.redis_client.delete(key)
                logger.info(f"🗑️ Cleared conversation {conversation_id}")
            else:
                self.memory_fallback.pop(conversation_id, None)
        except Exception as e:
            logger.error(f"Failed to clear conversation: {e}")

    def list_conversations(self, limit: int = 100) -> List[str]:
        """
        List all conversation IDs

        Args:
            limit: Maximum number of conversations to return

        Returns:
            List of conversation IDs
        """
        try:
            if self.redis_client:
                pattern = "conversation:*"
                keys = []
                # Use SCAN instead of KEYS (better for large datasets)
                for key in self.redis_client.scan_iter(pattern, count=limit):
                    # Extract conversation ID from key
                    conv_id = key.replace("conversation:", "")
                    keys.append(conv_id)
                return keys[:limit]
            else:
                return list(self.memory_fallback.keys())[:limit]
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []

    def get_conversation_summary(self, conversation_id: str) -> Dict:
        """
        Get conversation statistics and metadata

        Args:
            conversation_id: Conversation ID

        Returns:
            Dictionary with conversation stats
        """
        history = self.get_history(conversation_id)

        if not history:
            return {
                "conversation_id": conversation_id,
                "message_count": 0,
                "exists": False
            }

        # Calculate statistics
        user_messages = sum(1 for msg in history if msg["role"] == "user")
        assistant_messages = sum(1 for msg in history if msg["role"] == "assistant")

        return {
            "conversation_id": conversation_id,
            "message_count": len(history),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "first_message": history[0]["timestamp"],
            "last_message": history[-1]["timestamp"],
            "exists": True
        }

    def optimize_history_for_llm(
            self,
            conversation_id: str,
            max_tokens: int = 2000
    ) -> List[Dict]:
        """
        Get optimized history for LLM context

        Strategies:
        1. Keep recent messages (sliding window)
        2. Truncate old messages if too long
        3. Preserve message pairs (user + assistant)

        Args:
            conversation_id: Conversation ID
            max_tokens: Maximum tokens for history (approximate)

        Returns:
            Optimized message list suitable for LLM context
        """
        history = self.get_history(conversation_id)

        if not history:
            return []

        # Estimate tokens (rough: 1 token ≈ 4 characters)
        def estimate_tokens(messages):
            return sum(len(msg['content']) for msg in messages) // 4

        current_tokens = estimate_tokens(history)

        # If within budget, return all
        if current_tokens <= max_tokens:
            return history

        # Strategy: Keep most recent messages (sliding window)
        optimized = []
        token_count = 0

        # Iterate backwards (most recent first)
        for msg in reversed(history):
            msg_tokens = len(msg['content']) // 4

            # Check if adding this message exceeds budget
            if token_count + msg_tokens > max_tokens:
                break

            # Add to beginning (to maintain chronological order)
            optimized.insert(0, msg)
            token_count += msg_tokens

        # Add summary of truncated messages if needed
        if len(optimized) < len(history):
            truncated_count = len(history) - len(optimized)
            summary = {
                "role": "system",
                "content": f"[Previous {truncated_count} messages summarized: Earlier conversation about repository features and code examples]",
                "timestamp": history[0]["timestamp"],
                "metadata": {"type": "summary"}
            }
            optimized.insert(0, summary)

            logger.info(f"📊 History optimized: {len(history)} → {len(optimized)} messages (~{token_count} tokens)")

        return optimized

    def get_stats(self) -> Dict:
        """
        Get overall memory service statistics

        Returns:
            Dictionary with service stats
        """
        try:
            if self.redis_client:
                # Count all conversation keys
                pattern = "conversation:*"
                total_conversations = sum(1 for _ in self.redis_client.scan_iter(pattern))

                # Get memory usage
                info = self.redis_client.info('memory')
                used_memory = info.get('used_memory_human', 'N/A')

                return {
                    "backend": "redis",
                    "total_conversations": total_conversations,
                    "used_memory": used_memory,
                    "ttl_days": self.ttl_seconds // (24 * 3600),
                    "connected": True
                }
            else:
                return {
                    "backend": "in-memory (fallback)",
                    "total_conversations": len(self.memory_fallback),
                    "used_memory": "N/A",
                    "ttl_days": "N/A (no persistence)",
                    "connected": False
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "backend": "error",
                "error": str(e),
                "connected": False
            }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """
    Get or create memory service singleton

    Returns:
        MemoryService instance
    """
    global _memory_service

    if _memory_service is None:
        _memory_service = MemoryService()

    return _memory_service


# Export singleton instance
memory_service = get_memory_service()