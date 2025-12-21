"""
Graph API Router - Phase 3
Endpoints for code knowledge graph operations
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
import logging

from ..services.graph_populator_service import graph_populator_service
from ..services.neo4j_service import neo4j_service
from ..services.github_service import github_service
from ..services.git_factory import get_git_service

router = APIRouter(prefix="/graph", tags=["graph"])
logger = logging.getLogger(__name__)


@router.post("/analyze")
async def analyze_repository_graph(
    repository_url: str = Query(..., description="GitHub/GitLab repository URL")
) -> Dict:
    """
    Analyze repository and populate knowledge graph

    Args:
        repository_url: Full repository URL (e.g., https://github.com/owner/repo)

    Returns:
        Analysis statistics and graph metrics

    Example:
        POST /api/graph/analyze?repository_url=https://github.com/user/repo
    """
    try:
        logger.info(f"Analyzing repository for graph: {repository_url}")

        # Get appropriate git service
        git_service = get_git_service(repository_url)

        # Get repository info
        repo_info = git_service.get_repository_info(repository_url)

        if not repo_info:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Get ALL Python files recursively (GitHub service now handles this!)
        all_files = git_service.get_all_files_recursive(
            repository_url,
            file_extension=".py"
        )

        logger.info(f"Found {len(all_files)} Python files to analyze (recursive)")

        # Fetch content for each Python file (limit for safety)
        MAX_FILES = 100  # Limit to prevent overload
        files_with_content = []

        for file_info in all_files[:MAX_FILES]:
            file_path = file_info.get('path')

            try:
                content = git_service.get_file_content(repository_url, file_path)

                if content:
                    files_with_content.append({
                        'path': file_path,
                        'content': content,
                        'language': 'python'
                    })

            except Exception as e:
                logger.warning(f"Failed to fetch {file_path}: {e}")
                continue

        if len(all_files) > MAX_FILES:
            logger.warning(f"Limited to {MAX_FILES} files out of {len(all_files)} total Python files")

        logger.info(f"Successfully fetched content for {len(files_with_content)} files")

        # Populate graph database
        stats = graph_populator_service.populate_repository(
            repo_info=repo_info,
            files=files_with_content
        )

        return {
            "success": True,
            "repository": repo_info.get('full_name'),
            "statistics": {
                "total_python_files": len(all_files),
                "processed_files": stats.get('files', 0),
                "classes": stats.get('classes', 0),
                "functions": stats.get('functions', 0),
                "imports": stats.get('imports', 0),
                "relationships": stats.get('relationships', 0)
            },
            "message": f"Successfully analyzed {stats.get('files', 0)} out of {len(all_files)} Python files"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing repository graph: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/structure/{repo_owner}/{repo_name}")
async def get_repository_structure(
    repo_owner: str,
    repo_name: str
) -> Dict:
    """
    Get repository code structure from knowledge graph

    Args:
        repo_owner: Repository owner
        repo_name: Repository name

    Returns:
        Repository structure from graph database

    Example:
        GET /api/graph/structure/langchain-ai/langchain
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Querying graph structure for: {full_name}")

        structure = graph_populator_service.query_code_structure(full_name)

        if not structure:
            raise HTTPException(
                status_code=404,
                detail=f"No graph data found for repository: {full_name}"
            )

        return {
            "success": True,
            "repository": full_name,
            "structure": structure
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying repository structure: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/dependencies/{repo_owner}/{repo_name}/{entity_name}")
async def get_entity_dependencies(
    repo_owner: str,
    repo_name: str,
    entity_name: str,
    entity_type: str = Query("Class", description="Entity type: Class or Function")
) -> Dict:
    """
    Find dependencies of a code entity

    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        entity_name: Name of the entity (class/function)
        entity_type: Type of entity ("Class" or "Function")

    Returns:
        List of entities that depend on this entity

    Example:
        GET /api/graph/dependencies/user/repo/MyClass?entity_type=Class
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Finding dependencies for {entity_type} '{entity_name}' in {full_name}")

        dependencies = graph_populator_service.find_dependencies(
            repo_name=full_name,
            entity_name=entity_name,
            entity_type=entity_type
        )

        return {
            "success": True,
            "repository": full_name,
            "entity": {
                "name": entity_name,
                "type": entity_type
            },
            "dependencies": dependencies,
            "count": len(dependencies)
        }

    except Exception as e:
        logger.error(f"Error finding dependencies: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/call-graph/{repo_owner}/{repo_name}/{function_name}")
async def get_function_call_graph(
    repo_owner: str,
    repo_name: str,
    function_name: str
) -> Dict:
    """
    Get call graph for a function

    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        function_name: Name of the function

    Returns:
        Function call graph

    Example:
        GET /api/graph/call-graph/user/repo/process_data
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Getting call graph for function '{function_name}' in {full_name}")

        call_graph = graph_populator_service.find_call_graph(
            repo_name=full_name,
            function_name=function_name
        )

        return {
            "success": True,
            "repository": full_name,
            "call_graph": call_graph
        }

    except Exception as e:
        logger.error(f"Error getting call graph: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/visualize/{repo_owner}/{repo_name}")
async def get_graph_visualization_data(
    repo_owner: str,
    repo_name: str,
    max_nodes: int = Query(100, description="Maximum nodes to return")
) -> Dict:
    """
    Get graph visualization data for frontend

    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        max_nodes: Maximum number of nodes to return

    Returns:
        Nodes and edges for graph visualization

    Example:
        GET /api/graph/visualize/user/repo?max_nodes=50
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Getting visualization data for: {full_name}")

        # Get nodes and relationships from Neo4j
        with neo4j_service._driver.session() as session:
            # Get classes
            class_query = """
            MATCH (c:Class)
            WHERE c.file_path CONTAINS $repo_name
            RETURN c.name AS name, c.file_path AS file_path, 
                   c.start_line AS start_line, c.docstring AS docstring
            LIMIT $max_nodes
            """

            class_result = session.run(
                class_query,
                repo_name=repo_name,
                max_nodes=max_nodes
            )

            nodes = []
            for record in class_result:
                nodes.append({
                    "id": record["name"],
                    "label": record["name"],
                    "type": "class",
                    "file_path": record["file_path"],
                    "line": record["start_line"],
                    "docstring": record["docstring"]
                })

            # Get inheritance relationships
            inherit_query = """
            MATCH (derived:Class)-[:INHERITS_FROM]->(base:Class)
            WHERE derived.file_path CONTAINS $repo_name
            RETURN derived.name AS source, base.name AS target
            LIMIT $max_nodes
            """

            inherit_result = session.run(
                inherit_query,
                repo_name=repo_name,
                max_nodes=max_nodes
            )

            edges = []
            for record in inherit_result:
                edges.append({
                    "source": record["source"],
                    "target": record["target"],
                    "type": "inherits"
                })

            # Get import relationships
            import_query = """
            MATCH (f:File)-[:IMPORTS]->(m:Module)
            WHERE f.path CONTAINS $repo_name
            RETURN f.name AS source, m.name AS target
            LIMIT $max_nodes
            """

            import_result = session.run(
                import_query,
                repo_name=repo_name,
                max_nodes=max_nodes
            )

            for record in import_result:
                edges.append({
                    "source": record["source"],
                    "target": record["target"],
                    "type": "imports"
                })

            # Get statistics counts
            stats_query = """
            MATCH (n)
            WHERE n.file_path CONTAINS $repo_name OR n.path CONTAINS $repo_name
            WITH labels(n)[0] AS type, count(n) AS count
            RETURN type, count
            """

            stats_result = session.run(stats_query, repo_name=repo_name)

            classes_count = 0
            functions_count = 0
            files_count = 0

            for record in stats_result:
                node_type = record["type"]
                node_count = record["count"]

                if node_type == "Class":
                    classes_count = node_count
                elif node_type == "Function":
                    functions_count = node_count
                elif node_type == "File":
                    files_count = node_count

        return {
            "success": True,
            "repository": full_name,
            "graph": {
                "nodes": nodes,
                "edges": edges
            },
            "statistics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "classes": classes_count,
                "functions": functions_count,
                "files": files_count,
                "relationships": len(edges)
            }
        }

    except Exception as e:
        logger.error(f"Error getting visualization data: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.delete("/clear/{repo_owner}/{repo_name}")
async def clear_repository_graph(
    repo_owner: str,
    repo_name: str
) -> Dict:
    """
    Clear all graph data for a repository

    Args:
        repo_owner: Repository owner
        repo_name: Repository name

    Returns:
        Success confirmation

    Example:
        DELETE /api/graph/clear/user/repo
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Clearing graph data for: {full_name}")

        neo4j_service.clear_repository_graph(full_name)

        return {
            "success": True,
            "repository": full_name,
            "message": f"Graph data cleared for {full_name}"
        }

    except Exception as e:
        logger.error(f"Error clearing graph: {e}")
        raise HTTPException(status_code=500, detail=f"Clear failed: {str(e)}")


@router.get("/health")
async def graph_health_check() -> Dict:
    """
    Check Neo4j connection health

    Returns:
        Neo4j health status

    Example:
        GET /api/graph/health
    """
    try:
        health = neo4j_service.health_check()

        return {
            "success": health.get("status") == "healthy",
            "neo4j": health
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }