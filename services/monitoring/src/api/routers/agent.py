"""Agent API endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import get_db
from ...agents import PromptResponseAgent, PromptResponseService, PromptRequest, PromptResponse
from ...middleware import LLMMonitoringMiddleware
from ..dependencies import get_agent, get_monitoring_middleware

router = APIRouter()


@router.post("/agent/prompt", response_model=PromptResponse)
async def process_prompt(
    request: PromptRequest,
    agent: PromptResponseAgent = Depends(get_agent)
):
    """Process a single prompt through the prompt-response agent."""
    try:
        response = await agent.process_prompt(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/batch", response_model=List[PromptResponse])
async def process_batch_prompts(
    requests: List[PromptRequest],
    max_concurrent: int = 5,
    agent: PromptResponseAgent = Depends(get_agent)
):
    """Process multiple prompts concurrently."""
    try:
        service = PromptResponseService(agent)
        responses = await service.process_batch(requests, max_concurrent)
        
        # Filter out exceptions
        valid_responses = [r for r in responses if isinstance(r, PromptResponse)]
        return valid_responses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/simulate-session")
async def simulate_user_session(
    user_id: str,
    department: str = None,
    num_requests: int = 10,
    delay_seconds: float = 1.0,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    agent: PromptResponseAgent = Depends(get_agent)
):
    """Simulate a user session for testing and demonstration."""
    try:
        service = PromptResponseService(agent)
        
        # Run simulation in background
        background_tasks.add_task(
            service.simulate_user_session,
            user_id=user_id,
            department=department,
            num_requests=num_requests,
            delay_seconds=delay_seconds
        )
        
        return {
            "message": f"Started simulation for user {user_id}",
            "num_requests": num_requests,
            "estimated_duration": num_requests * delay_seconds
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/health")
async def agent_health_check(
    agent: PromptResponseAgent = Depends(get_agent)
):
    """Get agent health status."""
    try:
        health = await agent.health_check()
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/metrics/{user_id}")
async def get_agent_metrics(
    user_id: str,
    agent: PromptResponseAgent = Depends(get_agent)
):
    """Get metrics summary for a specific user."""
    try:
        metrics = await agent.get_metrics_summary(user_id)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))