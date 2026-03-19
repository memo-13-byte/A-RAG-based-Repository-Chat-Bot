"""
Graph Populator Service - Phase 3
Populates Neo4j graph database with code entities
"""

import logging
from typing import Dict, List, Optional, Any
from .code_parser_service import code_parser_service
from .neo4j_service import neo4j_service

logger = logging.getLogger(__name__)


class GraphPopulatorService:
    """
    Service for populating Neo4j graph with code entities

    Features:
    - Parse code files and extract entities
    - Create nodes and relationships in Neo4j
    - Handle repository structure
    - Link code entities (imports, inheritance, calls)
    """

    def __init__(self):
        """Initialize graph populator"""
        self.code_parser = code_parser_service
        self.neo4j = neo4j_service
        logger.info("Graph Populator Service initialized")

    def populate_from_file(
            self,
            repo_name: str,
            file_path: str,
            code: str,
            language: str = 'python'
    ) -> Dict[str, int]:
        """
        Parse a code file and populate graph database

        Args:
            repo_name: Repository full name (owner/repo)
            file_path: Path to the file in repository
            code: Source code content
            language: Programming language

        Returns:
            Statistics about created entities
        """
        stats = {
            "classes": 0,
            "functions": 0,
            "imports": 0,
            "relationships": 0
        }

        try:
            # Create file node first
            file_name = file_path.split('/')[-1]
            extension = '.' + file_name.split('.')[-1] if '.' in file_name else ''

            file_created = self.neo4j.create_file_node(
                repo_name=repo_name,
                file_path=file_path,
                file_name=file_name,
                extension=extension,
                language=language,
                size=len(code)
            )

            if not file_created:
                logger.warning(f"Failed to create file node for {file_path}")
                return stats

            # Parse code based on language
            if language.lower() == 'python':
                entities = self.code_parser.extract_python_entities(file_path, code)
            else:
                logger.warning(f"Language {language} not yet supported")
                return stats

            # Create class nodes
            for cls in entities['classes']:
                success = self.neo4j.create_class_node(
                    repo_name=repo_name,
                    file_path=file_path,
                    class_name=cls.name,
                    start_line=cls.start_line,
                    end_line=cls.end_line,
                    docstring=cls.docstring or "",
                    base_classes=cls.base_classes or []
                )

                if success:
                    stats["classes"] += 1


            # Create function nodes
            for func in entities['functions']:
                success = self.neo4j.create_function_node(
                    repo_name=repo_name,
                    file_path=file_path,
                    function_name=func.name,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    parameters=func.parameters or [],
                    return_type=func.return_type or "",
                    docstring=func.docstring or "",
                    parent_class=func.parent_class
                )

                if success:
                    stats["functions"] += 1

            # Create import nodes and relationships
            for imp in entities['imports']:
                # Create or link import relationship
                if imp.is_from_import:
                    for name in imp.names:
                        self.neo4j.create_import_relationship(
                            repo_name=repo_name,
                            file_path=file_path,
                            module=imp.module,
                            imported_name=name
                        )
                        stats["imports"] += 1
                else:
                    self.neo4j.create_import_relationship(
                        repo_name=repo_name,
                        file_path=file_path,
                        module=imp.module
                    )
                    stats["imports"] += 1

            logger.info(f"Populated graph for {file_path}: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error populating graph from {file_path}: {e}")
            return stats

    def populate_repository(
            self,
            repo_info: Dict,
            files: List[Dict[str, str]]
    ) -> Dict[str, int]:
        """
        Populate entire repository structure

        Args:
            repo_info: Repository metadata
            files: List of {path, content, language} dicts

        Returns:
            Aggregated statistics
        """
        total_stats = {
            "files": 0,
            "classes": 0,
            "functions": 0,
            "imports": 0,
            "relationships": 0
        }

        try:
            # Connect to Neo4j
            if not self.neo4j.connect():
                logger.error("Failed to connect to Neo4j")
                return total_stats

            # Create repository node
            repo_name = repo_info.get('full_name', 'unknown/unknown')

            self.neo4j.create_repository_node(repo_info)

            # Process each file
            for file_info in files:
                file_path = file_info.get('path')
                content = file_info.get('content')
                language = file_info.get('language', 'python')

                if not file_path or not content:
                    continue

                # Populate graph from this file
                file_stats = self.populate_from_file(
                    repo_name=repo_name,
                    file_path=file_path,
                    code=content,
                    language=language
                )

                # Aggregate stats
                total_stats["files"] += 1
                total_stats["classes"] += file_stats["classes"]
                total_stats["functions"] += file_stats["functions"]
                total_stats["imports"] += file_stats["imports"]
                total_stats["relationships"] += file_stats["relationships"]


            # === 2. PASS: Inheritance relationships ===
            # Tüm class node'ları oluştuktan sonra inheritance ekle
            logger.info("Starting inheritance pass...")
            for file_info in files:
                file_path = file_info.get('path')
                content = file_info.get('content', '')
                if not file_path or not content:
                    continue
                if file_info.get('language', 'python').lower() != 'python':
                    continue
                entities = self.code_parser.extract_python_entities(file_path, content)
                for cls in entities['classes']:
                    for base_class in (cls.base_classes or []):
                        self.neo4j.create_inheritance_relationship(
                            repo_name=repo_name,
                            derived_class=cls.name,
                            base_class=base_class,
                            file_path=file_path
                        )
                        total_stats["relationships"] += 1
            logger.info("Inheritance pass complete")

            logger.info(f"Repository {repo_name} populated: {total_stats}")
            return total_stats

        except Exception as e:
            logger.error(f"Error populating repository: {e}")
            return total_stats

    def query_code_structure(self, repo_name: str) -> Dict[str, Any]:
        """
        Query the complete code structure from graph

        Args:
            repo_name: Repository full name

        Returns:
            Structured code information
        """
        try:
            return self.neo4j.query_repository_structure(repo_name)
        except Exception as e:
            logger.error(f"Error querying code structure: {e}")
            return {}

    def find_dependencies(
            self,
            repo_name: str,
            entity_name: str,
            entity_type: str = 'Class'
    ) -> List[Dict]:
        """
        Find all dependencies of a code entity

        Args:
            repo_name: Repository full name
            entity_name: Name of the entity (class/function)
            entity_type: Type of entity ('Class', 'Function')

        Returns:
            List of dependent entities
        """
        try:
            return self.neo4j.find_entity_dependencies(
                repo_name=repo_name,
                entity_name=entity_name,
                entity_type=entity_type
            )
        except Exception as e:
            logger.error(f"Error finding dependencies: {e}")
            return []

    def find_call_graph(self, repo_name: str, function_name: str) -> Dict:
        """
        Find call graph for a function

        Args:
            repo_name: Repository full name
            function_name: Name of the function

        Returns:
            Call graph structure
        """
        try:
            return self.neo4j.get_function_call_graph(repo_name, function_name)
        except Exception as e:
            logger.error(f"Error finding call graph: {e}")
            return {}


# Singleton instance
graph_populator_service = GraphPopulatorService()