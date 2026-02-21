"""
GitHub Service - GitHub API Integration
Handles all GitHub API interactions with comprehensive error handling and logging
FIXED: Safe attribute access + RECURSIVE file tree fetching
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

import requests
from github import Github, GithubException
from github.Repository import Repository
from github.ContentFile import ContentFile
from github.Commit import Commit
from ..core.config import settings

logger = logging.getLogger(__name__)


class GitHubService:
    """
    GitHub API service for repository operations

    Provides methods for:
    - Repository information retrieval
    - Statistics and metrics
    - File tree navigation (single level AND recursive)
    - Code search
    - Commit history
    """

    def __init__(self):
        """Initialize the GitHub client with authentication token"""
        if not settings.GITHUB_TOKEN:
            logger.warning("GITHUB_TOKEN not set - using unauthenticated access (rate limited to 60 requests/hour)")
            self.client = Github()
        else:
            self.client = Github(settings.GITHUB_TOKEN)
            logger.info("GitHub client initialized with authentication")

    def parse_repo_url(self, url: str) -> Tuple[str, str]:
        """
        Extract owner and repo name from GitHub URL

        Supported formats:
        - https://github.com/owner/repo
        - http://github.com/owner/repo
        - github.com/owner/repo
        - owner/repo

        Args:
            url: GitHub repository URL or owner/repo string

        Returns:
            Tuple of (owner, repo_name)

        Raises:
            ValueError: If URL format is invalid

        Examples:
            >>> parse_repo_url("https://github.com/langchain-ai/langchain")
            ("langchain-ai", "langchain")
            >>> parse_repo_url("openai/gpt-4")
            ("openai", "gpt-4")
        """
        # Clean and normalize URL
        url = url.strip()
        url = url.replace("https://", "").replace("http://", "")
        url = url.replace("github.com/", "")
        url = url.rstrip("/")

        # Split into parts
        parts = url.split("/")

        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub URL format: '{url}'. Expected format: 'owner/repo' or 'https://github.com/owner/repo'")

        owner, repo_name = parts[0], parts[1]

        # Validate owner and repo name
        if not owner or not repo_name:
            raise ValueError(f"Invalid GitHub URL: owner or repository name is empty")

        logger.debug(f"Parsed URL '{url}' -> owner='{owner}', repo='{repo_name}'")
        return owner, repo_name

    def _parse_repo_url(self, repo_url: str) -> tuple:
        """Wrapper for parse_github_url"""
        return self.parse_repo_url(repo_url)

    def get_repository_info(self, repo_url: str) -> Dict[str, Any]:
        """
        Get comprehensive repository information from GitHub

        Args:
            repo_url: GitHub repository URL

        Returns:
            Dictionary containing repository metadata

        Raises:
            ValueError: If repository not found or API error occurs
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            logger.info(f"Fetching repository info for {owner}/{repo_name}")

            repo = self.client.get_repo(f"{owner}/{repo_name}")

            # Helper function for safe attribute access
            def safe_get(obj, attr, default=None):
                """Safely get attribute with fallback"""
                try:
                    return getattr(obj, attr, default)
                except:
                    return default

            return {
                "id": safe_get(repo, 'id', 0),
                "name": safe_get(repo, 'name', 'Unknown'),
                "full_name": safe_get(repo, 'full_name', 'Unknown'),
                "url": safe_get(repo, 'html_url', repo_url),
                "description": safe_get(repo, 'description') or "No description provided",
                "language": safe_get(repo, 'language') or "Not specified",
                "stars": safe_get(repo, 'stargazers_count', 0),
                "forks": safe_get(repo, 'forks_count', 0),
                "open_issues": safe_get(repo, 'open_issues_count', 0),
                "created_at": repo.created_at.isoformat() if safe_get(repo, 'created_at') else None,
                "updated_at": repo.updated_at.isoformat() if safe_get(repo, 'updated_at') else None,
                "pushed_at": repo.pushed_at.isoformat() if safe_get(repo, 'pushed_at') else None,
                "topics": safe_get(repo, 'get_topics', lambda: [])() if hasattr(repo, 'get_topics') else [],
                "default_branch": safe_get(repo, 'default_branch', 'main'),
                "size": safe_get(repo, 'size', 0),  # Size in KB
                "license": repo.license.name if safe_get(repo, 'license') and repo.license else None,
                "private": safe_get(repo, 'private', False),
                "archived": safe_get(repo, 'archived', False),
                "disabled": safe_get(repo, 'disabled', False),
                "homepage": safe_get(repo, 'homepage', ''),
            }

        except GithubException as e:
            if e.status == 404:
                logger.error(f"Repository not found: {owner}/{repo_name}")
                raise ValueError(f"Repository '{owner}/{repo_name}' not found")
            elif e.status == 403:
                logger.error(f"Access forbidden: {e.data.get('message', 'API rate limit exceeded or insufficient permissions')}")
                raise ValueError(f"Access forbidden: {e.data.get('message', 'Check your API token permissions')}")
            else:
                logger.error(f"GitHub API error ({e.status}): {e.data.get('message', str(e))}")
                raise ValueError(f"GitHub API error: {e.data.get('message', str(e))}")

        except ValueError:
            # Re-raise ValueError from parse_repo_url
            raise

        except Exception as e:
            logger.error(f"Unexpected error fetching repository info: {e}")
            raise ValueError(f"Failed to fetch repository: {str(e)}")

    def get_repository_stats(self, repo_url: str) -> Dict[str, Any]:
        """
        Get detailed repository statistics

        Args:
            repo_url: GitHub repository URL

        Returns:
            Dictionary containing statistics and metrics

        Raises:
            ValueError: If repository not found or API error occurs
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            logger.info(f"Fetching statistics for {owner}/{repo_name}")

            repo = self.client.get_repo(f"{owner}/{repo_name}")

            # Commit count (note: expensive operation for large repos)
            try:
                commits = repo.get_commits()
                commit_count = commits.totalCount
            except:
                commit_count = 0
                logger.warning(f"Could not fetch commit count for {owner}/{repo_name}")

            # Contributors
            try:
                contributors = list(repo.get_contributors())
                contributors_count = len(contributors)

                # Top 5 contributors
                top_contributors = [
                    {
                        "login": contrib.login,
                        "contributions": contrib.contributions,
                        "avatar_url": contrib.avatar_url,
                        "profile_url": contrib.html_url,
                    }
                    for contrib in contributors[:5]
                ]
            except:
                contributors_count = 0
                top_contributors = []
                logger.warning(f"Could not fetch contributors for {owner}/{repo_name}")

            # Languages (percentage distribution)
            try:
                languages = repo.get_languages()
                total_bytes = sum(languages.values())

                if total_bytes > 0:
                    language_percentages = {
                        lang: round((bytes_count / total_bytes) * 100, 2)
                        for lang, bytes_count in languages.items()
                    }
                else:
                    language_percentages = {}
            except:
                language_percentages = {}
                logger.warning(f"Could not fetch languages for {owner}/{repo_name}")

            # Issues and PRs
            try:
                open_issues = repo.open_issues_count
                closed_issues = repo.get_issues(state="closed").totalCount
            except:
                open_issues = 0
                closed_issues = 0

            try:
                total_prs = repo.get_pulls(state="all").totalCount
            except:
                total_prs = 0

            # Branches and releases
            try:
                branches_count = repo.get_branches().totalCount
            except:
                branches_count = 0

            try:
                releases_count = repo.get_releases().totalCount
            except:
                releases_count = 0

            return {
                "total_commits": commit_count,
                "contributors_count": contributors_count,
                "top_contributors": top_contributors,
                "languages": language_percentages,
                "open_issues": open_issues,
                "closed_issues": closed_issues,
                "pull_requests": total_prs,
                "branches": branches_count,
                "releases": releases_count,
                "watchers": repo.watchers_count,
                "network_count": repo.network_count,
            }

        except GithubException as e:
            logger.error(f"GitHub API error fetching stats: {e}")
            raise ValueError(f"Failed to fetch repository stats: {e.data.get('message', str(e))}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"Error fetching repository stats: {e}")
            raise ValueError(f"Failed to fetch stats: {str(e)}")

    def get_readme(self, repo_url: str) -> Optional[str]:
        """
        Get the README content of a repository

        Args:
            repo_url: GitHub repository URL

        Returns:
            README content as markdown string, or None if not found
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            logger.info(f"Fetching README for {owner}/{repo_name}")

            repo = self.client.get_repo(f"{owner}/{repo_name}")
            readme = repo.get_readme()
            content = readme.decoded_content.decode('utf-8')

            logger.info(f"README fetched successfully ({len(content)} characters)")
            return content

        except GithubException as e:
            if e.status == 404:
                logger.info(f"README not found for {repo_url}")
            else:
                logger.warning(f"Error fetching README: {e}")
            return None

        except Exception as e:
            logger.warning(f"Unexpected error fetching README: {e}")
            return None

    def get_recent_commits(self, repo_url: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent commits from a repository

        Args:
            repo_url: GitHub repository URL
            limit: Maximum number of commits to fetch (default: 10)

        Returns:
            List of commit dictionaries with details
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            logger.info(f"Fetching {limit} recent commits for {owner}/{repo_name}")

            repo = self.client.get_repo(f"{owner}/{repo_name}")
            commits = repo.get_commits()[:limit]

            commit_list = []
            for commit in commits:
                commit_list.append({
                    "sha": commit.sha[:7],  # Short SHA
                    "full_sha": commit.sha,
                    "message": commit.commit.message.split('\n')[0],  # First line only
                    "author": commit.commit.author.name if commit.commit.author else "Unknown",
                    "author_email": commit.commit.author.email if commit.commit.author else None,
                    "date": commit.commit.author.date.isoformat() if commit.commit.author and commit.commit.author.date else None,
                    "url": commit.html_url,
                })

            logger.info(f"Fetched {len(commit_list)} commits")
            return commit_list

        except Exception as e:
            logger.error(f"Error fetching recent commits: {e}")
            return []

    def get_file_tree(self, repo_url: str, path: str = "") -> List[Dict[str, Any]]:
        """
        Get the file tree of a repository at a given path (NON-RECURSIVE - single level only)

        Args:
            repo_url: GitHub repository URL
            path: Path within the repository (default: root "")

        Returns:
            List of files and directories with metadata (single level only)

        Raises:
            ValueError: If path is invalid

        Note:
            For recursive file fetching, use get_all_files_recursive()
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            logger.info(f"Fetching file tree for {owner}/{repo_name} at path: '{path}'")

            repo = self.client.get_repo(f"{owner}/{repo_name}")

            # Get contents at specified path
            contents = repo.get_contents(path)

            # Handle single file vs directory listing
            if not isinstance(contents, list):
                contents = [contents]

            # Sort: directories first, then files (alphabetically)
            sorted_contents = sorted(
                contents,
                key=lambda x: (x.type != 'dir', x.name.lower())
            )

            # Format file tree
            file_tree = []
            for content in sorted_contents:
                file_tree.append({
                    "name": content.name,
                    "path": content.path,
                    "type": content.type,  # 'file' or 'dir'
                    "size": content.size,
                    "sha": content.sha,  # Git SHA hash
                    "url": content.html_url,
                    "download_url": content.download_url if content.type == 'file' else None,
                })

            logger.info(f"Found {len(file_tree)} items at path '{path}'")
            return file_tree

        except GithubException as e:
            if e.status == 404:
                logger.error(f"Path not found: '{path}' in {repo_url}")
                raise ValueError(f"Path '{path}' not found in repository")
            else:
                logger.error(f"GitHub API error: {e}")
                raise ValueError(f"Failed to fetch file tree: {e.data.get('message', str(e))}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"Error fetching file tree: {e}")
            raise ValueError(f"Failed to fetch file tree: {str(e)}")

    def get_all_files_recursive(
        self,
        repo_url: str,
        path: str = "",
        file_extension: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Recursively get ALL files from repository (or filtered by extension)

        Args:
            repo_url: GitHub repository URL
            path: Starting path (default: root "")
            file_extension: Optional file extension filter (e.g., ".py", ".js")

        Returns:
            List of all files matching criteria (recursive through all subdirectories)

        Example:
            >>> get_all_files_recursive(url, file_extension=".py")
            [{"name": "main.py", "path": "src/main.py", ...}, ...]

        Note:
            This recursively traverses ALL subdirectories!
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            filter_msg = f" ({file_extension} only)" if file_extension else ""
            logger.info(f"Recursively fetching files{filter_msg} for {owner}/{repo_name} from path: '{path}'")

            repo = self.client.get_repo(f"{owner}/{repo_name}")
            all_files = []

            def fetch_recursive(current_path: str = ""):
                """Recursively fetch all files from current path"""
                try:
                    contents = repo.get_contents(current_path)

                    # Handle single file vs directory
                    if not isinstance(contents, list):
                        contents = [contents]

                    for content in contents:
                        if content.type == "file":
                            # Check extension filter if provided
                            if file_extension is None or content.name.endswith(file_extension):
                                all_files.append({
                                    "name": content.name,
                                    "path": content.path,
                                    "type": "file",
                                    "size": content.size,
                                    "sha": content.sha,
                                    "url": content.html_url,
                                    "download_url": content.download_url,
                                })

                        elif content.type == "dir":
                            # Recursively fetch subdirectory
                            fetch_recursive(content.path)

                except GithubException as e:
                    logger.warning(f"Error fetching path '{current_path}': {e}")
                except Exception as e:
                    logger.warning(f"Unexpected error at '{current_path}': {e}")

            # Start recursive fetch
            fetch_recursive(path)

            logger.info(f"Found {len(all_files)} files recursively{filter_msg}")

            return all_files

        except Exception as e:
            logger.error(f"Error in recursive file fetch: {e}")
            return []

    def search_code(
        self,
        query: str,
        repo_url: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search code within a repository

        Args:
            query: Search query string
            repo_url: GitHub repository URL
            max_results: Maximum number of results to return

        Returns:
            List of search results with file details
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            logger.info(f"Searching code in {owner}/{repo_name} for: '{query}'")

            # GitHub code search syntax: "query repo:owner/repo"
            full_query = f"{query} repo:{owner}/{repo_name}"
            results = self.client.search_code(full_query)

            search_results = []
            for result in results[:max_results]:
                search_results.append({
                    "name": result.name,
                    "path": result.path,
                    "sha": result.sha,
                    "url": result.html_url,
                    "repository": result.repository.full_name,
                    "score": result.score if hasattr(result, 'score') else None,
                })

            logger.info(f"Found {len(search_results)} code search results")
            return search_results

        except GithubException as e:
            logger.error(f"GitHub API error during code search: {e}")
            return []

        except Exception as e:
            logger.error(f"Error searching code: {e}")
            return []

    def get_file_content(self, repo_url: str, file_path: str) -> Optional[str]:
        """
        Get the content of a specific file from repository

        Args:
            repo_url: GitHub repository URL
            file_path: Path to the file within repository

        Returns:
            File content as string, or None if error

        Example:
            >>> get_file_content("https://github.com/user/repo", "src/main.py")
            "import os\n\ndef main():\n..."
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            logger.info(f"Fetching file content: {file_path} from {owner}/{repo_name}")

            repo = self.client.get_repo(f"{owner}/{repo_name}")
            content = repo.get_contents(file_path)

            if isinstance(content, ContentFile):
                file_content = content.decoded_content.decode('utf-8')
                logger.info(f"File content fetched ({len(file_content)} characters)")
                return file_content

            logger.warning(f"Path is not a file: {file_path}")
            return None

        except GithubException as e:
            if e.status == 404:
                logger.error(f"File not found: {file_path}")
            else:
                logger.error(f"Error fetching file content: {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error fetching file: {e}")
            return None

    def check_rate_limit(self) -> Dict[str, Any]:
        """
        Check GitHub API rate limit status

        Returns:
            Dictionary with rate limit information
        """
        try:
            rate_limit = self.client.get_rate_limit()
            core = rate_limit.core

            return {
                "limit": core.limit,
                "remaining": core.remaining,
                "reset": core.reset.isoformat() if core.reset else None,
                "used": core.limit - core.remaining,
            }
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return {
                "limit": 0,
                "remaining": 0,
                "reset": None,
                "used": 0,
            }

    def get_commit_details(self, repo_url: str, commit_sha: str) -> Dict[str, Any]:
        """Get detailed commit information including file changes"""
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            logger.info(f"Fetching commit details: {commit_sha[:7]} from {owner}/{repo_name}")

            repo = self.client.get_repo(f"{owner}/{repo_name}")
            commit = repo.get_commit(commit_sha)

            # Extract file changes
            files = []
            for file in commit.files:
                files.append({
                    'filename': file.filename,
                    'status': file.status,
                    'additions': file.additions,
                    'deletions': file.deletions,
                    'changes': file.changes,
                    'patch': getattr(file, 'patch', None),
                    'previous_filename': getattr(file, 'previous_filename', None)  # ← FİX!
                })

            logger.info(f"Commit {commit_sha[:7]} has {len(files)} files")

            return {
                'sha': commit.sha,
                'message': commit.commit.message,
                'author': {
                    'name': commit.commit.author.name,
                    'email': commit.commit.author.email
                },
                'date': commit.commit.author.date.isoformat(),
                'stats': {
                    'additions': commit.stats.additions,
                    'deletions': commit.stats.deletions,
                    'total': commit.stats.total
                },
                'files': files
            }

        except Exception as e:
            logger.error(f"Error getting commit details: {e}")
            return {'files': []}


# Singleton instance
github_service = GitHubService()