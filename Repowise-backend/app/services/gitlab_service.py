"""
GitLab Service - GitLab API Integration
Handles all GitLab API interactions maintaining compatibility with GitHubService interface
Supports both gitlab.com and self-hosted GitLab instances
"""

import logging
import gitlab
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
from ..core.config import settings

logger = logging.getLogger(__name__)

class GitLabService:
    """
    GitLab API service for repository operations
    Function signatures mirror GitHubService for seamless integration.
    Supports gitlab.com and self-hosted instances (e.g., gitlab.gnome.org)
    """

    def __init__(self):
        """Initialize the GitLab client with default gitlab.com"""
        # Default client for gitlab.com
        if hasattr(settings, "GITLAB_TOKEN") and settings.GITLAB_TOKEN:
            self.default_client = gitlab.Gitlab("https://gitlab.com", private_token=settings.GITLAB_TOKEN)
            logger.info("GitLab client initialized with authentication for gitlab.com")
        else:
            logger.warning("GITLAB_TOKEN not set - using unauthenticated access")
            self.default_client = gitlab.Gitlab("https://gitlab.com")

        # Cache for different GitLab instances
        self._instance_clients = {}

    def _get_gitlab_url(self, repo_url: str) -> str:
        """
        Extract GitLab instance URL from repository URL

        Examples:
            https://gitlab.com/user/project -> https://gitlab.com
            https://gitlab.gnome.org/GNOME/gnome-shell -> https://gitlab.gnome.org
            https://gitlab.freedesktop.org/mesa/mesa -> https://gitlab.freedesktop.org

        Returns:
            GitLab instance base URL
        """
        parsed = urlparse(repo_url)

        if not parsed.scheme:
            # If no scheme, assume gitlab.com
            return "https://gitlab.com"

        # Extract scheme + netloc (e.g., https://gitlab.gnome.org)
        gitlab_url = f"{parsed.scheme}://{parsed.netloc}"

        logger.debug(f"Extracted GitLab instance URL: {gitlab_url}")
        return gitlab_url

    def _get_client_for_url(self, repo_url: str):
        """
        Get or create GitLab client for specific instance

        Args:
            repo_url: Full repository URL

        Returns:
            GitLab client for that instance
        """
        gitlab_url = self._get_gitlab_url(repo_url)

        # Use cached client if available
        if gitlab_url in self._instance_clients:
            return self._instance_clients[gitlab_url]

        # Create new client for this instance
        try:
            # For gitlab.com, use token if available
            if "gitlab.com" in gitlab_url:
                if hasattr(settings, "GITLAB_TOKEN") and settings.GITLAB_TOKEN:
                    client = gitlab.Gitlab(gitlab_url, private_token=settings.GITLAB_TOKEN)
                else:
                    client = gitlab.Gitlab(gitlab_url)
            else:
                # For self-hosted instances, use without token (public access)
                logger.info(f"Creating unauthenticated client for {gitlab_url}")
                client = gitlab.Gitlab(gitlab_url)

            # Cache the client
            self._instance_clients[gitlab_url] = client
            logger.info(f"Created GitLab client for: {gitlab_url}")

            return client

        except Exception as e:
            logger.error(f"Failed to create GitLab client for {gitlab_url}: {e}")
            # Fallback to default client
            return self.default_client

    def parse_repo_url(self, url: str) -> Tuple[str, str]:
        """
        Extract namespace and project name from GitLab URL

        GitLab supports nested groups, so 'owner' might be 'group/subgroup'.

        Examples:
            https://gitlab.com/gitlab-org/gitlab -> ('gitlab-org', 'gitlab')
            https://gitlab.gnome.org/GNOME/gnome-shell -> ('GNOME', 'gnome-shell')
            https://gitlab.freedesktop.org/mesa/mesa -> ('mesa', 'mesa')

        Returns:
            Tuple of (namespace, project_name)
        """
        url = url.strip()

        # Handle simple string like "owner/repo"
        if "gitlab" not in url and "http" not in url:
            parts = url.split("/")
            if len(parts) >= 2:
                return "/".join(parts[:-1]), parts[-1]

        parsed = urlparse(url)
        path = parsed.path.strip("/")

        if path.endswith(".git"):
            path = path[:-4]

        parts = path.split("/")

        if len(parts) < 2:
            raise ValueError(f"Invalid GitLab URL format: '{url}'. Expected format: https://gitlab.xxx/namespace/project")

        # GitLab: last part is project name, everything before is namespace
        project_name = parts[-1]
        namespace = "/".join(parts[:-1])

        logger.debug(f"Parsed GitLab URL '{url}' -> namespace='{namespace}', project='{project_name}'")
        return namespace, project_name

    def _get_project(self, repo_url: str):
        """Helper to get GitLab project object from any instance"""
        # Get client for this specific GitLab instance
        client = self._get_client_for_url(repo_url)

        namespace, project_name = self.parse_repo_url(repo_url)

        # GitLab uses URL-encoded path as ID (e.g. group%2Fproject)
        project_path = f"{namespace}/{project_name}"

        try:
            logger.info(f"Fetching GitLab project: {project_path}")
            return client.projects.get(project_path)
        except gitlab.GitlabGetError as e:
            if e.response_code == 404:
                raise ValueError(f"GitLab repository '{project_path}' not found on {self._get_gitlab_url(repo_url)}")
            raise ValueError(f"GitLab API error: {e}")
        except Exception as e:
            logger.error(f"Error accessing GitLab project '{project_path}': {e}")
            raise ValueError(f"Failed to access GitLab repository: {str(e)}")

    def get_repository_info(self, repo_url: str) -> Dict[str, Any]:
        """Get comprehensive repository information matching GitHub format"""
        try:
            project = self._get_project(repo_url)

            # Helper function for safe attribute access
            def safe_get(obj, attr, default=None):
                """Safely get attribute with fallback"""
                try:
                    return getattr(obj, attr, default)
                except:
                    return default

            # Map GitLab attributes to GitHub-like structure
            return {
                "id": safe_get(project, 'id', 0),
                "name": safe_get(project, 'name', 'Unknown'),
                "full_name": safe_get(project, 'path_with_namespace', 'Unknown'),
                "url": safe_get(project, 'web_url', repo_url),
                "description": safe_get(project, 'description') or "No description provided",
                "language": "Mixed/Unknown",  # GitLab doesn't provide single primary language directly
                "stars": safe_get(project, 'star_count', 0),
                "forks": safe_get(project, 'forks_count', 0),
                "open_issues": safe_get(project, 'open_issues_count', 0),
                "created_at": safe_get(project, 'created_at', ''),
                "updated_at": safe_get(project, 'last_activity_at', ''),
                "pushed_at": safe_get(project, 'last_activity_at', ''),
                "topics": safe_get(project, 'topics', []),
                "default_branch": safe_get(project, 'default_branch', 'main'),
                "size": safe_get(project, 'statistics', {}).get('storage_size', 0) // 1024 if hasattr(project, 'statistics') else 0,
                "license": safe_get(project, 'license', {}).get('name') if hasattr(project, 'license') else None,
                "private": safe_get(project, 'visibility', 'public') == 'private',
                "archived": safe_get(project, 'archived', False),
                "disabled": False,
                "homepage": safe_get(project, 'web_url', repo_url)
            }
        except Exception as e:
            logger.error(f"Error fetching GitLab repo info for '{repo_url}': {e}")
            raise ValueError(f"Failed to fetch GitLab repository: {str(e)}")

    def get_repository_stats(self, repo_url: str) -> Dict[str, Any]:
        """Get repository statistics"""
        try:
            project = self._get_project(repo_url)

            # Helper function for safe attribute access
            def safe_get(obj, attr, default=None):
                """Safely get attribute with fallback"""
                try:
                    return getattr(obj, attr, default)
                except:
                    return default

            # Languages
            try:
                languages = project.languages()
                total_bytes = sum(languages.values()) if languages else 1
                language_percentages = {
                    lang: round((count / total_bytes) * 100, 2)
                    for lang, count in languages.items()
                } if languages else {}
            except Exception as e:
                logger.debug(f"Could not fetch languages: {e}")
                language_percentages = {}

            # Commits count (approximate via statistics if available)
            try:
                commit_count = safe_get(project, 'statistics', {}).get('commit_count', 0) if hasattr(project, 'statistics') else 0
            except:
                commit_count = 0

            return {
                "total_commits": commit_count,
                "contributors_count": 0,
                "top_contributors": [],
                "languages": language_percentages,
                "open_issues": safe_get(project, 'open_issues_count', 0),
                "closed_issues": 0,
                "pull_requests": 0,
                "branches": 0,
                "releases": 0,
                "watchers": 0,
                "network_count": 0
            }
        except Exception as e:
            logger.error(f"Error fetching GitLab stats: {e}")
            raise ValueError(f"Failed to fetch stats: {str(e)}")

    def get_readme(self, repo_url: str) -> Optional[str]:
        """Get README content"""
        try:
            project = self._get_project(repo_url)
            # Try typical README filenames
            for name in ['README.md', 'readme.md', 'README', 'README.txt', 'readme.txt']:
                try:
                    f = project.files.get(file_path=name, ref=project.default_branch)
                    return f.decode().decode('utf-8')
                except:
                    continue
            return None
        except Exception as e:
            logger.warning(f"Error fetching GitLab README: {e}")
            return None

    def get_recent_commits(self, repo_url: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent commits"""
        try:
            project = self._get_project(repo_url)
            commits = project.commits.list(per_page=limit)

            return [{
                "sha": c.short_id,
                "full_sha": c.id,
                "message": c.title,
                "author": c.author_name,
                "author_email": c.author_email,
                "date": c.created_at,
                "url": c.web_url
            } for c in commits]
        except Exception as e:
            logger.error(f"Error fetching GitLab commits: {e}")
            return []

    def get_file_tree(self, repo_url: str, path: str = "") -> List[Dict[str, Any]]:
        """Get file tree"""
        try:
            project = self._get_project(repo_url)
            # GitLab API: empty path returns root, otherwise returns specified folder
            items = project.repository_tree(path=path, ref=project.default_branch, per_page=100)

            tree = []
            for item in items:
                tree.append({
                    "name": item['name'],
                    "path": item['path'],
                    "type": 'dir' if item['type'] == 'tree' else 'file',
                    "size": 0,  # Tree endpoint doesn't return size
                    "sha": item['id'],
                    "url": f"{project.web_url}/-/blob/{project.default_branch}/{item['path']}" if item['type'] == 'blob' else f"{project.web_url}/-/tree/{project.default_branch}/{item['path']}",
                    "download_url": None
                })

            # Sort directories first
            return sorted(tree, key=lambda x: (x['type'] != 'dir', x['name'].lower()))

        except Exception as e:
            logger.error(f"Error fetching GitLab file tree: {e}")
            raise ValueError(f"Failed to fetch file tree: {str(e)}")

    def get_file_content(self, repo_url: str, file_path: str) -> Optional[str]:
        """Get content of a specific file"""
        try:
            project = self._get_project(repo_url)
            f = project.files.get(file_path=file_path, ref=project.default_branch)
            return f.decode().decode('utf-8')
        except Exception as e:
            logger.error(f"Error fetching GitLab file content: {e}")
            return None

    def search_code(self, query: str, repo_url: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search code (blobs) in GitLab"""
        try:
            project = self._get_project(repo_url)
            # GitLab requires 'scope' for search
            results = project.search('blobs', query)[:max_results]

            search_results = []
            for res in results:
                search_results.append({
                    "name": res['filename'],
                    "path": res['filename'],
                    "sha": res.get('id'),
                    "url": f"{project.web_url}/-/blob/{res['ref']}/{res['filename']}",
                    "repository": project.path_with_namespace,
                    "score": None
                })
            return search_results
        except Exception as e:
            logger.error(f"GitLab code search error: {e}")
            return []

# Singleton instance
gitlab_service = GitLabService()