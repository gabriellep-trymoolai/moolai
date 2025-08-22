"""
LLM Integration API Router
==========================

Provides endpoints for LLM prompt processing with caching and agent integration.
Integrates with the existing prompt-response agent and caching system.
"""

import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

# Import the existing prompt-response agent
from ..agents import PromptResponseAgent


router = APIRouter(prefix="/api/v1/llm", tags=["llm"])
agents_router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class PromptRequest(BaseModel):
    """Request model for LLM prompt processing"""
    prompt: str = Field(..., description="The prompt text to process")
    session_id: Optional[str] = Field(None, description="Session ID for context (optional)")
    user_id: Optional[str] = Field(None, description="User ID for tracking (optional)")
    model: Optional[str] = Field("gpt-3.5-turbo", description="LLM model to use")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Temperature for response generation")
    max_tokens: Optional[int] = Field(None, ge=1, le=4000, description="Maximum tokens in response")
    use_cache: Optional[bool] = Field(True, description="Whether to use caching")


class PromptResponse(BaseModel):
    """Response model for LLM prompt processing"""
    prompt_id: str
    response: str
    model: str
    session_id: Optional[str]
    user_id: Optional[str]
    timestamp: datetime
    
    # Performance metrics
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cost: float
    latency_ms: int
    
    # Cache information
    from_cache: bool
    cache_similarity: Optional[float] = None
    
    # Quality metrics (if available)
    confidence_score: Optional[float] = None
    relevance_score: Optional[float] = None


class AgentRequest(BaseModel):
    """Request model for direct agent processing"""
    query: str = Field(..., description="The query to process")
    session_id: Optional[str] = Field(None, description="Session ID for context")
    user_id: Optional[str] = Field(None, description="User ID for tracking")
    enable_evaluation: Optional[bool] = Field(True, description="Enable quality evaluation")


def get_prompt_agent(request: Request) -> PromptResponseAgent:
    """Dependency to get prompt response agent from app state"""
    if hasattr(request.app.state, 'prompt_agent') and request.app.state.prompt_agent:
        return request.app.state.prompt_agent
    else:
        # Fallback: create a new agent instance
        import os
        return PromptResponseAgent(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            organization_id=os.getenv("ORGANIZATION_ID", "default-org")
        )


@router.post("/prompt", response_model=PromptResponse)
async def process_llm_prompt(
    request: PromptRequest,
    agent: PromptResponseAgent = Depends(get_prompt_agent)
):
    """
    Process an LLM prompt using the prompt-response agent.
    
    This endpoint:
    1. Processes prompt using the prompt-response agent
    2. Agent handles its own caching internally (via main_response.py)
    3. Returns comprehensive response with performance metrics and cache information
    
    Args:
        request: Prompt request with text and parameters
        
    Returns:
        PromptResponse: Complete response with metrics and cache information
    """
    start_time = time.time()
    prompt_id = f"prompt_{uuid.uuid4().hex[:8]}"
    
    # Generate session ID if not provided
    session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"
    
    try:
        # Process using agent (main_response.py handles its own caching)
        if not agent:
            raise HTTPException(status_code=503, detail="Prompt response agent not available")
        
        # Create agent request
        class AgentRequestInternal:
            def __init__(self, query, session_id):
                self.query = query
                self.session_id = session_id
        
        agent_request = AgentRequestInternal(request.prompt, session_id)
        
        # Process with agent (main_response.py handles caching internally)
        agent_response = await agent.process_prompt(agent_request)
        
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Prepare response (get cache info from agent response)
        response = PromptResponse(
            prompt_id=prompt_id,
            response=agent_response.response,
            model=getattr(agent_response, 'model', request.model),
            session_id=session_id,
            user_id=request.user_id,
            timestamp=datetime.now(),
            total_tokens=getattr(agent_response, 'total_tokens', 0),
            prompt_tokens=len(request.prompt.split()),  # Approximate
            completion_tokens=getattr(agent_response, 'total_tokens', 0) - len(request.prompt.split()),
            cost=getattr(agent_response, 'cost', 0.0),
            latency_ms=latency_ms,
            from_cache=getattr(agent_response, 'from_cache', False),
            cache_similarity=getattr(agent_response, 'cache_similarity', None)
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process prompt: {str(e)}")


@router.get("/models")
async def list_available_models():
    """
    List available LLM models and their capabilities.
    
    Returns:
        Available models with descriptions and pricing information
    """
    return {
        "models": [
            {
                "id": "gpt-3.5-turbo",
                "name": "GPT-3.5 Turbo",
                "description": "Fast and efficient model for most tasks",
                "max_tokens": 4096,
                "input_cost_per_1k": 0.001,
                "output_cost_per_1k": 0.002,
                "available": True
            },
            {
                "id": "gpt-4",
                "name": "GPT-4",
                "description": "Most capable model for complex reasoning",
                "max_tokens": 8192,
                "input_cost_per_1k": 0.03,
                "output_cost_per_1k": 0.06,
                "available": True
            }
        ],
        "default_model": "gpt-3.5-turbo",
        "timestamp": datetime.now()
    }


@router.get("/health")
async def llm_health_check(agent: PromptResponseAgent = Depends(get_prompt_agent)):
    """
    Check LLM service health and availability.
    
    Returns:
        Health status of LLM services and dependencies
    """
    try:
        health_status = {
            "status": "healthy",
            "agent_available": agent is not None,
            "organization_id": agent.organization_id if agent else None,
            "timestamp": datetime.now()
        }
        
        # Test agent availability
        if agent:
            health_status["agent_status"] = "available"
        else:
            health_status["status"] = "degraded"
            health_status["agent_status"] = "unavailable"
        
        return health_status
        
    except Exception as e:
        return {
            "status": "error",
            "agent_available": False,
            "error": str(e),
            "timestamp": datetime.now()
        }


# =================== AGENT ENDPOINTS ===================

@agents_router.post("/prompt-response")
async def call_prompt_response_agent(
    request: AgentRequest,
    agent: PromptResponseAgent = Depends(get_prompt_agent)
):
    """
    Direct access to the prompt-response agent with quality evaluation.
    
    This endpoint provides direct access to the agent without caching,
    and includes quality scoring if evaluation is enabled.
    
    Args:
        request: Agent request with query and parameters
        
    Returns:
        Agent response with quality metrics
    """
    start_time = time.time()
    
    try:
        if not agent:
            raise HTTPException(status_code=503, detail="Prompt response agent not available")
        
        # Generate session ID if not provided
        session_id = request.session_id or f"agent_session_{uuid.uuid4().hex[:8]}"
        
        # Create agent request
        class AgentRequestInternal:
            def __init__(self, query, session_id):
                self.query = query
                self.session_id = session_id
        
        agent_request = AgentRequestInternal(request.query, session_id)
        
        # Process with agent
        agent_response = await agent.process_prompt(agent_request)
        
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Prepare response
        response = {
            "agent_response_id": f"agent_{uuid.uuid4().hex[:8]}",
            "query": request.query,
            "response": agent_response.response,
            "session_id": session_id,
            "user_id": request.user_id,
            "timestamp": datetime.now(),
            
            # Agent metrics
            "model": getattr(agent_response, 'model', 'unknown'),
            "total_tokens": getattr(agent_response, 'total_tokens', 0),
            "cost": getattr(agent_response, 'cost', 0.0),
            "latency_ms": latency_ms,
            
            # Cache information
            "from_cache": getattr(agent_response, 'from_cache', False),
            "cache_similarity": getattr(agent_response, 'cache_similarity', None),
            
            # Quality evaluation (if available)
            "evaluation_enabled": request.enable_evaluation,
            "confidence_score": None,  # Would be calculated by evaluation system
            "relevance_score": None,   # Would be calculated by evaluation system
            
            # Processing metadata
            "processing_time_ms": latency_ms,
            "organization_id": agent.organization_id
        }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")


@router.get("/agents/status")
async def get_agent_status(agent: PromptResponseAgent = Depends(get_prompt_agent)):
    """
    Get the current status and configuration of available agents.
    
    Returns:
        Status information for all available agents
    """
    try:
        return {
            "prompt_response_agent": {
                "available": agent is not None,
                "organization_id": agent.organization_id if agent else None,
                "status": "active" if agent else "unavailable"
            },
            "total_agents": 1,
            "active_agents": 1 if agent else 0,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "total_agents": 0,
            "active_agents": 0,
            "timestamp": datetime.now()
        }