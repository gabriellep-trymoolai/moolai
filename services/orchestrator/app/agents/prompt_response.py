"""Prompt-Response Agent for Orchestrator Service."""

import os
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.prompt_execution import PromptExecution
from ..models.user import User


class PromptRequest(BaseModel):
    """Request model for prompt-response."""
    prompt: str
    user_id: str
    organization_id: str
    department: Optional[str] = None
    session_id: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    max_tokens: Optional[int] = 1000
    temperature: float = 0.7
    stream: bool = False


class PromptResponse(BaseModel):
    """Response model for prompt-response."""
    prompt_id: str
    response: str
    user_id: str
    organization_id: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    latency_ms: int
    status: str
    timestamp: datetime
    session_id: Optional[str] = None


class PromptResponseAgent:
    """
    Prompt-Response Agent that handles LLM interactions within the orchestrator.
    
    This agent processes prompts, tracks usage, and integrates with the 
    orchestrator's database for comprehensive logging and analytics.
    """
    
    def __init__(
        self,
        openai_api_key: str = None,
        default_model: str = "gpt-3.5-turbo",
        organization_id: str = None
    ):
        """Initialize the prompt-response agent."""
        self.openai_client = AsyncOpenAI(
            api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
        )
        self.default_model = default_model
        self.organization_id = organization_id or os.getenv("ORGANIZATION_ID", "default-org")
        
        # Cost calculation (approximate)
        self.model_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004}
        }
        
    async def process_prompt(
        self, 
        request: PromptRequest,
        db: AsyncSession = None
    ) -> PromptResponse:
        """
        Process a prompt request with full tracking and database storage.
        
        Args:
            request: The prompt request
            db: Database session (optional, will create if not provided)
            
        Returns:
            Response with metrics and tracking data
        """
        start_time = time.time()
        prompt_id = f"prompt_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        # Create database session if not provided
        if db is None:
            async with get_db() as db_session:
                return await self._process_with_db(request, prompt_id, start_time, db_session)
        else:
            return await self._process_with_db(request, prompt_id, start_time, db)
    
    async def _process_with_db(
        self, 
        request: PromptRequest, 
        prompt_id: str, 
        start_time: float, 
        db: AsyncSession
    ) -> PromptResponse:
        """Internal method to process prompt with database session."""
        
        response = None
        error = None
        input_tokens = 0
        output_tokens = 0
        
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
                temperature=request.temperature,
                stream=request.stream
            )
            
            response = openai_response
            
            # Extract token usage
            if hasattr(openai_response, 'usage') and openai_response.usage:
                input_tokens = openai_response.usage.prompt_tokens
                output_tokens = openai_response.usage.completion_tokens
            else:
                # Estimate tokens if not provided
                input_tokens = len(request.prompt.split()) * 1.3  # Rough estimation
                output_tokens = len(response.choices[0].message.content.split()) * 1.3 if response and response.choices else 0
            
        except Exception as e:
            error = e
            print(f"OpenAI API error: {e}")
        
        # Calculate metrics
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)
        total_tokens = int(input_tokens + output_tokens)
        
        # Calculate cost
        cost = self._calculate_cost(request.model, input_tokens, output_tokens)
        
        # Prepare response data
        if response and not error:
            response_text = response.choices[0].message.content
            status = "success"
        else:
            response_text = f"Error: {str(error)}" if error else "No response"
            status = "error"
        
        # Store in database
        try:
            prompt_record = PromptExecution(
                prompt_id=prompt_id,
                user_id=request.user_id,
                organization_id=request.organization_id,
                prompt_text=request.prompt,
                response_text=response_text,
                model=request.model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                total_tokens=total_tokens,
                cost=cost,
                latency_ms=latency_ms,
                status=status,
                session_id=request.session_id,
                department=request.department,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                timestamp=datetime.utcnow()
            )
            
            db.add(prompt_record)
            await db.commit()
            print(f"Prompt record saved: {prompt_id}")
            
        except Exception as db_error:
            print(f"Database storage failed: {db_error}")
            await db.rollback()
        
        return PromptResponse(
            prompt_id=prompt_id,
            response=response_text,
            user_id=request.user_id,
            organization_id=request.organization_id,
            model=request.model,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            total_tokens=total_tokens,
            cost=cost,
            latency_ms=latency_ms,
            status=status,
            timestamp=datetime.utcnow(),
            session_id=request.session_id
        )
    
    def _calculate_cost(self, model: str, input_tokens: float, output_tokens: float) -> float:
        """Calculate the cost for the API call."""
        if model not in self.model_costs:
            # Default to GPT-3.5-turbo pricing
            model = "gpt-3.5-turbo"
        
        costs = self.model_costs[model]
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        
        return round(input_cost + output_cost, 6)
    
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
                "organization_id": self.organization_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "openai_connection": "failed",
                "organization_id": self.organization_id,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_user_prompt_history(
        self, 
        user_id: str, 
        limit: int = 50,
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        Get prompt history for a user.
        
        Args:
            user_id: The user ID
            limit: Maximum number of records to return
            db: Database session
            
        Returns:
            List of prompt records
        """
        if db is None:
            async with get_db() as db_session:
                return await self._get_history_with_db(user_id, limit, db_session)
        else:
            return await self._get_history_with_db(user_id, limit, db)
    
    async def _get_history_with_db(
        self, 
        user_id: str, 
        limit: int, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Internal method to get history with database session."""
        try:
            from sqlalchemy import select, desc
            
            query = select(PromptExecution).where(
                PromptExecution.user_id == user_id,
                PromptExecution.organization_id == self.organization_id
            ).order_by(desc(PromptExecution.timestamp)).limit(limit)
            
            result = await db.execute(query)
            prompts = result.scalars().all()
            
            return [
                {
                    "prompt_id": prompt.prompt_id,
                    "prompt_text": prompt.prompt_text[:100] + "..." if len(prompt.prompt_text) > 100 else prompt.prompt_text,
                    "response_text": prompt.response_text[:100] + "..." if len(prompt.response_text) > 100 else prompt.response_text,
                    "model": prompt.model,
                    "total_tokens": prompt.total_tokens,
                    "cost": prompt.cost,
                    "latency_ms": prompt.latency_ms,
                    "status": prompt.status,
                    "timestamp": prompt.timestamp.isoformat()
                }
                for prompt in prompts
            ]
            
        except Exception as e:
            print(f"Error getting prompt history: {e}")
            return []
    
    async def get_organization_metrics(
        self, 
        days_back: int = 7,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Get organization-wide prompt metrics.
        
        Args:
            days_back: Number of days to look back
            db: Database session
            
        Returns:
            Organization metrics summary
        """
        if db is None:
            async with get_db() as db_session:
                return await self._get_org_metrics_with_db(days_back, db_session)
        else:
            return await self._get_org_metrics_with_db(days_back, db)
    
    async def _get_org_metrics_with_db(
        self, 
        days_back: int, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Internal method to get organization metrics with database session."""
        try:
            from sqlalchemy import select, func
            from datetime import timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            # Total prompts
            total_query = select(func.count(PromptExecution.prompt_id)).where(
                PromptExecution.organization_id == self.organization_id,
                PromptExecution.timestamp >= cutoff_date
            )
            total_result = await db.execute(total_query)
            total_prompts = total_result.scalar() or 0
            
            # Total cost
            cost_query = select(func.sum(PromptExecution.cost)).where(
                PromptExecution.organization_id == self.organization_id,
                PromptExecution.timestamp >= cutoff_date
            )
            cost_result = await db.execute(cost_query)
            total_cost = cost_result.scalar() or 0.0
            
            # Total tokens
            tokens_query = select(func.sum(PromptExecution.total_tokens)).where(
                PromptExecution.organization_id == self.organization_id,
                PromptExecution.timestamp >= cutoff_date
            )
            tokens_result = await db.execute(tokens_query)
            total_tokens = tokens_result.scalar() or 0
            
            # Average latency
            latency_query = select(func.avg(PromptExecution.latency_ms)).where(
                PromptExecution.organization_id == self.organization_id,
                PromptExecution.timestamp >= cutoff_date,
                PromptExecution.status == "success"
            )
            latency_result = await db.execute(latency_query)
            avg_latency = latency_result.scalar() or 0.0
            
            return {
                "organization_id": self.organization_id,
                "time_period_days": days_back,
                "total_prompts": total_prompts,
                "total_cost": round(total_cost, 4),
                "total_tokens": total_tokens,
                "average_latency_ms": round(avg_latency, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Error getting organization metrics: {e}")
            return {
                "organization_id": self.organization_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


class PromptResponseService:
    """
    Service wrapper for the Prompt-Response Agent.
    
    Provides higher-level functionality and batch processing capabilities.
    """
    
    def __init__(self, agent: PromptResponseAgent):
        self.agent = agent
        
    async def process_batch(
        self, 
        requests: List[PromptRequest],
        max_concurrent: int = 5,
        db: AsyncSession = None
    ) -> List[PromptResponse]:
        """
        Process multiple prompts concurrently.
        
        Args:
            requests: List of prompt requests
            max_concurrent: Maximum concurrent requests
            db: Database session
            
        Returns:
            List of responses
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(request):
            async with semaphore:
                return await self.agent.process_prompt(request, db)
        
        tasks = [process_with_semaphore(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def simulate_user_session(
        self,
        user_id: str,
        organization_id: str,
        department: str = None,
        num_requests: int = 10,
        delay_seconds: float = 1.0,
        db: AsyncSession = None
    ) -> List[PromptResponse]:
        """
        Simulate a user session with multiple prompts.
        Useful for testing and demonstration.
        
        Args:
            user_id: The user ID
            organization_id: The organization ID
            department: User's department
            num_requests: Number of requests to simulate
            delay_seconds: Delay between requests
            db: Database session
            
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
        session_id = f"session_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        for i in range(num_requests):
            prompt = sample_prompts[i % len(sample_prompts)]
            
            request = PromptRequest(
                prompt=f"{prompt} (Request {i+1})",
                user_id=user_id,
                organization_id=organization_id,
                department=department,
                session_id=session_id
            )
            
            response = await self.agent.process_prompt(request, db)
            responses.append(response)
            
            # Wait between requests
            if i < num_requests - 1:
                await asyncio.sleep(delay_seconds)
        
        return responses