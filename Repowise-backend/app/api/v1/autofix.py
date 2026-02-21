"""
AutoFix API Router
Endpoints for automated code fixing with AutoCodeRover
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
import logging

from app.services.autocoderover_service import (
    AutoCodeRoverService,
    get_autocoderover_service
)
from app.models.autofix import (
    AutoFixSubmitRequest,
    AutoFixSubmitResponse,
    AutoFixStatusResponse,
    AutoFixHealthResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/autofix",
    tags=["AutoFix"],
    responses={
        503: {"description": "AutoCodeRover service unavailable"},
        500: {"description": "Internal server error"}
    }
)


@router.get(
    "/health",
    response_model=AutoFixHealthResponse,
    summary="Check AutoCodeRover health",
    description="Check if AutoCodeRover service is healthy and available"
)
async def check_health(
    service: AutoCodeRoverService = Depends(get_autocoderover_service)
) -> AutoFixHealthResponse:
    """Check AutoCodeRover service health"""
    
    is_healthy = await service.health_check()
    
    if not is_healthy:
        logger.warning("AutoCodeRover service is unhealthy")
        raise HTTPException(
            status_code=503,
            detail="AutoCodeRover service is unavailable"
        )
    
    return AutoFixHealthResponse(
        healthy=True,
        service="autocoderover",
        version="1.0"
    )


@router.post(
    "/submit",
    response_model=AutoFixSubmitResponse,
    status_code=202,
    summary="Submit automated fix request",
    description="Submit a repository and issue description for automated code fixing"
)
async def submit_autofix(
    request: AutoFixSubmitRequest,
    background_tasks: BackgroundTasks,
    service: AutoCodeRoverService = Depends(get_autocoderover_service)
) -> AutoFixSubmitResponse:
    """
    Submit an automated code fix request.
    
    The request is processed asynchronously. Use the returned task_id
    to check status with the /status/{task_id} endpoint.
    
    Args:
        request: AutoFix request with repo URL and issue description
        background_tasks: FastAPI background tasks
        service: AutoCodeRover service instance
        
    Returns:
        AutoFixSubmitResponse with task_id and initial status
        
    Raises:
        HTTPException 503: If AutoCodeRover service is unavailable
        HTTPException 500: If submission fails
    """
    
    # Health check before submitting
    is_healthy = await service.health_check()
    if not is_healthy:
        logger.error("AutoCodeRover service unhealthy on submit")
        raise HTTPException(
            status_code=503,
            detail="AutoCodeRover service is currently unavailable"
        )
    
    try:
        # Submit fix request
        result = await service.submit_fix(
            repo_url=str(request.repo_url),
            issue_description=request.issue_description,
            model=request.model,
            temperature=request.temperature
        )
        
        logger.info(f"AutoFix submitted: task_id={result['task_id']}")
        
        return AutoFixSubmitResponse(
            task_id=result['task_id'],
            status=result['status'],
            message=result['message']
        )
        
    except Exception as e:
        logger.error(f"Failed to submit autofix: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit fix request: {str(e)}"
        )


@router.get(
    "/status/{task_id}",
    response_model=AutoFixStatusResponse,
    summary="Get fix request status",
    description="Get the current status of an automated fix request"
)
async def get_autofix_status(
    task_id: str,
    service: AutoCodeRoverService = Depends(get_autocoderover_service)
) -> AutoFixStatusResponse:
    """
    Get status of an automated fix request.
    
    Args:
        task_id: Task ID from submit response
        service: AutoCodeRover service instance
        
    Returns:
        AutoFixStatusResponse with current status
        
    Raises:
        HTTPException 404: If task not found
        HTTPException 500: If status check fails
    """
    
    try:
        status = await service.get_status(task_id)
        
        return AutoFixStatusResponse(
            task_id=status['task_id'],
            status=status['status'],
            patch_path=status.get('patch_path'),
            error=status.get('error')
        )
        
    except Exception as e:
        logger.error(f"Failed to get status for task {task_id}: {e}")
        
        # Check if it's a 404 (task not found)
        if "404" in str(e):
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.post(
    "/submit-and-wait",
    response_model=AutoFixStatusResponse,
    summary="Submit and wait for completion",
    description="Submit a fix request and wait for it to complete (synchronous)"
)
async def submit_and_wait_autofix(
    request: AutoFixSubmitRequest,
    max_wait: int = 600,
    poll_interval: int = 10,
    service: AutoCodeRoverService = Depends(get_autocoderover_service)
) -> AutoFixStatusResponse:
    """
    Submit an autofix request and wait for completion.
    
    This is a synchronous endpoint that blocks until the fix is complete
    or times out. For long-running fixes, use /submit instead.
    
    Args:
        request: AutoFix request
        max_wait: Maximum wait time in seconds (default 600 = 10 min)
        poll_interval: Seconds between status checks (default 10)
        service: AutoCodeRover service instance
        
    Returns:
        Final status with patch_path if successful
        
    Raises:
        HTTPException 503: If service unavailable
        HTTPException 504: If request times out
        HTTPException 500: If fix fails
    """
    
    # Health check
    is_healthy = await service.health_check()
    if not is_healthy:
        raise HTTPException(
            status_code=503,
            detail="AutoCodeRover service is unavailable"
        )
    
    try:
        # Submit and wait
        final_status = await service.submit_and_wait(
            repo_url=str(request.repo_url),
            issue_description=request.issue_description,
            model=request.model,
            temperature=request.temperature,
            poll_interval=poll_interval,
            max_wait=max_wait
        )
        
        # Check if failed
        if final_status['status'] == 'failed':
            raise HTTPException(
                status_code=500,
                detail=f"AutoFix failed: {final_status.get('error', 'Unknown error')}"
            )
        
        return AutoFixStatusResponse(
            task_id=final_status['task_id'],
            status=final_status['status'],
            patch_path=final_status.get('patch_path'),
            error=final_status.get('error')
        )
        
    except TimeoutError as e:
        logger.error(f"AutoFix request timed out: {e}")
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out after {max_wait} seconds"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AutoFix request failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AutoFix request failed: {str(e)}"
        )
