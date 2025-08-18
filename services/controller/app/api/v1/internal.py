"""
Internal API Endpoints for Service-to-Service Communication
These endpoints are for orchestrator registration and controller management
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import logging

# Import database dependencies
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

# Import database session
from ...db.database import get_db
from ...models.orchestrator import Orchestrator, OrchestratorConnection
from ...services.database_pool import get_database_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["Internal Service Communication"])

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class OrchestratorRegistrationRequest(BaseModel):
	"""Request model for orchestrator registration."""
	orchestrator_id: str
	organization_id: str
	name: str
	internal_url: str
	database_url: str
	redis_url: Optional[str] = None
	container_id: Optional[str] = None
	image_name: Optional[str] = None
	environment_variables: Optional[dict] = {}

class OrchestratorHeartbeatRequest(BaseModel):
	"""Request model for orchestrator heartbeat."""
	orchestrator_id: str
	status: str  # active, degraded, error
	health_status: str  # healthy, degraded, unhealthy

class OrchestratorResponse(BaseModel):
	"""Response model for orchestrator information."""
	orchestrator_id: str
	organization_id: str
	name: str
	status: str
	health_status: str
	internal_url: str
	database_url: str
	registered_at: datetime
	last_heartbeat: datetime

# ============================================================================
# ORCHESTRATOR REGISTRATION ENDPOINTS
# ============================================================================

@router.post("/orchestrators/register")
async def register_orchestrator(
	registration: OrchestratorRegistrationRequest,
	db: AsyncSession = Depends(get_db)
):
	"""
	Register a new orchestrator with the controller.
	This endpoint is called by orchestrators during their startup process.
	"""
	try:
		logger.info(f"Registering orchestrator: {registration.orchestrator_id}")
		
		# Check if orchestrator already exists
		existing = await db.execute(
			select(Orchestrator).where(Orchestrator.orchestrator_id == registration.orchestrator_id)
		)
		existing_orchestrator = existing.scalar_one_or_none()
		
		if existing_orchestrator:
			# Update existing registration
			logger.info(f"Updating existing orchestrator: {registration.orchestrator_id}")
			
			await db.execute(
				update(Orchestrator)
				.where(Orchestrator.orchestrator_id == registration.orchestrator_id)
				.values(
					organization_id=registration.organization_id,
					name=registration.name,
					internal_url=registration.internal_url,
					database_url=registration.database_url,
					redis_url=registration.redis_url,
					container_id=registration.container_id,
					image_name=registration.image_name,
					environment_variables=registration.environment_variables,
					status="active",
					health_status="healthy",
					last_heartbeat=datetime.utcnow(),
					updated_at=datetime.utcnow()
				)
			)
			
			# Refresh the record
			result = await db.execute(
				select(Orchestrator).where(Orchestrator.orchestrator_id == registration.orchestrator_id)
			)
			orchestrator = result.scalar_one()
			
		else:
			# Create new registration
			logger.info(f"Creating new orchestrator registration: {registration.orchestrator_id}")
			
			orchestrator = Orchestrator(
				orchestrator_id=registration.orchestrator_id,
				organization_id=registration.organization_id,
				name=registration.name,
				internal_url=registration.internal_url,
				database_url=registration.database_url,
				redis_url=registration.redis_url,
				container_id=registration.container_id,
				image_name=registration.image_name,
				environment_variables=registration.environment_variables,
				status="active",
				health_status="healthy",
				last_heartbeat=datetime.utcnow()
			)
			
			db.add(orchestrator)
		
		await db.commit()
		
		# Create database connection record
		await _create_database_connection(db, registration)
		
		# Register database with pool manager
		pool = get_database_pool()
		db_registered = await pool.register_orchestrator_database(
			registration.orchestrator_id,
			registration.database_url
		)
		
		if not db_registered:
			logger.warning(f"Database pool registration failed for {registration.orchestrator_id}")
		
		logger.info(f"Successfully registered orchestrator: {registration.orchestrator_id}")
		
		return {
			"success": True,
			"message": "Orchestrator registered successfully",
			"orchestrator_id": registration.orchestrator_id,
			"organization_id": registration.organization_id,
			"status": "active",
			"controller_endpoints": {
				"heartbeat": "/api/v1/internal/orchestrators/heartbeat",
				"deregister": f"/api/v1/internal/orchestrators/{registration.orchestrator_id}/deregister"
			}
		}
		
	except Exception as e:
		logger.error(f"Failed to register orchestrator {registration.orchestrator_id}: {str(e)}")
		await db.rollback()
		raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.post("/orchestrators/heartbeat")
async def orchestrator_heartbeat(
	heartbeat: OrchestratorHeartbeatRequest,
	db: AsyncSession = Depends(get_db)
):
	"""
	Receive heartbeat from orchestrator to maintain registration.
	Orchestrators should call this endpoint periodically.
	"""
	try:
		# Update heartbeat timestamp and status
		result = await db.execute(
			update(Orchestrator)
			.where(Orchestrator.orchestrator_id == heartbeat.orchestrator_id)
			.values(
				status=heartbeat.status,
				health_status=heartbeat.health_status,
				last_heartbeat=datetime.utcnow(),
				updated_at=datetime.utcnow()
			)
		)
		
		if result.rowcount == 0:
			raise HTTPException(
				status_code=404, 
				detail=f"Orchestrator {heartbeat.orchestrator_id} not found. Please register first."
			)
		
		await db.commit()
		
		return {
			"success": True,
			"message": "Heartbeat received",
			"orchestrator_id": heartbeat.orchestrator_id,
			"timestamp": datetime.utcnow().isoformat(),
			"status": "acknowledged"
		}
		
	except Exception as e:
		logger.error(f"Heartbeat failed for {heartbeat.orchestrator_id}: {str(e)}")
		await db.rollback()
		raise HTTPException(status_code=500, detail=f"Heartbeat failed: {str(e)}")

@router.delete("/orchestrators/{orchestrator_id}/deregister")
async def deregister_orchestrator(
	orchestrator_id: str,
	db: AsyncSession = Depends(get_db)
):
	"""
	Deregister an orchestrator from the controller.
	Called during orchestrator shutdown.
	"""
	try:
		# Update status to inactive
		result = await db.execute(
			update(Orchestrator)
			.where(Orchestrator.orchestrator_id == orchestrator_id)
			.values(
				status="inactive",
				health_status="unknown",
				updated_at=datetime.utcnow()
			)
		)
		
		if result.rowcount == 0:
			raise HTTPException(status_code=404, detail=f"Orchestrator {orchestrator_id} not found")
		
		await db.commit()
		
		# Unregister database from pool manager
		pool = get_database_pool()
		await pool.unregister_orchestrator_database(orchestrator_id)
		
		logger.info(f"Deregistered orchestrator: {orchestrator_id}")
		
		return {
			"success": True,
			"message": "Orchestrator deregistered successfully",
			"orchestrator_id": orchestrator_id,
			"status": "inactive"
		}
		
	except Exception as e:
		logger.error(f"Deregistration failed for {orchestrator_id}: {str(e)}")
		await db.rollback()
		raise HTTPException(status_code=500, detail=f"Deregistration failed: {str(e)}")

# ============================================================================
# CONTROLLER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/orchestrators")
async def list_registered_orchestrators(
	organization_id: Optional[str] = None,
	status: Optional[str] = None,
	db: AsyncSession = Depends(get_db)
):
	"""
	List all registered orchestrators.
	Used by controller for management and monitoring.
	"""
	try:
		query = select(Orchestrator)
		
		if organization_id:
			query = query.where(Orchestrator.organization_id == organization_id)
		
		if status:
			query = query.where(Orchestrator.status == status)
		
		result = await db.execute(query)
		orchestrators = result.scalars().all()
		
		orchestrator_list = []
		for orch in orchestrators:
			orchestrator_list.append({
				"orchestrator_id": orch.orchestrator_id,
				"organization_id": orch.organization_id,
				"name": orch.name,
				"status": orch.status,
				"health_status": orch.health_status,
				"internal_url": orch.internal_url,
				"database_url": orch.database_url,
				"registered_at": orch.registered_at.isoformat(),
				"last_heartbeat": orch.last_heartbeat.isoformat() if orch.last_heartbeat else None
			})
		
		return {
			"success": True,
			"orchestrators": orchestrator_list,
			"total_count": len(orchestrator_list),
			"filters": {
				"organization_id": organization_id,
				"status": status
			}
		}
		
	except Exception as e:
		logger.error(f"Failed to list orchestrators: {str(e)}")
		raise HTTPException(status_code=500, detail=f"Failed to list orchestrators: {str(e)}")

@router.get("/orchestrators/{orchestrator_id}")
async def get_orchestrator_details(
	orchestrator_id: str,
	db: AsyncSession = Depends(get_db)
):
	"""Get detailed information about a specific orchestrator."""
	try:
		result = await db.execute(
			select(Orchestrator).where(Orchestrator.orchestrator_id == orchestrator_id)
		)
		orchestrator = result.scalar_one_or_none()
		
		if not orchestrator:
			raise HTTPException(status_code=404, detail=f"Orchestrator {orchestrator_id} not found")
		
		return {
			"success": True,
			"orchestrator": {
				"orchestrator_id": orchestrator.orchestrator_id,
				"organization_id": orchestrator.organization_id,
				"name": orchestrator.name,
				"status": orchestrator.status,
				"health_status": orchestrator.health_status,
				"internal_url": orchestrator.internal_url,
				"database_url": orchestrator.database_url,
				"redis_url": orchestrator.redis_url,
				"container_id": orchestrator.container_id,
				"image_name": orchestrator.image_name,
				"environment_variables": orchestrator.environment_variables,
				"registered_at": orchestrator.registered_at.isoformat(),
				"updated_at": orchestrator.updated_at.isoformat(),
				"last_heartbeat": orchestrator.last_heartbeat.isoformat() if orchestrator.last_heartbeat else None
			}
		}
		
	except Exception as e:
		logger.error(f"Failed to get orchestrator details for {orchestrator_id}: {str(e)}")
		raise HTTPException(status_code=500, detail=f"Failed to get orchestrator details: {str(e)}")

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/orchestrator-databases/status")
async def get_database_pool_status():
	"""Get status of all orchestrator database connections."""
	try:
		pool = get_database_pool()
		
		# Get connection status
		connection_status = pool.get_connection_status()
		connected_orchestrators = pool.get_connected_orchestrators()
		
		# Test all connections
		test_results = await pool.test_all_connections()
		
		return {
			"success": True,
			"database_pool": {
				"total_orchestrators": len(connection_status),
				"connected_orchestrators": len(connected_orchestrators),
				"connection_status": connection_status,
				"connection_tests": test_results
			},
			"timestamp": datetime.utcnow().isoformat()
		}
		
	except Exception as e:
		logger.error(f"Failed to get database pool status: {str(e)}")
		raise HTTPException(status_code=500, detail=f"Failed to get database pool status: {str(e)}")

@router.get("/orchestrator-databases/{orchestrator_id}/user-metrics")
async def get_orchestrator_user_metrics(
	orchestrator_id: str,
	user_id: Optional[str] = None,
	limit: int = 100
):
	"""Get user metrics from a specific orchestrator's database."""
	try:
		pool = get_database_pool()
		metrics = await pool.get_user_metrics(orchestrator_id, user_id, limit)
		
		return {
			"success": True,
			"orchestrator_id": orchestrator_id,
			"user_id": user_id,
			"metrics": metrics,
			"total_records": len(metrics)
		}
		
	except Exception as e:
		logger.error(f"Failed to get user metrics for {orchestrator_id}: {str(e)}")
		raise HTTPException(status_code=500, detail=f"Failed to get user metrics: {str(e)}")

@router.get("/orchestrator-databases/{orchestrator_id}/system-metrics")
async def get_orchestrator_system_metrics(
	orchestrator_id: str,
	hours_back: int = 24
):
	"""Get system metrics from a specific orchestrator's database."""
	try:
		pool = get_database_pool()
		metrics = await pool.get_system_metrics(orchestrator_id, hours_back)
		
		return {
			"success": True,
			"orchestrator_id": orchestrator_id,
			"hours_back": hours_back,
			"metrics": metrics,
			"total_records": len(metrics)
		}
		
	except Exception as e:
		logger.error(f"Failed to get system metrics for {orchestrator_id}: {str(e)}")
		raise HTTPException(status_code=500, detail=f"Failed to get system metrics: {str(e)}")

@router.post("/orchestrator-databases/refresh")
async def refresh_database_connections():
	"""Refresh all orchestrator database connections."""
	try:
		pool = get_database_pool()
		refresh_results = await pool.refresh_all_connections()
		
		return {
			"success": True,
			"message": "Database connections refreshed",
			"refresh_results": refresh_results,
			"timestamp": datetime.utcnow().isoformat()
		}
		
	except Exception as e:
		logger.error(f"Failed to refresh database connections: {str(e)}")
		raise HTTPException(status_code=500, detail=f"Failed to refresh connections: {str(e)}")

@router.get("/health")
async def internal_health_check():
	"""Health check for internal API endpoints."""
	return {
		"status": "healthy",
		"service": "controller-internal-api",
		"timestamp": datetime.utcnow().isoformat(),
		"endpoints": {
			"registration": "/api/v1/internal/orchestrators/register",
			"heartbeat": "/api/v1/internal/orchestrators/heartbeat",
			"list": "/api/v1/internal/orchestrators",
			"database_status": "/api/v1/internal/orchestrator-databases/status"
		}
	}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _create_database_connection(db: AsyncSession, registration: OrchestratorRegistrationRequest):
	"""Create database connection record for the orchestrator."""
	try:
		# Parse database URL to extract connection details
		# Format: postgresql+asyncpg://user:password@host:port/database
		db_url = registration.database_url
		
		# Basic parsing (in production, use proper URL parsing)
		if "://" in db_url:
			parts = db_url.split("://")[1]  # Remove protocol
			if "@" in parts:
				auth_and_host = parts.split("@")
				if len(auth_and_host) == 2:
					auth_part = auth_and_host[0]
					host_part = auth_and_host[1]
					
					# Extract username (ignore password for security)
					username = auth_part.split(":")[0] if ":" in auth_part else auth_part
					
					# Extract host, port, database
					if "/" in host_part:
						host_port, database = host_part.split("/", 1)
						if ":" in host_port:
							host, port = host_port.split(":", 1)
						else:
							host, port = host_port, "5432"
					else:
						host, port, database = host_part, "5432", "unknown"
					
					# Check if connection record already exists
					existing = await db.execute(
						select(OrchestratorConnection).where(
							OrchestratorConnection.orchestrator_id == registration.orchestrator_id
						)
					)
					existing_conn = existing.scalar_one_or_none()
					
					if existing_conn:
						# Update existing connection
						await db.execute(
							update(OrchestratorConnection)
							.where(OrchestratorConnection.orchestrator_id == registration.orchestrator_id)
							.values(
								database_name=database,
								host=host,
								port=port,
								username=username,
								connection_status="active",
								updated_at=datetime.utcnow()
							)
						)
					else:
						# Create new connection record
						connection = OrchestratorConnection(
							orchestrator_id=registration.orchestrator_id,
							database_name=database,
							host=host,
							port=port,
							username=username,
							connection_status="active"
						)
						db.add(connection)
					
					await db.commit()
					logger.info(f"Database connection record created for {registration.orchestrator_id}")
				
	except Exception as e:
		logger.warning(f"Failed to create database connection record: {str(e)}")
		# Don't fail registration if connection record creation fails