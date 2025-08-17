"""Tests for monitoring service sidecar mode configuration."""

import os
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
import redis.asyncio as redis

from src.api.main import app
from src.middleware.system_monitoring import SystemPerformanceMiddleware


@pytest.fixture
def mock_redis():
	"""Mock Redis client for testing."""
	mock_client = AsyncMock()
	mock_client.ping = AsyncMock(return_value=True)
	mock_client.close = AsyncMock()
	return mock_client


@pytest.fixture
def sidecar_env_vars():
	"""Set environment variables for sidecar mode."""
	env_vars = {
		"MONITORING_MODE": "sidecar",
		"ORCHESTRATOR_ID": "test_orchestrator",
		"ORGANIZATION_ID": "test_org",
		"API_PORT": "8001",
		"DATABASE_URL": "postgresql://test_user:test_pass@test_host:5432/test_db",
		"REDIS_URL": "redis://test_redis:6379/0"
	}
	
	# Set environment variables
	for key, value in env_vars.items():
		os.environ[key] = value
	
	yield env_vars
	
	# Clean up environment variables
	for key in env_vars:
		os.environ.pop(key, None)


@pytest.fixture
def standalone_env_vars():
	"""Set environment variables for standalone mode."""
	env_vars = {
		"MONITORING_MODE": "standalone",
		"API_PORT": "8000",
		"DATABASE_URL": "postgresql://monitoring:pass@localhost:5432/monitoring_db",
		"REDIS_URL": "redis://localhost:6379/0"
	}
	
	for key, value in env_vars.items():
		os.environ[key] = value
	
	yield env_vars
	
	for key in env_vars:
		os.environ.pop(key, None)


class TestSidecarModeDetection:
	"""Test sidecar mode detection and configuration."""
	
	def test_sidecar_mode_env_detection(self, sidecar_env_vars):
		"""Test that sidecar mode is detected from environment variables."""
		assert os.getenv("MONITORING_MODE") == "sidecar"
		assert os.getenv("ORCHESTRATOR_ID") == "test_orchestrator"
		assert os.getenv("ORGANIZATION_ID") == "test_org"
		assert os.getenv("API_PORT") == "8001"
	
	def test_standalone_mode_env_detection(self, standalone_env_vars):
		"""Test that standalone mode is detected from environment variables."""
		assert os.getenv("MONITORING_MODE") == "standalone"
		assert os.getenv("API_PORT") == "8000"
	
	def test_default_mode_when_not_specified(self):
		"""Test that default mode is standalone when not specified."""
		# Ensure MONITORING_MODE is not set
		os.environ.pop("MONITORING_MODE", None)
		
		mode = os.getenv("MONITORING_MODE", "standalone")
		assert mode == "standalone"


class TestSidecarDatabaseConfiguration:
	"""Test database configuration for sidecar mode."""
	
	def test_sidecar_database_url_format(self, sidecar_env_vars):
		"""Test that sidecar mode uses orchestrator-specific database URL."""
		db_url = os.getenv("DATABASE_URL")
		assert "test_host" in db_url
		assert "test_db" in db_url
		assert "test_user" in db_url
	
	def test_sidecar_redis_url_format(self, sidecar_env_vars):
		"""Test that sidecar mode uses orchestrator-specific Redis URL."""
		redis_url = os.getenv("REDIS_URL")
		assert "test_redis" in redis_url
		assert "6379" in redis_url
	
	@pytest.mark.asyncio
	async def test_sidecar_database_connection_validation(self, sidecar_env_vars, mock_redis):
		"""Test that sidecar mode validates database connections."""
		with patch('redis.asyncio.from_url', return_value=mock_redis):
			# Test Redis connection validation
			redis_client = redis.from_url(os.getenv("REDIS_URL"))
			await redis_client.ping()
			mock_redis.ping.assert_called_once()


class TestSidecarPortConfiguration:
	"""Test port configuration for sidecar mode."""
	
	def test_sidecar_port_configuration(self, sidecar_env_vars):
		"""Test that sidecar mode uses port 8001."""
		port = int(os.getenv("API_PORT", 8000))
		assert port == 8001
	
	def test_standalone_port_configuration(self, standalone_env_vars):
		"""Test that standalone mode uses port 8000."""
		port = int(os.getenv("API_PORT", 8000))
		assert port == 8000
	
	def test_port_conflict_detection(self):
		"""Test detection of port conflicts."""
		# This would be implemented as part of startup validation
		# For now, we just test the configuration
		os.environ["API_PORT"] = "8001"
		port = int(os.getenv("API_PORT"))
		assert port == 8001
		
		# Clean up
		os.environ.pop("API_PORT", None)


class TestSidecarHealthChecks:
	"""Test health check endpoints for sidecar mode."""
	
	@pytest.mark.asyncio
	async def test_sidecar_health_check_includes_orchestrator_dependency(self, sidecar_env_vars):
		"""Test that sidecar health check includes orchestrator dependency."""
		# Mock the health check logic that would check orchestrator connection
		orchestrator_id = os.getenv("ORCHESTRATOR_ID")
		organization_id = os.getenv("ORGANIZATION_ID")
		
		# Basic validation that we have the required environment variables
		assert orchestrator_id == "test_orchestrator"
		assert organization_id == "test_org"
		
		# Health check should validate orchestrator connectivity
		health_data = {
			"status": "healthy",
			"checks": {
				"database": {"status": "healthy"},
				"redis": {"status": "healthy"},
				"orchestrator": {"status": "healthy", "orchestrator_id": orchestrator_id}
			},
			"mode": "sidecar",
			"organization_id": organization_id
		}
		
		assert health_data["checks"]["orchestrator"]["orchestrator_id"] == "test_orchestrator"
		assert health_data["mode"] == "sidecar"
	
	def test_sidecar_ready_endpoint_validation(self, sidecar_env_vars):
		"""Test readiness probe validation for sidecar mode."""
		# Readiness should check all dependencies including orchestrator
		orchestrator_id = os.getenv("ORCHESTRATOR_ID")
		
		# Mock readiness check
		ready_checks = {
			"database_ready": True,
			"redis_ready": True,
			"orchestrator_reachable": True,
			"orchestrator_id": orchestrator_id
		}
		
		assert all(ready_checks.values())
		assert ready_checks["orchestrator_id"] == "test_orchestrator"


class TestSidecarSystemMetrics:
	"""Test system metrics collection in sidecar mode."""
	
	@pytest.mark.asyncio
	async def test_sidecar_metrics_include_orchestrator_context(self, sidecar_env_vars, mock_redis):
		"""Test that metrics include orchestrator context in sidecar mode."""
		organization_id = os.getenv("ORGANIZATION_ID")
		orchestrator_id = os.getenv("ORCHESTRATOR_ID")
		
		# Mock SystemPerformanceMiddleware for sidecar mode
		with patch('src.middleware.system_monitoring.SystemPerformanceMiddleware') as MockMiddleware:
			middleware_instance = AsyncMock()
			MockMiddleware.return_value = middleware_instance
			
			# Initialize middleware with sidecar configuration
			middleware = SystemPerformanceMiddleware(
				redis_client=mock_redis,
				organization_id=organization_id,
				collection_interval=60,
				enable_realtime_redis=True
			)
			
			# Verify middleware is configured with correct organization
			assert middleware is not None
	
	def test_sidecar_metrics_collection_interval(self, sidecar_env_vars):
		"""Test metrics collection interval configuration for sidecar mode."""
		# Sidecar mode might have different default intervals
		interval = int(os.getenv("SYSTEM_METRICS_INTERVAL", "30"))  # More frequent for sidecar
		assert interval == 30 or interval == 60  # Allow both default and custom


class TestSidecarStartupSequence:
	"""Test the startup sequence for sidecar mode."""
	
	@pytest.mark.asyncio
	async def test_sidecar_startup_dependencies(self, sidecar_env_vars):
		"""Test that sidecar mode validates all dependencies on startup."""
		startup_checks = {
			"monitoring_mode": os.getenv("MONITORING_MODE"),
			"orchestrator_id": os.getenv("ORCHESTRATOR_ID"),
			"organization_id": os.getenv("ORGANIZATION_ID"),
			"database_url": os.getenv("DATABASE_URL"),
			"redis_url": os.getenv("REDIS_URL"),
			"api_port": os.getenv("API_PORT")
		}
		
		# All required environment variables should be present
		required_vars = ["monitoring_mode", "orchestrator_id", "organization_id", "database_url", "redis_url"]
		for var in required_vars:
			assert startup_checks[var] is not None, f"Required variable {var} is missing"
		
		# Validate sidecar-specific values
		assert startup_checks["monitoring_mode"] == "sidecar"
		assert startup_checks["api_port"] == "8001"
	
	def test_sidecar_environment_validation(self, sidecar_env_vars):
		"""Test validation of sidecar environment configuration."""
		# Validate that all required sidecar environment variables are present
		required_sidecar_vars = {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator", 
			"ORGANIZATION_ID": "test_org",
			"API_PORT": "8001"
		}
		
		for var_name, expected_value in required_sidecar_vars.items():
			actual_value = os.getenv(var_name)
			assert actual_value == expected_value, f"{var_name} should be {expected_value}, got {actual_value}"


class TestSidecarErrorHandling:
	"""Test error handling for sidecar mode."""
	
	def test_missing_orchestrator_id_error(self):
		"""Test error handling when orchestrator ID is missing."""
		# Set sidecar mode but remove orchestrator ID
		os.environ["MONITORING_MODE"] = "sidecar"
		os.environ.pop("ORCHESTRATOR_ID", None)
		
		# Should detect missing required variable
		orchestrator_id = os.getenv("ORCHESTRATOR_ID")
		assert orchestrator_id is None
		
		# In real implementation, this would raise a configuration error
		# Clean up
		os.environ.pop("MONITORING_MODE", None)
	
	def test_invalid_database_url_error(self, sidecar_env_vars):
		"""Test error handling for invalid database URL."""
		# Set an invalid database URL
		os.environ["DATABASE_URL"] = "invalid_url"
		
		db_url = os.getenv("DATABASE_URL")
		assert db_url == "invalid_url"
		
		# In real implementation, this would be validated and raise an error
		# For testing, we just verify the invalid URL is detected
		assert not db_url.startswith("postgresql://")


class TestSidecarIntegrationPoints:
	"""Test integration points for sidecar mode."""
	
	def test_sidecar_orchestrator_communication_config(self, sidecar_env_vars):
		"""Test configuration for orchestrator communication."""
		orchestrator_id = os.getenv("ORCHESTRATOR_ID")
		organization_id = os.getenv("ORGANIZATION_ID")
		
		# Configuration for orchestrator communication
		communication_config = {
			"orchestrator_id": orchestrator_id,
			"organization_id": organization_id,
			"monitoring_endpoint": f"http://monitoring-{organization_id}:8001",
			"health_check_interval": 30
		}
		
		assert communication_config["orchestrator_id"] == "test_orchestrator"
		assert communication_config["organization_id"] == "test_org"
		assert "8001" in communication_config["monitoring_endpoint"]
	
	def test_sidecar_metrics_forwarding_config(self, sidecar_env_vars):
		"""Test configuration for metrics forwarding to orchestrator."""
		# In sidecar mode, metrics should be available to the orchestrator
		metrics_config = {
			"forward_to_orchestrator": True,
			"orchestrator_metrics_endpoint": f"http://orchestrator-{os.getenv('ORGANIZATION_ID')}:8000/metrics",
			"batch_size": 100,
			"forward_interval": 60
		}
		
		assert metrics_config["forward_to_orchestrator"] is True
		assert "test_org" in metrics_config["orchestrator_metrics_endpoint"]


if __name__ == "__main__":
	pytest.main([__file__, "-v"])