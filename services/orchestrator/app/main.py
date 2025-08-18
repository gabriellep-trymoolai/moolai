"""Main FastAPI application for orchestrator service."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import database components
from .db.database import db_manager, init_db

# Import controller registration client
from .services.controller_client import ensure_controller_registration, cleanup_controller_registration

# Import API routers
from .api.v1.orchestrator import router as orchestrator_router

# Import monitoring API routers
from .monitoring.api.routers.system_metrics import router as monitoring_metrics_router
from .monitoring.api.routers.streaming import router as monitoring_streaming_router
from .monitoring.api.routers.websocket import router as monitoring_websocket_router

# Import agents
from .agents import PromptResponseAgent

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("Starting MoolAI Orchestrator Service...")
    
    # Initialize database
    try:
        # Test database connection first
        connection_ok = await db_manager.test_connection()
        if not connection_ok:
            print("Warning: Database connection test failed")
        
        await init_db()
        print("Orchestrator database initialized successfully")
    except Exception as e:
        print(f"Orchestrator database initialization failed: {e}")
        raise  # Fail startup if database init fails
    
    # Register with controller (required for orchestrator to function)
    try:
        print("Registering with MoolAI Controller...")
        await ensure_controller_registration()
        print("Successfully registered with controller")
    except Exception as e:
        print(f"Controller registration failed: {e}")
        print("Orchestrator cannot start without controller registration")
        raise  # Fail startup if controller registration fails
    
    # Initialize prompt-response agent
    try:
        organization_id = os.getenv("ORGANIZATION_ID", "default-org")
        app.state.prompt_agent = PromptResponseAgent(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            organization_id=organization_id
        )
        print(f"Prompt-Response Agent initialized for organization: {organization_id}")
    except Exception as e:
        print(f"Prompt-Response Agent initialization failed: {e}")
        app.state.prompt_agent = None
    
    # Initialize embedded monitoring system
    try:
        from .monitoring.middleware.system_monitoring import SystemPerformanceMiddleware
        import redis.asyncio as redis
        
        print("Initializing embedded monitoring system...")
        
        # Setup Redis connection for monitoring
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url)
        
        # Create monitoring middleware
        monitoring_middleware = SystemPerformanceMiddleware(
            redis_client=redis_client,
            organization_id=organization_id,
            collection_interval=30,  # 30 seconds for testing
            enable_realtime_redis=True
        )
        
        # Start background monitoring
        await monitoring_middleware.start_continuous_organization_monitoring()
        app.state.monitoring_middleware = monitoring_middleware
        
        print(f"Embedded monitoring started for organization: {organization_id}")
    except Exception as e:
        print(f"Embedded monitoring initialization failed: {e}")
        app.state.monitoring_middleware = None
    
    yield
    
    # Shutdown
    print("Shutting down MoolAI Orchestrator Service...")
    
    # Stop embedded monitoring
    try:
        if hasattr(app.state, 'monitoring_middleware') and app.state.monitoring_middleware:
            print("Stopping embedded monitoring...")
            await app.state.monitoring_middleware.stop_continuous_organization_monitoring()
            print("Embedded monitoring stopped")
    except Exception as e:
        print(f"Error stopping embedded monitoring: {e}")
    
    # Deregister from controller
    try:
        print("Deregistering from controller...")
        await cleanup_controller_registration()
        print("Successfully deregistered from controller")
    except Exception as e:
        print(f"Error during controller deregistration: {e}")
    
    # Close database connections
    try:
        await db_manager.close()
        print("Orchestrator database connections closed")
    except Exception as e:
        print(f"Error closing orchestrator database connections: {e}")


# Create FastAPI app
app = FastAPI(
    title="MoolAI Orchestrator Service",
    description="AI Workflow Orchestration and LLM Management",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(orchestrator_router, prefix="/api/v1")

# Include monitoring API routers (routers already have their own prefixes)
app.include_router(monitoring_metrics_router, tags=["monitoring"])
app.include_router(monitoring_streaming_router, tags=["streaming"])
app.include_router(monitoring_websocket_router, tags=["websocket"])


@app.get("/")
def root():
    return {"message": "MoolAI Orchestrator Service", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "service": "orchestrator",
        "version": "1.0.0"
    }
    
    # Check database
    try:
        db_connected = await db_manager.test_connection()
        if db_connected:
            health_status["database"] = "connected"
        else:
            health_status["database"] = "disconnected"
            health_status["status"] = "degraded"
    except Exception:
        health_status["database"] = "error"
        health_status["status"] = "degraded"
    
    return health_status
