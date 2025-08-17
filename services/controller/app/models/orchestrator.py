"""Orchestrator model for controller service."""

from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
from ..db.database import Base


class Orchestrator(Base):
	"""Orchestrator instance table for controller service."""
	__tablename__ = "orchestrators"
	
	# Primary key
	orchestrator_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	
	# Organization assignment
	organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id"), nullable=False, index=True)
	
	# Orchestrator identification
	name = Column(String(255), nullable=False)
	slug = Column(String(100), nullable=False, index=True)  # URL-friendly identifier
	description = Column(Text)
	
	# Status and health
	status = Column(String(50), default="inactive")  # inactive, starting, active, stopping, error
	health_status = Column(String(50), default="unknown")  # healthy, degraded, unhealthy, unknown
	last_health_check = Column(DateTime)
	last_heartbeat = Column(DateTime)
	
	# Network and connectivity
	internal_url = Column(String(500))  # Internal container/service URL
	external_url = Column(String(500))  # External accessible URL (if any)
	database_url = Column(String(500))  # Dedicated database URL
	redis_url = Column(String(500))  # Redis connection URL
	
	# Configuration and settings
	configuration = Column(JSON, default={})  # Orchestrator-specific configuration
	environment_variables = Column(JSON, default={})  # Environment variables
	resource_limits = Column(JSON, default={})  # CPU, memory, storage limits
	
	# Container/deployment information
	container_id = Column(String(255))  # Docker container ID
	image_name = Column(String(255))  # Docker image name
	image_tag = Column(String(100))  # Docker image tag/version
	deployment_method = Column(String(50), default="docker")  # docker, kubernetes, manual
	
	# Performance and usage metrics
	uptime_seconds = Column(Integer, default=0)
	request_count = Column(Integer, default=0)
	error_count = Column(Integer, default=0)
	total_tokens_processed = Column(Integer, default=0)
	avg_response_time_ms = Column(Float, default=0.0)
	
	# Resource usage
	cpu_usage_percent = Column(Float, default=0.0)
	memory_usage_mb = Column(Float, default=0.0)
	storage_usage_gb = Column(Float, default=0.0)
	network_in_mb = Column(Float, default=0.0)
	network_out_mb = Column(Float, default=0.0)
	
	# Lifecycle management
	auto_scale_enabled = Column(Boolean, default=False)
	auto_restart_enabled = Column(Boolean, default=True)
	maintenance_mode = Column(Boolean, default=False)
	scheduled_restart = Column(DateTime)
	
	# Monitoring and alerts
	monitoring_enabled = Column(Boolean, default=True)
	alert_thresholds = Column(JSON, default={})  # Performance alert thresholds
	backup_enabled = Column(Boolean, default=True)
	backup_schedule = Column(String(100))  # Cron-like schedule
	
	# Security and access
	api_key = Column(String(255))  # API key for accessing this orchestrator
	secret_key = Column(String(255))  # Secret key for secure communication
	allowed_ips = Column(JSON, default=[])  # IP whitelist
	ssl_enabled = Column(Boolean, default=True)
	
	# Administrative
	created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
	managed_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
	
	# Timestamps
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	started_at = Column(DateTime)
	stopped_at = Column(DateTime)
	deleted_at = Column(DateTime)  # Soft delete
	
	def __repr__(self):
		return f"<Orchestrator(orchestrator_id={self.orchestrator_id}, name='{self.name}', status='{self.status}')>"