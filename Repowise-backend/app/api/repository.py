from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ..services.git_factory import get_git_service  # GitLab feature
import logging
from ..services import rag_service, neo4j_service_enhanced
from ..services.commit_diff_service import CommitDiffService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repository", tags=["repository"])

# In-memory storage (will be moved to the database in the future)
analyzed_repositories = []


# Response Models
class FileItem(BaseModel):
    """Single file or directory item"""
    name: str
    path: str
    type: str  # 'file' or 'dir'
    size: int
    url: str
    sha: Optional[str] = None


class FileTreeResponse(BaseModel):
    """File tree response model"""
    repository: str
    path: str
    files: List[FileItem]
    total_items: int


@router.get("/")
async def list_repositories():
    """List analyzed repositories"""
    return analyzed_repositories


@router.post("/analyze")
async def analyze_repository(repository_url: str, background_tasks: BackgroundTasks):
    """
    Analyze a new repository and add it to the system

    Supports both GitHub and GitLab repositories
    """
    try:
        # GitLab Feature: Select correct service based on URL
        git_service = get_git_service(repository_url)

        # Fetch repository information using the factory service
        logger.info(f"Analyzing repository: {repository_url}")
        repo_info = git_service.get_repository_info(repository_url)

        # Check if it has already been analyzed
        existing = next(
            (r for r in analyzed_repositories if r["id"] == repo_info["id"]),
            None
        )

        if existing:
            logger.info(f"Repository already analyzed: {repo_info['full_name']}")
            return {
                "status": "already_exists",
                "message": f"Repository '{repo_info['full_name']}' is already in the system",
                "repository": existing
            }

        # Check README (optional)
        readme_content = git_service.get_readme(repository_url)
        if readme_content:
            repo_info["has_readme"] = True
            repo_info["readme_length"] = len(readme_content)
        else:
            repo_info["has_readme"] = False

        # Add analysis date
        from datetime import datetime
        repo_info["analyzed_at"] = datetime.now().isoformat()

        # Add to list
        analyzed_repositories.append(repo_info)

        logger.info(f"Repository analyzed successfully: {repo_info['full_name']}")

        return {
            "status": "success",
            "message": f"Repository '{repo_info['full_name']}' analyzed successfully",
            "repository": repo_info
        }

    except ValueError as e:
        logger.error(f"Invalid repository: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing repository: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze repository: {str(e)}")


# ============================================================================
# NEW: RAG INDEXING ENDPOINTS
# ============================================================================

@router.post("/index")
async def index_repository(
        repo_url: str = Query(..., description="Repository URL (GitHub or GitLab)"),
        include_commits: bool = Query(True, description="Index commit history"),
        max_commits: int = Query(100, ge=10, le=1000, description="Maximum commits to index"),
        max_files: int = Query(500, ge=10, le=2000, description="Maximum files to index"),
        force_reindex: bool = Query(False, description="Force re-indexing")
):
    """
    Index repository for RAG with optional commit history

    This endpoint indexes repository content into:
    - ChromaDB (vector embeddings for semantic search)
    - Neo4j (code structure graph + commit history)

    Args:
        repo_url: Full repository URL
        include_commits: Whether to index commit history
        max_commits: Maximum number of commits to index
        max_files: Maximum number of files to index
        force_reindex: Force re-indexing even if already indexed

    Returns:
        Indexing statistics

    Examples:
        POST /api/repository/index?repo_url=https://github.com/psf/requests
        POST /api/repository/index?repo_url=https://github.com/psf/requests&include_commits=true&max_commits=100
    """
    try:
        logger.info(f"Indexing repository: {repo_url}")
        logger.info(f"Parameters: include_commits={include_commits}, max_commits={max_commits}, max_files={max_files}")

        if include_commits:
            # Index with commit history
            result = rag_service.index_with_commits(
                repo_url=repo_url,
                max_commits=max_commits,
                max_files=max_files,
                force_reindex=force_reindex
            )
        else:
            # Index without commits (vector only)
            result = rag_service.index_repository(
                repo_url=repo_url,
                max_files=max_files,
                force_reindex=force_reindex
            )

        logger.info(f"Indexing completed: {result.get('status')}")
        return result

    except Exception as e:
        logger.error(f"Error indexing repository: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to index repository: {str(e)}")


# ============================================================================
# NEW: ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/analytics/hot-spots")
async def get_hot_spots(
        repo_name: str = Query(..., description="Repository full name (e.g., 'owner/repo')"),
        limit: int = Query(20, ge=1, le=100, description="Maximum number of hot spots")
):
    """
    Get code hot spots (frequently modified files)

    Hot spots are files that have been modified frequently, which may indicate:
    - High maintenance areas
    - Complex or problematic code
    - Core functionality

    Args:
        repo_name: Repository full name (e.g., 'psf/requests')
        limit: Maximum number of results

    Returns:
        List of most frequently modified files

    Example:
        GET /api/repository/analytics/hot-spots?repo_name=psf/requests&limit=10
    """
    try:
        logger.info(f"Fetching hot spots for: {repo_name}")

        files = neo4j_service_enhanced.get_most_modified_files(
            repo_name=repo_name,
            limit=limit
        )

        logger.info(f"Found {len(files)} hot spots")

        return {
            "repository": repo_name,
            "hot_spots": files,
            "count": len(files)
        }

    except Exception as e:
        logger.error(f"Error fetching hot spots: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch hot spots: {str(e)}")


@router.get("/analytics/contributors")
async def get_contributors(
        repo_name: str = Query(..., description="Repository full name (e.g., 'owner/repo')"),
        limit: int = Query(10, ge=1, le=50, description="Maximum number of contributors")
):
    """
    Get top contributors

    Returns the most active contributors based on:
    - Number of commits
    - Lines added/deleted
    - Recent activity

    Args:
        repo_name: Repository full name (e.g., 'psf/requests')
        limit: Maximum number of results

    Returns:
        List of top contributors with statistics

    Example:
        GET /api/repository/analytics/contributors?repo_name=psf/requests&limit=5
    """
    try:
        logger.info(f"Fetching contributors for: {repo_name}")

        authors = neo4j_service_enhanced.get_active_authors(
            repo_name=repo_name,
            limit=limit
        )

        logger.info(f"Found {len(authors)} contributors")

        return {
            "repository": repo_name,
            "contributors": authors,
            "count": len(authors)
        }

    except Exception as e:
        logger.error(f"Error fetching contributors: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch contributors: {str(e)}")


@router.get("/analytics/file-history")
async def get_file_history(
        file_path: str = Query(..., description="File path in repository"),
        limit: int = Query(50, ge=1, le=100, description="Maximum number of commits")
):
    """
    Get commit history for a specific file

    Shows all commits that modified the given file, including:
    - Commit SHA
    - Author
    - Date
    - Message
    - Change type (added/modified/deleted)

    Args:
        file_path: Full path to file (e.g., 'src/main.py')
        limit: Maximum number of commits

    Returns:
        Commit history for the file

    Example:
        GET /api/repository/analytics/file-history?file_path=requests/sessions.py&limit=20
    """
    try:
        logger.info(f"Fetching file history for: {file_path}")

        history = neo4j_service_enhanced.get_file_commit_history(
            file_path=file_path,
            limit=limit
        )

        logger.info(f"Found {len(history)} commits")

        return {
            "file": file_path,
            "commits": history,
            "count": len(history)
        }

    except Exception as e:
        logger.error(f"Error fetching file history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch file history: {str(e)}")


@router.get("/analytics/code-owners")
async def get_code_owners(
        file_path: str = Query(..., description="File path in repository")
):
    """
    Find code owners for a specific file

    Identifies who owns/maintains a file based on:
    - Number of commits to the file
    - Lines added/deleted
    - Recent activity

    Args:
        file_path: Full path to file

    Returns:
        Primary owner and list of contributors

    Example:
        GET /api/repository/analytics/code-owners?file_path=requests/sessions.py
    """
    try:
        logger.info(f"Finding code owners for: {file_path}")

        owners = neo4j_service_enhanced.find_code_owners(file_path)

        if owners:
            logger.info(f"Found code owners for {file_path}")
        else:
            logger.warning(f"No code owners found for {file_path}")

        return owners

    except Exception as e:
        logger.error(f"Error finding code owners: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find code owners: {str(e)}")


@router.get("/analytics/impact")
async def analyze_impact(
        file_path: str = Query(..., description="File path in repository"),
        max_depth: int = Query(3, ge=1, le=5, description="Maximum dependency depth")
):
    """
    Analyze impact of changing a file

    Shows which other files would be affected if this file is modified,
    based on dependency relationships.

    Args:
        file_path: Full path to file
        max_depth: How deep to traverse dependencies

    Returns:
        List of potentially impacted files

    Example:
        GET /api/repository/analytics/impact?file_path=requests/sessions.py&max_depth=3
    """
    try:
        logger.info(f"Analyzing impact for: {file_path}")

        impact = neo4j_service_enhanced.analyze_impact_of_change(
            file_path=file_path,
            max_depth=max_depth
        )

        impact_score = impact.get('impact_score', 0)
        logger.info(f"Impact score: {impact_score}")

        return impact

    except Exception as e:
        logger.error(f"Error analyzing impact: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze impact: {str(e)}")


@router.get("/analytics/stats")
async def get_repository_analytics_stats(
        repo_name: str = Query(..., description="Repository full name (e.g., 'owner/repo')")
):
    """
    Get comprehensive repository statistics

    Returns aggregated statistics including:
    - File counts
    - Class/Function counts
    - Commit statistics
    - Language distribution
    - Author statistics

    Args:
        repo_name: Repository full name

    Returns:
        Comprehensive repository statistics

    Example:
        GET /api/repository/analytics/stats?repo_name=psf/requests
    """
    try:
        logger.info(f"Fetching analytics stats for: {repo_name}")

        stats = neo4j_service_enhanced.get_repository_statistics(repo_name)

        logger.info(f"Stats retrieved: {stats.get('files', 0)} files, {stats.get('total_commits', 0)} commits")

        return {
            "repository": repo_name,
            "statistics": stats
        }

    except Exception as e:
        logger.error(f"Error fetching analytics stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")


# ============================================================================
# EXISTING ENDPOINTS (Preserved)
# ============================================================================

@router.get("/{repo_name}/stats")
async def get_repository_stats(repo_name: str):
    """Get detailed statistics of a specific repository"""

    # Find from analyzed repositories
    repo = next(
        (r for r in analyzed_repositories if r["name"] == repo_name or r["full_name"] == repo_name),
        None
    )

    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    try:
        # GitLab Feature: Select service from URL
        repo_url = repo["url"]
        git_service = get_git_service(repo_url)

        # Fetch current statistics
        stats = git_service.get_repository_stats(repo_url)

        # Recent commits
        recent_commits = git_service.get_recent_commits(repo_url, limit=10)

        return {
            "repository": repo,
            "statistics": stats,
            "recent_commits": recent_commits,
        }

    except Exception as e:
        logger.error(f"Error fetching stats for {repo_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")


@router.get("/{repo_name}/readme")
async def get_repository_readme(repo_name: str):
    """Get the repository's README file"""

    repo = next(
        (r for r in analyzed_repositories if r["name"] == repo_name or r["full_name"] == repo_name),
        None
    )

    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    try:
        # GitLab Feature: Select service from URL
        repo_url = repo["url"]
        git_service = get_git_service(repo_url)

        readme = git_service.get_readme(repo_url)

        if not readme:
            raise HTTPException(status_code=404, detail="README not found")

        return {
            "repository": repo["full_name"],
            "content": readme,
            "length": len(readme),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching README for {repo_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch README: {str(e)}")


@router.get("/files", response_model=FileTreeResponse)
async def get_repository_files(
        repo_name: str = Query(...,
                               description="Repository name (e.g., 'langchain-ai/langchain' or 'https://gitlab.com/user/project')"),
        path: str = Query("", description="Path within the repository (e.g., 'src/components')")
):
    """
    Get the repository's file tree (Phase 2: uses query parameters)

    Supports both GitHub and GitLab repositories

    Args:
        repo_name: Repository full name or URL
        path: Optional path within the repository to list files from (default: root)

    Returns:
        List of files and directories with metadata

    Examples:
        GitHub:
            GET /api/repository/files?repo_name=langchain-ai/langchain
            GET /api/repository/files?repo_name=langchain-ai/langchain&path=libs

        GitLab:
            GET /api/repository/files?repo_name=https://gitlab.com/user/project
            GET /api/repository/files?repo_name=https://gitlab.com/user/project&path=src
    """

    logger.info(f"File tree request - repo_name: '{repo_name}', path: '{path}'")

    # Find repository in analyzed list
    repo = next(
        (r for r in analyzed_repositories if r["name"] == repo_name or r["full_name"] == repo_name),
        None
    )

    # If not found in analyzed list, try to fetch directly
    if not repo:
        logger.info(f"Repository '{repo_name}' not in analyzed list, fetching directly")

        # GitLab Feature: Smart URL detection
        if "http" in repo_name:
            # If repo_name is already a URL (GitHub or GitLab)
            repo_url = repo_name
        else:
            # If not URL, assume GitHub
            repo_url = f"https://github.com/{repo_name}"

        try:
            # GitLab Feature: Select correct service
            git_service = get_git_service(repo_url)

            # Verify repository exists by fetching basic info
            repo_info = git_service.get_repository_info(repo_url)

            # Create minimal repo dict for file fetching
            repo = {
                "url": repo_url,
                "full_name": repo_info["full_name"],
                "name": repo_info["name"]
            }

            logger.info(f"Repository found: {repo['full_name']}")

        except ValueError as e:
            logger.error(f"Repository not found: {repo_name} - {e}")
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{repo_name}' not found. Please check the repository name or analyze it first."
            )
        except Exception as e:
            logger.error(f"Error accessing Git API: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to access Git API: {str(e)}"
            )

    try:
        repo_full_name = repo.get('full_name', repo_name)
        repo_url = repo["url"]

        logger.info(f"Fetching file tree for '{repo_full_name}' at path: '{path}'")

        # GitLab Feature: Select correct service and fetch files
        git_service = get_git_service(repo_url)
        files = git_service.get_file_tree(repo_url, path)

        if not files:
            logger.warning(f"No files found at path '{path}' in {repo_full_name}")
            return {
                "repository": repo_full_name,
                "path": path,
                "files": [],
                "total_items": 0
            }

        logger.info(f"Found {len(files)} items at path '{path}'")

        return {
            "repository": repo_full_name,
            "path": path,
            "files": files,
            "total_items": len(files)
        }

    except ValueError as e:
        logger.error(f"Invalid path '{path}' in {repo_name}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid path '{path}': {str(e)}"
        )

    except Exception as e:
        logger.error(f"Error fetching files for {repo_name} at path '{path}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch files: {str(e)}"
        )


# ============================================================================
# LEGACY ENDPOINT: Phase 1 Frontend Compatibility
# ============================================================================
# IMPORTANT: This endpoint maintains backward compatibility with Phase 1 frontend.
# It will be removed in Phase 3. Please migrate to the new query-parameter version.
# ============================================================================

@router.get("/{repo_name}/files", response_model=FileTreeResponse)
async def get_repository_files_legacy(
        repo_name: str,
        path: str = Query("", description="Path within the repository")
):
    """
    Legacy endpoint for Phase 1 frontend compatibility

    DEPRECATED: This endpoint is maintained for backward compatibility with Phase 1 frontend.
    New code should use GET /files with query parameters instead.

    Args:
        repo_name: Repository full name (path parameter, e.g., 'langchain-ai/langchain')
        path: Optional path within the repository (query parameter)

    Returns:
        List of files and directories with metadata

    Examples:
        Phase 1 (Legacy):
            GET /api/repository/langchain-ai/langchain/files
            GET /api/repository/langchain-ai/langchain/files?path=libs

        Phase 2 (Current - Recommended):
            GET /api/repository/files?repo_name=langchain-ai/langchain
            GET /api/repository/files?repo_name=langchain-ai/langchain&path=libs

    Migration Notice:
        This endpoint will be REMOVED in Phase 3.
        Please update your frontend to use the new query parameter format.

    Deprecation Timeline:
        - Phase 2: Both endpoints work (current)
        - Phase 3: Legacy endpoint removed
    """
    logger.info(f"[LEGACY] File tree endpoint called - repo_name: '{repo_name}', path: '{path}'")
    logger.warning(f"[DEPRECATION WARNING] Legacy endpoint /{repo_name}/files is deprecated. "
                   f"Use /files?repo_name={repo_name}&path={path} instead.")

    # Delegate to the new implementation
    return await get_repository_files(repo_name=repo_name, path=path)


@router.delete("/{repo_name}")
async def delete_repository(repo_name: str):
    """Delete an analyzed repository from the system"""

    global analyzed_repositories

    initial_count = len(analyzed_repositories)
    analyzed_repositories = [
        r for r in analyzed_repositories
        if r["name"] != repo_name and r["full_name"] != repo_name
    ]

    if len(analyzed_repositories) == initial_count:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    return {
        "status": "success",
        "message": f"Repository '{repo_name}' removed from system"
    }

@router.get("/analytics/commit-diff")
async def get_commit_diff(
    repo_name: str = Query(...),
    commit_sha: str = Query(...)
):
    '''Get full diff for a commit'''
    try:
        from ..services import github_service, neo4j_service_enhanced
        diff_service = CommitDiffService(github_service, neo4j_service_enhanced)

        repo_url = f"https://github.com/{repo_name}"
        result = diff_service.get_commit_diff(repo_url, commit_sha)

        return {
            'status': 'success',
            'commit': result
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/analytics/compare-commits")
async def compare_commits(
    repo_name: str = Query(...),
    from_commit: str = Query(...),
    to_commit: str = Query(...)
):
    '''Compare two commits'''
    try:
        from ..services import github_service, neo4j_service_enhanced
        diff_service = CommitDiffService(github_service, neo4j_service_enhanced)

        repo_url = f"https://github.com/{repo_name}"
        result = diff_service.compare_commits(repo_url, from_commit, to_commit)

        return {
            'status': 'success',
            'comparison': result
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/analytics/file-diff")
async def get_file_diff(
    repo_name: str = Query(...),
    commit_sha: str = Query(...),
    file_path: str = Query(...)
):
    '''Get diff for specific file'''
    try:
        from ..services import github_service, neo4j_service_enhanced
        diff_service = CommitDiffService(github_service, neo4j_service_enhanced)

        repo_url = f"https://github.com/{repo_name}"
        patch = diff_service.get_file_diff(repo_url, commit_sha, file_path)

        if patch:
            formatted = diff_service.format_diff_for_display(patch)
            return {
                'status': 'success',
                'file_path': file_path,
                'patch': patch,
                'formatted': formatted
            }
        else:
            return {
                'status': 'not_found',
                'message': 'No diff found for this file'
            }
    except Exception as e:
        raise HTTPException(500, str(e))