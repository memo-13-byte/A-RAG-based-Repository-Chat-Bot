"""
LLM Service - Large Language Model Integration

Supports:
- OpenAI (GPT-3.5-turbo, GPT-4)
- Custom prompt templates
- Token counting and management
- Error handling and retries
"""

from typing import Optional, List, Dict, Any
from enum import Enum
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import logging

logger = logging.getLogger(__name__)

class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"

class LLModel(str, Enum):
    """Supported models"""
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo-preview"

class LLMService:
    """
    Service for interacting with Large Language Models
    """

    def __init__(
                self,
                 provider: LLMProvider = LLMProvider.OPENAI,
                 model: Optional[str] = None,
                 temperature: float = 0.7,
                 max_tokens: Optional[int] = None,
                 ):

        """
        Initialize LLM Service

        Args:
            provider: LLM provider (openai)
            model: Model name (defaults based on provider)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
        """
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Set default model based on provider
        if model is None:
            if provider == LLMProvider.OPENAI:
                model = LLModel.GPT_3_5_TURBO.value

        self.model = model
        self.llm = self._initialize_llm()

    def _initialize_llm(self):
        """Initialize the LLM client based on provider"""
        try:
            if self.provider == LLMProvider.OPENAI:
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

            else:
                raise ValueError(f"Unsupported LLM provider: {self.provider}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
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
            logger.info(f"Generating response with {len(messages)} messages")
            response = self.llm.invoke(messages, **kwargs)

            return response.content

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

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
        # Rough estimation: 1 token ≈ 4 characters
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


# Singleton instance
_llm_service_instance: Optional[LLMService] = None


def get_llm_service(
        provider: LLMProvider = LLMProvider.OPENAI,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
) -> LLMService:
    """
    Get or create LLM service instance

    Args:
        provider: LLM provider
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


# Example usage
if __name__ == "__main__":
    # Test the service
    print("Testing LLM Service...")

    # Simple generation
    response = llm_service.generate("What is Python?")
    print(f"\nSimple generation:\n{response}\n")

    # With system message
    response = llm_service.generate(
        "Explain list comprehensions",
        system_message="You are a Python expert. Explain concepts clearly and concisely."
    )
    print(f"\nWith system message:\n{response}\n")

    # Using template
    response = llm_service.generate_with_template(
        "code_explanation",
        variables={
            "language": "Python",
            "code": "def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"
        }
    )
    print(f"\nUsing template:\n{response}\n")

    # With chat history
    history = [
        {"role": "user", "content": "What is recursion?"},
        {"role": "assistant", "content": "Recursion is when a function calls itself."}
    ]
    response = llm_service.generate(
        "Can you give me an example?",
        chat_history=history
    )
    print(f"\nWith chat history:\n{response}\n")
