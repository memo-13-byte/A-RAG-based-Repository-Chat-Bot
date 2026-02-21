"""
AutoCodeRover Service Client
Handles communication with AutoCodeRover Docker container
"""
import httpx
import asyncio
from typing import Dict, Optional, Callable, Any
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AutoCodeRoverService:
    """
    Client for AutoCodeRover automated code fixing service.
    
    Communicates with AutoCodeRover Docker container to submit
    code fix requests and monitor their status.
    """
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8001",
        timeout: float = 700.0
    ):
        """
        Initialize AutoCodeRover service client.
        
        Args:
            base_url: AutoCodeRover API base URL
            timeout: Request timeout in seconds (default 11.67 minutes)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = httpx.Timeout(timeout)
        logger.info(f"AutoCodeRover service initialized: {self.base_url}")
    
    async def health_check(self) -> bool:
        """
        Check if AutoCodeRover service is healthy.
        
        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    is_healthy = data.get("status") == "healthy"
                    logger.info(f"Health check: {'healthy' if is_healthy else 'unhealthy'}")
                    return is_healthy
                logger.warning(f"Health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False
    
    async def submit_fix(
        self,
        repo_url: str,
        issue_description: str,
        model: str = "gpt-4o-mini-2024-07-18",
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Submit a code fix request to AutoCodeRover.
        
        Args:
            repo_url: GitHub repository URL
            issue_description: Description of the issue to fix
            model: LLM model to use
            temperature: Model temperature (0.0-1.0)
            
        Returns:
            Dict containing task_id, status, and message
            
        Raises:
            httpx.HTTPError: If request fails
        """
        payload = {
            "repo_url": repo_url,
            "issue_description": issue_description,
            "model": model,
            "temperature": temperature
        }
        
        logger.info(f"Submitting fix request for repo: {repo_url}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/fix",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fix request submitted: task_id={data.get('task_id')}")
            return data
    
    async def get_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a fix request.
        
        Args:
            task_id: Task ID from submit_fix
            
        Returns:
            Dict containing task_id, status, patch_path, and error
            
        Raises:
            httpx.HTTPError: If request fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/status/{task_id}"
            )
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Status check: task_id={task_id}, status={data.get('status')}")
            return data
    
    async def wait_for_completion(
        self,
        task_id: str,
        poll_interval: int = 10,
        max_wait: int = 600,
        on_update: Optional[Callable[[Dict], None]] = None
    ) -> Dict[str, Any]:
        """
        Wait for a task to complete with polling.
        
        Args:
            task_id: Task ID to monitor
            poll_interval: Seconds between status checks
            max_wait: Maximum wait time in seconds
            on_update: Optional callback for status updates
            
        Returns:
            Final status dict
            
        Raises:
            TimeoutError: If max_wait exceeded
        """
        start_time = datetime.now()
        
        while True:
            status = await self.get_status(task_id)
            
            if on_update:
                on_update(status)
            
            # Check if completed or failed
            if status['status'] in ['completed', 'failed']:
                logger.info(f"Task {task_id} finished: {status['status']}")
                return status
            
            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_wait:
                logger.error(f"Task {task_id} timed out after {elapsed}s")
                raise TimeoutError(f"Task {task_id} exceeded max wait time of {max_wait}s")
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
    
    async def submit_and_wait(
        self,
        repo_url: str,
        issue_description: str,
        model: str = "gpt-4o-mini-2024-07-18",
        temperature: float = 0.2,
        poll_interval: int = 10,
        max_wait: int = 600,
        on_update: Optional[Callable[[Dict], None]] = None
    ) -> Dict[str, Any]:
        """
        Submit a fix request and wait for completion.
        
        Convenience method that combines submit_fix and wait_for_completion.
        
        Args:
            repo_url: GitHub repository URL
            issue_description: Description of the issue to fix
            model: LLM model to use
            temperature: Model temperature
            poll_interval: Seconds between status checks
            max_wait: Maximum wait time in seconds
            on_update: Optional callback for status updates
            
        Returns:
            Final status dict with patch_path if successful
            
        Raises:
            TimeoutError: If max_wait exceeded
            httpx.HTTPError: If request fails
        """
        # Submit request
        submit_result = await self.submit_fix(
            repo_url=repo_url,
            issue_description=issue_description,
            model=model,
            temperature=temperature
        )
        
        task_id = submit_result['task_id']
        logger.info(f"Waiting for task {task_id} to complete...")
        
        # Wait for completion
        final_status = await self.wait_for_completion(
            task_id=task_id,
            poll_interval=poll_interval,
            max_wait=max_wait,
            on_update=on_update
        )
        
        return final_status


# Singleton instance
_autocoderover_service: Optional[AutoCodeRoverService] = None


def get_autocoderover_service() -> AutoCodeRoverService:
    """
    Get singleton AutoCodeRover service instance.
    
    Returns:
        AutoCodeRoverService instance
    """
    global _autocoderover_service
    if _autocoderover_service is None:
        _autocoderover_service = AutoCodeRoverService()
    return _autocoderover_service
