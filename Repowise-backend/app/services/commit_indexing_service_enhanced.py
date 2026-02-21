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
        self._commit_cache = {}
        
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

    def detect_file_renames(self, repo_url: str, commit_sha: str) -> List[Dict]:
        """
        Detect file renames using heuristic matching

        Git'in %50 similarity threshold'u yüzünden GitHub API'de
        'renamed' status'u gelmeyebilir. Bu durumda:
        - 'removed' (silinen) dosyalar
        - 'added' (eklenen) dosyalar
        arasında eşleştirme yaparak rename'leri buluruz.

        Heuristic Matching Kriterleri:
        1. Exact filename match (farklı path)
        2. Similar filename (typo fix, extension change)
        3. Same directory + similar name
        """
        try:
            # Use cached commit details
            cache_key = f"{repo_url}:{commit_sha}"

            if cache_key in self._commit_cache:
                commit_details = self._commit_cache[cache_key]
            else:
                if not hasattr(self.git, 'get_commit_details'):
                    logger.warning("git_service doesn't have get_commit_details method")
                    return []

                commit_details = self.git.get_commit_details(repo_url, commit_sha)

                if commit_details:
                    self._commit_cache[cache_key] = commit_details

            if not commit_details:
                return []

            files = commit_details.get('files', [])

            # File status'larını logla
            file_statuses = {}
            for f in files:
                status = f.get('status', 'unknown')
                file_statuses[status] = file_statuses.get(status, 0) + 1

            if file_statuses:
                logger.info(f"📊 Commit {commit_sha[:7]} file statuses: {file_statuses}")

            if not files:
                return []

            # Separate files by status
            removed_files = []
            added_files = []
            renamed_files = []

            for file_data in files:
                status = file_data.get('status', '')

                # GitHub API'den gelen rename'leri direkt kabul et
                if status == 'renamed':
                    renamed_files.append({
                        'old_path': file_data.get('previous_filename', ''),
                        'new_path': file_data.get('filename', ''),
                        'similarity': 100,
                        'method': 'api'  # API'den geldi
                    })

                elif status == 'removed':
                    removed_files.append({
                        'path': file_data.get('filename', ''),
                        'data': file_data
                    })

                elif status == 'added':
                    added_files.append({
                        'path': file_data.get('filename', ''),
                        'data': file_data
                    })

            # Heuristic matching: removed + added → rename
            if removed_files and added_files:
                heuristic_renames = self._match_renames_heuristic(
                    removed_files,
                    added_files,
                    commit_sha
                )
                renamed_files.extend(heuristic_renames)

            # Log results
            if renamed_files:
                api_count = sum(1 for r in renamed_files if r.get('method') == 'api')
                heuristic_count = sum(1 for r in renamed_files if r.get('method') == 'heuristic')

                logger.info(
                    f"✅ Found {len(renamed_files)} file renames in commit {commit_sha[:7]} "
                    f"(API: {api_count}, Heuristic: {heuristic_count})"
                )

            return renamed_files

        except Exception as e:
            logger.error(f"Error detecting renames in commit {commit_sha[:7]}: {e}")
            return []

    def _match_renames_heuristic(
            self,
            removed_files: List[Dict],
            added_files: List[Dict],
            commit_sha: str
    ) -> List[Dict]:
        """
        Match removed and added files to detect renames

        Matching Strategies (in order):
        1. Exact filename, different directory
        2. Same directory, similar filename
        3. Extension change only
        4. Typo fix (Levenshtein distance)
        """
        import os

        renames = []
        matched_added = set()  # Track which added files we've matched

        for removed in removed_files:
            old_path = removed['path']
            old_dir = os.path.dirname(old_path)
            old_name = os.path.basename(old_path)
            old_base, old_ext = os.path.splitext(old_name)

            best_match = None
            best_score = 0

            for i, added in enumerate(added_files):
                if i in matched_added:
                    continue  # Already matched

                new_path = added['path']
                new_dir = os.path.dirname(new_path)
                new_name = os.path.basename(new_path)
                new_base, new_ext = os.path.splitext(new_name)

                score = 0

                # Strategy 1: Exact filename, different directory
                # Example: src/utils.py → lib/utils.py
                if old_name == new_name and old_dir != new_dir:
                    score = 90

                # Strategy 2: Same directory, similar filename
                # Example: src/old_name.py → src/new_name.py
                elif old_dir == new_dir and old_ext == new_ext:
                    similarity = self._string_similarity(old_base, new_base)
                    if similarity > 0.6:  # 60% benzerlik
                        score = 70 + (similarity * 20)  # 70-90 arası

                # Strategy 3: Extension change only
                # Example: utils.js → utils.ts
                elif old_base == new_base and old_ext != new_ext:
                    score = 85

                # Strategy 4: Path similarity (full path)
                # Example: src/components/Button.jsx → src/components/ButtonNew.jsx
                else:
                    path_similarity = self._string_similarity(old_path, new_path)
                    if path_similarity > 0.7:  # 70% benzerlik
                        score = 60 + (path_similarity * 30)  # 60-90 arası

                # Update best match
                if score > best_score and score >= 60:  # Min 60 puan
                    best_score = score
                    best_match = (i, new_path)

            # If we found a good match, record it
            if best_match:
                matched_index, new_path = best_match
                matched_added.add(matched_index)

                renames.append({
                    'old_path': old_path,
                    'new_path': new_path,
                    'similarity': int(best_score),
                    'method': 'heuristic'  # Heuristic ile bulundu
                })

                logger.debug(
                    f"🔍 Heuristic rename detected in {commit_sha[:7]}: "
                    f"{old_path} → {new_path} (score: {best_score})"
                )

        return renames

    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate string similarity using simple algorithm

        Returns: 0.0 to 1.0 (0 = completely different, 1 = identical)
        """
        if s1 == s2:
            return 1.0

        if not s1 or not s2:
            return 0.0

        # Levenshtein-like simple algorithm
        # (basit versiyonu - production'da difflib kullanılabilir)

        # Convert to lowercase for comparison
        s1_lower = s1.lower()
        s2_lower = s2.lower()

        if s1_lower == s2_lower:
            return 0.95  # Case farklı ama aynı

        # Longest common substring ratio
        longer = max(len(s1), len(s2))

        # Count common characters
        common = 0
        for c in set(s1):
            common += min(s1.count(c), s2.count(c))

        return common / longer

    def index_rename_to_neo4j(
            self,
            repo_name: str,
            commit_sha: str,
            old_path: str,
            new_path: str,
            commit_date: str
    ):
        """
        Create file rename relationship in Neo4j

        Creates:
            (OldFile)-[:RENAMED_TO {commit_sha, date}]->(NewFile)
            (Commit)-[:RENAMED_FILE]->(NewFile)

        Args:
            repo_name: Full repository name (owner/repo)
            commit_sha: Commit that performed the rename
            old_path: Original file path
            new_path: New file path
            commit_date: ISO timestamp of commit
        """
        query = """
        // Get the commit
        MATCH (c:Commit {sha: $commit_sha})
        WHERE c.repo = $repo_name OR c.repository = $repo_name

        // Create or get file nodes
        MERGE (old:File {path: $old_path, repo: $repo_name})
        MERGE (new:File {path: $new_path, repo: $repo_name})

        // Create rename relationship
        MERGE (old)-[:RENAMED_TO {
            commit_sha: $commit_sha,
            date: datetime($commit_date),
            repo: $repo_name
        }]->(new)

        // Link commit to renamed file
        MERGE (c)-[:RENAMED_FILE]->(new)

        RETURN old.path as old_path, new.path as new_path
        """

        try:
            with self.neo4j._driver.session() as session:
                result = session.run(
                    query,
                    repo_name=repo_name,
                    commit_sha=commit_sha,
                    old_path=old_path,
                    new_path=new_path,
                    commit_date=commit_date
                )

                record = result.single()
                if record:
                    logger.info(f"✅ Indexed rename: {old_path} → {new_path}")
                    return True

        except Exception as e:
            logger.error(f"Error indexing rename to Neo4j: {e}")

        return False

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
                'renames_detected': 0,
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

                            # NEW: Detect and index file renames
                            if include_files:  # Only if file tracking is enabled
                                try:
                                    renames = self.detect_file_renames(repo_url, sha)

                                    for rename in renames:
                                        success = self.index_rename_to_neo4j(
                                            repo_name=repo_name,
                                            commit_sha=sha,
                                            old_path=rename['old_path'],
                                            new_path=rename['new_path'],
                                            commit_date=analyzed.get('date', '')
                                        )

                                        if success:
                                            stats['renames_detected'] += 1

                                except Exception as e:
                                    logger.error(f"Error processing renames for {sha[:7]}: {e}")

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

            # Cache'e kaydet
            cache_key = f"{repo_url}:{commit_sha}"
            if cache_key not in self._commit_cache:
                commit_details = self.git.get_commit_details(repo_url, commit_sha)
                self._commit_cache[cache_key] = commit_details
            else:
                commit_details = self._commit_cache[cache_key]
            
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
