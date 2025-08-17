"""Main FastAPI application for orchestrator service."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import database components
from .db.database import db_manager, init_db

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
    
    yield
    
    # Shutdown
    print("Shutting down MoolAI Orchestrator Service...")
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
