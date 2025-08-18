"""Orchestrator registration model for controller service."""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
from ..db.database import Base


class Orchestrator(Base):
	"""Orchestrator registration and management table."""
	__tablename__ = "orchestrators"
	
	# Primary identification
	orchestrator_id = Column(String(255), primary_key=True)  # Set by orchestrator (e.g., "org_001_orchestrator")
	organization_id = Column(String(255), nullable=False, index=True)  # Organization this orchestrator serves
	
	# Basic info
	name = Column(String(255), nullable=False)
	status = Column(String(50), default="starting")  # starting, active, inactive, error
	
	# Connection information
	internal_url = Column(String(500), nullable=False)  # e.g., "http://orchestrator-org-001:8000"
	database_url = Column(String(500), nullable=False)  # Orchestrator's database connection
	redis_url = Column(String(500))  # Optional Redis connection
	
	# System information
	container_id = Column(String(255))
	image_name = Column(String(255))
	environment_variables = Column(JSON, default={})
	
	# Health tracking
	last_heartbeat = Column(DateTime, default=datetime.utcnow)
	health_status = Column(String(50), default="unknown")  # healthy, degraded, unhealthy
	
	# Timestamps
	registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	
	def __repr__(self):
		return f"<Orchestrator(id={self.orchestrator_id}, org={self.organization_id}, status={self.status})>"


class OrchestratorConnection(Base):
	"""Track controller connections to orchestrator databases."""
	__tablename__ = "orchestrator_connections"
	
	# Primary key
	connection_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	
	# Reference to orchestrator
	orchestrator_id = Column(String(255), ForeignKey("orchestrators.orchestrator_id"), nullable=False)
	
	# Database connection details
	database_name = Column(String(255), nullable=False)
	host = Column(String(255), nullable=False)
	port = Column(String(10), nullable=False)
	username = Column(String(255), nullable=False)
	
	# Connection status
	connection_status = Column(String(50), default="pending")  # pending, active, failed
	last_tested = Column(DateTime)
	connection_error = Column(Text)
	
	# Timestamps
	created_at = Column(DateTime, default=datetime.utcnow)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	
	def __repr__(self):
		return f"<OrchestratorConnection(orchestrator={self.orchestrator_id}, db={self.database_name}, status={self.connection_status})>"