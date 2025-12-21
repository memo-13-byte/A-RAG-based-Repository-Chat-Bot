"""
Chat API with RAG Integration
Combines GitHub data, RAG vector search, and LLM for intelligent repository Q&A
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
# from ..services.github_service import github_service
from ..services.git_factory import get_git_service
from ..services.llm_service import llm_service
from ..services.rag_service import rag_service
import logging
import re
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory conversation storage
conversations = {}


class ChatMessage(BaseModel):
    message: str
    repository_url: Optional[str] = None
    conversation_id: Optional[str] = None
    use_llm: bool = True
    use_rag: bool = True  # NEW: Enable RAG
    auto_index: bool = True  # NEW: Auto-index repository if not indexed
    use_graph: bool = True  # NEW: Enable graph context


class ChatResponse(BaseModel):
    message: str
    sources: List[str]
    confidence: float
    conversation_id: str
    rag_used: bool = False  # NEW: Indicates if RAG was used
    indexed_chunks: Optional[int] = None  # NEW: Number of chunks indexed
    graph_used: bool = False  # NEW: Indicates if graph context was used
    graph_context: Optional[str] = None  # NEW: Graph context if available


def generate_conversation_id() -> str:
    """Create unique conversation ID"""
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
    """
    # --- Choosing the correct service ---
    git_service = get_git_service(repository_url)
    # -------------------------------------

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
           ["language", "dil", "teknoloji", "technology", "written", "yazilmis"]):
        try:
            # git_service kullanıldı
            stats = git_service.get_repository_stats(repository_url)
            if stats.get('languages'):
                context += "\nLanguage Distribution:\n"
                for lang, percentage in list(stats['languages'].items())[:5]:
                    context += f"- {lang}: {percentage}%\n"
                sources.append("Language statistics")
        except Exception as e:
            logger.warning(f"Could not fetch language stats: {e}")

    # Add contributor information for contributor-related questions
    if any(keyword in message_lower for keyword in
           ["who", "kim", "contributor", "develop", "gelistir", "author", "owner"]):
        try:
            # git_service kullanıldı
            stats = git_service.get_repository_stats(repository_url)
            if stats.get('contributors_count'):
                context += f"\nTotal Contributors: {stats['contributors_count']}\n"
            if stats.get('top_contributors'):
                context += "Top Contributors:\n"
                for contrib in stats['top_contributors'][:5]:
                    context += f"- @{contrib['login']}: {contrib['contributions']} contributions\n"
                sources.append("Contributors data")
        except Exception as e:
            logger.warning(f"Could not fetch contributors: {e}")

    # Add recent commits for update-related questions
    if any(keyword in message_lower for keyword in
           ["recent", "son", "last", "commit", "update", "guncel"]):
        try:
            # git_service kullanıldı
            recent_commits = git_service.get_recent_commits(repository_url, limit=5)
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


def is_code_question(message_lower: str) -> bool:
    """
    Detect if question is about code/implementation

    Args:
        message_lower: Lowercase user message

    Returns:
        True if question is code-related
    """
    code_keywords = [
        # English
        "how to", "how do i", "how can i", "implement", "code", "function",
        "class", "method", "api", "example", "usage", "use",
        "install", "setup", "configure", "import", "syntax",

        # Turkish
        "nasil", "nasil kullan", "kod", "fonksiyon", "sinif",
        "kullanim", "ornek", "kurulum", "import"
    ]

    return any(keyword in message_lower for keyword in code_keywords)


async def generate_rag_response(
        message: str,
        repository_url: str,
        repo_info: dict,
        auto_index: bool = True,
        use_graph: bool = True  # ← ADD THIS PARAMETER
) -> tuple[str, List[str], float, bool, int, bool, Optional[str]]:  # ← UPDATE RETURN TYPE (7 values)
    """
    Generate response using RAG (Retrieval-Augmented Generation)

    Returns:
        Tuple of (answer, sources, confidence, rag_used, indexed_chunks, graph_used, graph_context)
    """
    try:
        # --- DEĞİŞİKLİK: Doğru servisi seç ---
        git_service = get_git_service(repository_url)
        # -------------------------------------

        # Parse repo name using the correct service
        owner, repo_name = git_service.parse_repo_url(repository_url)
        full_repo_name = f"{owner}/{repo_name}"

        logger.info(f"Attempting RAG query for: {full_repo_name}")

        # Check if repository is indexed
        status = rag_service.get_index_status(full_repo_name)
        indexed_chunks = status.get("total_chunks", 0)

        # Auto-index if not indexed
        if not status["indexed"] and auto_index:
            logger.info(f"Repository not indexed, indexing now...")

            index_result = rag_service.index_repository(
                repo_url=repository_url,
                include_readme=True,
                include_code_files=True,  # Index code for better answers
                max_files=50  # Limit for reasonable performance
            )

            if index_result["status"] == "success":
                indexed_chunks = index_result.get("document_count", 0)
                logger.info(f"Indexed {indexed_chunks} chunks")
            else:
                logger.warning(f"Indexing failed: {index_result.get('message')}")
                return None, [], 0.0, False, 0, False, None  # ← 7 VALUES

        # Query using RAG
        if status["indexed"] or indexed_chunks > 0:
            logger.info(f"Querying RAG with {indexed_chunks} chunks...")

            rag_result = rag_service.query(
                repo_name=full_repo_name,
                question=message,
                n_results=3,
                use_llm=True,
                use_graph=use_graph  # ← FIXED: use parameter, not request
            )

            if rag_result.get("answer"):
                # Build sources from RAG
                sources = [s["file_path"] for s in rag_result.get("sources", [])]

                # Add repository context to sources
                sources.append(f"Repository: {full_repo_name}")

                confidence = rag_result.get("confidence", 0.85)

                logger.info(f"RAG response generated (confidence: {confidence:.2f})")

                return (
                    rag_result["answer"],
                    sources,
                    confidence,
                    True,
                    indexed_chunks,
                    rag_result.get("graph_used", False),  # ← GRAPH FIELD
                    rag_result.get("graph_context")  # ← GRAPH FIELD
                )

        # RAG failed or not applicable
        return None, [], 0.0, False, indexed_chunks, False, None  # ← 7 VALUES

    except Exception as e:
        logger.error(f"RAG error: {e}")
        return None, [], 0.0, False, 0, False, None  # ← 7 VALUES


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
- Use bullet points or numbered lists for multiple items
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
           ["what does", "what is", "purpose", "ne ise yarar", "ne yapar", "nedir"]):
        response_parts.append(f"**{repo_info['full_name']}** is a {repo_info['language']} project.")

        if repo_info.get('description'):
            response_parts.append(f"\n\n**Description:** {repo_info['description']}")

        if readme:
            readme_clean = clean_readme_text(readme, max_length=500)
            if readme_clean:
                response_parts.append(f"\n\n**From README:** {readme_clean}")

        if repo_info.get('topics'):
            topics = ", ".join(repo_info['topics'][:5])
            response_parts.append(f"\n\n**Topics:** {topics}")

        confidence = 0.85

    # Statistics questions
    elif any(keyword in message_lower for keyword in
             ["statistics", "stats", "how many", "kac", "istatistik", "star", "yildiz"]):
        response_parts.append(f"**{repo_info['full_name']}** Statistics:\n\n")
        response_parts.append(f"**Stars:** {repo_info['stars']:,}\n")
        response_parts.append(f"**Forks:** {repo_info['forks']:,}\n")
        response_parts.append(f"**Open Issues:** {repo_info['open_issues']:,}\n")
        response_parts.append(f"**Last Updated:** {repo_info['updated_at'][:10]}")

        if repo_info.get('license'):
            response_parts.append(f"\n**License:** {repo_info['license']}")

        confidence = 0.90

    # General fallback
    else:
        response_parts.append(f"**{repo_info['full_name']}**\n\n")

        if repo_info.get('description'):
            response_parts.append(f"{repo_info['description']}\n\n")

        response_parts.append(f"Stars: {repo_info['stars']:,}\n")
        response_parts.append(f"Forks: {repo_info['forks']:,}\n")
        response_parts.append(f"Language: {repo_info['language']}")

        if readme:
            readme_clean = clean_readme_text(readme, max_length=300)
            if readme_clean:
                response_parts.append(f"\n\n{readme_clean}")

        confidence = 0.80

    response_text = "".join(response_parts)
    return response_text, confidence


async def generate_smart_response(
        message: str,
        repository_url: Optional[str],
        use_llm: bool = True,
        use_rag: bool = True,
        auto_index: bool = True,
        use_graph: bool = True  # ← ADD THIS PARAMETER
) -> tuple[str, List[str], float, bool, int, bool, Optional[str]]:  # ← UPDATE RETURN TYPE (7 values)
    """
    Generate intelligent response using Git data, RAG, and LLM

    Returns:
        Tuple of (response, sources, confidence, rag_used, indexed_chunks, graph_used, graph_context)
    """

    # Return early if no repository selected
    if not repository_url:
        return (
            "Please select a repository first to ask questions about it.",
            [],
            0.0,
            False,
            0,
            False,  # ← GRAPH FIELD
            None  # ← GRAPH FIELD
        )

    try:
        # --- DEĞİŞİKLİK: Doğru servisi seç ---
        git_service = get_git_service(repository_url)
        # -------------------------------------

        # Fetch repository information from Git Service
        repo_info = git_service.get_repository_info(repository_url)
        message_lower = message.lower()

        rag_used = False
        indexed_chunks = 0

        # Try RAG for code-related questions
        if use_rag and is_code_question(message_lower):
            logger.info("Detected code question, trying RAG...")

            # ← UNPACK 7 VALUES (not 5!)
            rag_response, rag_sources, rag_confidence, rag_success, chunks, graph_used, graph_context = await generate_rag_response(
                message=message,
                repository_url=repository_url,
                repo_info=repo_info,
                auto_index=auto_index,
                use_graph=use_graph  # ← PASS PARAMETER
            )

            if rag_success and rag_response:
                logger.info("Using RAG response")
                return rag_response, rag_sources, rag_confidence, True, chunks, graph_used, graph_context  # ← 7 VALUES
            else:
                logger.info("RAG failed, falling back to standard data")

        # Fallback: Use standard Git data + LLM
        logger.info("Using Git data + LLM")

        readme = git_service.get_readme(repository_url)

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

                return response_text, sources, confidence, False, 0, False, None  # ← 7 VALUES

            except Exception as e:
                logger.error(f"LLM generation failed, falling back to rule-based: {e}")

        # Final fallback: Rule-based response
        logger.info("Using rule-based response")
        response_text, confidence = generate_rule_based_response(
            message_lower=message_lower,
            repo_info=repo_info,
            readme=readme,
            sources=sources
        )

        return response_text, sources, confidence, False, 0, False, None  # ← 7 VALUES

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return (
            f"I found the repository, but I'm having trouble analyzing it right now.\n\n"
            f"**Repository:** {repository_url}\n\n"
            f"**Error:** {str(e)}\n\n"
            f"Please try again or select a different repository.",
            ["Error log"],
            0.5,
            False,
            0,
            False,  # ← GRAPH FIELD
            None  # ← GRAPH FIELD
        )


@router.post("/send", response_model=ChatResponse)
async def send_message(chat_message: ChatMessage):
    """
    Receive message from user and generate intelligent response

    This endpoint:
    1. Receives user message and repository URL
    2. Maintains conversation history
    3. Uses RAG for code questions (if enabled)
    4. Falls back to GitHub data + LLM
    5. Returns response with sources and confidence score

    Request body:
    - **message**: User's question or query
    - **repository_url**: GitHub repository URL (optional)
    - **conversation_id**: Existing conversation ID (optional)
    - **use_llm**: Whether to use LLM for generation (default: True)
    - **use_rag**: Whether to use RAG for code questions (default: True)
    - **auto_index**: Auto-index repository if needed (default: True)
    - **use_graph**: Enable graph context for code structure (default: True)

    Returns:
    - **message**: Generated response text
    - **sources**: List of information sources used
    - **confidence**: Confidence score (0.0-1.0)
    - **conversation_id**: Conversation identifier
    - **rag_used**: Whether RAG was used
    - **indexed_chunks**: Number of chunks indexed (if applicable)
    - **graph_used**: Whether graph context was used
    - **graph_context**: Graph context data (if applicable)
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

    # Generate intelligent response
    # ← UNPACK 7 VALUES (not 5!)
    response_message, sources, confidence, rag_used, indexed_chunks, graph_used, graph_context = await generate_smart_response(
        message=chat_message.message,
        repository_url=chat_message.repository_url,
        use_llm=chat_message.use_llm,
        use_rag=chat_message.use_rag,
        auto_index=chat_message.auto_index,
        use_graph=chat_message.use_graph  # ← PASS PARAMETER
    )

    # Store assistant response in conversation history
    conversations[conversation_id]["messages"].append({
        "role": "assistant",
        "content": response_message,
        "sources": sources,
        "confidence": confidence,
        "rag_used": rag_used,
        "graph_used": graph_used,  # ← NEW FIELD
        "timestamp": datetime.now().isoformat(),
    })

    return ChatResponse(
        message=response_message,
        sources=sources,
        confidence=confidence,
        conversation_id=conversation_id,
        rag_used=rag_used,
        indexed_chunks=indexed_chunks if indexed_chunks > 0 else None,
        graph_used=graph_used,  # ← NEW FIELD
        graph_context=graph_context  # ← NEW FIELD
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


# RAG Management Endpoints

@router.post("/index")
async def index_repository(
        repository_url: str,
        include_code: bool = True,
        max_files: int = 50,
        force_reindex: bool = False
):
    """
    Manually index a repository for RAG

    Args:
        repository_url: GitHub repository URL
        include_code: Whether to include code files
        max_files: Maximum number of files to index
        force_reindex: Force re-indexing

    Returns:
        Indexing results
    """
    try:
        logger.info(f"Manual indexing request: {repository_url}")

        result = rag_service.index_repository(
            repo_url=repository_url,
            include_readme=True,
            include_code_files=include_code,
            max_files=max_files,
            force_reindex=force_reindex
        )

        return result

    except Exception as e:
        logger.error(f"Error indexing repository: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error indexing repository: {str(e)}"
        )


@router.get("/index-status")
async def get_index_status(repository_url: str):
    """
    Get indexing status for a repository
    """
    try:
        # --- DEĞİŞİKLİK ---
        git_service = get_git_service(repository_url)
        owner, repo_name = git_service.parse_repo_url(repository_url)
        # ------------------

        full_repo_name = f"{owner}/{repo_name}"

        status = rag_service.get_index_status(full_repo_name)

        return status

    except Exception as e:
        logger.error(f"Error getting index status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting index status: {str(e)}"
        )


@router.delete("/index")
async def delete_index(repository_url: str):
    """
    Delete repository index
    """
    try:
        # --- DEĞİŞİKLİK ---
        git_service = get_git_service(repository_url)
        owner, repo_name = git_service.parse_repo_url(repository_url)
        # ------------------
        
        full_repo_name = f"{owner}/{repo_name}"

        success = rag_service.delete_index(full_repo_name)

        if success:
            return {
                "status": "success",
                "message": f"Index deleted for {full_repo_name}"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete index"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting index: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting index: {str(e)}"
        )