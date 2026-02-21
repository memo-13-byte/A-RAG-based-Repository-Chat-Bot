"""
LLM Service - Large Language Model Integration

Supports:
- Groq (Llama-3-70B) - FREE & FAST - Priority 1
- OpenAI (GPT-3.5-turbo, GPT-4) - PAID - Priority 2
- Rule-based Fallback - Always available - Priority 3
- Custom prompt templates
- Token counting and management
- Error handling and retries
"""

from typing import Optional, List, Dict, Any
from enum import Enum
import os
import logging

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    GROQ = "groq"
    OPENAI = "openai"
    FALLBACK = "fallback"


class LLModel(str, Enum):
    """Supported models"""
    # Groq models (FREE)
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"  # NEW (Recommended)
    LLAMA_3_1_8B = "llama-3.1-8b-instant"      # Fast
    MIXTRAL = "mixtral-8x7b-32768"              # Good for code

    # OpenAI models (PAID)
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo-preview"


class LLMService:
    """
    Service for interacting with Large Language Models

    Priority order:
    1. Groq (if GROQ_API_KEY is set) - FREE & FAST
    2. OpenAI (if OPENAI_API_KEY is set) - PAID
    3. Rule-based fallback - Always available
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ):
        """
        Initialize LLM Service with automatic provider selection

        Args:
            provider: LLM provider (auto-detected if None)
            model: Model name (defaults based on provider)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
        """
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Auto-detect provider if not specified
        if provider is None:
            provider = self._detect_provider()

        self.provider = provider

        # Set default model based on provider
        if model is None:
            if provider == LLMProvider.GROQ:
                model = LLModel.LLAMA_3_3_70B.value  # NEW
            elif provider == LLMProvider.OPENAI:
                model = LLModel.GPT_3_5_TURBO.value
            else:
                model = "fallback"

        self.model = model
        self.llm = self._initialize_llm()

        logger.info(f"LLM Service initialized: provider={self.provider}, model={self.model}")

    def _detect_provider(self) -> LLMProvider:
        """
        Auto-detect available LLM provider

        Priority: Groq -> OpenAI -> Fallback

        Returns:
            LLMProvider: Detected provider
        """
        # Check Groq (priority 1 - FREE)
        if os.getenv("GROQ_API_KEY"):
            logger.info("Groq API key detected (FREE & FAST)")
            return LLMProvider.GROQ

        # Check OpenAI (priority 2 - PAID)
        if os.getenv("OPENAI_API_KEY"):
            logger.info("OpenAI API key detected (PAID)")
            return LLMProvider.OPENAI

        # Fallback (priority 3 - always available)
        logger.warning("No LLM API keys found - using rule-based fallback")
        return LLMProvider.FALLBACK

    def _initialize_llm(self):
        """Initialize the LLM client based on provider"""
        try:
            if self.provider == LLMProvider.GROQ:
                return self._initialize_groq()

            elif self.provider == LLMProvider.OPENAI:
                return self._initialize_openai()

            elif self.provider == LLMProvider.FALLBACK:
                logger.info("Using rule-based fallback (no LLM)")
                return None

            else:
                raise ValueError(f"Unsupported LLM provider: {self.provider}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM ({self.provider}): {e}")
            logger.warning("Falling back to rule-based responses")
            self.provider = LLMProvider.FALLBACK
            return None

    def _initialize_groq(self):
        """Initialize Groq client"""
        try:
            from groq import Groq

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY not found in environment variables")

            logger.info(f"Initializing Groq with model: {self.model}")
            return Groq(api_key=api_key)

        except ImportError:
            logger.error("Groq package not installed. Run: pip install groq")
            raise
        except Exception as e:
            logger.error(f"Groq initialization failed: {e}")
            raise

    def _initialize_openai(self):
        """Initialize OpenAI client"""
        try:
            from langchain_openai import ChatOpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")

            logger.info(f"Initializing OpenAI with model: {self.model}")
            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
            )

        except ImportError:
            logger.error("LangChain OpenAI package not installed")
            raise
        except Exception as e:
            logger.error(f"OpenAI initialization failed: {e}")
            raise

    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> str:
        """
        Generate a response from the LLM

        Args:
            prompt: User prompt/query
            system_message: System message to set context
            chat_history: Previous conversation history
                Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            **kwargs: Additional arguments for LLM

        Returns:
            Generated response text
        """
        try:
            # Route to appropriate provider
            if self.provider == LLMProvider.GROQ and self.llm:
                return self._generate_groq(prompt, system_message, chat_history, **kwargs)

            elif self.provider == LLMProvider.OPENAI and self.llm:
                return self._generate_openai(prompt, system_message, chat_history, **kwargs)

            else:
                # Fallback to rule-based
                return self._generate_fallback(prompt)

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            logger.info("Falling back to rule-based response")
            return self._generate_fallback(prompt)

    def _generate_groq(
        self,
        prompt: str,
        system_message: Optional[str],
        chat_history: Optional[List[Dict[str, str]]],
        **kwargs
    ) -> str:
        """Generate response using Groq"""
        logger.info(f"Generating with Groq ({self.model})")

        # Build messages
        messages = []

        # System message
        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })
        else:
            messages.append({
                "role": "system",
                "content": "You are a helpful AI assistant specializing in code repositories. Provide clear, concise answers."
            })

        # Chat history
        if chat_history:
            for msg in chat_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Current prompt
        messages.append({
            "role": "user",
            "content": prompt
        })

        # Prepare parameters - avoid duplicate kwargs
        params = {
            "model": self.model,
            "messages": messages,
        }

        # Add temperature if not in kwargs
        if "temperature" not in kwargs:
            params["temperature"] = self.temperature

        # Add max_tokens if not in kwargs
        if "max_tokens" not in kwargs:
            params["max_tokens"] = self.max_tokens or 500

        # Merge kwargs (they will override defaults if present)
        params.update(kwargs)

        # Generate
        response = self.llm.chat.completions.create(**params)

        return response.choices[0].message.content

    def _generate_openai(
        self,
        prompt: str,
        system_message: Optional[str],
        chat_history: Optional[List[Dict[str, str]]],
        **kwargs
    ) -> str:
        """Generate response using OpenAI (LangChain)"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        logger.info(f"Generating with OpenAI ({self.model})")

        messages = []

        # Add system message
        if system_message:
            messages.append(SystemMessage(content=system_message))

        # Add chat history
        if chat_history:
            for msg in chat_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        # Add current prompt
        messages.append(HumanMessage(content=prompt))

        # Generate response
        response = self.llm.invoke(messages, **kwargs)
        return response.content

    async def generate_stream(
            self,
            prompt: str,
            system_message: Optional[str] = None,
            chat_history: Optional[List[Dict[str, str]]] = None,
            **kwargs
    ):
        """
        Generate response with streaming support

        Yields:
            str: Response chunks as they arrive
        """
        try:
            # Build messages
            messages = []

            # System message
            if system_message:
                messages.append({
                    "role": "system",
                    "content": system_message
                })
            else:
                messages.append({
                    "role": "system",
                    "content": "You are a helpful AI assistant specializing in code repositories."
                })

            # Chat history
            if chat_history:
                messages.extend(chat_history)

            # User prompt
            messages.append({
                "role": "user",
                "content": prompt
            })

            # Prepare parameters
            params = {
                "model": self.model,
                "messages": messages,
                "stream": True,  # ← STREAMING ENABLED!
            }

            # Add temperature
            if "temperature" not in kwargs:
                params["temperature"] = self.temperature
            else:
                params["temperature"] = kwargs["temperature"]

            # Add max_tokens
            if "max_tokens" not in kwargs:
                params["max_tokens"] = self.max_tokens or 500
            else:
                params["max_tokens"] = kwargs["max_tokens"]

            # Generate with streaming
            if self.provider == LLMProvider.GROQ:
                logger.info(f"Streaming with Groq ({self.model})")
                response = self.llm.chat.completions.create(**params)

                # Yield chunks
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            elif self.provider == LLMProvider.OPENAI:
                logger.info(f"Streaming with OpenAI ({self.model})")
                response = self.llm.chat.completions.create(**params)

                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            else:
                # Fallback: Simulate streaming
                logger.info("Streaming with fallback (simulated)")
                response = self._generate_fallback(prompt)

                # Yield word by word
                import asyncio
                words = response.split()
                for i, word in enumerate(words):
                    if i == 0:
                        yield word
                    else:
                        yield " " + word
                    await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise

    def _generate_fallback(self, prompt: str) -> str:
        """
        Rule-based fallback response when no LLM available

        Args:
            prompt: User question

        Returns:
            Rule-based response
        """
        logger.info("Using rule-based fallback")

        prompt_lower = prompt.lower()

        # Purpose/description questions
        if any(word in prompt_lower for word in ["what", "describe", "explain", "purpose", "about"]):
            return (
                "Based on the repository information, you can find details about this project "
                "in the README file and repository statistics. The description and primary "
                "language provide good context about what this repository does."
            )

        # Statistics questions
        elif any(word in prompt_lower for word in ["how many", "count", "number", "statistics", "stats"]):
            return (
                "You can find detailed statistics including stars, forks, open issues, and "
                "contributors in the repository statistics section. Check the stats endpoint "
                "for comprehensive metrics."
            )

        # Installation questions
        elif any(word in prompt_lower for word in ["install", "setup", "how to use", "get started"]):
            return (
                "Installation instructions are typically found in the README file. "
                "Look for sections titled 'Installation', 'Getting Started', or 'Setup'. "
                "Most projects also include a requirements.txt or package.json file."
            )

        # Language questions
        elif "language" in prompt_lower:
            return (
                "The primary programming language and full language distribution are shown "
                "in the repository information. Check the statistics section for a detailed "
                "breakdown of all languages used in the codebase."
            )

        # Contributors questions
        elif any(word in prompt_lower for word in ["contributor", "author", "maintainer", "developer"]):
            return (
                "You can find the top contributors and their contribution counts in the "
                "repository statistics section. This includes information about the most "
                "active developers and their commit history."
            )

        # Recent activity
        elif any(word in prompt_lower for word in ["recent", "latest", "update", "commit"]):
            return (
                "Recent activity including the latest commits, their authors, and commit "
                "messages can be found in the repository information. Check the commits "
                "section for detailed update history."
            )

        # Default
        else:
            return (
                "I don't have enough context to provide a detailed answer. "
                "Please check the repository README, statistics, or file structure for more information. "
                "You can also try asking more specific questions about the repository's purpose, "
                "installation, or contributors."
            )

    def generate_with_template(
        self,
        template_name: str,
        variables: Dict[str, Any],
        **kwargs
    ) -> str:
        """
        Generate response using a predefined template

        Args:
            template_name: Name of the template
            variables: Variables to fill in the template
            **kwargs: Additional arguments

        Returns:
            Generated response
        """
        template = self._get_template(template_name)
        prompt = template.format(**variables)
        return self.generate(prompt, **kwargs)

    def _get_template(self, template_name: str) -> str:
        """Get a prompt template by name"""
        templates = {
            "code_explanation": """Analyze the following code and explain what it does:

```{language}
{code}
```

Provide a clear, concise explanation focusing on:
1. What the code does
2. Key functionality
3. Important patterns or techniques used

Explanation:""",

            "code_improvement": """Review the following code and suggest improvements:

```{language}
{code}
```

Context: {context}

Suggest improvements for:
1. Code quality and readability
2. Performance optimizations
3. Best practices
4. Potential bugs

Suggestions:""",

            "bug_detection": """Analyze the following code for potential bugs:

```{language}
{code}
```

Look for:
1. Logic errors
2. Edge cases not handled
3. Potential runtime errors
4. Security vulnerabilities

Findings:""",

            "documentation": """Generate documentation for the following code:

```{language}
{code}
```

Include:
1. Brief description
2. Parameters (if any)
3. Return values (if any)
4. Usage examples

Documentation:""",

            "repository_summary": """Based on the following information about a repository, provide a comprehensive summary:

Repository: {repo_name}
Description: {description}
Language: {language}
README excerpt: {readme}

Summarize:
1. What the repository does
2. Main features
3. Target use cases
4. Key technologies

Summary:"""
        }

        if template_name not in templates:
            raise ValueError(f"Template '{template_name}' not found")

        return templates[template_name]

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text

        Args:
            text: Input text

        Returns:
            Approximate token count
        """
        # Rough estimation: 1 token approximately equals 4 characters
        return len(text) // 4

    def switch_model(self, model: str):
        """
        Switch to a different model

        Args:
            model: New model name
        """
        self.model = model
        self.llm = self._initialize_llm()
        logger.info(f"Switched to model: {model}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current LLM service status

        Returns:
            Dictionary with status information
        """
        return {
            "provider": self.provider.value,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "available": self.llm is not None or self.provider == LLMProvider.FALLBACK,
            "api_key_set": {
                "groq": bool(os.getenv("GROQ_API_KEY")),
                "openai": bool(os.getenv("OPENAI_API_KEY")),
            }
        }


# Singleton instance
_llm_service_instance: Optional[LLMService] = None


def get_llm_service(
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> LLMService:
    """
    Get or create LLM service instance

    Args:
        provider: LLM provider (auto-detected if None)
        model: Model name
        temperature: Sampling temperature
        max_tokens: Maximum tokens

    Returns:
        LLMService instance
    """
    global _llm_service_instance

    if _llm_service_instance is None:
        _llm_service_instance = LLMService(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    return _llm_service_instance


# Export
llm_service = get_llm_service()


# Example usage and testing
if __name__ == "__main__":
    print("=" * 80)
    print("Testing LLM Service")
    print("=" * 80)

    # Show status
    status = llm_service.get_status()
    print(f"\nStatus:")
    print(f"  Provider: {status['provider']}")
    print(f"  Model: {status['model']}")
    print(f"  Available: {status['available']}")
    print(f"  Groq key: {'[SET]' if status['api_key_set']['groq'] else '[NOT SET]'}")
    print(f"  OpenAI key: {'[SET]' if status['api_key_set']['openai'] else '[NOT SET]'}")

    # Test generation
    print("\n" + "=" * 80)
    print("Test 1: Simple generation")
    print("=" * 80)
    response = llm_service.generate("What is Python? Answer in one sentence.")
    print(f"Response:\n{response}\n")

    # With system message
    print("=" * 80)
    print("Test 2: With system message")
    print("=" * 80)
    response = llm_service.generate(
        "Explain list comprehensions",
        system_message="You are a Python expert. Explain concepts clearly and concisely."
    )
    print(f"Response:\n{response}\n")

    # Using template
    print("=" * 80)
    print("Test 3: Using template")
    print("=" * 80)
    response = llm_service.generate_with_template(
        "code_explanation",
        variables={
            "language": "Python",
            "code": "def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"
        }
    )
    print(f"Response:\n{response}\n")

    # With chat history
    print("=" * 80)
    print("Test 4: With chat history")
    print("=" * 80)
    history = [
        {"role": "user", "content": "What is recursion?"},
        {"role": "assistant", "content": "Recursion is when a function calls itself."}
    ]
    response = llm_service.generate(
        "Can you give me an example?",
        chat_history=history
    )
    print(f"Response:\n{response}\n")

    print("=" * 80)
    print("All tests complete!")
    print("=" * 80)