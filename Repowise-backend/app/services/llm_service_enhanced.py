from typing import Optional, List, Dict, Any
import logging
import time
from functools import wraps
from .llm_service import LLMService, LLMProvider, LLModel

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SYSTEM_PROMPT_ADVANCED = """You are RepoWise AI, an expert software engineering assistant specialized in code repository analysis and documentation.

YOUR CAPABILITIES:
- Deep understanding of software architecture and design patterns
- Expertise in 20+ programming languages (Python, JavaScript, Java, Go, Rust, C++, etc.)
- Knowledge of modern development practices (CI/CD, testing, documentation)
- Understanding of git workflows, version control, and collaboration patterns

YOUR GOALS:
1. Provide accurate, actionable answers based on the repository context provided
2. Cite specific files, functions, and code snippets when relevant
3. Explain complex concepts in clear, accessible language
4. Suggest best practices and improvements when appropriate
5. Acknowledge uncertainty when context is insufficient

RESPONSE STYLE:
- Be direct and specific - avoid vague or generic statements
- Use code examples to illustrate technical points
- Structure longer answers with clear sections
- Prioritize correctness over speed - take time to analyze properly

CONTEXT AWARENESS:
- You have access to repository files, commit history, and documentation
- When citing sources, reference specific files and line numbers when possible
- If multiple interpretations exist, present the most likely one first
- If you're uncertain, explain what additional context would help

IMPORTANT: Your answers directly impact developer productivity. Always prioritize accuracy and helpfulness over brevity."""

COT_SYSTEM_PROMPT = """For complex queries, use step-by-step reasoning:

THINKING PROCESS:
1. Understand the Question: What is the user really asking?
2. Analyze Context: What relevant information do I have from the repository?
3. Break Down Problem: What are the sub-questions I need to answer?
4. Reason Through Each: Address each part systematically
5. Synthesize Answer: Combine insights into coherent response

EXAMPLE REASONING:
Query: "Why is my API endpoint returning 500 errors?"

THINKING:
1. User has a production issue - need to diagnose server errors
2. Check: error handling code, database queries, external dependencies
3. Sub-questions: What triggers the endpoint? What operations happen? Where could it fail?
4. Analysis: [examine code patterns, identify potential failure points]
5. Answer: [specific findings with file references + recommendations]

Use this approach for: debugging, architecture questions, optimization queries, comparison requests."""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_optimal_temperature(query: str, intent: str = None) -> float:
    """
    Determine optimal temperature based on query type

    Args:
        query: User query
        intent: Detected intent (structure/dependency/history/usage/implementation)

    Returns:
        float: Temperature between 0.0 (deterministic) and 1.0 (creative)
    """
    query_lower = query.lower()

    # FACTUAL/STRUCTURAL queries → Very low temperature (deterministic)
    if intent in ['structure', 'dependency', 'history']:
        return 0.2

    # DEBUG/ERROR queries → Lowest temperature (precision critical)
    if any(word in query_lower for word in ['bug', 'error', 'fix', 'debug', 'crash', 'fail']):
        return 0.1

    # DOCUMENTATION/EXPLANATION queries → Low-medium temperature
    if any(word in query_lower for word in ['document', 'explain', 'what is', 'how does', 'describe']):
        return 0.3

    # CREATIVE/SUGGESTION queries → High temperature
    if any(word in query_lower for word in ['suggest', 'improve', 'alternative', 'better way', 'optimize']):
        return 0.8

    # EXAMPLE/TUTORIAL generation → Medium-high temperature
    if any(word in query_lower for word in ['example', 'sample', 'demo', 'tutorial', 'show me']):
        return 0.7

    # COMPARISON queries → Medium temperature
    if any(word in query_lower for word in ['compare', 'difference', 'versus', 'vs', 'better']):
        return 0.5

    # Default: Medium-low (balanced)
    return 0.4


def get_optimal_max_tokens(query: str, context_length: int = 0) -> int:
    """
    Determine optimal max_tokens based on query complexity

    Args:
        query: User query
        context_length: Length of provided context (in tokens)

    Returns:
        int: Optimal max_tokens
    """
    query_lower = query.lower()

    # SIMPLE factual queries → Short answers
    if any(word in query_lower for word in ['what is', 'when', 'who', 'which', 'where']):
        if len(query.split()) <= 8:
            return 1500

    # LIST queries → Medium answers
    if any(word in query_lower for word in ['list', 'show all', 'enumerate', 'what are']):
        return 1500

    # EXPLANATION queries → Long answers
    if any(word in query_lower for word in ['explain', 'how', 'why', 'describe', 'tell me about']):
        return 2000

    # COMPARISON queries → Very long answers
    if any(word in query_lower for word in ['compare', 'difference', 'versus', 'vs']):
        return 2000

    # TUTORIAL/GUIDE queries → Extra long answers
    if any(word in query_lower for word in ['tutorial', 'guide', 'walkthrough', 'step by step']):
        return 2500

    # CODE GENERATION queries → Based on context, but generous
    if any(word in query_lower for word in ['generate', 'create', 'write code', 'implement']):
        return min(2500, max(1500, context_length // 2))

    # DEBUG queries → Long (need detailed analysis)
    if any(word in query_lower for word in ['debug', 'error', 'bug', 'issue', 'problem']):
        return 1500

    # Default: Medium
    return 1500


def should_use_cot(query: str) -> bool:
    """
    Determine if query benefits from chain-of-thought reasoning

    Args:
        query: User query

    Returns:
        bool: True if CoT should be used
    """
    query_lower = query.lower()

    cot_keywords = [
        'why', 'how come', 'reason', 'cause', 'debug',
        'optimize', 'improve', 'slow', 'error', 'bug',
        'best way', 'should i', 'recommend', 'compare',
        'difference between', 'which is better'
    ]

    return any(keyword in query_lower for keyword in cot_keywords)


def build_optimized_context(contexts: List[Dict], max_tokens: int = 3000) -> str:
    """
    Build optimized context with smart truncation and relevance ranking

    Args:
        contexts: Retrieved context chunks with metadata and similarity scores
        max_tokens: Maximum tokens for context (leave room for answer)

    Returns:
        Optimized context string
    """
    if not contexts:
        return ""

    # Sort by relevance (similarity score)
    sorted_contexts = sorted(
        contexts,
        key=lambda x: x.get('similarity', x.get('score', 0)),
        reverse=True
    )

    # Build context with token budget
    context_parts = []
    current_tokens = 0

    for i, ctx in enumerate(sorted_contexts):
        # Extract metadata
        metadata = ctx.get('metadata', {})
        source = metadata.get('source', 'Unknown')
        language = metadata.get('language', 'text')
        chunk_index = metadata.get('chunk_index', '')
        similarity = ctx.get('similarity', ctx.get('score', 0))

        # Create informative header
        header_parts = [f"[Source {i + 1}: {source}"]
        if chunk_index:
            header_parts.append(f"Part {chunk_index}")
        header_parts.append(f"Relevance: {similarity:.0%}")
        if language and language != 'text':
            header_parts.append(f"Language: {language}")
        header = " | ".join(header_parts) + "]\n"

        # Get content
        content = ctx.get('content', ctx.get('text', ''))

        # Estimate tokens (rough: 1 token ≈ 4 characters)
        content_tokens = len(content) // 4
        header_tokens = len(header) // 4

        # Check if we can fit this context
        if current_tokens + content_tokens + header_tokens > max_tokens:
            # Try to fit a truncated version
            remaining_tokens = max_tokens - current_tokens - header_tokens
            if remaining_tokens > 100:  # Only if we can fit meaningful content
                truncated_content = content[:remaining_tokens * 4]
                # Try to truncate at a natural boundary
                last_newline = truncated_content.rfind('\n')
                if last_newline > len(truncated_content) // 2:
                    truncated_content = truncated_content[:last_newline]

                context_parts.append(header + truncated_content + "\n...[truncated]")
                current_tokens += remaining_tokens
            break

        # Add full context
        context_parts.append(header + content)
        current_tokens += content_tokens + header_tokens

    # Add summary header
    summary = f"""╔══════════════════════════════════════════════════════════════╗
║ RETRIEVED CONTEXT ({len(context_parts)} sources, ~{current_tokens} tokens)
║ Sources ranked by relevance (highest first)
╚══════════════════════════════════════════════════════════════╝

"""

    return summary + "\n\n".join(context_parts)


def reformulate_query(query: str, context_summary: str = "") -> str:
    """
    Reformulate vague queries into more specific ones

    Args:
        query: Original user query
        context_summary: Brief summary of available context

    Returns:
        Reformulated query (or original if already clear)
    """
    query_lower = query.lower().strip()

    # Very vague queries
    if query_lower in ['help', 'what can you do', 'info', 'tell me', '?']:
        return f"""Based on the repository context available, please provide a comprehensive overview including:
1. Main purpose and functionality of this repository
2. Key features and capabilities
3. How to get started (installation/setup instructions)
4. Common use cases and examples
5. Main technologies and dependencies used"""

    # Too broad queries - add specificity request
    if len(query.split()) <= 3 and any(w in query_lower for w in ['how', 'what', 'why']):
        return f"{query} - Please provide a detailed explanation with specific examples from the codebase when possible."

    # Code requests without examples
    if 'code' in query_lower and not any(w in query_lower for w in ['example', 'sample', 'show']):
        return f"{query} - Please include concrete code examples from the repository and explain the implementation details."

    # "How to" queries - add practical focus
    if query_lower.startswith('how to') or query_lower.startswith('how do i'):
        return f"{query} - Please provide step-by-step instructions with code examples."

    return query


def retry_with_exponential_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Retry decorator with exponential backoff for API calls

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # Don't retry on certain errors
                    if any(x in error_msg for x in ['invalid', 'authentication', 'not found', 'unauthorized']):
                        logger.error(f"Non-retryable error: {e}")
                        raise

                    # Last attempt - raise
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise

                    # Log and wait
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)

                    # Exponential backoff with jitter
                    delay = min(delay * 2, 60.0)

            # Should never reach here
            raise last_exception

        return wrapper

    return decorator


# ============================================================================
# ENHANCED LLM SERVICE
# ============================================================================

class EnhancedLLMService(LLMService):
    """
    Enhanced LLM service with all optimizations:
    - Advanced system prompts
    - Dynamic temperature control
    - Optimal token allocation
    - Context optimization
    - Chain-of-thought reasoning
    - Retry logic
    """

    def __init__(self, *args, **kwargs):
        """Initialize with parent class"""
        super().__init__(*args, **kwargs)
        logger.info("Enhanced LLM Service initialized with optimizations")

    @retry_with_exponential_backoff(max_retries=3, base_delay=1.0)
    def generate_enhanced(
            self,
            prompt: str,
            system_message: Optional[str] = None,
            intent: Optional[str] = None,
            context: Optional[str] = None,
            context_length: Optional[int] = None,
            chat_history: Optional[List[Dict[str, str]]] = None,
            **kwargs
    ) -> str:
        """
        Enhanced generation with all optimizations applied

        Args:
            prompt: User query
            system_message: Optional system context (will be enhanced if not provided)
            intent: Query intent for optimization (structure/dependency/history/usage/implementation)
            context: Optimized context string from RAG
            context_length: Estimated context length in tokens
            chat_history: Previous conversation messages
            **kwargs: Additional LLM parameters

        Returns:
            Generated response
        """
        # Calculate context length if not provided
        if context_length is None and context:
            context_length = len(context) // 4
        elif context_length is None:
            context_length = len(system_message or "") // 4

        # 1. OPTIMIZE TEMPERATURE
        if 'temperature' not in kwargs:
            optimal_temp = get_optimal_temperature(prompt, intent)
            kwargs['temperature'] = optimal_temp
            logger.debug(f"Set temperature: {optimal_temp} (intent: {intent})")

        # 2. OPTIMIZE MAX_TOKENS
        if 'max_tokens' not in kwargs:
            optimal_tokens = get_optimal_max_tokens(prompt, context_length)
            kwargs['max_tokens'] = optimal_tokens
            logger.debug(f"Set max_tokens: {optimal_tokens}")

        # 3. ENHANCE SYSTEM MESSAGE
        if not system_message:
            system_message = SYSTEM_PROMPT_ADVANCED

        # Add CoT if needed
        if should_use_cot(prompt):
            system_message = COT_SYSTEM_PROMPT + "\n\n" + system_message
            logger.debug("Chain-of-Thought reasoning enabled")

        # Add context if provided
        if context:
            system_message = system_message + "\n\n" + context

        # 4. REFORMULATE VAGUE QUERIES
        original_prompt = prompt
        prompt = reformulate_query(prompt)
        if prompt != original_prompt:
            logger.debug(f"Query reformulated: '{original_prompt[:50]}...' → '{prompt[:50]}...'")

        # 5. GENERATE WITH PARENT METHOD
        logger.info(f"Generating response (temp={kwargs.get('temperature')}, max_tokens={kwargs.get('max_tokens')})")

        response = self.generate(
            prompt=prompt,
            system_message=system_message,
            chat_history=chat_history,
            **kwargs
        )

        logger.info(f"Response generated: {len(response)} characters")
        return response


    @retry_with_exponential_backoff(max_retries=3, base_delay=1.0)
    async def generate_enhanced_stream(
            self,
            prompt: str,
            system_message: Optional[str] = None,
            intent: Optional[str] = None,
            context: Optional[str] = None,
            context_length: Optional[int] = None,
            chat_history: Optional[List[Dict[str, str]]] = None,
            **kwargs
    ):
        """
        Enhanced generation with streaming support

        Yields:
            str: Response chunks
        """
        # Calculate context length
        if context_length is None and context:
            context_length = len(context) // 4
        elif context_length is None:
            context_length = len(system_message or "") // 4

        # 1. OPTIMIZE TEMPERATURE
        if 'temperature' not in kwargs:
            optimal_temp = get_optimal_temperature(prompt, intent)
            kwargs['temperature'] = optimal_temp
            logger.debug(f"Set temperature: {optimal_temp}")

        # 2. OPTIMIZE MAX_TOKENS
        if 'max_tokens' not in kwargs:
            optimal_tokens = get_optimal_max_tokens(prompt, context_length)
            kwargs['max_tokens'] = optimal_tokens
            logger.debug(f"Set max_tokens: {optimal_tokens}")

        # 3. ENHANCE SYSTEM MESSAGE
        if not system_message:
            system_message = SYSTEM_PROMPT_ADVANCED

        # Add CoT if needed
        if should_use_cot(prompt):
            system_message = COT_SYSTEM_PROMPT + "\n\n" + system_message
            logger.debug("Chain-of-Thought enabled")

        # Add context
        if context:
            system_message = system_message + "\n\n" + context

        # 4. REFORMULATE QUERY
        original_prompt = prompt
        prompt = reformulate_query(prompt)
        if prompt != original_prompt:
            logger.debug(f"Query reformulated")

        # 5. GENERATE WITH STREAMING
        logger.info(f"🌊 Streaming response (temp={kwargs.get('temperature')}, max_tokens={kwargs.get('max_tokens')})")

        # Check if base LLM supports streaming
        if hasattr(self, 'generate_stream'):
            # Use parent's generate_stream
            async for chunk in self.generate_stream(
                    prompt=prompt,
                    system_message=system_message,
                    chat_history=chat_history,
                    **kwargs
            ):
                yield chunk
        else:
            # Fallback: simulate streaming
            logger.warning("Simulating streaming")
            response = self.generate(
                prompt=prompt,
                system_message=system_message,
                chat_history=chat_history,
                **kwargs
            )

            # Yield word by word
            import asyncio
            words = response.split()
            for i, word in enumerate(words):
                if i == 0:
                    yield word
                else:
                    yield " " + word
                await asyncio.sleep(0.01)

# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_enhanced_llm_service: Optional[EnhancedLLMService] = None


def get_enhanced_llm_service() -> EnhancedLLMService:
    """Get or create enhanced LLM service singleton"""
    global _enhanced_llm_service

    if _enhanced_llm_service is None:
        _enhanced_llm_service = EnhancedLLMService()

    return _enhanced_llm_service


# Export
enhanced_llm_service = get_enhanced_llm_service()