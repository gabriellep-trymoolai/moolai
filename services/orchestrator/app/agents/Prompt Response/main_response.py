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
import time
import json
import hashlib
import numpy as np

# Import firewall services for security checks
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../services'))
from Firewall.server import _pii_local, _secrets_local, _toxicity_local

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
LLM_CACHE_REDIS_URL = os.getenv("REDIS_LLM_CACHE_URL", "redis://localhost:6379/1")

# Firewall service configuration
ENABLE_FIREWALL = os.getenv("ENABLE_FIREWALL", "true").lower() == "true"

# Initialize dedicated LLM cache (completely separate from monitoring cache)
llm_cache_client = None
if ENABLE_CACHING:
    # Create dedicated Redis client for LLM cache only
    import redis
    from urllib.parse import urlparse
    import json
    import hashlib
    from sentence_transformers import SentenceTransformer
    
    parsed_url = urlparse(LLM_CACHE_REDIS_URL)
    redis_host = parsed_url.hostname or "localhost"
    redis_port = parsed_url.port or 6379
    redis_db = int(parsed_url.path.lstrip('/')) if parsed_url.path else 1
    
    try:
        llm_cache_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False,
            socket_timeout=2,
            socket_connect_timeout=2,
            health_check_interval=30,
        )
        
        # Test connection
        llm_cache_client.ping()
        logger.info(f"LLM cache connected to Redis DB {redis_db} at {redis_host}:{redis_port}")
        
        # Initialize sentence transformer for semantic similarity
        sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        
    except Exception as e:
        logger.warning(f"Failed to initialize LLM cache: {e}")
        llm_cache_client = None

# Set cache_service to None - we'll use llm_cache_client directly
cache_service = None

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

# LLM Cache integration - completely separate from monitoring cache
async def get_cached_response(query: str, session_id: str = "default") -> Optional[dict]:
    """Try to get response from dedicated LLM cache"""
    if not ENABLE_CACHING or not llm_cache_client:
        return None
        
    try:
        # Create cache key from query
        cache_key = f"llm_cache:{session_id}:{hashlib.md5(query.encode()).hexdigest()}"
        
        # Check for exact match first
        cached_data = llm_cache_client.get(cache_key)
        if cached_data:
            result = json.loads(cached_data.decode('utf-8'))
            logger.info(f"LLM cache hit (exact): {cache_key}")
            return {
                "response": result["response"],
                "from_cache": True,
                "similarity": 1.0,
                "session_id": session_id,
                "cache_key": cache_key
            }
        
        # Semantic similarity search (simplified)
        if 'sentence_model' in globals():
            query_embedding = sentence_model.encode(query)
            
            # Search for similar queries in cache (simplified approach)
            # For production, you'd want a more sophisticated vector search
            pattern = f"llm_cache:{session_id}:*"
            cache_keys = llm_cache_client.keys(pattern)
            
            for key in cache_keys[:10]:  # Limit to 10 most recent for performance
                try:
                    cached_data = llm_cache_client.get(key)
                    if cached_data:
                        cached_result = json.loads(cached_data.decode('utf-8'))
                        if 'original_query' in cached_result:
                            cached_embedding = sentence_model.encode(cached_result['original_query'])
                            similarity = float(np.dot(query_embedding, cached_embedding) / 
                                             (np.linalg.norm(query_embedding) * np.linalg.norm(cached_embedding)))
                            
                            if similarity >= 0.75:  # 75% similarity threshold
                                logger.info(f"LLM cache hit (semantic): similarity={similarity:.3f}")
                                return {
                                    "response": cached_result["response"],
                                    "from_cache": True,
                                    "similarity": similarity,
                                    "session_id": session_id,
                                    "cache_key": key.decode('utf-8') if isinstance(key, bytes) else key
                                }
                except Exception as e:
                    logger.debug(f"Error checking cached item {key}: {e}")
                    continue
        
        return None
    except Exception as e:
        logger.error(f"LLM cache error: {e}")
        return None

async def store_cached_response(query: str, response: str, session_id: str = "default", ttl: int = 3600):
    """Store response in dedicated LLM cache"""
    if not ENABLE_CACHING or not llm_cache_client:
        return
        
    try:
        cache_key = f"llm_cache:{session_id}:{hashlib.md5(query.encode()).hexdigest()}"
        cache_data = {
            "response": response,
            "original_query": query,
            "timestamp": time.time(),
            "session_id": session_id
        }
        
        llm_cache_client.setex(cache_key, ttl, json.dumps(cache_data))
        logger.info(f"Stored in LLM cache: {cache_key}")
    except Exception as e:
        logger.error(f"Error storing in LLM cache: {e}")

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
    """Generate LLM response with dedicated LLM cache integration"""
    
    # Try dedicated LLM cache first
    if ENABLE_CACHING:
        cache_result = await get_cached_response(query, session_id)
        if cache_result and cache_result.get("from_cache"):
            logger.info(f"LLM Cache HIT for session {session_id} (similarity: {cache_result.get('similarity', 'exact')})")
            return {
                "answer": cache_result["response"],
                "session_id": session_id,
                "from_cache": True,
                "similarity": cache_result.get("similarity")
            }
    
    # Generate fresh response from OpenAI
    logger.info(f"LLM Cache MISS - generating fresh response for session {session_id}")
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
    
    # Store in dedicated LLM cache (completely separate from monitoring)
    if ENABLE_CACHING:
        await store_cached_response(query, answer, session_id)
        logger.info(f"Stored fresh response in dedicated LLM cache for session {session_id}")
    
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
