"""Monitoring middleware for LLM calls."""

import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import json
import asyncio
from decimal import Decimal

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from ..models.user_metrics import UserLLMRealtime, UserSession
from ..utils.cost_calculator import calculate_cost


def safe_uuid(value: Any) -> uuid.UUID:
    """Safely convert a value to UUID, generating a new one if invalid."""
    if value is None:
        return uuid.uuid4()
    
    if isinstance(value, uuid.UUID):
        return value
    
    if isinstance(value, str):
        # Handle placeholder strings from Swagger UI
        if value in ["string", "uuid", ""]:
            return uuid.uuid4()
        
        try:
            return uuid.UUID(value)
        except ValueError:
            # If invalid UUID string, generate a new one
            return uuid.uuid4()
    
    # For any other type, generate new UUID
    return uuid.uuid4()


class LLMMonitoringMiddleware:
    """Middleware to monitor and track LLM API calls."""
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        db_session: Optional[AsyncSession] = None,
        organization_id: str = None
    ):
        self.redis_client = redis_client
        self.db_session = db_session
        self.organization_id = organization_id or str(uuid.uuid4())
        self.metrics_buffer = []
        self.buffer_size = 100  # Batch size for DB writes
        
    async def track_request(
        self,
        user_id: str,
        agent_type: str = "prompt_response",
        prompt: str = "",
        department: str = None,
        session_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Track the start of an LLM request.
        
        Returns:
            Dict containing request tracking information
        """
        request_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())  # For future Langfuse integration
        
        request_context = {
            "request_id": request_id,
            "trace_id": trace_id,
            "user_id": user_id,
            "organization_id": self.organization_id,
            "agent_type": agent_type,
            "prompt": prompt,
            "department": department,
            "session_id": session_id or str(uuid.uuid4()),
            "request_timestamp": datetime.utcnow(),
            "start_time": time.time(),
            **kwargs
        }
        
        # Store in Redis for real-time tracking
        if self.redis_client:
            await self._store_realtime_start(request_context)
        
        return request_context
    
    async def track_response(
        self,
        request_context: Dict[str, Any],
        response: Any,
        model: str = "gpt-3.5-turbo",
        error: Optional[Exception] = None
    ) -> Dict[str, Any]:
        """
        Track the completion of an LLM request.
        
        Returns:
            Dict containing complete metrics for the request
        """
        end_time = time.time()
        latency_ms = int((end_time - request_context["start_time"]) * 1000)
        
        # Extract token usage and calculate cost
        if hasattr(response, 'usage'):
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
        else:
            # Estimate tokens if not provided
            input_tokens = len(request_context["prompt"].split()) * 1.3
            output_tokens = len(str(response).split()) * 1.3 if response else 0
            total_tokens = input_tokens + output_tokens
        
        cost = calculate_cost(model, input_tokens, output_tokens)
        
        # Build metrics object
        metrics = {
            **request_context,
            "response_timestamp": datetime.utcnow(),
            "model_name": model,
            "model_provider": self._get_provider(model),
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "total_tokens": int(total_tokens),
            "cost": cost,
            "latency_ms": latency_ms,
            "status": "error" if error else "success",
            "error_type": type(error).__name__ if error else None,
            "error_message": str(error) if error else None,
            "response_text": str(response)[:500] if response else None,
            "prompt_text": request_context["prompt"][:500],
        }
        
        # Store metrics
        await self._store_metrics(metrics)
        
        # Update real-time metrics in Redis
        if self.redis_client:
            await self._update_realtime_metrics(metrics)
        
        return metrics
    
    async def _store_metrics(self, metrics: Dict[str, Any]):
        """Store metrics in database."""
        if not self.db_session:
            return
        
        try:
            # Create realtime record
            realtime_record = UserLLMRealtime(
                request_id=safe_uuid(metrics["request_id"]),
                user_id=safe_uuid(metrics["user_id"]),
                organization_id=safe_uuid(metrics["organization_id"]),
                agent_type=metrics["agent_type"],
                model_name=metrics["model_name"],
                model_provider=metrics["model_provider"],
                prompt_text=metrics.get("prompt_text"),
                response_text=metrics.get("response_text"),
                input_tokens=metrics["input_tokens"],
                output_tokens=metrics["output_tokens"],
                cost=Decimal(str(metrics["cost"])),
                latency_ms=metrics["latency_ms"],
                status=metrics["status"],
                error_type=metrics.get("error_type"),
                error_message=metrics.get("error_message"),
                department=metrics.get("department"),
                session_id=safe_uuid(metrics.get("session_id")) if metrics.get("session_id") else None,
                trace_id=safe_uuid(metrics["trace_id"]),
                request_timestamp=metrics["request_timestamp"],
                response_timestamp=metrics["response_timestamp"],
            )
            
            self.db_session.add(realtime_record)
            
            # Update session if exists
            if metrics.get("session_id"):
                await self._update_session(metrics)
            
            await self.db_session.commit()
            
        except Exception as e:
            print(f"Error storing metrics: {e}")
            await self.db_session.rollback()
    
    async def _update_session(self, metrics: Dict[str, Any]):
        """Update user session with new metrics."""
        # This would update the session table with aggregated metrics
        # Implementation depends on your session management strategy
        pass
    
    async def _store_realtime_start(self, request_context: Dict[str, Any]):
        """Store request start in Redis for real-time tracking."""
        key = f"user:metrics:{request_context['user_id']}:active"
        value = json.dumps({
            "request_id": request_context["request_id"],
            "agent_type": request_context["agent_type"],
            "start_time": request_context["start_time"],
            "status": "in_progress"
        })
        
        await self.redis_client.zadd(
            key,
            {value: request_context["start_time"]}
        )
        
        # Set expiry for 1 hour
        await self.redis_client.expire(key, 3600)
    
    async def _update_realtime_metrics(self, metrics: Dict[str, Any]):
        """Update real-time metrics in Redis."""
        # User-level real-time metrics
        user_key = f"user:metrics:{metrics['user_id']}:realtime"
        
        # Increment counters
        pipe = self.redis_client.pipeline()
        pipe.hincrby(user_key, "total_queries", 1)
        pipe.hincrbyfloat(user_key, "total_cost", metrics["cost"])
        pipe.hincrby(user_key, "total_tokens", metrics["total_tokens"])
        
        if metrics["status"] == "success":
            pipe.hincrby(user_key, "successful_queries", 1)
        else:
            pipe.hincrby(user_key, "failed_queries", 1)
        
        # Update agent breakdown
        agent_key = f"{user_key}:agents:{metrics['agent_type']}"
        pipe.hincrby(agent_key, "count", 1)
        pipe.hincrbyfloat(agent_key, "cost", metrics["cost"])
        pipe.hincrby(agent_key, "tokens", metrics["total_tokens"])
        
        # Update model breakdown
        model_key = f"{user_key}:models:{metrics['model_name']}"
        pipe.hincrby(model_key, "count", 1)
        pipe.hincrbyfloat(model_key, "cost", metrics["cost"])
        pipe.hincrby(model_key, "tokens", metrics["total_tokens"])
        
        # Organization-level metrics
        org_key = f"org:metrics:{metrics['organization_id']}:realtime"
        pipe.hincrby(org_key, "total_queries", 1)
        pipe.hincrbyfloat(org_key, "total_cost", metrics["cost"])
        
        # Execute pipeline
        await pipe.execute()
        
        # Publish for real-time subscribers
        await self.redis_client.publish(
            f"org:{metrics['organization_id']}:metrics",
            json.dumps({
                "type": "metric_update",
                "user_id": metrics["user_id"],
                "cost": metrics["cost"],
                "tokens": metrics["total_tokens"],
                "latency_ms": metrics["latency_ms"],
                "status": metrics["status"],
                "timestamp": datetime.utcnow().isoformat()
            })
        )
    
    def _get_provider(self, model: str) -> str:
        """Get provider name from model name."""
        if "gpt" in model.lower():
            return "openai"
        elif "claude" in model.lower():
            return "anthropic"
        elif "llama" in model.lower():
            return "meta"
        else:
            return "unknown"
    
    async def get_user_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get real-time metrics for a user from Redis."""
        if not self.redis_client:
            return {}
        
        user_key = f"user:metrics:{user_id}:realtime"
        metrics = await self.redis_client.hgetall(user_key)
        
        # Decode and convert metrics
        return {
            k.decode() if isinstance(k, bytes) else k: 
            v.decode() if isinstance(v, bytes) else v
            for k, v in metrics.items()
        }
    
    async def get_organization_metrics(self) -> Dict[str, Any]:
        """Get real-time metrics for the organization from Redis."""
        if not self.redis_client:
            return {}
        
        org_key = f"org:metrics:{self.organization_id}:realtime"
        metrics = await self.redis_client.hgetall(org_key)
        
        # Decode and convert metrics
        return {
            k.decode() if isinstance(k, bytes) else k: 
            v.decode() if isinstance(v, bytes) else v
            for k, v in metrics.items()
        }