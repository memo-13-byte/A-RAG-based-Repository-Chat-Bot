from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List
from app.services.github_service import github_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage (will be moved to the database in the future)
analyzed_repositories = []


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


@router.get("/{repo_name}/files")
async def get_repository_files(repo_name: str, path: str = ""):
    """Get the repository's file tree"""

    repo = next(
        (r for r in analyzed_repositories if r["name"] == repo_name or r["full_name"] == repo_name),
        None
    )

    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    try:
        files = github_service.get_file_tree(repo["url"], path)

        return {
            "repository": repo["full_name"],
            "path": path,
            "files": files,
        }

    except Exception as e:
        logger.error(f"Error fetching files for {repo_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch files: {str(e)}")


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