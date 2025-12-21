"""
Enhanced Commit Indexing Service
Indexes commits into Neo4j with file tracking, diff data, and real-time updates

NEW FEATURES:
✅ File-level commit tracking (hot spots)
✅ Diff data collection (line changes)
✅ Real-time webhook support
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class EnhancedCommitIndexingService:
    """
    Enhanced service to index commit history into Neo4j
    
    NEW Features:
    - ✅ File modification tracking (for hot spots)
    - ✅ Diff data collection (additions/deletions per file)
    - ✅ Real-time webhook processing
    - Batch commit processing
    - Conventional Commits type detection
    - Author tracking
    
    Uses your existing git_service for analysis
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
        
        logger.info("Enhanced Commit Indexing Service initialized")

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

    # ========================================================================
    # NEW: Enhanced Indexing with File Tracking
    # ========================================================================

    def index_commits_enhanced(
        self,
        repo_url: str,
        max_commits: int = 100,
        include_files: bool = True,  # NEW: File tracking toggle
        include_diffs: bool = True,   # NEW: Diff data toggle
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Enhanced commit indexing with file tracking and diff data
        
        Args:
            repo_url: Repository URL
            max_commits: Maximum number of commits to index
            include_files: Track which files were modified (for hot spots)
            include_diffs: Collect line addition/deletion data
            force: Force re-indexing
            
        Returns:
            Statistics about indexed commits
        """
        try:
            logger.info(f"Starting ENHANCED commit indexing for {repo_url}")
            logger.info(f"Options: files={include_files}, diffs={include_diffs}")
            
            stats = {
                'commits_processed': 0,
                'authors_created': 0,
                'files_tracked': 0,        # NEW
                'modifications_tracked': 0, # NEW
                'total_additions': 0,       # NEW
                'total_deletions': 0,       # NEW
                'errors': 0
            }
            
            # Get repository info
            repo_info = self.git.get_repository_info(repo_url)
            repo_name = repo_info['full_name']
            
            # Get recent commits
            commits = self.git.get_recent_commits(repo_url, limit=max_commits)
            
            logger.info(f"Found {len(commits)} commits to process")
            
            # Connect to Neo4j
            if not self.neo4j.connect():
                raise Exception("Failed to connect to Neo4j")
            
            try:
                for i, commit_data in enumerate(commits, 1):
                    try:
                        sha = commit_data.get('sha', '')
                        
                        # Analyze commit
                        analyzed = self._analyze_commit(commit_data)
                        analyzed['repository'] = repo_name
                        
                        # Create commit node
                        commit_created = self._create_commit_node_enhanced(analyzed)
                        
                        if commit_created:
                            stats['commits_processed'] += 1
                            
                            # Create/update author
                            author_stats = self._create_author_node_enhanced(
                                analyzed['author_name'],
                                analyzed['author_email']
                            )
                            
                            if author_stats.get('created'):
                                stats['authors_created'] += 1
                            
                            # Link commit to author
                            self._link_commit_to_author(
                                sha,
                                analyzed['author_email']
                            )
                            
                            # NEW: File tracking
                            if include_files and sha:
                                file_stats = self._index_commit_files(
                                    repo_url,
                                    repo_name,
                                    sha,
                                    include_diffs=include_diffs
                                )
                                
                                stats['files_tracked'] += file_stats.get('files_processed', 0)
                                stats['modifications_tracked'] += file_stats.get('modifications', 0)
                                stats['total_additions'] += file_stats.get('additions', 0)
                                stats['total_deletions'] += file_stats.get('deletions', 0)
                            
                            if i % 10 == 0:
                                logger.info(f"Progress: {i}/{len(commits)} commits")
                            
                            logger.debug(f"Indexed commit: {sha[:7]}")
                    
                    except Exception as e:
                        logger.error(f"Error processing commit {commit_data.get('sha', 'unknown')}: {e}")
                        stats['errors'] += 1
                        continue
                
            finally:
                self.neo4j.close()
            
            logger.info(f"Enhanced commit indexing completed: {stats}")
            
            return {
                'status': 'success',
                'repository': repo_name,
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"Enhanced commit indexing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'statistics': stats
            }

    def _index_commit_files(
        self,
        repo_url: str,
        repo_name: str,
        commit_sha: str,
        include_diffs: bool = True
    ) -> Dict[str, Any]:
        """
        NEW: Index files modified in a commit
        
        This enables:
        - Hot spots (frequently modified files)
        - File history (commits per file)
        - Code owners (who modifies which files)
        - Diff data (line changes)
        
        Args:
            repo_url: Repository URL
            repo_name: Repository full name
            commit_sha: Commit SHA
            include_diffs: Collect line addition/deletion data
            
        Returns:
            Statistics about indexed files
        """
        stats = {
            'files_processed': 0,
            'modifications': 0,
            'additions': 0,
            'deletions': 0
        }
        
        try:
            # Check if git_service has get_commit_details method
            if not hasattr(self.git, 'get_commit_details'):
                logger.warning("git_service doesn't have get_commit_details method")
                return stats
            
            # Get detailed commit info with file list
            commit_details = self.git.get_commit_details(repo_url, commit_sha)
            
            files = commit_details.get('files', [])
            
            if not files:
                logger.debug(f"No files found in commit {commit_sha[:7]}")
                return stats
            
            with self.neo4j._driver.session() as session:
                for file_data in files:
                    file_path = file_data.get('filename')
                    
                    if not file_path:
                        continue
                    
                    try:
                        # Extract file metadata
                        file_name = file_path.split('/')[-1]
                        file_ext = file_path.split('.')[-1] if '.' in file_path else ''
                        
                        # File change statistics
                        additions = file_data.get('additions', 0) if include_diffs else 0
                        deletions = file_data.get('deletions', 0) if include_diffs else 0
                        changes = file_data.get('changes', 0) if include_diffs else 0
                        status = file_data.get('status', 'modified')
                        
                        # Create or update File node
                        session.run("""
                            MERGE (f:File {path: $path, repository: $repository})
                            SET f.name = $name,
                                f.extension = $extension,
                                f.last_modified = $date
                        """, {
                            'path': file_path,
                            'repository': repo_name,
                            'name': file_name,
                            'extension': file_ext,
                            'date': datetime.now().isoformat()
                        })
                        
                        # Create MODIFIED relationship with change statistics
                        session.run("""
                            MATCH (c:Commit {sha: $sha})
                            MATCH (f:File {path: $path, repository: $repository})
                            MERGE (c)-[m:MODIFIED]->(f)
                            SET m.additions = $additions,
                                m.deletions = $deletions,
                                m.changes = $changes,
                                m.status = $status,
                                m.date = $date
                        """, {
                            'sha': commit_sha,
                            'path': file_path,
                            'repository': repo_name,
                            'additions': additions,
                            'deletions': deletions,
                            'changes': changes,
                            'status': status,
                            'date': datetime.now().isoformat()
                        })
                        
                        stats['files_processed'] += 1
                        stats['modifications'] += 1
                        stats['additions'] += additions
                        stats['deletions'] += deletions
                        
                    except Exception as e:
                        logger.error(f"Error indexing file {file_path}: {e}")
                        continue
            
            logger.debug(f"Indexed {stats['files_processed']} files for commit {commit_sha[:7]}")
            
        except Exception as e:
            logger.error(f"Error indexing commit files: {e}")
        
        return stats

    # ========================================================================
    # NEW: Real-time Webhook Support
    # ========================================================================

    def process_webhook_push(
        self,
        webhook_payload: Dict[str, Any],
        platform: str = 'github'  # 'github' or 'gitlab'
    ) -> Dict[str, Any]:
        """
        NEW: Process push webhook for real-time commit indexing
        
        This enables:
        - Real-time commit tracking
        - Instant hot spot updates
        - Live contributor stats
        
        Args:
            webhook_payload: Raw webhook payload from GitHub/GitLab
            platform: Source platform ('github' or 'gitlab')
            
        Returns:
            Processing statistics
            
        Example GitHub Webhook:
            POST /webhook/github
            {
                "repository": {"full_name": "owner/repo", "clone_url": "..."},
                "commits": [{"id": "abc123", "message": "...", ...}],
                "pusher": {"name": "...", "email": "..."}
            }
        """
        try:
            logger.info(f"Processing {platform} webhook push event")
            
            stats = {
                'commits_processed': 0,
                'files_tracked': 0,
                'errors': 0
            }
            
            # Extract repository info
            if platform == 'github':
                repo_data = webhook_payload.get('repository', {})
                repo_name = repo_data.get('full_name')
                repo_url = repo_data.get('clone_url') or repo_data.get('html_url')
                commits_data = webhook_payload.get('commits', [])
                
            elif platform == 'gitlab':
                project = webhook_payload.get('project', {})
                repo_name = project.get('path_with_namespace')
                repo_url = project.get('git_http_url') or project.get('web_url')
                commits_data = webhook_payload.get('commits', [])
                
            else:
                raise ValueError(f"Unsupported platform: {platform}")
            
            if not repo_name or not commits_data:
                logger.warning("Incomplete webhook payload")
                return {
                    'status': 'skipped',
                    'reason': 'No commits or repository info',
                    'statistics': stats
                }
            
            logger.info(f"Processing {len(commits_data)} commits from webhook")
            
            # Connect to Neo4j
            if not self.neo4j.connect():
                raise Exception("Failed to connect to Neo4j")
            
            try:
                for commit_data in commits_data:
                    try:
                        # Parse commit from webhook
                        analyzed = self._parse_webhook_commit(
                            commit_data,
                            platform,
                            repo_name
                        )
                        
                        # Create commit node
                        commit_created = self._create_commit_node_enhanced(analyzed)
                        
                        if commit_created:
                            stats['commits_processed'] += 1
                            
                            # Create author
                            self._create_author_node_enhanced(
                                analyzed['author_name'],
                                analyzed['author_email']
                            )
                            
                            # Link commit to author
                            self._link_commit_to_author(
                                analyzed['sha'],
                                analyzed['author_email']
                            )
                            
                            # Index files if available in webhook
                            if 'added' in commit_data or 'modified' in commit_data:
                                file_stats = self._index_webhook_files(
                                    analyzed['sha'],
                                    repo_name,
                                    commit_data
                                )
                                stats['files_tracked'] += file_stats.get('files_processed', 0)
                            
                            logger.debug(f"Processed webhook commit: {analyzed['sha'][:7]}")
                    
                    except Exception as e:
                        logger.error(f"Error processing webhook commit: {e}")
                        stats['errors'] += 1
                        continue
            
            finally:
                self.neo4j.close()
            
            logger.info(f"Webhook processing completed: {stats}")
            
            return {
                'status': 'success',
                'repository': repo_name,
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'statistics': stats
            }

    def _parse_webhook_commit(
        self,
        commit_data: Dict,
        platform: str,
        repo_name: str
    ) -> Dict[str, Any]:
        """
        Parse commit from webhook payload
        
        Handles different webhook formats from GitHub/GitLab
        """
        if platform == 'github':
            author = commit_data.get('author', {})
            return {
                'sha': commit_data.get('id', ''),
                'message': commit_data.get('message', ''),
                'author_name': author.get('name', 'Unknown'),
                'author_email': author.get('email', ''),
                'date': commit_data.get('timestamp', datetime.now().isoformat()),
                'repository': repo_name,
                'additions': 0,
                'deletions': 0,
                'files_changed': len(commit_data.get('added', [])) + 
                                len(commit_data.get('modified', [])) + 
                                len(commit_data.get('removed', [])),
                'commit_type': self.detect_commit_type(commit_data.get('message', ''))
            }
        
        elif platform == 'gitlab':
            author = commit_data.get('author', {})
            return {
                'sha': commit_data.get('id', ''),
                'message': commit_data.get('message', ''),
                'author_name': author.get('name', 'Unknown'),
                'author_email': author.get('email', ''),
                'date': commit_data.get('timestamp', datetime.now().isoformat()),
                'repository': repo_name,
                'additions': 0,
                'deletions': 0,
                'files_changed': len(commit_data.get('added', [])) + 
                                len(commit_data.get('modified', [])) + 
                                len(commit_data.get('removed', [])),
                'commit_type': self.detect_commit_type(commit_data.get('message', ''))
            }
        
        return {}

    def _index_webhook_files(
        self,
        commit_sha: str,
        repo_name: str,
        commit_data: Dict
    ) -> Dict[str, Any]:
        """
        Index files from webhook commit data
        
        Webhooks provide file lists but not diff data
        """
        stats = {'files_processed': 0}
        
        try:
            # Get file lists from webhook
            added = commit_data.get('added', [])
            modified = commit_data.get('modified', [])
            removed = commit_data.get('removed', [])
            
            all_files = []
            
            # Create file change records
            for filepath in added:
                all_files.append({'path': filepath, 'status': 'added'})
            for filepath in modified:
                all_files.append({'path': filepath, 'status': 'modified'})
            for filepath in removed:
                all_files.append({'path': filepath, 'status': 'removed'})
            
            with self.neo4j._driver.session() as session:
                for file_data in all_files:
                    file_path = file_data['path']
                    status = file_data['status']
                    
                    # Create File node
                    session.run("""
                        MERGE (f:File {path: $path, repository: $repository})
                        SET f.name = $name,
                            f.extension = $extension,
                            f.last_modified = $date
                    """, {
                        'path': file_path,
                        'repository': repo_name,
                        'name': file_path.split('/')[-1],
                        'extension': file_path.split('.')[-1] if '.' in file_path else '',
                        'date': datetime.now().isoformat()
                    })
                    
                    # Create MODIFIED relationship
                    session.run("""
                        MATCH (c:Commit {sha: $sha})
                        MATCH (f:File {path: $path, repository: $repository})
                        MERGE (c)-[m:MODIFIED]->(f)
                        SET m.status = $status,
                            m.date = $date
                    """, {
                        'sha': commit_sha,
                        'path': file_path,
                        'repository': repo_name,
                        'status': status,
                        'date': datetime.now().isoformat()
                    })
                    
                    stats['files_processed'] += 1
            
        except Exception as e:
            logger.error(f"Error indexing webhook files: {e}")
        
        return stats

    # ========================================================================
    # Helper Methods (Enhanced)
    # ========================================================================

    def _create_commit_node_enhanced(self, commit_data: Dict) -> bool:
        """Create or update commit node with enhanced data"""
        try:
            with self.neo4j._driver.session() as session:
                session.run("""
                    MERGE (c:Commit {sha: $sha})
                    SET c.message = $message,
                        c.date = $date,
                        c.author_name = $author_name,
                        c.author_email = $author_email,
                        c.repository = $repository,
                        c.additions = $additions,
                        c.deletions = $deletions,
                        c.files_changed = $files_changed,
                        c.commit_type = $commit_type
                """, commit_data)
            return True
        except Exception as e:
            logger.error(f"Error creating commit node: {e}")
            return False

    def _create_author_node_enhanced(
        self,
        name: str,
        email: str
    ) -> Dict[str, Any]:
        """Create or update author node"""
        try:
            with self.neo4j._driver.session() as session:
                result = session.run("""
                    MERGE (a:Author {email: $email})
                    ON CREATE SET a.name = $name, a.created_at = datetime()
                    ON MATCH SET a.name = $name
                    RETURN a.created_at as created_at
                """, {'name': name, 'email': email})
                
                record = result.single()
                
                return {
                    'created': record is not None,
                    'email': email
                }
        except Exception as e:
            logger.error(f"Error creating author node: {e}")
            return {'created': False}

    def _link_commit_to_author(self, commit_sha: str, author_email: str) -> bool:
        """Link commit to author"""
        try:
            with self.neo4j._driver.session() as session:
                session.run("""
                    MATCH (c:Commit {sha: $sha})
                    MATCH (a:Author {email: $email})
                    MERGE (c)-[:COMMITTED_BY]->(a)
                """, {'sha': commit_sha, 'email': author_email})
            return True
        except Exception as e:
            logger.error(f"Error linking commit to author: {e}")
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
        
        # Extract author info
        author_data = commit_data.get('author', {})
        if isinstance(author_data, dict):
            author_name = author_data.get('name', 'Unknown')
            author_email = author_data.get('email', '')
        else:
            author_name = str(author_data) if author_data else 'Unknown'
            author_email = ''
        
        return {
            'sha': commit_data.get('sha') or commit_data.get('full_sha', ''),
            'message': message,
            'author_name': author_name,
            'author_email': author_email,
            'date': date_str,
            'additions': commit_data.get('additions', 0),
            'deletions': commit_data.get('deletions', 0),
            'files_changed': commit_data.get('files_changed', 0),
            'commit_type': commit_type
        }

    # ========================================================================
    # Legacy Compatibility (from original service)
    # ========================================================================

    def index_commits(
        self,
        repo_url: str,
        max_commits: int = 100,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility
        
        Calls enhanced version with file tracking disabled
        """
        logger.info("Using legacy index_commits (no file tracking)")
        
        return self.index_commits_enhanced(
            repo_url=repo_url,
            max_commits=max_commits,
            include_files=False,  # Disabled for legacy compatibility
            include_diffs=False,
            force=force
        )

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
                'total_authors': stats.get('authors', 0),
                'total_files': stats.get('files', 0)  # NEW
            }
            
        except Exception as e:
            logger.error(f"Error getting indexing status: {e}")
            return {
                'repository': repo_url,
                'indexed': False,
                'error': str(e)
            }


# ============================================================================
# Factory Functions
# ============================================================================

def create_enhanced_commit_indexing_service(neo4j_service, git_service):
    """Create EnhancedCommitIndexingService instance"""
    return EnhancedCommitIndexingService(neo4j_service, git_service)


# Backward compatibility
def create_commit_indexing_service(neo4j_service, git_service):
    """Legacy factory - creates enhanced service"""
    return EnhancedCommitIndexingService(neo4j_service, git_service)
