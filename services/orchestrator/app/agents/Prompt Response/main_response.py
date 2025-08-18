from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
import asyncio
from typing import Optional
import httpx
import logging

# Import local services
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../services'))
from Caching.cache import RedisCache, process_prompt, store_response
from Caching.main import PromptRequest
from Firewall.server import _pii_local, _secrets_local, _toxicity_local

# Import evaluation services
sys.path.append(os.path.join(os.path.dirname(__file__), '../../services/Evaluation'))
from answer_correctness import evaluate_answer_correctness
from answer_relevance import evaluate_answer_relevance
from goal_accuracy import evaluate_goal_accuracy
from hallucination import evaluate_hallucination
from toxicity import evaluate_toxicity as eval_toxicity
from summarization import evaluate_summarization
from human_vs_ai import evaluate_human_vs_ai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

client = AsyncOpenAI(api_key=openai_api_key)

# Cache service configuration
ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"

# Firewall service configuration
ENABLE_FIREWALL = os.getenv("ENABLE_FIREWALL", "true").lower() == "true"

# Initialize local services
cache_service = RedisCache() if ENABLE_CACHING else None

# Pydantic models
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"

class QueryResponse(BaseModel):
    answer: str
    session_id: str
    from_cache: bool = False
    similarity: Optional[float] = None

class CacheConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    ttl: Optional[int] = None
    similarity_threshold: Optional[float] = None

# Initialize FastAPI app
app = FastAPI(
    title="LLM Response API",
    description="A minimal FastAPI app that returns LLM responses for user queries",
    version="1.0.0"
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# System instruction
SYSTEM_INSTRUCTION = "You are a helpful assistant. Provide clear, concise, and accurate responses to user questions."

# Cache service integration
async def get_cached_response(query: str, session_id: str = "default") -> Optional[dict]:
    """Try to get response from cache service"""
    if not ENABLE_CACHING or not cache_service:
        return None
        
    try:
        # Use local cache service
        prompt_request = PromptRequest(session_id=session_id, message=query)
        result = process_prompt(cache_service, prompt_request)
        logger.info(f"Cache service response: from_cache={result.from_cache}, similarity={result.similarity}")
        
        # Convert PromptResponse to dict for consistency
        if result.from_cache:
            return {
                "response": result.response,
                "from_cache": result.from_cache,
                "similarity": result.similarity,
                "session_id": result.session_id,
                "label": result.label
            }
        return None
    except Exception as e:
        logger.error(f"Cache service error: {e}")
        return None

async def firewall_scan(text: str) -> dict:
    """
    Fan out PII, secrets, and toxicity scans in parallel.
    Returns a dict with each scan's JSON response.
    """
    if not ENABLE_FIREWALL:
        return {"pii": {"contains_pii": False}, "secrets": {"contains_secrets": False}, "toxicity": {"contains_toxicity": False}}
    
    try:
        # Use local firewall service functions
        tasks = [
            asyncio.create_task(asyncio.to_thread(_pii_local, text)),
            asyncio.create_task(asyncio.to_thread(_secrets_local, text)),
            asyncio.create_task(asyncio.to_thread(_toxicity_local, text)),
        ]
        
        pii_result, secrets_result, toxicity_result = await asyncio.gather(*tasks)
        
        return {
            "pii": pii_result,
            "secrets": secrets_result,
            "toxicity": toxicity_result,
        }
    except Exception as e:
        logger.error(f"Firewall service error: {e}")
        raise HTTPException(status_code=500, detail=f"Firewall error: {str(e)}")

async def generate_llm_response(query: str, session_id: str = "default") -> dict:
    """Generate LLM response with cache integration"""
    
    # Try cache first
    if ENABLE_CACHING:
        cache_result = await get_cached_response(query, session_id)
        if cache_result and cache_result.get("from_cache"):
            logger.info(f"Cache HIT for session {session_id}")
            return {
                "answer": cache_result["response"],
                "session_id": session_id,
                "from_cache": True,
                "similarity": cache_result.get("similarity")
            }
    
    # Generate fresh response from OpenAI
    logger.info(f"Cache MISS - generating fresh response for session {session_id}")
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": query.strip()}
        ],
        max_tokens=1000,
        temperature=0.2
    )
    
    answer = response.choices[0].message.content
    
    # Store in cache if cache service is available
    if ENABLE_CACHING and cache_service:
        try:
            store_response(cache_service, session_id, query, answer)
            logger.info(f"Stored fresh response in cache for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to store in cache: {e}")
    
    return {
        "answer": answer,
        "session_id": session_id,
        "from_cache": False,
        "similarity": None
    }

@app.get("/respond")
async def get_response(
    query: str = Query(..., description="User query to get LLM response for"),
    session_id: str = Query("default", description="Session ID for caching")
):
    """
    Get LLM response for a user query with caching support.
    
    Args:
        query: The user's question or prompt
        session_id: Session ID for cache isolation
        
    Returns:
        JSON response with the LLM's answer and cache metadata
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty")
    
    # Firewall check
    if ENABLE_FIREWALL:
        scan = await firewall_scan(query.strip())
        if scan["pii"]["contains_pii"] or scan["secrets"]["contains_secrets"] or scan["toxicity"]["contains_toxicity"]:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Content blocked by firewall",
                    "scan_results": scan
                }
            )
    
    try:
        result = await asyncio.wait_for(
            generate_llm_response(query.strip(), session_id),
            timeout=35.0  # Slightly longer timeout to account for cache calls
        )
        return result
        
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=408,
            content={"error": "Request timeout - the service took too long to respond"}
        )
    except Exception as e:
        logger.error(f"Error in get_response: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

@app.post("/respond", response_model=QueryResponse)
async def post_response(request: QueryRequest):
    """
    Get LLM response for a user query (POST version with JSON body).
    
    Args:
        request: JSON body containing the query and optional session_id
        
    Returns:
        JSON response with the LLM's answer and cache metadata
    """
    query = request.query
    session_id = request.session_id or "default"
    
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Firewall check
    if ENABLE_FIREWALL:
        scan = await firewall_scan(query.strip())
        if scan["pii"]["contains_pii"] or scan["secrets"]["contains_secrets"] or scan["toxicity"]["contains_toxicity"]:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Content blocked by firewall",
                    "scan_results": scan
                }
            )
    
    try:
        result = await asyncio.wait_for(
            generate_llm_response(query.strip(), session_id),
            timeout=35.0  # Slightly longer timeout to account for cache calls
        )
        
        return QueryResponse(
            answer=result["answer"],
            session_id=result["session_id"],
            from_cache=result["from_cache"],
            similarity=result["similarity"]
        )
        
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=408,
            content={"error": "Request timeout - the service took too long to respond"}
        )
    except Exception as e:
        logger.error(f"Error in post_response: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

@app.get("/health")
async def health_check():
    """Health check endpoint with cache service status"""
    cache_status = "unknown"
    if ENABLE_CACHING and cache_service:
        try:
            cache_status = "connected" if cache_service.ping() else "disconnected"
        except:
            cache_status = "disconnected"
    else:
        cache_status = "disabled"
    
    return {
        "status": "healthy",
        "cache_service": cache_status,
        "caching_enabled": ENABLE_CACHING
    }

# Cache management endpoints
@app.get("/cache/health")
async def cache_health():
    """Check cache service health"""
    if not ENABLE_CACHING or not cache_service:
        return {"cache_available": False, "message": "Caching is disabled"}
    
    try:
        cache_available = cache_service.ping()
        if cache_available:
            return {
                "cache_available": True,
                "cache_service": "local",
                "cache_details": cache_service.stats()
            }
        else:
            return {
                "cache_available": False,
                "cache_service": "local",
                "error": "Cache service ping failed"
            }
    except Exception as e:
        return {
            "cache_available": False,
            "cache_service": "local",
            "error": str(e)
        }

@app.get("/cache/config")
async def get_cache_config():
    """Get cache service configuration"""
    if not ENABLE_CACHING or not cache_service:
        return {"error": "Caching is disabled"}
    
    try:
        # Return basic cache configuration
        return {
            "enabled": ENABLE_CACHING,
            "cache_type": "Redis",
            "status": "local_service"
        }
    except Exception as e:
        return {"error": f"Cache service unavailable: {str(e)}"}

@app.post("/cache/config")
async def update_cache_config(config: CacheConfigUpdate):
    """Update cache service configuration"""
    if not ENABLE_CACHING or not cache_service:
        return {"error": "Caching is disabled"}
    
    try:
        # Update cache configuration if supported
        updated_config = {"message": "Cache config update not supported in local mode"}
        if config.enabled is not None:
            updated_config["enabled"] = config.enabled
        if config.ttl is not None:
            updated_config["ttl"] = config.ttl
        if config.similarity_threshold is not None:
            updated_config["similarity_threshold"] = config.similarity_threshold
        return updated_config
    except Exception as e:
        return {"error": f"Cache service unavailable: {str(e)}"}

@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache service statistics"""
    if not ENABLE_CACHING or not cache_service:
        return {"error": "Caching is disabled"}
    
    try:
        return cache_service.stats()
    except Exception as e:
        return {"error": f"Cache service unavailable: {str(e)}"}

@app.delete("/cache/keys")
async def clear_cache():
    """Clear all cache entries"""
    if not ENABLE_CACHING or not cache_service:
        return {"error": "Caching is disabled"}
    
    try:
        cache_service.clear()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        return {"error": f"Cache service unavailable: {str(e)}"}

# Evaluation endpoints
@app.post("/evaluate/correctness")
async def evaluate_response_correctness(request: QueryRequest):
    """Evaluate answer correctness for a query-response pair"""
    try:
        # First get the response
        response_data = await generate_llm_response(request.query, request.session_id)
        answer = response_data["answer"]
        
        # Then evaluate it
        evaluation = await evaluate_answer_correctness(request.query, answer)
        
        return {
            "query": request.query,
            "answer": answer,
            "evaluation": evaluation,
            "session_id": request.session_id
        }
    except Exception as e:
        logger.error(f"Error in correctness evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate/relevance")
async def evaluate_response_relevance(request: QueryRequest):
    """Evaluate answer relevance for a query-response pair"""
    try:
        # First get the response
        response_data = await generate_llm_response(request.query, request.session_id)
        answer = response_data["answer"]
        
        # Then evaluate it
        evaluation = await evaluate_answer_relevance(request.query, answer)
        
        return {
            "query": request.query,
            "answer": answer,
            "evaluation": evaluation,
            "session_id": request.session_id
        }
    except Exception as e:
        logger.error(f"Error in relevance evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate/comprehensive")
async def evaluate_response_comprehensive(request: QueryRequest):
    """Run comprehensive evaluation on a query-response pair"""
    try:
        # First get the response
        response_data = await generate_llm_response(request.query, request.session_id)
        answer = response_data["answer"]
        
        # Run all evaluations in parallel
        evaluations = await asyncio.gather(
            evaluate_answer_correctness(request.query, answer),
            evaluate_answer_relevance(request.query, answer),
            evaluate_goal_accuracy(request.query, answer),
            evaluate_hallucination(request.query, answer),
            evaluate_summarization(request.query, answer)
        )
        
        return {
            "query": request.query,
            "answer": answer,
            "evaluations": {
                "correctness": evaluations[0],
                "relevance": evaluations[1],
                "goal_accuracy": evaluations[2],
                "hallucination": evaluations[3],
                "summarization": evaluations[4]
            },
            "session_id": request.session_id
        }
    except Exception as e:
        logger.error(f"Error in comprehensive evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
