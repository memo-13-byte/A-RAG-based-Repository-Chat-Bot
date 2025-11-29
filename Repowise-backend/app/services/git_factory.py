"""
Git Service Factory
Decides which service (GitHub or GitLab) to use based on the URL.
"""

from typing import Union
from .github_service import github_service, GitHubService
from .gitlab_service import gitlab_service, GitLabService
import logging

logger = logging.getLogger(__name__)

def get_git_service(repo_url: str) -> Union[GitHubService, GitLabService]:
    """
    Returns the appropriate service based on the repository URL.

    Supports:
    - GitHub (github.com)
    - GitLab.com (gitlab.com)
    - Self-hosted GitLab instances (any URL with 'gitlab' in domain)
    """
    if not repo_url:
        logger.warning("Empty repo_url provided, defaulting to GitHub service")
        return github_service  # Default fallback

    url_lower = repo_url.lower()

    # Check for GitLab (any instance)
    # Supports: gitlab.com, gitlab.gnome.org, gitlab.freedesktop.org, etc.
    if "gitlab" in url_lower:
        logger.debug(f"Routing to GitLabService for: {repo_url}")
        return gitlab_service

    # Check for GitHub
    elif "github.com" in url_lower or "github" in url_lower:
        logger.debug(f"Routing to GitHubService for: {repo_url}")
        return github_service

    else:
        # Default fallback to GitHub
        logger.warning(f"Unknown git hosting service for '{repo_url}', defaulting to GitHub")
        return github_service