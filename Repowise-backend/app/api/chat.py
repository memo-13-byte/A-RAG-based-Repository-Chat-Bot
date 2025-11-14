from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..services.github_service import github_service
from ..services.llm_service import llm_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory conversation storage
conversations = {}


class ChatMessage(BaseModel):
    message: str
    repository_url: Optional[str] = None
    conversation_id: Optional[str] = None
    use_llm: bool = True  # Toggle LLM usage


class ChatResponse(BaseModel):
    message: str
    sources: List[str]
    confidence: float
    conversation_id: str


def generate_conversation_id() -> str:
    """Create unique conversation ID"""
    import uuid
    return f"conv_{uuid.uuid4().hex[:12]}"


def clean_readme_text(readme_content: str, max_length: int = 500) -> str:
    """
    Clean HTML/markdown from README content and return plain text

    Args:
        readme_content: Raw README content
        max_length: Maximum number of characters

    Returns:
        Cleaned text
    """
    import re

    if not readme_content:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', readme_content)

    # Remove Markdown image syntax: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

    # Simplify Markdown link syntax: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Clear Markdown headers: ### Header -> Header
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Reduce multiple spaces to single space
    text = re.sub(r'\s+', ' ', text)

    # Clean leading/trailing spaces
    text = text.strip()

    # Maximum length limit
    if len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + "..."

    return text


def build_repository_context(
        repo_info: dict,
        readme: str,
        message_lower: str,
        repository_url: str
) -> tuple[str, List[str]]:
    """
    Build context string from repository information for LLM

    Args:
        repo_info: Repository metadata from GitHub
        readme: README content
        message_lower: Lowercase user message for keyword detection
        repository_url: Repository URL

    Returns:
        (context_string, sources_list)
    """
    sources = []

    # Basic repository information
    context = f"""Repository Information:
Name: {repo_info['full_name']}
Description: {repo_info.get('description', 'No description')}
Primary Language: {repo_info['language']}
Stars: {repo_info['stars']:,}
Forks: {repo_info['forks']:,}
Open Issues: {repo_info['open_issues']:,}
Last Updated: {repo_info['updated_at'][:10]}
"""

    # Add topics if available
    if repo_info.get('topics'):
        topics = ", ".join(repo_info['topics'][:5])
        context += f"Topics: {topics}\n"

    # Add license information
    if repo_info.get('license'):
        context += f"License: {repo_info['license']}\n"

    # Add README excerpt
    if readme:
        readme_clean = clean_readme_text(readme, max_length=1000)
        if readme_clean:
            context += f"\nREADME Excerpt:\n{readme_clean}\n"
            sources.append("README.md")

    # Add language statistics for language-related questions
    if any(keyword in message_lower for keyword in
           ["language", "dil", "teknoloji", "technology", "written", "yazılmış"]):
        try:
            stats = github_service.get_repository_stats(repository_url)
            if stats.get('languages'):
                context += "\nLanguage Distribution:\n"
                for lang, percentage in list(stats['languages'].items())[:5]:
                    context += f"- {lang}: {percentage}%\n"
                sources.append("GitHub language statistics")
        except Exception as e:
            logger.warning(f"Could not fetch language stats: {e}")

    # Add contributor information for contributor-related questions
    if any(keyword in message_lower for keyword in
           ["who", "kim", "contributor", "develop", "geliştir", "author", "owner"]):
        try:
            stats = github_service.get_repository_stats(repository_url)
            if stats.get('contributors_count'):
                context += f"\nTotal Contributors: {stats['contributors_count']}\n"
            if stats.get('top_contributors'):
                context += "Top Contributors:\n"
                for contrib in stats['top_contributors'][:5]:
                    context += f"- @{contrib['login']}: {contrib['contributions']} contributions\n"
                sources.append("GitHub contributors data")
        except Exception as e:
            logger.warning(f"Could not fetch contributors: {e}")

    # Add recent commits for update-related questions
    if any(keyword in message_lower for keyword in
           ["recent", "son", "last", "commit", "update", "güncel"]):
        try:
            recent_commits = github_service.get_recent_commits(repository_url, limit=5)
            context += "\nRecent Commits:\n"
            for commit in recent_commits:
                context += f"- {commit['sha'][:7]}: {commit['message']} (by {commit['author']} on {commit['date'][:10]})\n"
            sources.append("Recent commit history")
        except Exception as e:
            logger.warning(f"Could not fetch commits: {e}")

    # Always include repository metadata as a source
    if "Repository metadata" not in sources:
        sources.append("Repository metadata")

    return context, sources


def generate_llm_response(
        message: str,
        context: str,
        sources: List[str]
) -> tuple[str, float]:
    """
    Generate response using LLM with repository context

    Args:
        message: User query
        context: Repository context information
        sources: List of information sources

    Returns:
        (response_text, confidence_score)
    """
    try:
        # System message to guide LLM behavior
        system_message = """You are a helpful AI assistant specialized in analyzing GitHub repositories and answering questions about software projects.

Your responsibilities:
- Provide clear, accurate, and concise answers based on the repository information
- Use markdown formatting (bold, lists, code blocks) for better readability
- When asked about statistics, provide exact numbers from the context
- When asked about features or functionality, explain clearly and comprehensively
- Always base your answers on the provided context
- If information is not in the context, acknowledge the limitation
- Be professional, helpful, and technically accurate

Response guidelines:
- Use **bold** for emphasis on key points
- Use bullet points (•) or numbered lists for multiple items
- Use emojis sparingly (⭐ for stars, 🍴 for forks, 🐛 for issues)
- Keep paragraphs short and scannable
- Include specific numbers and dates when available"""

        # Construct the prompt
        prompt = f"""Based on the following repository information, answer the user's question comprehensively:

{context}

User Question: {message}

Instructions:
- Provide a well-structured answer using the repository information above
- Use markdown formatting for readability
- Include relevant statistics and facts
- Be concise but thorough
- Focus on directly answering the question

Answer:"""

        # Generate response using LLM
        response_text = llm_service.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7,
            max_tokens=500
        )

        # High confidence when using LLM with real data
        confidence = 0.90

        return response_text, confidence

    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise  # Re-raise to trigger fallback


def generate_rule_based_response(
        message_lower: str,
        repo_info: dict,
        readme: str,
        sources: List[str]
) -> tuple[str, float]:
    """
    Generate simple rule-based response as fallback when LLM is unavailable

    Args:
        message_lower: Lowercase user message
        repo_info: Repository metadata
        readme: README content
        sources: List of sources

    Returns:
        (response_text, confidence_score)
    """
    response_parts = []

    # "What does it do?" questions
    if any(keyword in message_lower for keyword in
           ["what does", "what is", "purpose", "ne işe yarar", "ne yapar", "nedir"]):
        response_parts.append(f"**{repo_info['full_name']}** is a {repo_info['language']} project.")

        if repo_info.get('description'):
            response_parts.append(f"\n\n📝 **Description:** {repo_info['description']}")

        if readme:
            readme_clean = clean_readme_text(readme, max_length=500)
            if readme_clean:
                response_parts.append(f"\n\n📚 **From README:** {readme_clean}")

        if repo_info.get('topics'):
            topics = ", ".join(repo_info['topics'][:5])
            response_parts.append(f"\n\n🏷️ **Topics:** {topics}")

        confidence = 0.85

    # Statistics questions
    elif any(keyword in message_lower for keyword in
             ["statistics", "stats", "how many", "kaç", "istatistik", "star", "yıldız"]):
        response_parts.append(f"**{repo_info['full_name']}** Statistics:\n\n")
        response_parts.append(f"⭐ **Stars:** {repo_info['stars']:,}\n")
        response_parts.append(f"🍴 **Forks:** {repo_info['forks']:,}\n")
        response_parts.append(f"🐛 **Open Issues:** {repo_info['open_issues']:,}\n")
        response_parts.append(f"📅 **Last Updated:** {repo_info['updated_at'][:10]}")

        if repo_info.get('license'):
            response_parts.append(f"\n📜 **License:** {repo_info['license']}")

        confidence = 0.90

    # General fallback
    else:
        response_parts.append(f"**{repo_info['full_name']}**\n\n")

        if repo_info.get('description'):
            response_parts.append(f"📝 {repo_info['description']}\n\n")

        response_parts.append(f"⭐ Stars: {repo_info['stars']:,}\n")
        response_parts.append(f"🍴 Forks: {repo_info['forks']:,}\n")
        response_parts.append(f"💻 Language: {repo_info['language']}")

        if readme:
            readme_clean = clean_readme_text(readme, max_length=300)
            if readme_clean:
                response_parts.append(f"\n\n📚 {readme_clean}")

        confidence = 0.80

    response_text = "".join(response_parts)
    return response_text, confidence


def generate_smart_response_with_llm(
        message: str,
        repository_url: Optional[str],
        use_llm: bool = True
) -> tuple[str, List[str], float]:
    """
    Generate intelligent response using GitHub data and LLM

    This function:
    1. Fetches repository data from GitHub
    2. Builds context based on query type
    3. Uses LLM to generate natural, context-aware response
    4. Falls back to rule-based response if LLM fails

    Args:
        message: User query
        repository_url: GitHub repository URL
        use_llm: Whether to use LLM for response generation

    Returns:
        (response_text, sources, confidence)
    """

    # Return early if no repository selected
    if not repository_url:
        return (
            "Please select a repository first to ask questions about it.",
            [],
            0.0
        )

    try:
        # Fetch repository information from GitHub
        repo_info = github_service.get_repository_info(repository_url)
        readme = github_service.get_readme(repository_url)

        # Convert message to lowercase for keyword matching
        message_lower = message.lower()

        # Build context and collect sources
        context, sources = build_repository_context(
            repo_info=repo_info,
            readme=readme,
            message_lower=message_lower,
            repository_url=repository_url
        )

        # Generate response using LLM if enabled
        if use_llm:
            try:
                response_text, confidence = generate_llm_response(
                    message=message,
                    context=context,
                    sources=sources
                )

                # Add GitHub API statistics to sources if query is about stats
                if any(keyword in message_lower for keyword in
                       ["statistics", "stats", "how many", "kaç", "star", "fork"]):
                    if "GitHub API statistics" not in sources:
                        sources.append("GitHub API statistics")

                return response_text, sources, confidence

            except Exception as e:
                logger.error(f"LLM generation failed, falling back to rule-based: {e}")
                # Fall through to rule-based response

        # Fallback: Generate rule-based response
        response_text, confidence = generate_rule_based_response(
            message_lower=message_lower,
            repo_info=repo_info,
            readme=readme,
            sources=sources
        )

        return response_text, sources, confidence

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return (
            f"I found the repository, but I'm having trouble analyzing it right now.\n\n"
            f"**Repository:** {repository_url}\n\n"
            f"**Error:** {str(e)}\n\n"
            f"Please try again or select a different repository.",
            ["Error log"],
            0.5
        )


@router.post("/send", response_model=ChatResponse)
async def send_message(chat_message: ChatMessage):
    """
    Receive message from user and generate intelligent response

    This endpoint:
    1. Receives user message and repository URL
    2. Maintains conversation history
    3. Generates context-aware response using LLM
    4. Returns response with sources and confidence score

    Request body:
    - **message**: User's question or query
    - **repository_url**: GitHub repository URL (optional)
    - **conversation_id**: Existing conversation ID (optional)
    - **use_llm**: Whether to use LLM for generation (default: True)

    Returns:
    - **message**: Generated response text
    - **sources**: List of information sources used
    - **confidence**: Confidence score (0.0-1.0)
    - **conversation_id**: Conversation identifier
    """

    # Create or use existing conversation ID
    conversation_id = chat_message.conversation_id or generate_conversation_id()

    # Initialize conversation if new
    if conversation_id not in conversations:
        conversations[conversation_id] = {
            "id": conversation_id,
            "repository_url": chat_message.repository_url,
            "messages": [],
            "created_at": datetime.now().isoformat(),
        }

    # Store user message in conversation history
    conversations[conversation_id]["messages"].append({
        "role": "user",
        "content": chat_message.message,
        "timestamp": datetime.now().isoformat(),
    })

    # Generate intelligent response using LLM
    response_message, sources, confidence = generate_smart_response_with_llm(
        message=chat_message.message,
        repository_url=chat_message.repository_url,
        use_llm=chat_message.use_llm
    )

    # Store assistant response in conversation history
    conversations[conversation_id]["messages"].append({
        "role": "assistant",
        "content": response_message,
        "sources": sources,
        "confidence": confidence,
        "timestamp": datetime.now().isoformat(),
    })

    return ChatResponse(
        message=response_message,
        sources=sources,
        confidence=confidence,
        conversation_id=conversation_id,
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    Retrieve conversation history by ID

    Args:
        conversation_id: Unique conversation identifier

    Returns:
        Complete conversation object with all messages

    Raises:
        HTTPException: If conversation not found (404)
    """

    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversations[conversation_id]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete conversation by ID

    Args:
        conversation_id: Unique conversation identifier

    Returns:
        Success status and message

    Raises:
        HTTPException: If conversation not found (404)
    """

    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    del conversations[conversation_id]

    return {"status": "success", "message": "Conversation deleted successfully"}