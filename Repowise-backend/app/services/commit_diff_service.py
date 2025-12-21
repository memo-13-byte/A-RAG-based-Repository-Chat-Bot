"""
Commit Diff Comparison Feature
Iki commit arasindaki kod degisikliklerini gosterir

YENI OZELLIK:
- get_commit_diff(): Tek commit'in diff'ini al
- compare_commits(): Iki commit arasindaki farklari goster
- get_file_diff(): Belirli bir dosyanin diff'ini al
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CommitDiffService:
    """
    Service to get and compare commit diffs

    Features:
    - Get full diff for a commit
    - Compare two commits
    - Get diff for specific files
    - Show line-by-line changes
    """

    def __init__(self, github_service, neo4j_service):
        self.github = github_service
        self.neo4j = neo4j_service

    def get_commit_diff(
            self,
            repo_url: str,
            commit_sha: str
    ) -> Dict[str, Any]:
        """
        Get full diff for a single commit

        Returns:
        {
            'sha': 'abc123',
            'message': 'fix: bug fix',
            'author': 'John Doe',
            'files': [
                {
                    'filename': 'requests/sessions.py',
                    'additions': 15,
                    'deletions': 8,
                    'patch': '@@ -10,5 +10,7 @@\n-old code\n+new code'
                }
            ]
        }
        """
        try:
            # Use existing get_commit_details
            commit_details = self.github.get_commit_details(repo_url, commit_sha)

            if not commit_details or not commit_details.get('files'):
                logger.warning(f"No diff data for commit {commit_sha}")
                return {'files': []}

            # Format for easy consumption
            result = {
                'sha': commit_details['sha'],
                'message': commit_details['message'],
                'author': commit_details['author'],
                'date': commit_details['date'],
                'stats': commit_details.get('stats', {}),
                'files': []
            }

            for file in commit_details['files']:
                result['files'].append({
                    'filename': file['filename'],
                    'status': file['status'],
                    'additions': file['additions'],
                    'deletions': file['deletions'],
                    'changes': file['changes'],
                    'patch': file.get('patch', '')  # ← DIFF!
                })

            logger.info(f"Retrieved diff for commit {commit_sha[:7]} with {len(result['files'])} files")

            return result

        except Exception as e:
            logger.error(f"Error getting commit diff: {e}")
            return {'files': []}

    def compare_commits(
            self,
            repo_url: str,
            commit_sha_from: str,
            commit_sha_to: str
    ) -> Dict[str, Any]:
        """
        Compare two commits and show what changed

        Args:
            repo_url: Repository URL
            commit_sha_from: Base commit SHA
            commit_sha_to: Target commit SHA

        Returns:
            Dictionary with comparison results

        Example:
            compare_commits(url, "abc123", "def456")

            Returns:
            {
                'from': 'abc123',
                'to': 'def456',
                'total_changes': {
                    'files_changed': 5,
                    'additions': 150,
                    'deletions': 80
                },
                'files': [
                    {
                        'filename': 'requests/sessions.py',
                        'status': 'modified',
                        'additions': 15,
                        'deletions': 8,
                        'patch': '...'
                    }
                ]
            }
        """
        try:
            owner, repo_name = self.github.parse_repo_url(repo_url)
            logger.info(f"Comparing commits {commit_sha_from[:7]}...{commit_sha_to[:7]}")

            # Get repository
            repo = self.github.client.get_repo(f"{owner}/{repo_name}")

            # Get comparison
            comparison = repo.compare(commit_sha_from, commit_sha_to)

            # Extract changes
            total_changes = {
                'files_changed': len(comparison.files),
                'additions': sum(f.additions for f in comparison.files),
                'deletions': sum(f.deletions for f in comparison.files),
                'commits': comparison.total_commits
            }

            files = []
            for file in comparison.files:
                files.append({
                    'filename': file.filename,
                    'status': file.status,
                    'additions': file.additions,
                    'deletions': file.deletions,
                    'changes': file.changes,
                    'patch': getattr(file, 'patch', '')  # ← LINE-BY-LINE DIFF!
                })

            result = {
                'from': commit_sha_from,
                'to': commit_sha_to,
                'total_changes': total_changes,
                'files': files
            }

            logger.info(f"Comparison: {total_changes['files_changed']} files, "
                        f"+{total_changes['additions']} -{total_changes['deletions']}")

            return result

        except Exception as e:
            logger.error(f"Error comparing commits: {e}")
            return {'files': []}

    def get_file_diff(
            self,
            repo_url: str,
            commit_sha: str,
            file_path: str
    ) -> Optional[str]:
        """
        Get diff for a specific file in a commit

        Args:
            repo_url: Repository URL
            commit_sha: Commit SHA
            file_path: Path to file

        Returns:
            Diff patch string or None

        Example:
            get_file_diff(url, "abc123", "requests/sessions.py")

            Returns:
            '''
            @@ -10,5 +10,7 @@
            def session():
            -    old_code = True
            +    new_code = True
            +    added_line = True
                return session
            '''
        """
        try:
            commit_details = self.github.get_commit_details(repo_url, commit_sha)

            if not commit_details or not commit_details.get('files'):
                return None

            # Find the file
            for file in commit_details['files']:
                if file['filename'] == file_path:
                    patch = file.get('patch', '')

                    if patch:
                        logger.info(f"Retrieved diff for {file_path} in {commit_sha[:7]}")
                        return patch
                    else:
                        logger.warning(f"No patch data for {file_path}")
                        return None

            logger.warning(f"File {file_path} not found in commit {commit_sha[:7]}")
            return None

        except Exception as e:
            logger.error(f"Error getting file diff: {e}")
            return None

    def format_diff_for_display(self, patch: str) -> Dict[str, Any]:
        """
        Parse and format diff patch for easy display

        Args:
            patch: Raw diff patch string

        Returns:
            Formatted diff with line-by-line changes

        Example:
            Input:
            "@@ -10,5 +10,7 @@\n def foo():\n-    old\n+    new"

            Output:
            {
                'hunks': [
                    {
                        'header': '@@ -10,5 +10,7 @@',
                        'lines': [
                            {'type': 'context', 'content': ' def foo():'},
                            {'type': 'removed', 'content': '-    old'},
                            {'type': 'added', 'content': '+    new'}
                        ]
                    }
                ]
            }
        """
        if not patch:
            return {'hunks': []}

        hunks = []
        current_hunk = None

        for line in patch.split('\n'):
            # Hunk header
            if line.startswith('@@'):
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = {
                    'header': line,
                    'lines': []
                }
            elif current_hunk is not None:
                # Line changes
                if line.startswith('+'):
                    current_hunk['lines'].append({
                        'type': 'added',
                        'content': line
                    })
                elif line.startswith('-'):
                    current_hunk['lines'].append({
                        'type': 'removed',
                        'content': line
                    })
                else:
                    current_hunk['lines'].append({
                        'type': 'context',
                        'content': line
                    })

        if current_hunk:
            hunks.append(current_hunk)

        return {'hunks': hunks}
