from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ..services.github_service import github_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

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

    - **repository_url**: GitHub repository URL (ex: https://github.com/langchain-ai/langchain)
    """
    try:
        # Fetch repository information from GitHub
        logger.info(f"Analyzing repository: {repository_url}")
        repo_info = github_service.get_repository_info(repository_url)

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
        readme_content = github_service.get_readme(repository_url)
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

        # More detailed analysis can be done in the Background
        # background_tasks.add_task(deep_analyze_repository, repo_info)

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
        # Fetch current statistics from GitHub
        stats = github_service.get_repository_stats(repo["url"])

        # Recent commits
        recent_commits = github_service.get_recent_commits(repo["url"], limit=10)

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
        readme = github_service.get_readme(repo["url"])

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
        repo_name: str = Query(..., description="Repository name (e.g., 'langchain-ai/langchain')"),
        path: str = Query("", description="Path within the repository (e.g., 'src/components')")
):
    """
    Get the repository's file tree (FIXED: uses query parameters)

    Args:
        repo_name: Repository full name (e.g., 'langchain-ai/langchain')
        path: Optional path within the repository to list files from (default: root)

    Returns:
        List of files and directories with metadata

    Examples:
        GET /api/repository/files?repo_name=langchain-ai/langchain
        GET /api/repository/files?repo_name=langchain-ai/langchain&path=libs
        GET /api/repository/files?repo_name=langchain-ai/langchain&path=libs/langchain
    """

    logger.info(f"File tree request - repo_name: '{repo_name}', path: '{path}'")

    # Find repository in analyzed list
    repo = next(
        (r for r in analyzed_repositories if r["name"] == repo_name or r["full_name"] == repo_name),
        None
    )

    # If not found in analyzed list, try to fetch directly from GitHub
    if not repo:
        logger.info(f"Repository '{repo_name}' not in analyzed list, fetching directly from GitHub")

        # Construct GitHub URL
        repo_url = f"https://github.com/{repo_name}"

        try:
            # Verify repository exists by fetching basic info
            repo_info = github_service.get_repository_info(repo_url)

            # Create minimal repo dict for file fetching
            repo = {
                "url": repo_url,
                "full_name": repo_info["full_name"],
                "name": repo_info["name"]
            }

            logger.info(f"Repository found on GitHub: {repo['full_name']}")

        except ValueError as e:
            logger.error(f"Repository not found on GitHub: {repo_name} - {e}")
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{repo_name}' not found. Please check the repository name or analyze it first."
            )
        except Exception as e:
            logger.error(f"Error accessing GitHub: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to access GitHub API: {str(e)}"
            )

    try:
        repo_full_name = repo.get('full_name', repo_name)
        logger.info(f"Fetching file tree for '{repo_full_name}' at path: '{path}'")

        # Get file tree from GitHub service
        files = github_service.get_file_tree(repo["url"], path)

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
        # Invalid path or access denied
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