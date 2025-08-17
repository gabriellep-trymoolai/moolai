"""Main FastAPI application."""

import os
from contextlib import asynccontextmanager
from typing import Dict, Any
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from ..config.database import db_manager, init_db
from ..agents import PromptResponseAgent
from ..services.system_metrics import system_metrics_service
from ..middleware.system_monitoring import SystemPerformanceMiddleware, global_system_scheduler
from .routers import metrics, agent, dashboard, system_metrics, streaming, websocket
from .dependencies import set_app_state

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import configuration
from ..config.settings import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("Starting MoolAI Monitoring System...")
    
    # Validate configuration based on mode
    try:
        config.validate_sidecar_configuration()
    except ValueError as e:
        print(f"Configuration validation failed: {e}")
        raise
    
    # Initialize database
    try:
        # Test database connection first
        connection_ok = await db_manager.test_connection()
        if not connection_ok:
            print("Warning: Database connection test failed")
        
        await init_db()
        print(f"Database initialized successfully for {config.monitoring_mode} mode")
        if config.is_sidecar_mode:
            print(f"Using orchestrator database for: {config.orchestrator_id}")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        # In sidecar mode, this is more critical
        if config.is_sidecar_mode:
            print("Warning: Sidecar mode requires database connectivity")
    
    # Initialize Redis connection
    try:
        redis_url = config.redis_url or "redis://localhost:6379/0"
        redis_client = redis.from_url(redis_url)
        await redis_client.ping()
        print("Redis connection established")
        app.state.redis = redis_client
    except Exception as e:
        print(f"Redis connection failed: {e}")
        app.state.redis = None
    
    # Initialize prompt-response agent
    try:
        app.state.agent = PromptResponseAgent(
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        print("Prompt-Response Agent initialized")
    except Exception as e:
        print(f"Agent initialization failed: {e}")
        app.state.agent = None
    
    # Initialize system performance monitoring
    try:
        app.state.system_middleware = SystemPerformanceMiddleware(
            redis_client=app.state.redis if hasattr(app.state, 'redis') else None,
            organization_id=config.get_organization_id(),
            collection_interval=config.system_metrics_interval,
            enable_realtime_redis=True
        )
        print("System Performance Middleware initialized")
        
        # Register with global scheduler
        global_system_scheduler.register_middleware(
            app.state.system_middleware.organization_id,
            app.state.system_middleware
        )
        print("System metrics scheduler registered")
        
        # Start automatic background collection
        try:
            # Start continuous organization monitoring with default intervals (30s in sidecar mode)
            await app.state.system_middleware.start_continuous_organization_monitoring()
            print(f"Started continuous organization monitoring ({config.system_metrics_interval}-second intervals)")
            
            # Start global scheduler for cross-organization metrics
            await global_system_scheduler.start_global_collection()
            print("Started global system metrics collection")
            
            # Trigger immediate collection to populate tables
            initial_metrics = await app.state.system_middleware.track_organization_system_performance(
                force_collection=True
            )
            if initial_metrics:
                print("Initial system metrics collected and recorded")
            else:
                print("Warning: Initial metrics collection failed")
                
        except Exception as collection_error:
            print(f"Warning: Background collection startup failed: {collection_error}")
        
    except Exception as e:
        print(f"System performance initialization failed: {e}")
        app.state.system_middleware = None
    
    # Set app state for dependencies
    set_app_state(app.state)
    
    yield
    
    # Shutdown
    print("Shutting down MoolAI Monitoring System...")
    
    # Stop system performance monitoring
    try:
        if hasattr(app.state, 'system_middleware') and app.state.system_middleware:
            # Stop continuous monitoring
            await app.state.system_middleware.stop_continuous_organization_monitoring()
            await app.state.system_middleware.stop_all_monitoring()
            
            # Stop global scheduler
            await global_system_scheduler.stop_global_collection()
            global_system_scheduler.unregister_middleware(app.state.system_middleware.organization_id)
            print("System performance monitoring stopped")
    except Exception as e:
        print(f"Error stopping system monitoring: {e}")
    
    # Close database connections
    try:
        await db_manager.close()
        print("Database connections closed")
    except Exception as e:
        print(f"Error closing database connections: {e}")
    
    # Close Redis connection
    if hasattr(app.state, 'redis') and app.state.redis:
        await app.state.redis.close()


# Create FastAPI app
app = FastAPI(
    title="MoolAI Monitoring System",
    description="Per-User LLM Statistics and System Performance Monitoring Framework",
    version="1.1.0",
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

# Include routers
app.include_router(agent.router, prefix="/api/v1", tags=["agent"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
app.include_router(system_metrics.router, tags=["system-metrics"])
app.include_router(streaming.router, tags=["streaming"])
app.include_router(websocket.router, tags=["websocket"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "MoolAI Monitoring System",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "mode": config.monitoring_mode,
        "services": {}
    }
    
    # Add sidecar-specific information
    if config.is_sidecar_mode:
        health_status["orchestrator_id"] = config.orchestrator_id
        health_status["organization_id"] = config.organization_id
    
    # Check database
    try:
        db_connected = await db_manager.test_connection()
        if db_connected:
            health_status["services"]["database"] = "connected"
            if config.is_sidecar_mode:
                health_status["services"]["database_type"] = "orchestrator_specific"
        else:
            health_status["services"]["database"] = "disconnected"
            health_status["status"] = "degraded"
    except Exception:
        health_status["services"]["database"] = "error"
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        if hasattr(app.state, 'redis') and app.state.redis:
            await app.state.redis.ping()
            health_status["services"]["redis"] = "connected"
        else:
            health_status["services"]["redis"] = "not_configured"
    except Exception:
        health_status["services"]["redis"] = "disconnected"
        health_status["status"] = "degraded"
    
    # Check OpenAI agent
    try:
        if hasattr(app.state, 'agent'):
            agent_health = await app.state.agent.health_check()
            health_status["services"]["openai_agent"] = agent_health["status"]
        else:
            health_status["services"]["openai_agent"] = "not_configured"
    except Exception:
        health_status["services"]["openai_agent"] = "error"
        health_status["status"] = "degraded"
    
    # Check system performance monitoring
    try:
        if hasattr(app.state, 'system_middleware') and app.state.system_middleware:
            health_status["services"]["system_monitoring"] = "active"
            health_status["services"]["system_metrics_interval"] = f"{app.state.system_middleware.collection_interval}s"
        else:
            health_status["services"]["system_monitoring"] = "not_configured"
    except Exception:
        health_status["services"]["system_monitoring"] = "error"
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/ready")
async def readiness_check():
    """Readiness probe endpoint for container orchestration."""
    try:
        # Basic readiness checks
        ready_checks = {
            "database": False,
            "redis": False,
            "system_monitoring": False
        }
        
        # Check database connectivity
        try:
            ready_checks["database"] = await db_manager.test_connection()
        except Exception:
            pass
        
        # Check Redis connectivity
        try:
            if hasattr(app.state, 'redis') and app.state.redis:
                await app.state.redis.ping()
                ready_checks["redis"] = True
        except Exception:
            pass
        
        # Check system monitoring
        try:
            if hasattr(app.state, 'system_middleware') and app.state.system_middleware:
                ready_checks["system_monitoring"] = True
        except Exception:
            pass
        
        # For sidecar mode, add orchestrator-specific checks
        if config.is_sidecar_mode:
            ready_checks["orchestrator_mode"] = True
            ready_checks["orchestrator_id"] = config.orchestrator_id is not None
            ready_checks["organization_id"] = config.organization_id is not None
            
            # Check that database is orchestrator-specific
            if ready_checks["database"]:
                try:
                    db_url = db_manager.get_database_url()
                    # Verify it's not the default database
                    ready_checks["orchestrator_database"] = "localhost/moolai_monitoring" not in db_url
                except Exception:
                    ready_checks["orchestrator_database"] = False
        
        # All checks must pass for readiness
        all_ready = all(ready_checks.values())
        
        if all_ready:
            return {"status": "ready", "checks": ready_checks}
        else:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": ready_checks})
            
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"status": "error", "error": str(e)})


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check including orchestrator dependencies."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "mode": config.monitoring_mode,
        "checks": {}
    }
    
    # Add sidecar-specific information
    if config.is_sidecar_mode:
        health_status["orchestrator_id"] = config.orchestrator_id
        health_status["organization_id"] = config.organization_id
    
    # Database check with detailed info
    try:
        start_time = datetime.now()
        db_connected = await db_manager.test_connection()
        end_time = datetime.now()
        latency_ms = int((end_time - start_time).total_seconds() * 1000)
        
        if db_connected:
            health_status["checks"]["database"] = {
                "status": "healthy",
                "latency_ms": latency_ms,
                "type": "orchestrator_specific" if config.is_sidecar_mode else "standalone"
            }
        else:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "latency_ms": latency_ms
            }
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Redis check with detailed info
    try:
        if hasattr(app.state, 'redis') and app.state.redis:
            start_time = datetime.now()
            await app.state.redis.ping()
            end_time = datetime.now()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            health_status["checks"]["redis"] = {
                "status": "healthy",
                "latency_ms": latency_ms
            }
        else:
            health_status["checks"]["redis"] = {
                "status": "not_configured"
            }
    except Exception as e:
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Orchestrator dependency check (sidecar mode only)
    if config.is_sidecar_mode:
        orchestrator_health = {
            "status": "unknown",
            "orchestrator_id": config.orchestrator_id
        }
        
        # In a real implementation, this would ping the orchestrator
        # For now, we just verify the configuration is valid
        try:
            if config.orchestrator_id and config.organization_id:
                orchestrator_health["status"] = "configured"
                orchestrator_health["organization_id"] = config.organization_id
            else:
                orchestrator_health["status"] = "misconfigured"
                health_status["status"] = "degraded"
        except Exception as e:
            orchestrator_health["status"] = "error"
            orchestrator_health["error"] = str(e)
            health_status["status"] = "degraded"
        
        health_status["checks"]["orchestrator"] = orchestrator_health
    
    # System monitoring check
    try:
        if hasattr(app.state, 'system_middleware') and app.state.system_middleware:
            health_status["checks"]["system_monitoring"] = {
                "status": "active",
                "organization_id": app.state.system_middleware.organization_id,
                "collection_interval": app.state.system_middleware.collection_interval
            }
        else:
            health_status["checks"]["system_monitoring"] = {
                "status": "not_configured"
            }
    except Exception as e:
        health_status["checks"]["system_monitoring"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    return health_status



if __name__ == "__main__":
    import uvicorn
    
    host = config.api_host
    port = config.api_port
    
    print(f"Starting MoolAI Monitoring in {config.monitoring_mode} mode on {host}:{port}")
    if config.is_sidecar_mode and config.orchestrator_id:
        print(f"Sidecar for orchestrator: {config.orchestrator_id}")
    
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )