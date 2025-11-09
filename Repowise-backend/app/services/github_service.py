"""
GitHub Service - GitHub API integration
"""

from github import Github, GithubException
from typing import Dict, List, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class GitHubService:
    """GitHub API service"""

    def __init__(self):
        """Begin the GitHub client"""
        if not settings.GITHUB_TOKEN:
            logger.warning("GITHUB_TOKEN not set, using unauthenticated access (limited)")
            self.client = Github()
        else:
            self.client = Github(settings.GITHUB_TOKEN)

    def parse_repo_url(self, url: str) -> tuple[str, str]:
        """
        Extract owner and repo name from GitHub URL

        Examples:
        - https://github.com/langchain-ai/langchain -> ("langchain-ai", "langchain")
        - github.com/openai/gpt-4 -> ("openai", "gpt-4")

        :param url: GitHub repository URL
        :return: (owner, repo_name)
        """

        # Clean URL
        url = url.strip().lower()
        url = url.replace("https://", "").replace("http://", "")
        url = url.replace("github.com/", "")
        url = url.rstrip("/")

        # Parse in owner/repo format
        parts = url.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]

        raise ValueError(f"Invalid GitHub URL: {url}")

    def get_repository_info(self, repo_url: str) -> Dict:
        """
        Get repository information from GitHub

        :param repo_url: GitHub repository URL
        :return: Repository information dictionary
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            repo = self.client.get_repo(f"{owner}/{repo_name}")
            return {
                "id": repo.id,
                "name": repo.name,
                "full_name": repo.full_name,
                "url": repo.html_url,
                "description": repo.description,
                "language": repo.language,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "topics": repo.get_topics(),
                "default_branch": repo.default_branch,
                "size": repo.size, # in KB
                "license": repo.license.name if repo.license else None
            }
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            raise ValueError(f"Failed to fetch repositoy: {e.data.get('message', str(e))}")
        except Exception as e:
            logger.error(f"Error fetching repository info: {e}")
            raise ValueError(f"Invalid repository URL or API error: {str(e)}")

    def get_repository_stats(self, repo_url: str) -> Dict:
        """
        Get repository statistics from GitHub

        :param repo_url: GitHub repository URL
        :return: Repository statistics dictionary
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            repo = self.client.get_repo(f"{owner}/{repo_name}")

            # Commit numbers (may require pagination for large repos)
            commits = repo.get_commits()
            commit_count = commits.totalCount if hasattr(commits, 'totalCount') else 0

            # Contributors
            contributors = list(repo.get_contributors())

            # Top 5 contributors
            top_contributors = [
                {
                    "login": contrib.login,
                    "contributions": contrib.contributions,
                    "avatar_url": contrib.avatar_url,
                }
                for contrib in contributors[:5]
            ]

            # Languages
            languages = repo.get_languages()
            total_bytes = sum(languages.values())
            language_percentages = {
                lang: round((bytes_count / total_bytes) * 100, 2)
                for lang, bytes_count in languages.items()
            }

            return {
                "total_commits": commit_count,
                "contributors_count": len(contributors),
                "top_contributors": top_contributors,
                "languages": language_percentages,
                "open_issues": repo.open_issues_count,
                "closed_issues": repo.get_issues(state="closed").totalCount if hasattr(repo.get_issues(state="closed"), 'totalCount') else 0,
                "pull_requests": repo.get_pulls(state="all").totalCount if hasattr(repo.get_pulls(state="all"), 'totalCount') else 0,
                "branches": repo.get_branches().totalCount if hasattr(repo.get_branches(), 'totalCount') else 0,
                "releases": repo.get_releases().totalCount if hasattr(repo.get_releases(), 'totalCount') else 0,
            }
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            raise ValueError(f"Failed to fetch repository stats: {e.data.get('message', str(e))}")
        except Exception as e:
            logger.error(f"Error fetching repository stats: {e}")
            raise ValueError(f"Invalid repository URL or API error: {str(e)}")

    def get_readme(self, repo_url: str) -> Optional[str]:
        """
        Get the README content of a repository

        :param repo_url: GitHub repository URL
        :return: README content as string (markdown) or None if not found
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            repo = self.client.get_repo(f"{owner}/{repo_name}")

            readme = repo.get_readme()
            content = readme.decoded_content.decode('utf-8')

            return content

        except Exception as e:
            logger.warning(f"README not found or error: {e}")
            return None

    def get_recent_commits(self, repo_url: str, limit: int = 10) -> List[Dict]:
        """
        Get recent commits from a repository

        :param repo_url: GitHub repository URL
        :param limit: Number of recent commits to fetch
        :return: List of recent commits with details
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            repo = self.client.get_repo(f"{owner}/{repo_name}")

            commits = repo.get_commits()[:limit]

            return [
                {
                    "sha": commit.sha[:7],
                    "message": commit.commit.message.split('\n')[0], # First line of commit message
                    "author": commit.commit.author.name,
                    "date": commit.commit.author.date.isoformat() if commit.commit.author.date else None,
                    "url": commit.html_url,
                }
                for commit in commits
            ]

        except Exception as e:
            logger.error(f"Error fetching recent commits: {e}")
            return []

    def get_file_tree(self, repo_url: str, path: str = "") -> List[Dict]:
        """
        Get the file tree of a repository at a given path

        :param repo_url: GitHub repository URL
        :param path: Path within the repository to list files from
        :return: List of files and directories with details
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            repo = self.client.get_repo(f"{owner}/{repo_name}")

            contents = repo.get_contents(path)
            if not isinstance(contents, list):
                contents = [contents]

            return [
                {
                    "name": content.name,
                    "path": content.path,
                    "type": content.type, # 'file' or 'dir'
                    "size": content.size,
                    "url": content.html_url,
                }
                for content in contents
            ]

        except Exception as e:
            logger.error(f"Error fetching file tree: {e}")
            return []

    def search_code(self, query: str, repo_url: str, max_results: int = 10) -> List[Dict]:
        """
        Search code within a repository

        :param query: Search query string
        :param repo_url: GitHub repository URL
        :param max_results: Maximum number of results to return
        :return: List of search results with details
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_url)

            # GitHub code search syntax: "query repo:owner/repo"
            full_query = f"{query} repo:{owner}/{repo_name}"
            results = self.client.search_code(full_query)

            return [
                {
                    "name": result.name,
                    "path": result.path,
                    "url": result.html_url,
                    "repository": result.repository.full_name,
                }
                for result in results[:max_results]
            ]

        except Exception as e:
            logger.error(f"Error searching code: {e}")
            return []

# Global instance
github_service = GitHubService()