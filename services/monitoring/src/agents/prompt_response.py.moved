"""Prompt-Response Agent with monitoring integration."""

import os
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

from openai import AsyncOpenAI
from pydantic import BaseModel

from ..middleware.monitoring import LLMMonitoringMiddleware
from ..middleware.system_monitoring import SystemPerformanceMiddleware


class PromptRequest(BaseModel):
    """Request model for prompt-response."""
    prompt: str
    user_id: str
    department: Optional[str] = None
    session_id: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    max_tokens: Optional[int] = 1000
    temperature: float = 0.7


class PromptResponse(BaseModel):
    """Response model for prompt-response."""
    response: str
    request_id: str
    user_id: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    latency_ms: int
    status: str
    timestamp: datetime
    system_metrics: Optional[Dict[str, Any]] = None


class PromptResponseAgent:
    """
    Prompt-Response Agent that handles LLM interactions with monitoring.
    
    This agent simulates the behavior of a prompt-response service
    with integrated monitoring and metrics collection.
    """
    
    def __init__(
        self,
        openai_api_key: str = None,
        monitoring_middleware: LLMMonitoringMiddleware = None,
        system_middleware: SystemPerformanceMiddleware = None,
        default_model: str = "gpt-3.5-turbo"
    ):
        self.openai_client = AsyncOpenAI(
            api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
        )
        self.monitoring = monitoring_middleware
        self.system_middleware = system_middleware
        self.default_model = default_model
        
    async def process_prompt(self, request: PromptRequest) -> PromptResponse:
        """
        Process a prompt request with full monitoring.
        
        Args:
            request: The prompt request
            
        Returns:
            Response with metrics and monitoring data
        """
        # Start monitoring
        request_context = await self.monitoring.track_request(
            user_id=request.user_id,
            agent_type="prompt_response",
            prompt=request.prompt,
            department=request.department,
            session_id=request.session_id,
            model=request.model,
        )
        
        # Trigger organization-based system metrics collection
        system_metrics = None
        if self.system_middleware:
            try:
                # Use organization-based tracking instead of user-based
                # The middleware handles database storage automatically
                system_metrics = await self.system_middleware.track_organization_system_performance(
                    force_collection=False  # Use normal interval logic
                )
                    
            except Exception as e:
                print(f"System metrics collection failed: {e}")
                system_metrics = None
        
        response = None
        error = None
        
        try:
            # Make OpenAI API call
            openai_response = await self.openai_client.chat.completions.create(
                model=request.model,
                messages=[
                    {
                        "role": "user", 
                        "content": request.prompt
                    }
                ],
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            response = openai_response
            
        except Exception as e:
            error = e
            print(f"OpenAI API error: {e}")
        
        # Track response and get metrics
        metrics = await self.monitoring.track_response(
            request_context=request_context,
            response=response,
            model=request.model,
            error=error
        )
        
        # Build response object
        if response and not error:
            response_text = response.choices[0].message.content
            status = "success"
        else:
            response_text = f"Error: {str(error)}" if error else "No response"
            status = "error"
        
        return PromptResponse(
            response=response_text,
            request_id=metrics["request_id"],
            user_id=request.user_id,
            model=request.model,
            input_tokens=metrics["input_tokens"],
            output_tokens=metrics["output_tokens"],
            total_tokens=metrics["total_tokens"],
            cost=metrics["cost"],
            latency_ms=metrics["latency_ms"],
            status=status,
            timestamp=metrics["response_timestamp"],
            system_metrics=system_metrics
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the agent.
        
        Returns:
            Health status information
        """
        try:
            # Simple test call to OpenAI
            test_response = await self.openai_client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            return {
                "status": "healthy",
                "openai_connection": "ok",
                "default_model": self.default_model,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "openai_connection": "failed",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_metrics_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get a summary of metrics for a user.
        
        Args:
            user_id: The user ID to get metrics for
            
        Returns:
            Dictionary containing user metrics summary
        """
        if not self.monitoring:
            return {"error": "Monitoring not configured"}
        
        return await self.monitoring.get_user_metrics(user_id)


class PromptResponseService:
    """
    Service wrapper for the Prompt-Response Agent.
    
    Provides higher-level functionality and batch processing capabilities.
    """
    
    def __init__(self, agent: PromptResponseAgent):
        self.agent = agent
        
    async def process_batch(
        self, 
        requests: list[PromptRequest],
        max_concurrent: int = 5
    ) -> list[PromptResponse]:
        """
        Process multiple prompts concurrently.
        
        Args:
            requests: List of prompt requests
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of responses
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(request):
            async with semaphore:
                return await self.agent.process_prompt(request)
        
        tasks = [process_with_semaphore(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def simulate_user_session(
        self,
        user_id: str,
        department: str = None,
        num_requests: int = 10,
        delay_seconds: float = 1.0
    ) -> list[PromptResponse]:
        """
        Simulate a user session with multiple prompts.
        Useful for testing and demonstration.
        
        Args:
            user_id: The user ID
            department: User's department
            num_requests: Number of requests to simulate
            delay_seconds: Delay between requests
            
        Returns:
            List of responses
        """
        sample_prompts = [
            "Explain machine learning in simple terms",
            "What are the benefits of cloud computing?",
            "How does natural language processing work?",
            "Describe the software development lifecycle",
            "What is the difference between AI and ML?",
            "Explain REST API principles",
            "What are microservices?",
            "How does blockchain technology work?",
            "Describe agile methodology",
            "What is DevOps and why is it important?"
        ]
        
        responses = []
        session_id = f"session_{user_id}_{datetime.utcnow().timestamp()}"
        
        for i in range(num_requests):
            prompt = sample_prompts[i % len(sample_prompts)]
            
            request = PromptRequest(
                prompt=f"{prompt} (Request {i+1})",
                user_id=user_id,
                department=department,
                session_id=session_id
            )
            
            response = await self.agent.process_prompt(request)
            responses.append(response)
            
            # Wait between requests
            if i < num_requests - 1:
                await asyncio.sleep(delay_seconds)
        
        return responses