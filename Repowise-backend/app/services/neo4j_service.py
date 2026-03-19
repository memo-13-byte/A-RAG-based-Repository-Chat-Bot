"""
Neo4j Graph Database Service - Phase 3
Manages code knowledge graph for repository structure and relationships
"""

from neo4j import GraphDatabase
from typing import Dict, List, Any
import logging
import os

logger = logging.getLogger(__name__)


class Neo4jService:
    """
    Service for managing code knowledge graph in Neo4j

    Features:
    - Repository structure modeling
    - Code entity relationships
    - Dependency tracking
    - Query optimization
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password123"
    ):
        """
        Initialize Neo4j connection

        Args:
            uri: Neo4j connection URI
            username: Database username
            password: Database password
        """
        self.uri = uri
        self.username = username
        self.password = password
        self._driver = None

        logger.info(f"Initializing Neo4j service with URI: {uri}")

    def connect(self) -> bool:
        """
        Establish connection to Neo4j database

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )

            # Test connection
            with self._driver.session() as session:
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]

            if test_value == 1:
                logger.info("Successfully connected to Neo4j")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False

    def close(self):
        """Close Neo4j connection"""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed")

    def clear_repository_graph(self, repo_name: str) -> bool:
        """
        Clear all nodes and relationships for a specific repository

        Args:
            repo_name: Repository full name (e.g., 'owner/repo')

        Returns:
            True if successful
        """
        try:
            with self._driver.session() as session:
                # Delete all nodes related to this repository
                query = """
                MATCH (r:Repository {full_name: $repo_name})
                OPTIONAL MATCH (r)-[*]-(n)
                DETACH DELETE r, n
                """

                session.run(query, repo_name=repo_name)
                logger.info(f"Cleared graph for repository: {repo_name}")
                return True

        except Exception as e:
            logger.error(f"Error clearing repository graph: {e}")
            return False

    def create_repository_node(self, repo_info: Dict[str, Any]) -> bool:
        """
        Create repository node in the graph

        Args:
            repo_info: Repository metadata

        Returns:
            True if successful
        """
        try:
            with self._driver.session() as session:
                query = """
                CREATE (r:Repository {
                    name: $name,
                    full_name: $full_name,
                    url: $url,
                    language: $language,
                    description: $description,
                    stars: $stars,
                    created_at: $created_at
                })
                RETURN r
                """

                session.run(
                    query,
                    name=repo_info.get('name'),
                    full_name=repo_info.get('full_name'),
                    url=repo_info.get('url'),
                    language=repo_info.get('language'),
                    description=repo_info.get('description', ''),
                    stars=repo_info.get('stars', 0),
                    created_at=repo_info.get('created_at', '')
                )

                logger.info(f"Created repository node: {repo_info.get('full_name')}")
                return True

        except Exception as e:
            logger.error(f"Error creating repository node: {e}")
            return False

    def create_file_node(
        self,
        repo_name: str,
        file_path: str,
        file_name: str,
        extension: str,
        language: str,
        size: int = 0
    ) -> bool:
        """
        Create file node and link to repository

        Args:
            repo_name: Repository full name
            file_path: Relative path in repository
            file_name: File name
            extension: File extension
            language: Programming language
            size: File size in bytes

        Returns:
            True if successful
        """
        try:
            with self._driver.session() as session:
                query = """
                MATCH (r:Repository {full_name: $repo_name})
                CREATE (f:File {
                    path: $path,
                    name: $name,
                    extension: $extension,
                    language: $language,
                    size: $size
                })
                CREATE (r)-[:CONTAINS]->(f)
                RETURN f
                """

                session.run(
                    query,
                    repo_name=repo_name,
                    path=file_path,
                    name=file_name,
                    extension=extension,
                    language=language,
                    size=size
                )

                return True

        except Exception as e:
            logger.error(f"Error creating file node: {e}")
            return False

    def create_class_node(
        self,
        repo_name: str,
        file_path: str,
        class_name: str,
        start_line: int,
        end_line: int,
        docstring: str = "",
        base_classes: List[str] = None
    ) -> bool:
        """
        Create class node and relationships

        Args:
            repo_name: Repository full name
            file_path: File containing the class
            class_name: Class name
            start_line: Starting line number
            end_line: Ending line number
            docstring: Class docstring
            base_classes: List of parent class names

        Returns:
            True if successful
        """
        try:
            with self._driver.session() as session:
                # Create class node
                query = """
                                MATCH (f:File {path: $file_path})
                                CREATE (c:Class {
                                    name: $class_name,
                                    repository: $repo_name,
                                    file_path: $file_path,
                                    start_line: $start_line,
                                    end_line: $end_line,
                                    docstring: $docstring
                                })
                                CREATE (f)-[:DEFINES]->(c)
                                RETURN c
                                """

                session.run(
                    query,
                    repo_name=repo_name,
                    file_path=file_path,
                    class_name=class_name,
                    start_line=start_line,
                    end_line=end_line,
                    docstring=docstring or ""
                )

                # Create inheritance relationships if base classes exist
                if base_classes:
                    for base_class in base_classes:
                        inherit_query = """
                                        MATCH (c:Class {name: $class_name, file_path: $file_path, repository: $repo_name})
                                        MATCH (b:Class {name: $base_class, repository: $repo_name})
                                        MERGE (c)-[:INHERITS_FROM]->(b)
                                        """

                        session.run(
                            inherit_query,
                            class_name=class_name,
                            file_path=file_path,
                            base_class=base_class,
                            repo_name=repo_name
                        )

                return True

        except Exception as e:
            logger.error(f"Error creating class node: {e}")
            return False

    def create_function_node(
        self,
        repo_name: str,
        file_path: str,
        function_name: str,
        start_line: int,
        end_line: int,
        parameters: List[str] = None,
        return_type: str = "",
        docstring: str = "",
        parent_class: str = None
    ) -> bool:
        """
        Create function/method node and relationships

        Args:
            repo_name: Repository full name
            file_path: File containing the function
            function_name: Function name
            start_line: Starting line number
            end_line: Ending line number
            parameters: List of parameter names
            return_type: Return type annotation
            docstring: Function docstring
            parent_class: Class name if this is a method

        Returns:
            True if successful
        """
        try:
            with self._driver.session() as session:
                # Normalize parameters
                params_list = parameters if parameters else []

                # Create function node - separate query without list in CREATE
                query = """
                                MATCH (f:File {path: $file_path})
                                CREATE (fn:Function {
                                    name: $function_name,
                                    repository: $repo_name,
                                    file_path: $file_path,
                                    start_line: $start_line,
                                    end_line: $end_line,
                                    return_type: $return_type,
                                    docstring: $docstring,
                                    param_count: $param_count
                                })
                                CREATE (f)-[:DEFINES]->(fn)
                                RETURN fn
                                """

                result = session.run(
                    query,
                    repo_name=repo_name,
                    file_path=file_path,
                    function_name=function_name,
                    start_line=start_line,
                    end_line=end_line,
                    return_type=return_type or "",
                    docstring=docstring or "",
                    param_count=len(params_list)
                )

                # Consume result
                result.consume()

                # Now add parameters as JSON string if they exist
                if params_list:
                    import json
                    params_json = json.dumps(params_list)

                    update_query = """
                    MATCH (fn:Function {name: $function_name, file_path: $file_path})
                    SET fn.parameters_json = $parameters_json
                    """

                    session.run(
                        update_query,
                        function_name=function_name,
                        file_path=file_path,
                        parameters_json=params_json
                    )

                # Link to parent class if it's a method
                if parent_class:
                    method_query = """
                    MATCH (c:Class {name: $parent_class, file_path: $file_path})
                    MATCH (fn:Function {name: $function_name, file_path: $file_path})
                    CREATE (c)-[:HAS_METHOD]->(fn)
                    """

                    session.run(
                        method_query,
                        parent_class=parent_class,
                        file_path=file_path,
                        function_name=function_name
                    )

                return True

        except Exception as e:
            logger.error(f"Error creating function node: {e}")
            return False

    def create_function_call_relationship(
        self,
        caller_function: str,
        caller_file: str,
        called_function: str,
        called_file: str = None
    ) -> bool:
        """
        Create function call relationship

        Args:
            caller_function: Name of calling function
            caller_file: File containing caller
            called_function: Name of called function
            called_file: File containing called function (optional)

        Returns:
            True if successful
        """
        try:
            with self._driver.session() as session:
                if called_file:
                    # Cross-file function call
                    query = """
                    MATCH (caller:Function {name: $caller_name, file_path: $caller_file})
                    MATCH (called:Function {name: $called_name, file_path: $called_file})
                    CREATE (caller)-[:CALLS]->(called)
                    """

                    session.run(
                        query,
                        caller_name=caller_function,
                        caller_file=caller_file,
                        called_name=called_function,
                        called_file=called_file
                    )
                else:
                    # Same-file function call
                    query = """
                    MATCH (caller:Function {name: $caller_name, file_path: $caller_file})
                    MATCH (called:Function {name: $called_name, file_path: $caller_file})
                    CREATE (caller)-[:CALLS]->(called)
                    """

                    session.run(
                        query,
                        caller_name=caller_function,
                        caller_file=caller_file,
                        called_name=called_function
                    )

                return True

        except Exception as e:
            logger.error(f"Error creating function call relationship: {e}")
            return False

    def query_repository_structure(self, repo_name: str) -> Dict[str, Any]:
        """
        Get repository structure overview

        Args:
            repo_name: Repository full name

        Returns:
            Dictionary with structure statistics
        """
        try:
            with self._driver.session() as session:
                query = """
                MATCH (r:Repository {full_name: $repo_name})
                OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
                OPTIONAL MATCH (f)-[:DEFINES]->(c:Class)
                OPTIONAL MATCH (f)-[:DEFINES]->(fn:Function)
                RETURN 
                    count(DISTINCT f) as file_count,
                    count(DISTINCT c) as class_count,
                    count(DISTINCT fn) as function_count
                """

                result = session.run(query, repo_name=repo_name)
                record = result.single()

                return {
                    "repository": repo_name,
                    "files": record["file_count"],
                    "classes": record["class_count"],
                    "functions": record["function_count"]
                }

        except Exception as e:
            logger.error(f"Error querying repository structure: {e}")
            return {}

    def find_dependencies(self, file_path: str) -> List[str]:
        """
        Find all dependencies of a file

        Args:
            file_path: Path to the file

        Returns:
            List of dependent file paths
        """
        try:
            with self._driver.session() as session:
                query = """
                MATCH (f:File {path: $file_path})-[:DEPENDS_ON]->(dep:File)
                RETURN dep.path as dependency
                """

                result = session.run(query, file_path=file_path)
                dependencies = [record["dependency"] for record in result]

                return dependencies

        except Exception as e:
            logger.error(f"Error finding dependencies: {e}")
            return []

    def find_class_hierarchy(self, class_name: str) -> Dict[str, Any]:
        """
        Get class inheritance hierarchy

        Args:
            class_name: Name of the class

        Returns:
            Dictionary with parent and child classes
        """
        try:
            with self._driver.session() as session:
                # Find parent classes
                parent_query = """
                MATCH (c:Class {name: $class_name})-[:INHERITS_FROM*]->(parent:Class)
                RETURN parent.name as parent_class
                """

                parents = [
                    record["parent_class"]
                    for record in session.run(parent_query, class_name=class_name)
                ]

                # Find child classes
                child_query = """
                MATCH (child:Class)-[:INHERITS_FROM*]->(c:Class {name: $class_name})
                RETURN child.name as child_class
                """

                children = [
                    record["child_class"]
                    for record in session.run(child_query, class_name=class_name)
                ]

                return {
                    "class": class_name,
                    "parents": parents,
                    "children": children
                }

        except Exception as e:
            logger.error(f"Error finding class hierarchy: {e}")
            return {}

    def health_check(self) -> Dict[str, Any]:
        """
        Check Neo4j service health

        Returns:
            Health status dictionary
        """
        try:
            with self._driver.session() as session:
                # Check connection
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]

                # Get database stats
                stats_query = """
                MATCH (n)
                RETURN 
                    count(n) as node_count,
                    count(DISTINCT labels(n)) as label_count
                """

                stats = session.run(stats_query).single()

                return {
                    "status": "healthy" if test_value == 1 else "unhealthy",
                    "connected": True,
                    "total_nodes": stats["node_count"],
                    "total_labels": stats["label_count"]
                }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }

    def create_inheritance_relationship(
        self,
        repo_name: str,
        derived_class: str,
        base_class: str,
        file_path: str
    ) -> bool:
        """Create inheritance relationship between classes"""
        try:
            with self._driver.session() as session:
                query = """
                                MATCH (derived:Class {name: $derived_class, file_path: $file_path, repository: $repo_name})
                                MATCH (base:Class {name: $base_class, repository: $repo_name})
                                MERGE (derived)-[:INHERITS_FROM]->(base)
                                """
                session.run(
                    query,
                    derived_class=derived_class,
                    base_class=base_class,
                    file_path=file_path,
                    repo_name=repo_name
                )

                return True

        except Exception as e:
            logger.error(f"Error creating inheritance relationship: {e}")
            return False

    def create_import_relationship(
        self,
        repo_name: str,
        file_path: str,
        module: str,
        imported_name: str = None
    ) -> bool:
        """Create import relationship"""
        try:
            with self._driver.session() as session:
                # Create or match module node
                module_query = """
                MERGE (m:Module {name: $module})
                RETURN m
                """

                session.run(module_query, module=module)

                # Create import relationship
                if imported_name:
                    import_query = """
                    MATCH (f:File {path: $file_path})
                    MATCH (m:Module {name: $module})
                    MERGE (f)-[:IMPORTS {imported_name: $imported_name}]->(m)
                    """

                    session.run(
                        import_query,
                        file_path=file_path,
                        module=module,
                        imported_name=imported_name
                    )
                else:
                    import_query = """
                    MATCH (f:File {path: $file_path})
                    MATCH (m:Module {name: $module})
                    MERGE (f)-[:IMPORTS]->(m)
                    """

                    session.run(
                        import_query,
                        file_path=file_path,
                        module=module
                    )

                return True

        except Exception as e:
            logger.error(f"Error creating import relationship: {e}")
            return False

    def find_entity_dependencies(
        self,
        repo_name: str,
        entity_name: str,
        entity_type: str = 'Class'
    ) -> List[Dict]:
        """Find dependencies of an entity"""
        try:
            with self._driver.session() as session:
                if entity_type == 'Class':
                    # Find classes that inherit from this class
                    query = """
                    MATCH (c:Class {name: $entity_name})<-[:INHERITS_FROM]-(derived:Class)
                    RETURN derived.name AS name, derived.file_path AS file_path
                    """
                else:
                    # Find functions that call this function
                    query = """
                    MATCH (f:Function {name: $entity_name})<-[:CALLS]-(caller:Function)
                    RETURN caller.name AS name, caller.file_path AS file_path
                    """

                result = session.run(query, entity_name=entity_name)

                dependencies = []
                for record in result:
                    dependencies.append({
                        "name": record["name"],
                        "file_path": record["file_path"]
                    })

                return dependencies

        except Exception as e:
            logger.error(f"Error finding dependencies: {e}")
            return []

    def get_function_call_graph(self, repo_name: str, function_name: str) -> Dict:
        """Get call graph for a function"""
        try:
            with self._driver.session() as session:
                # Find functions called by this function
                query = """
                MATCH (f:Function {name: $function_name})-[:CALLS]->(called:Function)
                RETURN called.name AS name, called.file_path AS file_path
                """

                result = session.run(query, function_name=function_name)

                calls = []
                for record in result:
                    calls.append({
                        "name": record["name"],
                        "file_path": record["file_path"]
                    })

                return {
                    "function": function_name,
                    "calls": calls
                }

        except Exception as e:
            logger.error(f"Error getting call graph: {e}")
            return {}

    def get_commit_frequency_timeline(self, repo_name: str, granularity: str = 'month'):
        """Get commit frequency over time"""
        if granularity == 'week':
            query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(c:Commit)
            WITH date(c.date).year as year, 
                 date(c.date).week as week,
                 count(c) as commits
            RETURN year, week, commits
            ORDER BY year, week
            """
        else:  # month
            query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(c:Commit)
            WITH date(c.date).year as year, 
                 date(c.date).month as month,
                 count(c) as commits
            RETURN year, month, commits
            ORDER BY year, month
            """
        return self.execute_query(query, {"repo_name": repo_name})

    def get_commits_by_folder(self, repo_name: str):
        """Get commit breakdown by folder/module"""
        query = """
        MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(c:Commit)
              -[:MODIFIES]->(f:File)
        WITH split(f.path, '/')[0] as folder, count(DISTINCT c) as commits
        RETURN folder, commits
        ORDER BY commits DESC
        LIMIT 100
        """
        return self.execute_query(query, {"repo_name": repo_name})

    def get_largest_commits(self, repo_name: str, limit: int = 25):
        """Get commits with most lines changed"""
        query = """
        MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(c:Commit)
        WHERE c.additions IS NOT NULL AND c.deletions IS NOT NULL
        WITH c, (c.additions + c.deletions) as total_changes
        RETURN c, total_changes
        ORDER BY total_changes DESC
        LIMIT $limit
        """
        return self.execute_query(query, {"repo_name": repo_name, "limit": limit})

    def get_module_from_path(self, file_path: str) -> str:
        """Extract module name from file path"""
        parts = file_path.split('/')
        if len(parts) > 1:
            return parts[0]  # Top-level directory
        return "root"

    def get_modules(self, repo_name: str):
        """Get all modules in repository"""
        query = """
        MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)
        WITH split(f.path, '/')[0] as module, count(f) as file_count
        RETURN module, file_count
        ORDER BY file_count DESC
        """
        return self.execute_query(query, {"repo_name": repo_name})

    def get_commits_by_module(self, repo_name: str, module: str):
        """Get commits that modified a specific module"""
        query = """
        MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(c:Commit)
              -[:MODIFIES]->(f:File)
        WHERE f.path STARTS WITH $module + '/'
        RETURN DISTINCT c
        ORDER BY c.date DESC
        """
        return self.execute_query(query, {
            "repo_name": repo_name,
            "module": module
        })

    def get_developers_by_module(self, repo_name: str, module: str):
        """Get developers who worked on a module"""
        query = """
        MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(c:Commit)
              -[:MODIFIES]->(f:File),
              (d:Developer)-[:AUTHORED]->(c)
        WHERE f.path STARTS WITH $module + '/'
        RETURN DISTINCT d, count(c) as commits
        ORDER BY commits DESC
        """
        return self.execute_query(query, {
            "repo_name": repo_name,
            "module": module
        })

    def get_module_evolution(self, repo_name: str, module: str):
        """Get evolution timeline of a module"""
        query = """
        MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(c:Commit)
              -[:MODIFIES]->(f:File)
        WHERE f.path STARTS WITH $module + '/'
        RETURN c, collect(f.path) as files_modified
        ORDER BY c.date ASC
        """
        return self.execute_query(query, {
            "repo_name": repo_name,
            "module": module
        })

    def get_dependencies(self, repo_name: str) -> list:
        """Get file dependencies from knowledge graph via IMPORTS relationships."""
        try:
            if not self._driver:
                self.connect()
            with self._driver.session() as session:
                result = session.run("""
                    MATCH (f:File {repository: $repo})-[:IMPORTS]->(dep)
                    RETURN f.path AS file,
                           collect(dep.name) AS dependencies,
                           count(dep) AS dep_count
                    ORDER BY dep_count DESC
                    LIMIT 100
                """, repo=repo_name)
                return [{"file": r["file"], "dependencies": r["dependencies"], "dep_count": r["dep_count"]} for r in
                        result]
        except Exception as e:
            logger.warning(f"get_dependencies error: {e}")
            return []

    def get_repository_overview(self, repo_name: str) -> dict:
        """Get high-level repository stats from Neo4j graph."""
        try:
            if not self._driver:
                self.connect()
            with self._driver.session() as session:
                result = session.run("""
                                    MATCH (f:File {repository: $repo})
                                    OPTIONAL MATCH (f)-[:DEFINES]->(c:Class)
                                    OPTIONAL MATCH (f)-[:DEFINES]->(fn:Function)
                                    RETURN count(DISTINCT f) AS file_count,
                                           count(DISTINCT c) AS class_count,
                                           count(DISTINCT fn) AS function_count
                                """, repo=repo_name)
                record = result.single()
                if record:
                    return {
                        "file_count": record["file_count"],
                        "class_count": record["class_count"],
                        "function_count": record["function_count"],
                        "repository": repo_name
                    }
                return {}
        except Exception as e:
            logger.warning(f"get_repository_overview error: {e}")
            return {}

    def get_class_hierarchy(self, repo_name: str) -> list:
        """Get class inheritance hierarchy from Neo4j graph."""
        try:
            if not self._driver:
                self.connect()
            with self._driver.session() as session:
                result = session.run("""
                                    MATCH (c:Class {repository: $repo})
                                    OPTIONAL MATCH (c)-[:INHERITS_FROM]->(parent:Class)
                                    RETURN c.name AS class_name,
                                           c.file_path AS file,
                                           collect(parent.name) AS parents
                                    ORDER BY c.name
                                """, repo=repo_name)
                return [{"class": r["class_name"], "file": r["file"], "parents": r["parents"]} for r in result]
        except Exception as e:
            logger.warning(f"get_class_hierarchy error: {e}")
            return []

    def get_repository_structure(self, repo_name: str) -> dict:
        """Get repository file and code structure overview."""
        try:
            if not self._driver:
                self.connect()
            with self._driver.session() as session:
                # File/class/function counts
                result = session.run("""
                    MATCH (f:File {repository: $repo})
                    OPTIONAL MATCH (f)-[:CONTAINS]->(c:Class)
                    OPTIONAL MATCH (f)-[:CONTAINS]->(fn:Function)
                    RETURN count(DISTINCT f) AS files,
                           count(DISTINCT c) AS classes,
                           count(DISTINCT fn) AS functions,
                           collect(DISTINCT f.path)[0..20] AS sample_files
                """, repo=repo_name)
                r = result.single()
                data = {"files": r["files"], "classes": r["classes"],
                        "functions": r["functions"], "sample_files": r["sample_files"]} if r else {}

                # Total commit count
                commit_result = session.run("""
                    MATCH (c:Commit {repository: $repo})
                    RETURN count(c) AS total_commits
                """, repo=repo_name)
                cr = commit_result.single()
                data["total_commits"] = cr["total_commits"] if cr else 0

                # Most modified files
                modified_result = session.run("""
                    MATCH (f:File)<-[:MODIFIED]-(c:Commit)
                    WHERE f.repository = $repo
                    RETURN f.path AS path, count(c) AS modifications
                    ORDER BY modifications DESC
                    LIMIT 25
                """, repo=repo_name)
                data["most_modified_files"] = [
                    {"path": r["path"], "modifications": r["modifications"]}
                    for r in modified_result
                ]

                return data
        except Exception as e:
            logger.warning(f"get_repository_structure error: {e}")
            return {}

    def get_commit_history(self, repo_name: str, limit: int = 100) -> list:
        """Get commit history from Neo4j graph."""
        try:
            if not self._driver:
                self.connect()
            with self._driver.session() as session:
                result = session.run("""
                    MATCH (c:Commit {repository: $repo})
                    OPTIONAL MATCH (c)-[:COMMITTED_BY]->(a:Author)
                    RETURN c.sha AS sha, c.message AS message,
                           COALESCE(a.name, c.author_name, c.author, 'Unknown') AS author,
                           c.date AS date
                    ORDER BY c.date DESC
                    LIMIT $limit
                """, repo=repo_name, limit=limit)
                return [{"sha": r["sha"], "message": r["message"],
                         "author": r["author"], "date": r["date"]} for r in result]
        except Exception as e:
            logger.warning(f"get_commit_history error: {e}")
            return []

    def get_file_contributors(self, repo_name: str, file_path: str, limit: int = 10) -> list:
        """Get top contributors for a specific file using COMMITTED_BY relationship."""
        try:
            if not self._driver:
                self.connect()
            with self._driver.session() as session:
                result = session.run("""
                    MATCH (c:Commit)-[:MODIFIED]->(f:File)
                    WHERE f.repository = $repo AND f.path CONTAINS $file_path
                    OPTIONAL MATCH (c)-[:COMMITTED_BY]->(a:Author)
                    WITH COALESCE(a.name, c.author_name, c.author, 'Unknown') AS author,
                         count(c) AS commits
                    RETURN author, commits
                    ORDER BY commits DESC
                    LIMIT $limit
                """, repo=repo_name, file_path=file_path, limit=limit)
                return [{"author": r["author"], "commits": r["commits"]} for r in result]
        except Exception as e:
            logger.warning(f"get_file_contributors error: {e}")
            return []

    def get_recently_modified_files(self, repo_name: str, n_commits: int = 20, limit: int = 15) -> list:
        """Get files most frequently modified in the last N commits (HIST-008 fix)."""
        try:
            if not self._driver:
                self.connect()
            with self._driver.session() as session:
                result = session.run("""
                    MATCH (c:Commit {repository: $repo})
                    WITH c ORDER BY c.date DESC LIMIT $n_commits
                    MATCH (c)-[:MODIFIED]->(f:File)
                    RETURN f.path AS path, count(c) AS modifications
                    ORDER BY modifications DESC
                    LIMIT $limit
                """, repo=repo_name, n_commits=n_commits, limit=limit)
                return [{"path": r["path"], "modifications": r["modifications"]} for r in result]
        except Exception as e:
            logger.warning(f"get_recently_modified_files error: {e}")
            return []

    def get_class_hierarchy_full(self, repo_name: str, class_name: str) -> dict:
        """Get FULL transitive class hierarchy for a specific class (STR-007 fix)."""
        try:
            if not self._driver:
                self.connect()
            with self._driver.session() as session:
                # Direct parents
                parents_result = session.run("""
                    MATCH (c:Class {repository: $repo, name: $class_name})
                           -[:INHERITS_FROM]->(parent:Class)
                    RETURN DISTINCT parent.name AS parent
                """, repo=repo_name, class_name=class_name)
                parents = [r["parent"] for r in parents_result]

                # Full transitive chain
                chain_result = session.run("""
                    MATCH path = (c:Class {repository: $repo, name: $class_name})
                                  -[:INHERITS_FROM*1..5]->(ancestor:Class)
                    RETURN DISTINCT ancestor.name AS ancestor,
                           length(path) AS depth
                    ORDER BY depth ASC
                """, repo=repo_name, class_name=class_name)
                chain = [r["ancestor"] for r in chain_result]

                # Subclasses
                children_result = session.run("""
                    MATCH (child:Class {repository: $repo})
                           -[:INHERITS_FROM]->(c:Class {name: $class_name})
                    RETURN DISTINCT child.name AS child
                """, repo=repo_name, class_name=class_name)
                children = [r["child"] for r in children_result]

                return {
                    "class": class_name,
                    "direct_parents": parents,
                    "full_chain": chain,
                    "subclasses": children
                }
        except Exception as e:
            logger.warning(f"get_class_hierarchy_full error: {e}")
            return {}

# Singleton instance
neo4j_service = Neo4jService(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    username=os.getenv("NEO4J_USERNAME", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password123")
)

# Connect on module import
neo4j_service.connect()

