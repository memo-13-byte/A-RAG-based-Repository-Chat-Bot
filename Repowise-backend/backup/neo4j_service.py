"""
Neo4j Graph Database Service - Phase 3
Manages code knowledge graph for repository structure and relationships
"""

from neo4j import GraphDatabase
from typing import Dict, List, Optional, Any
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
                        MATCH (c:Class {name: $class_name, file_path: $file_path})
                        MATCH (b:Class {name: $base_class})
                        CREATE (c)-[:INHERITS_FROM]->(b)
                        """

                        session.run(
                            inherit_query,
                            class_name=class_name,
                            file_path=file_path,
                            base_class=base_class
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
                MATCH (derived:Class {name: $derived_class, file_path: $file_path})
                MATCH (base:Class {name: $base_class})
                MERGE (derived)-[:INHERITS_FROM]->(base)
                """

                session.run(
                    query,
                    derived_class=derived_class,
                    base_class=base_class,
                    file_path=file_path
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


# Singleton instance
neo4j_service = Neo4jService(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    username=os.getenv("NEO4J_USERNAME", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password123")
)

# Connect on module import
neo4j_service.connect()