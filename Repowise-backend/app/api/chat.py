"""
Chat API with RAG Integration + Phase 3 Enhancements
Combines GitHub data, RAG vector search, Graph queries, Analytics, and LLM
for intelligent repository Q&A

ENHANCEMENTS ADDED:
- Commit diff integration
- Analytics shortcuts
- Enhanced intent detection
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from ..services.git_factory import get_git_service
from ..services.llm_service import llm_service
from ..services.rag_service import rag_service
from ..services.memory_service import memory_service
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
    use_rag: bool = True
    auto_index: bool = True
    use_graph: bool = True
    stream: bool = False


class ChatResponse(BaseModel):
    message: str
    sources: List[str]
    confidence: float
    conversation_id: str
    rag_used: bool = False
    indexed_chunks: Optional[int] = None
    graph_used: bool = False
    graph_context: Optional[str] = None


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
    # Remove Markdown image syntax
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
    # Simplify Markdown link syntax
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Clear Markdown headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Reduce multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Clean spaces
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
    git_service = get_git_service(repository_url)
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


# ============================================================================
# 🆕 ENHANCEMENT 1: COMMIT DIFF DETECTION
# ============================================================================

def is_commit_question(message_lower: str) -> bool:
    """
    Detect if question is about commits or diffs

    Args:
        message_lower: Lowercase user message

    Returns:
        True if question is commit-related
    """
    commit_keywords = [
        # Commit questions
        "commit", "commits", "committed", "latest commit", "recent commit",
        "last commit", "commit history", "commit message",
        # Diff questions
        "diff", "difference", "differences", "changed", "changes",
        "what changed", "show diff", "compare commit",
        # Turkish
        "değişiklik", "fark", "ne değişti", "son commit"
    ]

    return any(keyword in message_lower for keyword in commit_keywords)


# ============================================================================
# 🆕 ENHANCEMENT 2: ANALYTICS DETECTION
# ============================================================================

def is_analytics_question(message_lower: str) -> bool:
    """
    Detect if question is about analytics/statistics

    Args:
        message_lower: Lowercase user message

    Returns:
        True if question is analytics-related
    """
    analytics_keywords = [
        # Hot spots
        "hot spot", "hot spots", "most changed", "most modified",
        "frequently changed", "frequently modified",
        # File history
        "file history", "history of", "changes to",
        # Code owners
        "code owner", "owner of", "who owns",
        "who maintains", "maintainer",
        # Contributors
        "top contributor", "main contributor", "who contributed",
        # Turkish
        "en çok değişen", "dosya geçmişi", "kod sahibi"
    ]

    return any(keyword in message_lower for keyword in analytics_keywords)


async def generate_rag_response(
        message: str,
        repository_url: str,
        repo_info: dict,
        auto_index: bool = True,
        use_graph: bool = True,
        chat_history: Optional[List[Dict]] = None  # ← YENİ PARAMETRE
) -> tuple[str, List[str], float, bool, int, bool, Optional[str]]:
    """
    Generate response using RAG (Retrieval-Augmented Generation)

    Returns:
        Tuple of (answer, sources, confidence, rag_used, indexed_chunks, graph_used, graph_context)
    """
    try:
        git_service = get_git_service(repository_url)
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
                include_code_files=True,
                max_files=50
            )

            if index_result["status"] == "success":
                indexed_chunks = index_result.get("document_count", 0)
                logger.info(f"Indexed {indexed_chunks} chunks")
            else:
                logger.warning(f"Indexing failed: {index_result.get('message')}")
                return None, [], 0.0, False, 0, False, None

        # Query using RAG
        if status["indexed"] or indexed_chunks > 0:
            logger.info(f"Querying RAG with {indexed_chunks} chunks...")

            rag_result = rag_service.query(
                repo_name=full_repo_name,
                question=message,
                n_results=3,
                use_llm=True,
                use_graph=use_graph,
                chat_history=chat_history  # ← YENİ PARAMETRE
            )

            if rag_result.get("answer"):
                # Build sources from RAG
                sources = [s["file_path"] for s in rag_result.get("sources", [])]
                sources.append(f"Repository: {full_repo_name}")

                confidence = rag_result.get("confidence", 0.85)

                logger.info(f"RAG response generated (confidence: {confidence:.2f})")

                return (
                    rag_result["answer"],
                    sources,
                    confidence,
                    True,
                    indexed_chunks,
                    rag_result.get("graph_used", False),
                    rag_result.get("graph_context")
                )

        # RAG failed or not applicable
        return None, [], 0.0, False, indexed_chunks, False, None

    except Exception as e:
        logger.error(f"RAG error: {e}")
        return None, [], 0.0, False, 0, False, None


"""
Enhanced commit diff response with FULL diff option
Replace in chat.py around line 350
"""


async def generate_commit_diff_response(
        message: str,
        repository_url: str,
        message_lower: str
) -> tuple[Optional[str], List[str], float]:
    """
    Generate response for commit-related questions

    🆕 NEW: Detects "full diff" or "complete diff" keywords

    Returns:
        Tuple of (response, sources, confidence)
    """
    try:
        from ..services.commit_diff_service import CommitDiffService
        from ..services import github_service, neo4j_service_enhanced

        diff_service = CommitDiffService(github_service, neo4j_service_enhanced)
        git_service = get_git_service(repository_url)

        # Get recent commits
        commits = git_service.get_recent_commits(repository_url, limit=5)

        if not commits:
            return None, [], 0.0

        response_parts = []
        sources = []

        # 🆕 Detect if user wants FULL diff
        wants_full_diff = any(keyword in message_lower for keyword in [
            'full diff', 'complete diff', 'entire diff', 'all changes',
            'full patch', 'complete patch', 'all files', 'everything'
        ])

        # Detect specific commit SHA in message
        sha_match = re.search(r'\b[0-9a-f]{7,40}\b', message_lower)

        if sha_match:
            # User asked about specific commit
            commit_sha = sha_match.group(0)

            response_parts.append(f"## 📝 Commit Details: `{commit_sha[:7]}`\n\n")

            # Get commit diff
            diff_result = diff_service.get_commit_diff(repository_url, commit_sha)

            if diff_result and diff_result.get('files'):
                response_parts.append(f"**Message:** {diff_result['message']}\n")
                response_parts.append(f"**Author:** {diff_result['author']['name']}\n")
                response_parts.append(f"**Date:** {diff_result['date'][:10]}\n\n")

                response_parts.append(f"### 📊 Changes\n\n")
                response_parts.append(f"**Files changed:** {len(diff_result['files'])}\n\n")

                # 🆕 FULL DIFF MODE vs PREVIEW MODE
                if wants_full_diff:
                    # ✅ SHOW EVERYTHING!
                    response_parts.append(f"### 📄 Complete Diff (All Files)\n\n")

                    for i, file in enumerate(diff_result['files'], 1):
                        response_parts.append(f"#### {i}. {file['filename']}\n\n")
                        response_parts.append(f"- **Status:** `{file['status']}`\n")
                        response_parts.append(f"- **Changes:** +{file['additions']} -{file['deletions']}\n\n")

                        # Show FULL patch (no limits!)
                        if file.get('patch'):
                            response_parts.append(f"```diff\n{file['patch']}\n```\n\n")
                        else:
                            response_parts.append(f"*No patch available (binary file or too large)*\n\n")

                    response_parts.append(f"\n✅ **Complete diff shown for all {len(diff_result['files'])} files**\n")

                else:
                    # ❌ PREVIEW MODE (current - limited)
                    for file in diff_result['files'][:5]:  # Limit to 5 files
                        response_parts.append(f"**{file['filename']}**\n")
                        response_parts.append(f"- Status: `{file['status']}`\n")
                        response_parts.append(f"- Changes: +{file['additions']} -{file['deletions']}\n")

                        # Show small diff preview
                        if file.get('patch'):
                            preview = file['patch'][:200]
                            response_parts.append(f"```diff\n{preview}...\n```\n")
                        response_parts.append("\n")

                    if len(diff_result['files']) > 5:
                        response_parts.append(f"*... and {len(diff_result['files']) - 5} more files*\n\n")
                        response_parts.append(f"💡 **Tip:** Ask for \"full diff\" to see complete changes!\n")

                sources.append(f"Commit {commit_sha[:7]}")
                return "".join(response_parts), sources, 0.90

        elif "compare" in message_lower or "between" in message_lower:
            # User wants to compare commits
            if len(commits) >= 2:
                from_commit = commits[1]['full_sha']
                to_commit = commits[0]['full_sha']

                response_parts.append(f"## 🔄 Comparing Commits\n\n")
                response_parts.append(f"**From:** `{from_commit[:7]}` - {commits[1]['message'][:50]}\n")
                response_parts.append(f"**To:** `{to_commit[:7]}` - {commits[0]['message'][:50]}\n\n")

                comparison = diff_service.compare_commits(repository_url, from_commit, to_commit)

                if comparison and comparison.get('files'):
                    total = comparison['total_changes']
                    response_parts.append(f"### 📊 Summary\n\n")
                    response_parts.append(f"- **Files changed:** {total['files_changed']}\n")
                    response_parts.append(f"- **Additions:** +{total['additions']}\n")
                    response_parts.append(f"- **Deletions:** -{total['deletions']}\n")
                    response_parts.append(f"- **Commits between:** {total.get('commits', 1)}\n\n")

                    # 🆕 FULL DIFF MODE vs PREVIEW MODE
                    if wants_full_diff:
                        response_parts.append(f"### 📄 Complete Changes (All Files)\n\n")

                        for i, file in enumerate(comparison['files'], 1):
                            response_parts.append(f"#### {i}. {file['filename']}\n\n")
                            response_parts.append(f"- **Status:** `{file['status']}`\n")
                            response_parts.append(f"- **Changes:** +{file['additions']} -{file['deletions']}\n\n")

                            if file.get('patch'):
                                response_parts.append(f"```diff\n{file['patch']}\n```\n\n")

                        response_parts.append(f"\n✅ **Complete diff shown for all {len(comparison['files'])} files**\n")

                    else:
                        response_parts.append(f"### 📁 Changed Files (Preview)\n\n")
                        for file in comparison['files'][:10]:
                            response_parts.append(
                                f"- **{file['filename']}**: +{file['additions']} -{file['deletions']}\n")

                        if len(comparison['files']) > 10:
                            response_parts.append(f"\n*... and {len(comparison['files']) - 10} more files*\n")
                            response_parts.append(f"💡 **Tip:** Ask for \"full diff\" to see all changes!\n")

                    sources.append(f"Commits {from_commit[:7]}...{to_commit[:7]}")
                    return "".join(response_parts), sources, 0.85

        else:
            # Show recent commits with basic info
            response_parts.append(f"## 📝 Recent Commits\n\n")

            for i, commit in enumerate(commits, 1):
                response_parts.append(f"{i}. **{commit['sha']}** - {commit['message'][:60]}\n")
                response_parts.append(f"   *by {commit['author']} on {commit['date'][:10]}*\n\n")

            response_parts.append(f"\n💡 **Tip:** Ask about a specific commit by SHA to see detailed changes.\n")
            response_parts.append(f"💡 **Tip:** Add \"full diff\" to see complete patch for all files.\n")

            sources.append("Recent commits")
            return "".join(response_parts), sources, 0.80

        return None, [], 0.0

    except Exception as e:
        logger.error(f"Error generating commit diff response: {e}")
        return None, [], 0.0

# ============================================================================
# 🆕 ENHANCEMENT 2: ANALYTICS RESPONSE GENERATOR
# ============================================================================

async def generate_analytics_response(
    message: str,
    repository_url: str,
    message_lower: str
) -> tuple[Optional[str], List[str], float]:
    """
    Generate response for analytics questions

    Returns:
        Tuple of (response, sources, confidence)
    """
    try:
        from ..services import neo4j_service_enhanced

        git_service = get_git_service(repository_url)
        owner, repo_name = git_service.parse_repo_url(repository_url)
        full_repo_name = f"{owner}/{repo_name}"

        response_parts = []
        sources = []

        # Hot spots detection
        if "hot spot" in message_lower or "most changed" in message_lower or "frequently" in message_lower:
            response_parts.append(f"## 🔥 Hot Spots Analysis\n\n")
            response_parts.append(f"*Most frequently modified files:*\n\n")

            hot_spots = neo4j_service_enhanced.get_hot_spots(full_repo_name, limit=10)

            if hot_spots:
                for i, spot in enumerate(hot_spots, 1):
                    response_parts.append(
                        f"{i}. **{spot['file']}**\n"
                        f"   - Modifications: {spot['modifications']}\n"
                        f"   - Changes: +{spot['additions']} -{spot['deletions']}\n\n"
                    )
                sources.append("Neo4j Hot Spots Analysis")
                return "".join(response_parts), sources, 0.90

        # File history
        elif "file history" in message_lower or "history of" in message_lower:
            # Extract filename from message
            filename_match = re.search(r'[\w\-]+\.\w+', message)

            if filename_match:
                filename = filename_match.group(0)

                response_parts.append(f"## 📜 File History: `{filename}`\n\n")

                history = neo4j_service_enhanced.get_file_history(full_repo_name, filename)

                if history:
                    response_parts.append(f"**Total modifications:** {len(history)}\n\n")

                    for i, change in enumerate(history[:10], 1):
                        response_parts.append(
                            f"{i}. **{change['commit_sha'][:7]}** - {change['message'][:50]}\n"
                            f"   *by {change['author']} on {change['date'][:10]}*\n"
                            f"   Changes: +{change.get('additions', 0)} -{change.get('deletions', 0)}\n\n"
                        )

                    if len(history) > 10:
                        response_parts.append(f"*... and {len(history) - 10} more commits*\n")

                    sources.append(f"File history for {filename}")
                    return "".join(response_parts), sources, 0.90

        # Code owners
        elif "owner" in message_lower or "maintains" in message_lower:
            # Extract filename
            filename_match = re.search(r'[\w\-]+\.\w+', message)

            if filename_match:
                filename = filename_match.group(0)

                response_parts.append(f"## 👤 Code Ownership: `{filename}`\n\n")

                owners = neo4j_service_enhanced.get_code_owners(full_repo_name, filename)

                if owners:
                    primary = owners[0]
                    response_parts.append(f"**Primary Maintainer:**\n")
                    response_parts.append(f"- {primary['author']} ({primary['email']})\n")
                    response_parts.append(f"- Commits: {primary['commits']}\n")
                    response_parts.append(f"- Contribution: {primary['percentage']:.1f}%\n\n")

                    if len(owners) > 1:
                        response_parts.append(f"**Other Contributors:**\n")
                        for owner in owners[1:5]:
                            response_parts.append(
                                f"- {owner['author']}: {owner['commits']} commits ({owner['percentage']:.1f}%)\n"
                            )

                    sources.append(f"Code ownership for {filename}")
                    return "".join(response_parts), sources, 0.90

        # Top contributors
        elif "top contributor" in message_lower or "main contributor" in message_lower:
            response_parts.append(f"## 👥 Top Contributors\n\n")

            contributors = neo4j_service_enhanced.get_active_authors(full_repo_name, limit=10)

            if contributors:
                for i, contrib in enumerate(contributors, 1):
                    response_parts.append(
                        f"{i}. **{contrib['author']}**\n"
                        f"   - Email: {contrib['email']}\n"
                        f"   - Commits: {contrib['commits']}\n"
                        f"   - Changes: +{contrib['additions']} -{contrib['deletions']}\n\n"
                    )

                sources.append("Neo4j Contributor Analysis")
                return "".join(response_parts), sources, 0.90

        return None, [], 0.0

    except Exception as e:
        logger.error(f"Error generating analytics response: {e}")
        return None, [], 0.0


def generate_llm_response(
        message: str,
        context: str,
        sources: List[str],
        chat_history: Optional[List[Dict]] = None  # ← EKLE
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

        response_text = llm_service.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7,
            max_tokens=500,
            chat_history=chat_history  # ← EKLE
        )

        confidence = 0.90
        return response_text, confidence

    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise


def generate_rule_based_response(
        message_lower: str,
        repo_info: dict,
        readme: str,
        sources: List[str]
) -> tuple[str, float]:
    """
    Generate simple rule-based response as fallback when LLM is unavailable
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


# ============================================================================
# 🆕 ENHANCED SMART RESPONSE WITH ALL IMPROVEMENTS
# ============================================================================

async def generate_smart_response(
        message: str,
        repository_url: Optional[str],
        use_llm: bool = True,
        use_rag: bool = True,
        auto_index: bool = True,
        use_graph: bool = True,
        chat_history: Optional[List[Dict]] = None  # ← YENİ PARAMETRE
) -> tuple[str, List[str], float, bool, int, bool, Optional[str]]:
    """
    🆕 ENHANCED: Generate intelligent response using Git data, RAG, Analytics, Commit Diff, and LLM

    Priority order:
    1. Commit/Diff questions → commit_diff_service
    2. Analytics questions → neo4j_service_enhanced
    3. Code questions → RAG (vector + graph)
    4. General questions → Git data + LLM

    Returns:
        Tuple of (response, sources, confidence, rag_used, indexed_chunks, graph_used, graph_context)
    """

    if not repository_url:
        return (
            "Please select a repository first to ask questions about it.",
            [],
            0.0,
            False,
            0,
            False,
            None
        )

    try:
        git_service = get_git_service(repository_url)
        repo_info = git_service.get_repository_info(repository_url)
        message_lower = message.lower()

        # ========================================================================
        # 🆕 PRIORITY 1: Check for commit/diff questions FIRST
        # ========================================================================
        if is_commit_question(message_lower):
            logger.info("Detected commit/diff question, using commit diff service...")

            commit_response, commit_sources, commit_confidence = await generate_commit_diff_response(
                message=message,
                repository_url=repository_url,
                message_lower=message_lower
            )

            if commit_response:
                logger.info("Using commit diff response")
                return commit_response, commit_sources, commit_confidence, False, 0, True, "commit_diff"

        # ========================================================================
        # 🆕 PRIORITY 2: Check for analytics questions
        # ========================================================================
        if is_analytics_question(message_lower):
            logger.info("Detected analytics question, using Neo4j analytics...")

            analytics_response, analytics_sources, analytics_confidence = await generate_analytics_response(
                message=message,
                repository_url=repository_url,
                message_lower=message_lower
            )

            if analytics_response:
                logger.info("Using analytics response")
                return analytics_response, analytics_sources, analytics_confidence, False, 0, True, "analytics"

        # ========================================================================
        # PRIORITY 3: Try RAG for code-related questions
        # ========================================================================
        if use_rag and is_code_question(message_lower):
            logger.info("Detected code question, trying RAG...")

            rag_response, rag_sources, rag_confidence, rag_success, chunks, graph_used, graph_context = await generate_rag_response(
                message=message,
                repository_url=repository_url,
                repo_info=repo_info,
                auto_index=auto_index,
                use_graph=use_graph,
                chat_history=chat_history  # ← YENİ PARAMETRE
            )

            if rag_success and rag_response:
                logger.info("Using RAG response")
                return rag_response, rag_sources, rag_confidence, True, chunks, graph_used, graph_context
            else:
                logger.info("RAG failed, falling back to standard data")

        # ========================================================================
        # PRIORITY 4: Fallback to Git data + LLM
        # ========================================================================
        logger.info("Using Git data + LLM")

        readme = git_service.get_readme(repository_url)
        context, sources = build_repository_context(
            repo_info=repo_info,
            readme=readme,
            message_lower=message_lower,
            repository_url=repository_url
        )

        if use_llm:
            try:
                response_text, confidence = generate_llm_response(
                    message=message,
                    context=context,
                    sources=sources,
                    chat_history=chat_history  # ← YENİ
                )
                return response_text, sources, confidence, False, 0, False, None
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

        return response_text, sources, confidence, False, 0, False, None

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
            False,
            None
        )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/send")
async def send_message(chat_message: ChatMessage):
    """
    Receive message from user and generate intelligent response

    🆕 ENHANCED with:
    - Commit diff and analytics support
    - Streaming support (set stream=true)
    - Memory persistence
    - Cache integration

    This endpoint:
    1. Receives user message and repository URL
    2. Detects question type (commit/analytics/code/general)
    3. Routes to appropriate service
    4. Returns response (normal JSON or SSE stream)

    Request body:
    - **message**: User's question or query
    - **repository_url**: GitHub/GitLab repository URL (optional)
    - **conversation_id**: Existing conversation ID (optional)
    - **use_llm**: Whether to use LLM for generation (default: True)
    - **use_rag**: Whether to use RAG for code questions (default: True)
    - **auto_index**: Auto-index repository if needed (default: True)
    - **use_graph**: Enable graph context for code structure (default: True)
    - **stream**: Enable streaming response (default: False) 🆕

    Returns:
    - Normal mode: ChatResponse (JSON)
    - Stream mode: StreamingResponse (SSE)
    """

    # ============================================================
    # STEP 1: SETUP CONVERSATION
    # ============================================================

    conversation_id = chat_message.conversation_id or generate_conversation_id()

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

    # ============================================================
    # STEP 2: SAVE TO PERSISTENT MEMORY
    # ============================================================

    memory_service.save_message(
        conversation_id=conversation_id,
        role="user",
        content=chat_message.message
    )

    # ============================================================
    # STEP 3: GET CONVERSATION HISTORY
    # ============================================================

    chat_history = memory_service.optimize_history_for_llm(
        conversation_id=conversation_id,
        max_tokens=2000
    )

    llm_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in chat_history
        if msg["role"] in ["user", "assistant"]
    ]

    logger.info(f"Conversation {conversation_id}: {len(llm_history)} history messages")

    # ============================================================
    # STEP 4: BRANCH - STREAMING vs NORMAL
    # ============================================================

    if chat_message.stream:
        # ========================================================
        # 🌊 STREAMING MODE
        # ========================================================
        logger.info("🌊 Streaming mode activated")

        return StreamingResponse(
            generate_streaming_response(
                chat_message=chat_message,
                conversation_id=conversation_id,
                llm_history=llm_history
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    else:
        # ========================================================
        # 📄 NORMAL MODE (JSON Response)
        # ========================================================
        logger.info("📄 Normal mode (JSON response)")

        # Generate intelligent response
        response_message, sources, confidence, rag_used, indexed_chunks, graph_used, graph_context = await generate_smart_response(
            message=chat_message.message,
            repository_url=chat_message.repository_url,
            use_llm=chat_message.use_llm,
            use_rag=chat_message.use_rag,
            auto_index=chat_message.auto_index,
            use_graph=chat_message.use_graph,
            chat_history=llm_history
        )

        # Store assistant response in conversation history
        conversations[conversation_id]["messages"].append({
            "role": "assistant",
            "content": response_message,
            "sources": sources,
            "confidence": confidence,
            "rag_used": rag_used,
            "graph_used": graph_used,
            "timestamp": datetime.now().isoformat(),
        })

        # Save to persistent memory
        memory_service.save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response_message,
            metadata={
                "sources": sources,
                "confidence": confidence,
                "rag_used": rag_used,
                "graph_used": graph_used
            }
        )

        return ChatResponse(
            message=response_message,
            sources=sources,
            confidence=confidence,
            conversation_id=conversation_id,
            rag_used=rag_used,
            indexed_chunks=indexed_chunks,
            graph_used=graph_used,
            graph_context=graph_context
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


# ============================================================================
# RAG MANAGEMENT ENDPOINTS
# ============================================================================

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
        repository_url: GitHub/GitLab repository URL
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
        git_service = get_git_service(repository_url)
        owner, repo_name = git_service.parse_repo_url(repository_url)
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
        git_service = get_git_service(repository_url)
        owner, repo_name = git_service.parse_repo_url(repository_url)
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


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    from ..services.cache_service import cache_service
    return cache_service.get_stats()


@router.get("/cache/stats/{repository_url:path}")
async def get_repository_cache_stats(repository_url: str):
    """Get cache stats for specific repository"""
    from ..services.cache_service import cache_service
    from ..services.git_factory import get_git_service

    git_service = get_git_service(repository_url)
    owner, repo = git_service.parse_repo_url(repository_url)
    full_repo_name = f"{owner}/{repo}"

    return cache_service.get_repository_stats(full_repo_name)


@router.delete("/cache")
async def clear_cache():
    """Clear entire cache"""
    from ..services.cache_service import cache_service
    deleted = cache_service.invalidate_all()
    return {
        "status": "success",
        "message": f"Cache cleared: {deleted} entries deleted"
    }


@router.delete("/cache/{repository_url:path}")
async def clear_repository_cache(repository_url: str):
    """Clear cache for specific repository"""
    from ..services.cache_service import cache_service
    from ..services.git_factory import get_git_service

    git_service = get_git_service(repository_url)
    owner, repo = git_service.parse_repo_url(repository_url)
    full_repo_name = f"{owner}/{repo}"

    deleted = cache_service.invalidate_repository(full_repo_name)
    return {
        "status": "success",
        "message": f"Cache cleared for {full_repo_name}: {deleted} entries deleted"
    }


async def generate_streaming_response(
        chat_message: ChatMessage,
        conversation_id: str,
        llm_history: List[Dict]
):
    """
    Generate streaming response in SSE format

    Yields:
        Server-Sent Events formatted chunks
    """
    try:
        from ..services.llm_service_enhanced import enhanced_llm_service

        # Send metadata
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"

        full_response = ""
        sources = []

        # Get repository context if RAG is enabled
        if chat_message.use_rag and chat_message.repository_url:
            try:
                git_service = get_git_service(chat_message.repository_url)
                repo_info = git_service.get_repository_info(chat_message.repository_url)
                readme = git_service.get_readme(chat_message.repository_url)

                context, sources = build_repository_context(
                    repo_info=repo_info,
                    readme=readme,
                    message_lower=chat_message.message.lower(),
                    repository_url=chat_message.repository_url
                )

                # Send sources
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

                # Stream with context
                async for chunk in enhanced_llm_service.generate_enhanced_stream(
                        prompt=chat_message.message,
                        context=context,
                        chat_history=llm_history
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            except Exception as e:
                logger.error(f"RAG streaming error: {e}")
                # Fallback to simple streaming
                async for chunk in enhanced_llm_service.generate_enhanced_stream(
                        prompt=chat_message.message,
                        chat_history=llm_history
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

        else:
            # Simple LLM streaming (no RAG)
            async for chunk in enhanced_llm_service.generate_enhanced_stream(
                    prompt=chat_message.message,
                    chat_history=llm_history
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

        # Send completion
        yield f"data: {json.dumps({'type': 'done', 'length': len(full_response)})}\n\n"

        # Save to conversation history
        conversations[conversation_id]["messages"].append({
            "role": "assistant",
            "content": full_response,
            "sources": sources,
            "timestamp": datetime.now().isoformat(),
        })

        # Save to memory
        memory_service.save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_response,
            metadata={"sources": sources}
        )

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"