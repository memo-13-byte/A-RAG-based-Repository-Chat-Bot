"""
Webhook Endpoint for Real-time Commit Indexing
FastAPI endpoint to receive GitHub/GitLab webhooks

Add to app/api/webhook.py
"""

from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional
import logging
import hmac
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None)
):
    """
    GitHub webhook endpoint for real-time commit indexing
    
    Listens for 'push' events and indexes commits automatically
    
    Setup:
    1. Go to GitHub repo settings → Webhooks
    2. Add webhook: https://your-domain.com/api/webhook/github
    3. Content type: application/json
    4. Select 'push' events
    5. Add secret (optional, recommended)
    
    Example payload structure:
    {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "owner/repo",
            "clone_url": "https://github.com/owner/repo.git"
        },
        "commits": [
            {
                "id": "abc123",
                "message": "feat: add new feature",
                "author": {"name": "John", "email": "john@example.com"},
                "added": ["file1.py"],
                "modified": ["file2.py"],
                "removed": []
            }
        ]
    }
    """
    try:
        # Get payload
        payload = await request.json()
        
        logger.info(f"Received GitHub webhook: {x_github_event}")
        
        # Verify signature (optional but recommended)
        # if x_hub_signature_256:
        #     if not verify_github_signature(await request.body(), x_hub_signature_256):
        #         raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Only process push events
        if x_github_event != "push":
            logger.info(f"Ignoring non-push event: {x_github_event}")
            return {"status": "ignored", "event": x_github_event}
        
        # Process push event
        from ..services import commit_indexing_service
        
        result = commit_indexing_service.process_webhook_push(
            webhook_payload=payload,
            platform='github'
        )
        
        if result['status'] == 'success':
            logger.info(f"Webhook processed: {result['statistics']}")
            return {
                "status": "success",
                "message": "Commits indexed successfully",
                "statistics": result['statistics']
            }
        else:
            logger.warning(f"Webhook processing failed: {result.get('error')}")
            return {
                "status": "error",
                "message": result.get('error', 'Unknown error')
            }
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_event: Optional[str] = Header(None),
    x_gitlab_token: Optional[str] = Header(None)
):
    """
    GitLab webhook endpoint for real-time commit indexing
    
    Listens for 'Push Hook' events and indexes commits automatically
    
    Setup:
    1. Go to GitLab project settings → Webhooks
    2. Add webhook: https://your-domain.com/api/webhook/gitlab
    3. Select 'Push events'
    4. Add Secret Token (optional, recommended)
    
    Example payload structure:
    {
        "object_kind": "push",
        "project": {
            "path_with_namespace": "owner/repo",
            "git_http_url": "https://gitlab.com/owner/repo.git"
        },
        "commits": [
            {
                "id": "abc123",
                "message": "feat: add new feature",
                "author": {"name": "John", "email": "john@example.com"},
                "added": ["file1.py"],
                "modified": ["file2.py"],
                "removed": []
            }
        ]
    }
    """
    try:
        # Get payload
        payload = await request.json()
        
        logger.info(f"Received GitLab webhook: {x_gitlab_event}")
        
        # Verify token (optional but recommended)
        # if x_gitlab_token:
        #     if not verify_gitlab_token(x_gitlab_token):
        #         raise HTTPException(status_code=401, detail="Invalid token")
        
        # Only process push events
        object_kind = payload.get('object_kind')
        if object_kind != "push":
            logger.info(f"Ignoring non-push event: {object_kind}")
            return {"status": "ignored", "event": object_kind}
        
        # Process push event
        from ..services import commit_indexing_service
        
        result = commit_indexing_service.process_webhook_push(
            webhook_payload=payload,
            platform='gitlab'
        )
        
        if result['status'] == 'success':
            logger.info(f"Webhook processed: {result['statistics']}")
            return {
                "status": "success",
                "message": "Commits indexed successfully",
                "statistics": result['statistics']
            }
        else:
            logger.warning(f"Webhook processing failed: {result.get('error')}")
            return {
                "status": "error",
                "message": result.get('error', 'Unknown error')
            }
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def webhook_status():
    """
    Check webhook endpoint status
    
    Returns:
        Current webhook configuration and status
    """
    return {
        "status": "active",
        "endpoints": {
            "github": "/api/webhook/github",
            "gitlab": "/api/webhook/gitlab"
        },
        "supported_events": {
            "github": ["push"],
            "gitlab": ["push"]
        }
    }


# ============================================================================
# Signature Verification (Optional)
# ============================================================================

def verify_github_signature(payload_body: bytes, signature_header: str) -> bool:
    """
    Verify GitHub webhook signature
    
    Args:
        payload_body: Raw request body
        signature_header: X-Hub-Signature-256 header value
        
    Returns:
        True if signature is valid
        
    Setup:
        Set GITHUB_WEBHOOK_SECRET in .env
    """
    import os
    
    secret = os.getenv('GITHUB_WEBHOOK_SECRET')
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not set, skipping verification")
        return True
    
    # Compute signature
    hash_object = hmac.new(
        secret.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    # Compare
    return hmac.compare_digest(expected_signature, signature_header)


def verify_gitlab_token(token: str) -> bool:
    """
    Verify GitLab webhook token
    
    Args:
        token: X-Gitlab-Token header value
        
    Returns:
        True if token is valid
        
    Setup:
        Set GITLAB_WEBHOOK_TOKEN in .env
    """
    import os
    
    expected_token = os.getenv('GITLAB_WEBHOOK_TOKEN')
    if not expected_token:
        logger.warning("GITLAB_WEBHOOK_TOKEN not set, skipping verification")
        return True
    
    return token == expected_token
