"""Main FastAPI application for controller service."""

import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import database components
from .db.database import db_manager, init_db

# Import API routers
from .api.v1.controller import router as controller_router
from .api.v1.internal import router as internal_router

# Import database pool manager
from .services.database_pool import initialize_database_pool, cleanup_database_pool

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("Starting MoolAI Controller Service...")
    
    # Initialize database
    try:
        # Test database connection first
        connection_ok = await db_manager.test_connection()
        if not connection_ok:
            print("Warning: Database connection test failed")
        
        await init_db()
        print("Controller database initialized successfully")
    except Exception as e:
        print(f"Controller database initialization failed: {e}")
    
    # Initialize database pool for orchestrator connections
    try:
        await initialize_database_pool()
        print("Database pool manager initialized successfully")
    except Exception as e:
        print(f"Database pool manager initialization failed: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down MoolAI Controller Service...")
    
    # Clean up database pool
    try:
        await cleanup_database_pool()
        print("Database pool cleaned up")
    except Exception as e:
        print(f"Error cleaning up database pool: {e}")
    
    # Close controller database connections
    try:
        await db_manager.close()
        print("Controller database connections closed")
    except Exception as e:
        print(f"Error closing controller database connections: {e}")


# Create FastAPI app
app = FastAPI(
    title="MoolAI Controller Service",
    description="Central Management and Analytics for MoolAI Platform",
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
app.include_router(controller_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")


@app.get("/")
def home():
    return {"message": "MoolAI Controller Service", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "service": "controller",
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8765, reload=True)
