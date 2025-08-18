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
    
    yield
    
    # Shutdown
    print("Shutting down MoolAI Orchestrator Service...")
    
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
