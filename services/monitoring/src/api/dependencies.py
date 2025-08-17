"""FastAPI dependencies."""

import os
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from ..models import get_db
from ..middleware import LLMMonitoringMiddleware, SystemPerformanceMiddleware
from ..agents import PromptResponseAgent


# Global app state - will be set by main.py
app_state = None


def set_app_state(state):
    """Set the global app state reference."""
    global app_state
    app_state = state


async def get_monitoring_middleware(
    db: AsyncSession = Depends(get_db)
) -> LLMMonitoringMiddleware:
    """Get monitoring middleware instance."""
    redis_client = getattr(app_state, 'redis', None) if app_state else None
    organization_id = os.getenv("DEFAULT_ORG_ID")
    
    return LLMMonitoringMiddleware(
        redis_client=redis_client,
        db_session=db,
        organization_id=organization_id
    )


async def get_system_monitoring_middleware(
    db: AsyncSession = Depends(get_db)
) -> SystemPerformanceMiddleware:
    """Get system performance monitoring middleware instance."""
    if app_state and hasattr(app_state, 'system_middleware') and app_state.system_middleware:
        # Update database session for the middleware
        app_state.system_middleware.db_session = db
        return app_state.system_middleware
    
    # Fallback: create new instance
    redis_client = getattr(app_state, 'redis', None) if app_state else None
    organization_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default-org")
    
    return SystemPerformanceMiddleware(
        redis_client=redis_client,
        db_session=db,
        organization_id=organization_id,
        collection_interval=int(os.getenv("SYSTEM_METRICS_INTERVAL", "60")),
        enable_realtime_redis=True
    )


async def get_agent(
    monitoring: LLMMonitoringMiddleware = Depends(get_monitoring_middleware),
    system_monitoring: SystemPerformanceMiddleware = Depends(get_system_monitoring_middleware)
) -> PromptResponseAgent:
    """Get prompt-response agent instance."""
    if not app_state or not hasattr(app_state, 'agent') or app_state.agent is None:
        raise HTTPException(status_code=503, detail="Agent not available")
    
    # Set monitoring middleware
    app_state.agent.monitoring = monitoring
    app_state.agent.system_middleware = system_monitoring
    return app_state.agent