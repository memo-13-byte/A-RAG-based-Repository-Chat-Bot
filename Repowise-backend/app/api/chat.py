from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.services.github_service import github_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory conversation storage
conversations = {}


class ChatMessage(BaseModel):
    message: str
    repository_url: Optional[str] = None
    conversation_id: Optional[str] = None


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

    # Reduce multiple spaces to a single space
    text = re.sub(r'\s+', ' ', text)

    # Clean leading/trailing spaces
    text = text.strip()

    # Maximum length limit
    if len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + "..."

    return text


def generate_smart_response(message: str, repository_url: Optional[str]) -> tuple[str, List[str], float]:
    """
    Generate smart reply using GitHub data based on user message

    TODO: Will be replaced by RAG pipeline in the future
    """

    # General response if there is no repository
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

        # Convert the message to lowercase (case-insensitive matching)
        message_lower = message.lower()

        # Create an answer based on the question type
        response_parts = []
        sources = []

        #
        # 1. "What does it do?" questions
        if any(keyword in message_lower for keyword in
               ["ne işe yarar", "ne yapar", "nedir", "what does", "what is", "purpose"]):
            response_parts.append(f"**{repo_info['full_name']}** is a {repo_info['language']} project.")

            if repo_info.get('description'):
                response_parts.append(f"\n\n📝 **Description:** {repo_info['description']}")

            if readme and len(readme) > 0:
                # Clear and show the first 500 characters of the README
                readme_clean = clean_readme_text(readme, max_length=500)
                if readme_clean:
                    response_parts.append(f"\n\n📚 **From README:** {readme_clean}")
                    sources.append("README.md")

            if repo_info.get('topics'):
                topics = ", ".join(repo_info['topics'][:5])
                response_parts.append(f"\n\n🏷️ **Topics:** {topics}")

            sources.append("Repository metadata")
            confidence = 0.92

        # 2. Statistics questions
        elif any(keyword in message_lower for keyword in
                 ["kaç", "how many", "istatistik", "statistics", "stats", "yıldız", "star"]):
            response_parts.append(f"**{repo_info['full_name']}** Statistics:\n")
            response_parts.append(f"⭐ **Stars:** {repo_info['stars']:,}")
            response_parts.append(f"\n **Forks:** {repo_info['forks']:,}")
            response_parts.append(f"\n **Open Issues:** {repo_info['open_issues']:,}")
            response_parts.append(f"\n **Last Updated:** {repo_info['updated_at'][:10]}")

            if repo_info.get('license'):
                response_parts.append(f"\n📜 **License:** {repo_info['license']}")

            sources.append("GitHub API statistics")
            confidence = 0.98

        # 3. Language/technology questions
        elif any(keyword in message_lower for keyword in
                 ["dil", "language", "teknoloji", "technology", "yazılmış", "written"]):
            response_parts.append(f"**Primary Language:** {repo_info['language']}")

            try:
                stats = github_service.get_repository_stats(repository_url)
                if stats.get('languages'):
                    response_parts.append("\n\n**Language Distribution:**")
                    for lang, percentage in list(stats['languages'].items())[:5]:
                        response_parts.append(f"\n- {lang}: {percentage}%")
                    sources.append("GitHub language statistics")
            except Exception as e:
                logger.warning(f"Could not fetch language stats: {e}")

            sources.append("Repository metadata")
            confidence = 0.95

        # 4. Contributor/developer questions
        elif any(keyword in message_lower for keyword in
                 ["kim", "who", "geliştir", "develop", "contributor", "author", "owner"]):
            try:
                stats = github_service.get_repository_stats(repository_url)
                response_parts.append(
                    f"**{repo_info['full_name']}** has **{stats['contributors_count']} contributors**.\n")

                if stats.get('top_contributors'):
                    response_parts.append("\n**Top Contributors:**")
                    for contrib in stats['top_contributors'][:5]:
                        response_parts.append(f"\n- @{contrib['login']}: {contrib['contributions']} contributions")
                    sources.append("GitHub contributors data")

                confidence = 0.93
            except Exception as e:
                logger.warning(f"Could not fetch contributors: {e}")
                response_parts.append(f"This is the **{repo_info['full_name']}** repository.")
                sources.append("Repository metadata")
                confidence = 0.85

        # 5. Latest commits/updates
        elif any(keyword in message_lower for keyword in ["son", "last", "recent", "güncel", "commit", "update"]):
            try:
                recent_commits = github_service.get_recent_commits(repository_url, limit=5)
                response_parts.append(f"**Recent commits in {repo_info['full_name']}:**\n")

                for commit in recent_commits:
                    response_parts.append(f"\n🔸 **{commit['sha']}** - {commit['message']}")
                    response_parts.append(f"\n   *by {commit['author']} on {commit['date'][:10]}*")

                sources.append("Recent commit history")
                confidence = 0.96
            except Exception as e:
                logger.warning(f"Could not fetch commits: {e}")
                response_parts.append(f"Repository last updated: {repo_info['updated_at'][:10]}")
                sources.append("Repository metadata")
                confidence = 0.85

        # 6. General questions - Summary information
        else:
            response_parts.append(f"**{repo_info['full_name']}**\n")

            if repo_info.get('description'):
                response_parts.append(f"📝 {repo_info['description']}\n")

            response_parts.append(f"\n⭐ Stars: {repo_info['stars']:,}")
            response_parts.append(f"\n Forks: {repo_info['forks']:,}")
            response_parts.append(f"\n Language: {repo_info['language']}")

            if readme and len(readme) > 0:
                readme_clean = clean_readme_text(readme, max_length=300)
                if readme_clean:
                    response_parts.append(f"\n\n {readme_clean}")
                    sources.append("README.md")

            sources.append("Repository metadata")
            confidence = 0.88

        response_text = "".join(response_parts)

        return response_text, sources, confidence

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return (
            f"I found the repository, but I'm having trouble analyzing it right now. Here's what I know:\n\n"
            f"Repository: {repository_url}\n\n"
            f"Error: {str(e)}",
            ["Error log"],
            0.5
        )


@router.post("/send", response_model=ChatResponse)
async def send_message(chat_message: ChatMessage):
    """
    Receive messages from user and respond

    - **message**: User message
    - **repository_url**: Which repository is being asked about (optional)
    - **conversation_id**: Current conversation ID (optional)
    """

    # Create or use conversation ID
    conversation_id = chat_message.conversation_id or generate_conversation_id()

    # Save or update conversation
    if conversation_id not in conversations:
        conversations[conversation_id] = {
            "id": conversation_id,
            "repository_url": chat_message.repository_url,
            "messages": [],
            "created_at": datetime.now().isoformat(),
        }

    # Save user message
    conversations[conversation_id]["messages"].append({
        "role": "user",
        "content": chat_message.message,
        "timestamp": datetime.now().isoformat(),
    })

    # Create an answer (using GitHub data)
    response_message, sources, confidence = generate_smart_response(
        chat_message.message,
        chat_message.repository_url
    )

    # Save Bot response
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
    """Get the history of a specific conversation by ID"""

    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversations[conversation_id]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete Conversation by ID"""

    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    del conversations[conversation_id]

    return {"status": "success", "message": "Conversation deleted"}