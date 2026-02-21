"""
Graph API Router - ENHANCED VERSION
Adds temporal queries, statistics, module queries, and file history endpoints

NEW ENDPOINTS:
- /temporal/* - Date/time based queries
- /statistics/* - Activity metrics and aggregations
- /modules/* - Module-based queries
- /files/* - File history tracking
- /releases/* - Tag/release management
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime
import logging

from ..services.graph_populator_service import graph_populator_service
from ..services.neo4j_service import neo4j_service
from ..services.github_service import github_service
from ..services.git_factory import get_git_service
from ..services.neo4j_service_enhanced import get_enhanced_queries

router = APIRouter(prefix="/graph", tags=["graph"])
logger = logging.getLogger(__name__)

# Get enhanced queries instance
enhanced_queries = get_enhanced_queries(neo4j_service)


# ============================================================================
# EXISTING ENDPOINTS (Keep as is)
# ============================================================================

@router.post("/analyze")
async def analyze_repository_graph(
    repository_url: str = Query(..., description="GitHub/GitLab repository URL")
) -> Dict:
    """Analyze repository and populate knowledge graph"""
    try:
        logger.info(f"Analyzing repository for graph: {repository_url}")

        git_service = get_git_service(repository_url)
        repo_info = git_service.get_repository_info(repository_url)

        if not repo_info:
            raise HTTPException(status_code=404, detail="Repository not found")

        all_files = git_service.get_all_files_recursive(
            repository_url,
            file_extension=".py"
        )

        logger.info(f"Found {len(all_files)} Python files to analyze")

        MAX_FILES = 100
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
            logger.warning(f"Limited to {MAX_FILES} files out of {len(all_files)}")

        logger.info(f"Successfully fetched {len(files_with_content)} files")

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
            "message": f"Analyzed {stats.get('files', 0)} out of {len(all_files)} files"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/structure/{repo_owner}/{repo_name}")
async def get_repository_structure(repo_owner: str, repo_name: str) -> Dict:
    """Get repository code structure from knowledge graph"""
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Querying graph structure for: {full_name}")

        structure = graph_populator_service.query_code_structure(full_name)

        if not structure:
            raise HTTPException(
                status_code=404,
                detail=f"No graph data found for: {full_name}"
            )

        return {
            "success": True,
            "repository": full_name,
            "structure": structure
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visualize/{repo_owner}/{repo_name}")
async def get_graph_visualization_data(
    repo_owner: str,
    repo_name: str,
    max_nodes: int = Query(100, description="Maximum nodes to return")
) -> Dict:
    """Get graph visualization data for frontend"""
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Getting visualization data for: {full_name}")

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

            # Get relationships
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

            # Get statistics
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
        logger.error(f"Error getting visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 🆕 NEW: TEMPORAL QUERIES
# ============================================================================

@router.get("/temporal/by-date/{repo_owner}/{repo_name}")
async def get_commits_by_date(
    repo_owner: str,
    repo_name: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format")
) -> Dict:
    """
    Get all commits on a specific date

    Example: /api/graph/temporal/by-date/psf/requests?date=2024-12-30
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Getting commits on {date} for {full_name}")

        commits = enhanced_queries.get_commits_by_date(full_name, date)

        return {
            "success": True,
            "repository": full_name,
            "date": date,
            "commits": commits,
            "count": len(commits)
        }

    except Exception as e:
        logger.error(f"Error getting commits by date: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal/range/{repo_owner}/{repo_name}")
async def get_commits_in_range(
    repo_owner: str,
    repo_name: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)")
) -> Dict:
    """
    Get commits between two dates

    Example: /api/graph/temporal/range/psf/requests?start_date=2024-01-01&end_date=2024-12-31
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Getting commits from {start_date} to {end_date}")

        commits = enhanced_queries.get_commits_in_range(full_name, start_date, end_date)

        return {
            "success": True,
            "repository": full_name,
            "start_date": start_date,
            "end_date": end_date,
            "commits": commits,
            "count": len(commits)
        }

    except Exception as e:
        logger.error(f"Error getting commits in range: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal/by-month/{repo_owner}/{repo_name}")
async def get_commits_by_month(
    repo_owner: str,
    repo_name: str,
    year: int = Query(..., description="Year (e.g., 2024)"),
    month: int = Query(..., description="Month (1-12)")
) -> Dict:
    """
    Get commits in a specific month

    Example: /api/graph/temporal/by-month/psf/requests?year=2024&month=12
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Getting commits for {year}-{month:02d}")

        result = enhanced_queries.get_commits_by_month(full_name, year, month)

        return {
            "success": True,
            "repository": full_name,
            **result
        }

    except Exception as e:
        logger.error(f"Error getting commits by month: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal/developers/{repo_owner}/{repo_name}")
async def get_developers_in_timeframe(
    repo_owner: str,
    repo_name: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)")
) -> Dict:
    """
    Get developers who contributed in a timeframe

    Example: /api/graph/temporal/developers/psf/requests?start_date=2024-01-01&end_date=2024-12-31
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        developers = enhanced_queries.get_developers_in_timeframe(
            full_name, start_date, end_date
        )

        return {
            "success": True,
            "repository": full_name,
            "timeframe": {
                "start": start_date,
                "end": end_date
            },
            "developers": developers,
            "count": len(developers)
        }

    except Exception as e:
        logger.error(f"Error getting developers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 🆕 NEW: STATISTICS & METRICS
# ============================================================================

@router.get("/statistics/timeline/{repo_owner}/{repo_name}")
async def get_commit_frequency_timeline(
    repo_owner: str,
    repo_name: str,
    granularity: str = Query("month", description="'week' or 'month'")
) -> Dict:
    """
    Get commit frequency timeline

    Example: /api/graph/statistics/timeline/psf/requests?granularity=month
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        timeline = enhanced_queries.get_commit_frequency_timeline(
            full_name, granularity
        )

        return {
            "success": True,
            "repository": full_name,
            "granularity": granularity,
            "timeline": timeline
        }

    except Exception as e:
        logger.error(f"Error getting timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/by-folder/{repo_owner}/{repo_name}")
async def get_commits_by_folder(
    repo_owner: str,
    repo_name: str,
    limit: int = Query(20, description="Maximum folders to return")
) -> Dict:
    """
    Get commit breakdown by folder

    Example: /api/graph/statistics/by-folder/psf/requests?limit=20
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        folders = enhanced_queries.get_commits_by_folder(full_name, limit)

        return {
            "success": True,
            "repository": full_name,
            "folders": folders,
            "count": len(folders)
        }

    except Exception as e:
        logger.error(f"Error getting folder stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/largest-commits/{repo_owner}/{repo_name}")
async def get_largest_commits(
    repo_owner: str,
    repo_name: str,
    limit: int = Query(10, description="Number of commits to return")
) -> Dict:
    """
    Get largest commits by lines changed

    Example: /api/graph/statistics/largest-commits/psf/requests?limit=10
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        commits = enhanced_queries.get_largest_commits(full_name, limit)

        return {
            "success": True,
            "repository": full_name,
            "commits": commits,
            "count": len(commits)
        }

    except Exception as e:
        logger.error(f"Error getting largest commits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/contributors/{repo_owner}/{repo_name}")
async def get_contributor_breakdown(
    repo_owner: str,
    repo_name: str
) -> Dict:
    """
    Get detailed contributor breakdown

    Example: /api/graph/statistics/contributors/psf/requests
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        contributors = enhanced_queries.get_developer_contribution_breakdown(full_name)

        return {
            "success": True,
            "repository": full_name,
            "contributors": contributors,
            "count": len(contributors)
        }

    except Exception as e:
        logger.error(f"Error getting contributors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 🆕 NEW: MODULE QUERIES
# ============================================================================

@router.get("/modules/list/{repo_owner}/{repo_name}")
async def get_modules(
    repo_owner: str,
    repo_name: str
) -> Dict:
    """
    Get all modules (top-level directories) in repository

    Example: /api/graph/modules/list/psf/requests
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        modules = enhanced_queries.get_modules(full_name)

        return {
            "success": True,
            "repository": full_name,
            "modules": modules,
            "count": len(modules)
        }

    except Exception as e:
        logger.error(f"Error getting modules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/commits/{repo_owner}/{repo_name}/{module_name}")
async def get_module_commits(
    repo_owner: str,
    repo_name: str,
    module_name: str
) -> Dict:
    """
    Get commits that modified a specific module

    Example: /api/graph/modules/commits/psf/requests/src
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        commits = enhanced_queries.get_commits_by_module(full_name, module_name)

        return {
            "success": True,
            "repository": full_name,
            "module": module_name,
            "commits": commits,
            "count": len(commits)
        }

    except Exception as e:
        logger.error(f"Error getting module commits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/developers/{repo_owner}/{repo_name}/{module_name}")
async def get_module_developers(
    repo_owner: str,
    repo_name: str,
    module_name: str
) -> Dict:
    """
    Get developers who worked on a module

    Example: /api/graph/modules/developers/psf/requests/src
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        developers = enhanced_queries.get_developers_by_module(full_name, module_name)

        return {
            "success": True,
            "repository": full_name,
            "module": module_name,
            "developers": developers,
            "count": len(developers)
        }

    except Exception as e:
        logger.error(f"Error getting module developers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/evolution/{repo_owner}/{repo_name}/{module_name}")
async def get_module_evolution(
    repo_owner: str,
    repo_name: str,
    module_name: str
) -> Dict:
    """
    Get evolution timeline of a module

    Example: /api/graph/modules/evolution/psf/requests/src
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        evolution = enhanced_queries.get_module_evolution(full_name, module_name)

        return {
            "success": True,
            "repository": full_name,
            "module": module_name,
            "evolution": evolution,
            "commit_count": len(evolution)
        }

    except Exception as e:
        logger.error(f"Error getting module evolution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 🆕 NEW: FILE HISTORY
# ============================================================================

@router.get("/files/history/{repo_owner}/{repo_name}")
async def get_file_history(
    repo_owner: str,
    repo_name: str,
    file_path: str = Query(..., description="Path to file")
) -> Dict:
    """
    Get commit history for a file

    Example: /api/graph/files/history/psf/requests?file_path=src/requests/api.py
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        history = enhanced_queries.get_file_history(full_name, file_path)

        return {
            "success": True,
            "repository": full_name,
            "file_path": file_path,
            "history": history,
            "commit_count": len(history)
        }

    except Exception as e:
        logger.error(f"Error getting file history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/authors/{repo_owner}/{repo_name}")
async def get_file_authors(
    repo_owner: str,
    repo_name: str,
    file_path: str = Query(..., description="Path to file")
) -> Dict:
    """
    Get developers who modified a file

    Example: /api/graph/files/authors/psf/requests?file_path=src/requests/api.py
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        authors = enhanced_queries.get_file_authors(full_name, file_path)

        return {
            "success": True,
            "repository": full_name,
            "file_path": file_path,
            "authors": authors,
            "count": len(authors)
        }

    except Exception as e:
        logger.error(f"Error getting file authors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/timeline/{repo_owner}/{repo_name}")
async def get_file_timeline(
    repo_owner: str,
    repo_name: str,
    file_path: str = Query(..., description="Path to file")
) -> Dict:
    """
    Get timeline of changes to a file

    Example: /api/graph/files/timeline/psf/requests?file_path=src/requests/api.py
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        timeline = enhanced_queries.get_file_changes_timeline(full_name, file_path)

        return {
            "success": True,
            "repository": full_name,
            "file_path": file_path,
            "timeline": timeline,
            "change_count": len(timeline)
        }

    except Exception as e:
        logger.error(f"Error getting file timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/renames/{repo_owner}/{repo_name}")
async def get_file_renames(
        repo_owner: str,
        repo_name: str,
        file_path: str = Query(..., description="File path to track renames for")
) -> Dict:
    """Get complete rename history for a file"""
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Getting rename history for {file_path} in {full_name}")

        renames = enhanced_queries.get_file_rename_history(full_name, file_path)

        return {
            "success": True,
            "repository": full_name,
            "file_path": file_path,
            "renames": renames,
            "count": len(renames),
            "has_renames": len(renames) > 0
        }

    except Exception as e:
        logger.error(f"Error getting file renames: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/all-moves/{repo_owner}/{repo_name}")
async def get_all_file_moves(
        repo_owner: str,
        repo_name: str,
        start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
        end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
        module: Optional[str] = Query(None, description="Filter by module (e.g., 'src')")
) -> Dict:
    """Get all file renames/moves in repository"""
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Getting all file moves in {full_name}")

        moves = enhanced_queries.get_all_file_moves(
            full_name,
            start_date=start_date,
            end_date=end_date,
            module=module
        )

        cross_module_moves = sum(1 for m in moves if m.get('moved_across_modules', False))
        same_module = len(moves) - cross_module_moves

        return {
            "success": True,
            "repository": full_name,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "module": module
            },
            "moves": moves,
            "statistics": {
                "total_moves": len(moves),
                "cross_module_moves": cross_module_moves,
                "same_module_renames": same_module
            }
        }

    except Exception as e:
        logger.error(f"Error getting file moves: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/current-location/{repo_owner}/{repo_name}")
async def get_file_current_location(
        repo_owner: str,
        repo_name: str,
        historical_path: str = Query(..., description="Historical file path")
) -> Dict:
    """Find current location of a renamed file"""
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Finding current location of {historical_path} in {full_name}")

        current = enhanced_queries.get_file_current_location(full_name, historical_path)

        if current:
            return {
                "success": True,
                "repository": full_name,
                "historical_path": historical_path,
                "current_path": current,
                "was_renamed": current != historical_path,
                "status": "found"
            }
        else:
            return {
                "success": True,
                "repository": full_name,
                "historical_path": historical_path,
                "current_path": None,
                "was_renamed": None,
                "status": "not_found",
                "message": "File not found (may have been deleted)"
            }

    except Exception as e:
        logger.error(f"Error finding current location: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/reorganization/{repo_owner}/{repo_name}/{module_name}")
async def get_module_reorganization(
        repo_owner: str,
        repo_name: str,
        module_name: str
) -> Dict:
    """Analyze module reorganization history"""
    try:
        full_name = f"{repo_owner}/{repo_name}"
        logger.info(f"Analyzing reorganization of {module_name} in {full_name}")

        analysis = enhanced_queries.get_module_reorganization_history(full_name, module_name)

        return {
            "success": True,
            "repository": full_name,
            "module": module_name,
            "reorganization": analysis
        }

    except Exception as e:
        logger.error(f"Error analyzing module reorganization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# 🆕 NEW: RELEASES & TAGS
# ============================================================================

@router.post("/releases/index/{repo_owner}/{repo_name}")
async def index_repository_tags(
    repo_owner: str,
    repo_name: str
) -> Dict:
    """
    Index all tags/releases for a repository

    Example: POST /api/graph/releases/index/psf/requests
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"
        repo_url = f"https://github.com/{full_name}"

        # Get tags from GitHub
        git_service = get_git_service(repo_url)
        tags = git_service.get_releases(repo_url)

        # Index each tag
        for tag in tags:
            enhanced_queries.index_tag(
                repo_name=full_name,
                tag_name=tag['tag_name'],
                sha=tag['sha'],
                date=tag['date']
            )

        return {
            "success": True,
            "repository": full_name,
            "tags_indexed": len(tags),
            "message": f"Indexed {len(tags)} tags"
        }

    except Exception as e:
        logger.error(f"Error indexing tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/releases/info/{repo_owner}/{repo_name}/{tag_name}")
async def get_release_info(
    repo_owner: str,
    repo_name: str,
    tag_name: str
) -> Dict:
    """
    Get information about a specific release

    Example: /api/graph/releases/info/psf/requests/v2.28.0
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        info = enhanced_queries.get_tag_info(full_name, tag_name)

        if not info:
            raise HTTPException(
                status_code=404,
                detail=f"Tag {tag_name} not found"
            )

        return {
            "success": True,
            "repository": full_name,
            **info
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting release info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/releases/commits/{repo_owner}/{repo_name}/{tag_name}")
async def get_release_commits(
    repo_owner: str,
    repo_name: str,
    tag_name: str,
    previous_tag: Optional[str] = Query(None, description="Previous release tag")
) -> Dict:
    """
    Get commits in a release

    Example: /api/graph/releases/commits/psf/requests/v2.28.0?previous_tag=v2.27.0
    """
    try:
        full_name = f"{repo_owner}/{repo_name}"

        commits = enhanced_queries.get_commits_in_release(
            full_name, tag_name, previous_tag
        )

        return {
            "success": True,
            "repository": full_name,
            "release": tag_name,
            "previous_release": previous_tag,
            "commits": commits,
            "count": len(commits)
        }

    except Exception as e:
        logger.error(f"Error getting release commits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EXISTING: CLEANUP & HEALTH
# ============================================================================

@router.delete("/clear/{repo_owner}/{repo_name}")
async def clear_repository_graph(
    repo_owner: str,
    repo_name: str
) -> Dict:
    """Clear all graph data for a repository"""
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def graph_health_check() -> Dict:
    """Check Neo4j connection health"""
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