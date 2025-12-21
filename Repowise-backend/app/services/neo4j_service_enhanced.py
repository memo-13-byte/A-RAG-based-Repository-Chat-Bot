"""
Enhanced Neo4j Service - Extension of Existing Neo4jService
Adds commit tracking, author relationships, and advanced analytics
Compatible with existing RepoWise architecture
"""

from neo4j import GraphDatabase
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class Neo4jServiceEnhanced:
    """
    Enhanced Neo4j Service - extends existing functionality with:
    - Commit history tracking
    - Author relationships  
    - File modification history
    - Code ownership analysis
    - Impact analysis
    
    NOTE: This extends your existing Neo4jService class
    Use this alongside or merge methods into your existing service
    """

    def __init__(
        self,
        uri: str = None,
        username: str = None,
        password: str = None
    ):
        """Initialize with environment variables or defaults"""
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password123")
        self._driver = None
        
        logger.info(f"Enhanced Neo4j Service initialized")

    def connect(self) -> bool:
        """Establish connection"""
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            
            with self._driver.session() as session:
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]
            
            if test_value == 1:
                self._create_indexes()
                logger.info("Enhanced Neo4j connected successfully")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def _create_indexes(self):
        """Create performance indexes"""
        try:
            with self._driver.session() as session:
                indexes = [
                    "CREATE INDEX file_path_idx IF NOT EXISTS FOR (f:File) ON (f.path)",
                    "CREATE INDEX commit_sha_idx IF NOT EXISTS FOR (c:Commit) ON (c.sha)",
                    "CREATE INDEX author_email_idx IF NOT EXISTS FOR (a:Author) ON (a.email)",
                ]
                
                for index_query in indexes:
                    try:
                        session.run(index_query)
                    except Exception:
                        pass
                
                logger.info("Indexes created/verified")
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")

    def close(self):
        """Close connection"""
        if self._driver:
            self._driver.close()

    # ============================================================================
    # COMMIT TRACKING METHODS
    # ============================================================================

    def create_commit_node(self, commit_data: Dict[str, Any]) -> bool:
        """
        Create commit node
        
        Args:
            commit_data: {
                'sha': str (required),
                'message': str,
                'author_name': str,
                'author_email': str,
                'date': str (ISO format) or datetime,
                'additions': int,
                'deletions': int,
                'files_changed': int,
                'commit_type': str (feat/fix/docs/etc)
            }
        """
        try:
            with self._driver.session() as session:
                query = """
                MERGE (c:Commit {sha: $sha})
                SET c.message = $message,
                    c.author_name = $author_name,
                    c.author_email = $author_email,
                    c.date = datetime($date),
                    c.additions = $additions,
                    c.deletions = $deletions,
                    c.files_changed = $files_changed,
                    c.commit_type = $commit_type,
                    c.updated_at = datetime()
                RETURN c
                """
                
                # Convert datetime to ISO string if needed
                date_str = commit_data.get('date', datetime.now().isoformat())
                if isinstance(date_str, datetime):
                    date_str = date_str.isoformat()
                
                session.run(
                    query,
                    sha=commit_data['sha'],
                    message=commit_data.get('message', ''),
                    author_name=commit_data.get('author_name', 'Unknown'),
                    author_email=commit_data.get('author_email', ''),
                    date=date_str,
                    additions=commit_data.get('additions', 0),
                    deletions=commit_data.get('deletions', 0),
                    files_changed=commit_data.get('files_changed', 0),
                    commit_type=commit_data.get('commit_type', 'other')
                )
                
                logger.debug(f"Created commit node: {commit_data['sha'][:7]}")
                return True
                
        except Exception as e:
            logger.error(f"Error creating commit node: {e}")
            return False

    def create_author_node(
        self,
        name: str,
        email: str
    ) -> bool:
        """Create or update author node"""
        try:
            with self._driver.session() as session:
                query = """
                MERGE (a:Author {email: $email})
                SET a.name = $name,
                    a.updated_at = datetime()
                RETURN a
                """
                
                session.run(query, name=name, email=email)
                return True
                
        except Exception as e:
            logger.error(f"Error creating author node: {e}")
            return False

    def link_commit_to_author(self, commit_sha: str, author_email: str) -> bool:
        """Create COMMITTED_BY relationship"""
        try:
            with self._driver.session() as session:
                query = """
                MATCH (c:Commit {sha: $commit_sha})
                MATCH (a:Author {email: $author_email})
                MERGE (c)-[:COMMITTED_BY]->(a)
                """
                
                session.run(query, commit_sha=commit_sha, author_email=author_email)
                return True
                
        except Exception as e:
            logger.error(f"Error linking commit to author: {e}")
            return False

    def create_file_modification(
        self,
        file_path: str,
        commit_sha: str,
        change_type: str,  # 'added', 'modified', 'deleted'
        additions: int = 0,
        deletions: int = 0
    ) -> bool:
        """Create file modification relationship"""
        try:
            with self._driver.session() as session:
                # Update file metadata
                file_update = """
                MATCH (f:File {path: $file_path})
                SET f.last_modified = datetime(),
                    f.modification_count = coalesce(f.modification_count, 0) + 1
                """
                session.run(file_update, file_path=file_path)
                
                # Create modification relationship
                query = """
                MATCH (f:File {path: $file_path})
                MATCH (c:Commit {sha: $commit_sha})
                MERGE (f)-[m:MODIFIED_IN]->(c)
                SET m.change_type = $change_type,
                    m.additions = $additions,
                    m.deletions = $deletions
                """
                
                session.run(
                    query,
                    file_path=file_path,
                    commit_sha=commit_sha,
                    change_type=change_type,
                    additions=additions,
                    deletions=deletions
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating file modification: {e}")
            return False

    def create_commit_parent_relationship(
        self,
        child_sha: str,
        parent_sha: str
    ) -> bool:
        """Create parent-child relationship between commits"""
        try:
            with self._driver.session() as session:
                query = """
                MATCH (child:Commit {sha: $child_sha})
                MATCH (parent:Commit {sha: $parent_sha})
                MERGE (child)-[:PARENT_OF]->(parent)
                """
                
                session.run(query, child_sha=child_sha, parent_sha=parent_sha)
                return True
                
        except Exception as e:
            logger.error(f"Error creating parent relationship: {e}")
            return False

    # ============================================================================
    # ANALYTICS & QUERY METHODS
    # ============================================================================

    def get_file_commit_history(
        self,
        file_path: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get commit history for a file"""
        try:
            with self._driver.session() as session:
                query = """
                MATCH (f:File {path: $file_path})-[m:MODIFIED_IN]->(c:Commit)
                OPTIONAL MATCH (c)-[:COMMITTED_BY]->(a:Author)
                RETURN c.sha as sha,
                       c.message as message,
                       c.date as date,
                       coalesce(a.name, c.author_name) as author,
                       m.change_type as change_type,
                       m.additions as additions,
                       m.deletions as deletions
                ORDER BY c.date DESC
                LIMIT $limit
                """
                
                result = session.run(query, file_path=file_path, limit=limit)
                
                history = []
                for record in result:
                    history.append({
                        'sha': record['sha'],
                        'message': record['message'],
                        'date': str(record['date']),
                        'author': record['author'],
                        'change_type': record['change_type'],
                        'additions': record.get('additions', 0),
                        'deletions': record.get('deletions', 0)
                    })
                
                return history
                
        except Exception as e:
            logger.error(f"Error getting file history: {e}")
            return []

    def get_most_modified_files(
        self,
        repo_name: str,
        limit: int = 20
    ) -> List[Dict]:
        """Get most frequently modified files (hot spots)"""
        try:
            with self._driver.session() as session:
                query = """
                MATCH (r:Repository {full_name: $repo_name})-[:CONTAINS]->(f:File)
                OPTIONAL MATCH (f)-[m:MODIFIED_IN]->(c:Commit)
                WITH f, count(m) as modification_count
                WHERE modification_count > 0
                ORDER BY modification_count DESC
                LIMIT $limit
                RETURN f.path as path,
                       f.language as language,
                       modification_count,
                       f.size as size
                """
                
                result = session.run(query, repo_name=repo_name, limit=limit)
                
                files = []
                for record in result:
                    files.append({
                        'path': record['path'],
                        'language': record['language'],
                        'modifications': record['modification_count'],
                        'size': record.get('size', 0)
                    })
                
                return files
                
        except Exception as e:
            logger.error(f"Error getting hot spots: {e}")
            return []

    def get_active_authors(
        self,
        repo_name: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get most active contributors"""
        try:
            with self._driver.session() as session:
                query = """
                MATCH (c:Commit)-[:COMMITTED_BY]->(a:Author)
                WITH a, count(c) as commit_count,
                     sum(c.additions) as total_additions,
                     sum(c.deletions) as total_deletions
                ORDER BY commit_count DESC
                LIMIT $limit
                RETURN a.name as author,
                       a.email as email,
                       commit_count,
                       total_additions,
                       total_deletions
                """
                
                result = session.run(query, limit=limit)
                
                authors = []
                for record in result:
                    authors.append({
                        'author': record['author'],
                        'email': record['email'],
                        'commits': record['commit_count'],
                        'additions': record['total_additions'],
                        'deletions': record['total_deletions']
                    })
                
                return authors
                
        except Exception as e:
            logger.error(f"Error getting contributors: {e}")
            return []

    def find_code_owners(self, file_path: str) -> Dict[str, Any]:
        """Find who owns/maintains a file"""
        try:
            with self._driver.session() as session:
                query = """
                MATCH (f:File {path: $file_path})-[:MODIFIED_IN]->(c:Commit)
                      -[:COMMITTED_BY]->(a:Author)
                WITH a, count(c) as commit_count,
                     sum(c.additions) as additions,
                     sum(c.deletions) as deletions
                ORDER BY commit_count DESC
                LIMIT 5
                RETURN a.name as author,
                       a.email as email,
                       commit_count,
                       additions,
                       deletions
                """
                
                result = session.run(query, file_path=file_path)
                
                owners = []
                for record in result:
                    owners.append({
                        'author': record['author'],
                        'email': record['email'],
                        'commits': record['commit_count'],
                        'additions': record['additions'],
                        'deletions': record['deletions']
                    })
                
                return {
                    'file': file_path,
                    'primary_owner': owners[0] if owners else None,
                    'contributors': owners
                }
                
        except Exception as e:
            logger.error(f"Error finding code owners: {e}")
            return {}

    def analyze_impact_of_change(
        self,
        file_path: str,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """Analyze potential impact of changing a file"""
        try:
            with self._driver.session() as session:
                query = f"""
                MATCH (f:File {{path: $file_path}})
                MATCH path = (f)<-[:DEPENDS_ON*1..{max_depth}]-(dependent:File)
                WITH dependent, length(path) as depth
                ORDER BY depth
                RETURN DISTINCT dependent.path as path,
                       dependent.language as language,
                       depth
                LIMIT 50
                """
                
                result = session.run(query, file_path=file_path)
                
                impacted = []
                for record in result:
                    impacted.append({
                        'path': record['path'],
                        'language': record['language'],
                        'dependency_depth': record['depth']
                    })
                
                return {
                    'file': file_path,
                    'impacted_files': impacted,
                    'impact_score': len(impacted)
                }
                
        except Exception as e:
            logger.error(f"Error analyzing impact: {e}")
            return {}

    """
    Fixed get_repository_statistics() method
    Reads additions/deletions from MODIFIED relationships instead of Commit nodes

    Add/replace this in neo4j_service_enhanced.py
    """

    def get_repository_statistics(self, repo_name: str) -> Dict[str, Any]:
        """
        Get comprehensive repository statistics from Neo4j

        FIXED: Now reads additions/deletions from MODIFIED relationships

        Args:
            repo_name: Repository full name (owner/repo)

        Returns:
            Dictionary with repository statistics including:
            - Total commits, authors, files
            - Total additions/deletions (from MODIFIED relationships)
            - Language distribution
        """
        try:
            if not self.connect():
                return {}

            with self._driver.session() as session:
                # Basic counts
                result = session.run("""
                    MATCH (c:Commit {repository: $repo})
                    WITH count(c) as commits
                    MATCH (a:Author)<-[:COMMITTED_BY]-(c2:Commit {repository: $repo})
                    WITH commits, count(DISTINCT a) as authors
                    MATCH (f:File {repository: $repo})
                    RETURN commits, authors, count(f) as files
                """, {'repo': repo_name})

                record = result.single()
                if not record:
                    return {}

                stats = {
                    'total_commits': record['commits'],
                    'authors': record['authors'],
                    'files': record['files']
                }

                # ✅ FIX: Read additions/deletions from MODIFIED relationships
                result = session.run("""
                    MATCH (c:Commit {repository: $repo})-[m:MODIFIED]->(:File)
                    RETURN 
                        sum(m.additions) as total_additions,
                        sum(m.deletions) as total_deletions,
                        count(m) as total_modifications
                """, {'repo': repo_name})

                record = result.single()
                if record:
                    stats['total_additions'] = record['total_additions'] or 0
                    stats['total_deletions'] = record['total_deletions'] or 0
                    stats['total_modifications'] = record['total_modifications'] or 0
                else:
                    stats['total_additions'] = 0
                    stats['total_deletions'] = 0
                    stats['total_modifications'] = 0

                # Code structure stats
                result = session.run("""
                    MATCH (n {repository: $repo})
                    WHERE n:Class OR n:Function
                    WITH n.type as type, count(*) as count
                    RETURN type, count
                """, {'repo': repo_name})

                for record in result:
                    node_type = record['type']
                    if node_type == 'class':
                        stats['classes'] = record['count']
                    elif node_type == 'function':
                        stats['functions'] = record['count']

                # Set defaults
                stats.setdefault('classes', 0)
                stats.setdefault('functions', 0)

                # Language distribution
                result = session.run("""
                    MATCH (f:File {repository: $repo})
                    WHERE f.extension IS NOT NULL
                    WITH f.extension as lang, count(*) as count
                    RETURN lang, count
                    ORDER BY count DESC
                """, {'repo': repo_name})

                languages = {}
                for record in result:
                    lang = record['lang']
                    if lang and lang != '':
                        # Map extensions to language names
                        lang_map = {
                            'py': 'python',
                            'js': 'javascript',
                            'ts': 'typescript',
                            'java': 'java',
                            'cpp': 'cpp',
                            'c': 'c',
                            'go': 'go',
                            'rs': 'rust',
                            'rb': 'ruby',
                            'php': 'php',
                        }
                        lang_name = lang_map.get(lang, lang)
                        languages[lang_name] = record['count']

                stats['languages'] = languages

                return stats

        except Exception as e:
            logger.error(f"Error getting repository statistics: {e}")
            return {}
        finally:
            self.close()


# Factory function to create enhanced service
def create_enhanced_neo4j_service() -> Neo4jServiceEnhanced:
    """Create enhanced Neo4j service instance"""
    service = Neo4jServiceEnhanced()
    service.connect()
    return service


# Export for compatibility
neo4j_service_enhanced = create_enhanced_neo4j_service()
