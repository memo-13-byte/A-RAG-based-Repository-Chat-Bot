"""
GitLab Service - GitLab API Integration
Handles all GitLab API interactions maintaining compatibility with GitHubService interface
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
    """

    def __init__(self):
        """Initialize the GitLab client"""
        # .env dosyasındaki GITLAB_TOKEN'ı kullanır
        if hasattr(settings, "GITLAB_TOKEN") and settings.GITLAB_TOKEN:
            self.client = gitlab.Gitlab(private_token=settings.GITLAB_TOKEN)
            logger.info("GitLab client initialized with authentication")
        else:
            logger.warning("GITLAB_TOKEN not set - functionality may be limited")
            self.client = gitlab.Gitlab()

    def parse_repo_url(self, url: str) -> Tuple[str, str]:
        """
        Extract namespace and project name from GitLab URL
        
        GitLab supports nested groups, so 'owner' might be 'group/subgroup'.
        
        Returns:
            Tuple of (namespace, project_name)
        """
        url = url.strip()
        
        # Handle simple string like "owner/repo"
        if "gitlab.com" not in url and "http" not in url:
            parts = url.split("/")
            if len(parts) >= 2:
                return "/".join(parts[:-1]), parts[-1]
                
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        
        if path.endswith(".git"):
            path = path[:-4]
            
        parts = path.split("/")
        
        if len(parts) < 2:
            raise ValueError(f"Invalid GitLab URL format: '{url}'")
            
        # GitLab'da son parça proje adı, öncekiler namespace (group/subgroup)
        project_name = parts[-1]
        namespace = "/".join(parts[:-1])
        
        logger.debug(f"Parsed GitLab URL '{url}' -> namespace='{namespace}', project='{project_name}'")
        return namespace, project_name

    def _get_project(self, repo_url: str):
        """Helper to get GitLab project object"""
        namespace, project_name = self.parse_repo_url(repo_url)
        # GitLab uses URL-encoded path as ID (e.g. group%2Fproject)
        project_path = f"{namespace}/{project_name}"
        try:
            return self.client.projects.get(project_path)
        except gitlab.GitlabGetError as e:
            if e.response_code == 404:
                raise ValueError(f"GitLab repository '{project_path}' not found")
            raise ValueError(f"GitLab API error: {e}")

    def get_repository_info(self, repo_url: str) -> Dict[str, Any]:
        """Get comprehensive repository information matching GitHub format"""
        try:
            project = self._get_project(repo_url)
            
            # Map GitLab attributes to GitHub-like structure
            return {
                "id": project.id,
                "name": project.name,
                "full_name": project.path_with_namespace,
                "url": project.web_url,
                "description": project.description or "No description provided",
                "language": "Mixed/Unknown", # GitLab doesn't provide single primary language directly in simple calls
                "stars": project.star_count,
                "forks": project.forks_count,
                "open_issues": project.open_issues_count if hasattr(project, 'open_issues_count') else 0,
                "created_at": project.created_at,
                "updated_at": project.last_activity_at,
                "pushed_at": project.last_activity_at,
                "topics": project.topics,
                "default_branch": project.default_branch,
                "size": getattr(project, 'statistics', {}).get('storage_size', 0) // 1024 if hasattr(project, 'statistics') else 0,
                "license": project.license.get('name') if hasattr(project, 'license') and project.license else None,
                "private": project.visibility == 'private',
                "archived": project.archived,
                "disabled": False, # GitLab concept matches archived mostly
                "homepage": project.web_url
            }
        except Exception as e:
            logger.error(f"Error fetching GitLab repo info: {e}")
            raise ValueError(f"Failed to fetch GitLab repository: {str(e)}")

    def get_repository_stats(self, repo_url: str) -> Dict[str, Any]:
        """Get repository statistics"""
        try:
            project = self._get_project(repo_url)
            
            # Languages
            languages = project.languages()
            total_bytes = sum(languages.values())
            language_percentages = {
                lang: round((count / total_bytes) * 100, 2)
                for lang, count in languages.items()
            }
            
            # Commits count (approximate via statistics if available)
            commit_count = getattr(project, 'statistics', {}).get('commit_count', 0)
            
            return {
                "total_commits": commit_count,
                "contributors_count": 0, # GitLab API doesn't give simple contributor count without iteration
                "top_contributors": [], # Expensive to calculate on GitLab
                "languages": language_percentages,
                "open_issues": project.open_issues_count,
                "closed_issues": 0, # Requires separate API call
                "pull_requests": 0, # "Merge Requests" in GitLab
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
            for name in ['README.md', 'readme.md', 'README', 'readme.txt']:
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
            # GitLab API'de path boşsa root döner, path varsa o klasörü döner
            items = project.repository_tree(path=path, ref=project.default_branch, per_page=100)
            
            tree = []
            for item in items:
                tree.append({
                    "name": item['name'],
                    "path": item['path'],
                    "type": 'dir' if item['type'] == 'tree' else 'file',
                    "size": 0, # Tree endpoint doesn't return size
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
                    "path": res['filename'], # API returns filename as path usually
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