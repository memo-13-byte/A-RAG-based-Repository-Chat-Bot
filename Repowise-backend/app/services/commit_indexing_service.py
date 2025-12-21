"""
Commit Indexing Service
Indexes commits into Neo4j graph database
Works with your existing CommitAnalyzer service
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class CommitIndexingService:
    """
    Service to index commit history into Neo4j
    
    Features:
    - Batch commit processing
    - Conventional Commits type detection
    - Author tracking
    - File modification tracking
    
    Uses your existing CommitAnalyzer for analysis
    """

    def __init__(
        self,
        neo4j_service,
        git_service
    ):
        """
        Initialize with services
        
        Args:
            neo4j_service: Enhanced Neo4j service
            git_service: GitHub/GitLab service from git_factory
        """
        self.neo4j = neo4j_service
        self.git = git_service
        
        logger.info("Commit Indexing Service initialized")

    def detect_commit_type(self, message: str) -> str:
        """
        Detect commit type from message (Conventional Commits)
        
        Types: feat, fix, docs, style, refactor, test, chore, etc.
        """
        if not message:
            return 'other'
        
        patterns = {
            'feat': r'^feat(\(.+\))?:',
            'fix': r'^fix(\(.+\))?:',
            'docs': r'^docs(\(.+\))?:',
            'style': r'^style(\(.+\))?:',
            'refactor': r'^refactor(\(.+\))?:',
            'test': r'^test(\(.+\))?:',
            'chore': r'^chore(\(.+\))?:',
            'perf': r'^perf(\(.+\))?:',
            'build': r'^build(\(.+\))?:',
            'ci': r'^ci(\(.+\))?:',
        }
        
        message_lower = message.lower()
        
        for commit_type, pattern in patterns.items():
            if re.match(pattern, message_lower):
                return commit_type
        
        # Fallback detection
        if any(word in message_lower for word in ['add', 'create', 'implement']):
            return 'feat'
        elif any(word in message_lower for word in ['fix', 'bug', 'issue']):
            return 'fix'
        elif any(word in message_lower for word in ['doc', 'readme']):
            return 'docs'
        
        return 'other'

    def index_commits(
        self,
        repo_url: str,
        max_commits: int = 100,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Index commits from repository into Neo4j
        
        Args:
            repo_url: Repository URL
            max_commits: Maximum number of commits to index
            force: Force re-indexing
            
        Returns:
            Statistics about indexed commits
        """
        try:
            logger.info(f"Starting commit indexing for {repo_url}")
            
            stats = {
                'commits_processed': 0,
                'authors_created': 0,
                'files_modified': 0,
                'errors': 0
            }
            
            # Get recent commits
            commits = self.git.get_recent_commits(repo_url, limit=max_commits)
            
            logger.info(f"Found {len(commits)} commits to process")
            
            for commit_data in commits:
                try:
                    # Analyze commit
                    analyzed = self._analyze_commit(commit_data)
                    
                    # Create commit node
                    commit_created = self.neo4j.create_commit_node(analyzed)
                    
                    if commit_created:
                        stats['commits_processed'] += 1
                        
                        # Create author
                        author_created = self.neo4j.create_author_node(
                            name=analyzed['author_name'],
                            email=analyzed['author_email']
                        )
                        
                        if author_created:
                            stats['authors_created'] += 1
                        
                        # Link commit to author
                        self.neo4j.link_commit_to_author(
                            commit_sha=analyzed['sha'],
                            author_email=analyzed['author_email']
                        )
                        
                        logger.debug(f"Indexed commit: {analyzed['sha'][:7]}")
                
                except Exception as e:
                    logger.error(f"Error processing commit: {e}")
                    stats['errors'] += 1
            
            logger.info(f"Commit indexing completed: {stats}")
            
            return {
                'status': 'success',
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"Commit indexing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'statistics': stats
            }

    def index_commit_with_files(
        self,
        repo_url: str,
        commit_sha: str
    ) -> bool:
        """
        Index a specific commit with its file modifications
        
        Note: This requires detailed commit info from GitHub/GitLab API
        Your existing git_service may need a method to get commit details
        """
        try:
            # This would call git_service.get_commit_details(repo_url, commit_sha)
            # For now, placeholder implementation
            
            logger.info(f"Indexing commit {commit_sha} with files")
            
            # Create file modifications
            # files = commit_details.get('files', [])
            # for file in files:
            #     self.neo4j.create_file_modification(...)
            
            return True
            
        except Exception as e:
            logger.error(f"Error indexing commit with files: {e}")
            return False

    def _analyze_commit(self, commit_data: Dict) -> Dict[str, Any]:
        """
        Analyze commit data and prepare for Neo4j
        
        Args:
            commit_data: Raw commit data from git service
            
        Returns:
            Analyzed commit data ready for Neo4j
        """
        # Detect commit type
        message = commit_data.get('message', '')
        commit_type = self.detect_commit_type(message)
        
        # Parse date
        date_str = commit_data.get('date', '')
        if isinstance(date_str, datetime):
            date_str = date_str.isoformat()
        elif not date_str:
            date_str = datetime.now().isoformat()
        
        return {
            'sha': commit_data.get('sha') or commit_data.get('full_sha', ''),
            'message': message,
            'author_name': commit_data.get('author', 'Unknown'),
            'author_email': commit_data.get('author_email', ''),
            'date': date_str,
            'additions': 0,  # Would come from detailed commit data
            'deletions': 0,  # Would come from detailed commit data
            'files_changed': 0,  # Would come from detailed commit data
            'commit_type': commit_type
        }

    def get_indexing_status(self, repo_url: str) -> Dict[str, Any]:
        """
        Get commit indexing status for repository
        
        Returns statistics about indexed commits
        """
        try:
            repo_info = self.git.get_repository_info(repo_url)
            repo_name = repo_info['full_name']
            
            # Get stats from Neo4j
            stats = self.neo4j.get_repository_statistics(repo_name)
            
            return {
                'repository': repo_name,
                'indexed': stats.get('total_commits', 0) > 0,
                'total_commits': stats.get('total_commits', 0),
                'total_authors': stats.get('authors', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting indexing status: {e}")
            return {
                'repository': repo_url,
                'indexed': False,
                'error': str(e)
            }


# Factory function
def create_commit_indexing_service(neo4j_service, git_service):
    """Create CommitIndexingService instance"""
    return CommitIndexingService(neo4j_service, git_service)
