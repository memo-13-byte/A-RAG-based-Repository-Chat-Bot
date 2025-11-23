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
    """
    if not repo_url:
        return github_service  # Default fallback
        
    url_lower = repo_url.lower()
    
    if "gitlab.com" in url_lower:
        logger.debug(f"Routing to GitLabService for: {repo_url}")
        return gitlab_service
    elif "github.com" in url_lower:
        logger.debug(f"Routing to GitHubService for: {repo_url}")
        return github_service
    else:
        # Default fallback
        return github_service