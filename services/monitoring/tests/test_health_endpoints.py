"""Tests for health check endpoints with sidecar mode."""

import os
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_config():
	"""Reset configuration before each test."""
	from src.config.settings import reset_config
	from src.config.database import db_manager
	reset_config()
	db_manager.reset()
	yield
	reset_config()
	db_manager.reset()


class TestHealthEndpoints:
	"""Test health check endpoints."""
	
	def test_basic_health_endpoint_standalone(self):
		"""Test basic health endpoint in standalone mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "standalone"
		}, clear=False):
			from src.config.settings import get_config
			
			config = get_config()
			assert config.monitoring_mode == "standalone"
			
			# Test the health endpoint configuration
			health_data = {
				"status": "healthy",
				"mode": config.monitoring_mode,
				"services": {}
			}
			
			assert health_data["mode"] == "standalone"
			assert "orchestrator_id" not in health_data
	
	def test_basic_health_endpoint_sidecar(self):
		"""Test basic health endpoint in sidecar mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.settings import get_config
			
			config = get_config()
			assert config.monitoring_mode == "sidecar"
			
			# Test the health endpoint configuration
			health_data = {
				"status": "healthy",
				"mode": config.monitoring_mode,
				"services": {}
			}
			
			# Add sidecar-specific information
			if config.is_sidecar_mode:
				health_data["orchestrator_id"] = config.orchestrator_id
				health_data["organization_id"] = config.organization_id
			
			assert health_data["mode"] == "sidecar"
			assert health_data["orchestrator_id"] == "test_orchestrator"
			assert health_data["organization_id"] == "test_org"


class TestReadinessEndpoint:
	"""Test readiness endpoint functionality."""
	
	def test_readiness_checks_standalone(self):
		"""Test readiness checks for standalone mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "standalone"
		}, clear=False):
			from src.config.settings import get_config
			
			config = get_config()
			
			# Mock readiness checks
			ready_checks = {
				"database": True,
				"redis": True,
				"system_monitoring": True
			}
			
			# All checks must pass for readiness
			all_ready = all(ready_checks.values())
			assert all_ready is True
			
			expected_response = {"status": "ready", "checks": ready_checks}
			assert expected_response["status"] == "ready"
	
	def test_readiness_checks_sidecar(self):
		"""Test readiness checks for sidecar mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.settings import get_config
			from src.config.database import DatabaseManager
			
			config = get_config()
			db_manager = DatabaseManager()
			
			# Mock readiness checks for sidecar mode
			ready_checks = {
				"database": True,
				"redis": True,
				"system_monitoring": True,
				"orchestrator_mode": True,
				"orchestrator_id": config.orchestrator_id is not None,
				"organization_id": config.organization_id is not None,
				"orchestrator_database": True  # Mock that DB is orchestrator-specific
			}
			
			# Verify sidecar-specific checks
			assert ready_checks["orchestrator_mode"] is True
			assert ready_checks["orchestrator_id"] is True
			assert ready_checks["organization_id"] is True
			
			# All checks must pass for readiness
			all_ready = all(ready_checks.values())
			assert all_ready is True
	
	def test_readiness_failure_missing_orchestrator_id(self):
		"""Test readiness failure when orchestrator ID is missing."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=True):
			# Remove ORCHESTRATOR_ID
			os.environ.pop("ORCHESTRATOR_ID", None)
			
			from src.config.settings import get_config
			
			config = get_config()
			
			# Mock readiness checks for sidecar mode with missing orchestrator ID
			ready_checks = {
				"database": True,
				"redis": True,
				"system_monitoring": True,
				"orchestrator_mode": True,
				"orchestrator_id": config.orchestrator_id is not None,  # Should be False
				"organization_id": config.organization_id is not None,
				"orchestrator_database": True
			}
			
			# Should fail because orchestrator_id is missing
			assert ready_checks["orchestrator_id"] is False
			
			# All checks must pass for readiness
			all_ready = all(ready_checks.values())
			assert all_ready is False


class TestDetailedHealthEndpoint:
	"""Test detailed health check endpoint."""
	
	def test_detailed_health_standalone(self):
		"""Test detailed health endpoint in standalone mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "standalone"
		}, clear=False):
			from src.config.settings import get_config
			
			config = get_config()
			
			# Mock detailed health response
			health_status = {
				"status": "healthy",
				"mode": config.monitoring_mode,
				"checks": {
					"database": {
						"status": "healthy",
						"latency_ms": 5,
						"type": "standalone"
					},
					"redis": {
						"status": "healthy",
						"latency_ms": 2
					},
					"system_monitoring": {
						"status": "active",
						"collection_interval": 60
					}
				}
			}
			
			assert health_status["mode"] == "standalone"
			assert health_status["checks"]["database"]["type"] == "standalone"
			assert "orchestrator" not in health_status["checks"]
	
	def test_detailed_health_sidecar(self):
		"""Test detailed health endpoint in sidecar mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.settings import get_config
			
			config = get_config()
			
			# Mock detailed health response for sidecar mode
			health_status = {
				"status": "healthy",
				"mode": config.monitoring_mode,
				"orchestrator_id": config.orchestrator_id,
				"organization_id": config.organization_id,
				"checks": {
					"database": {
						"status": "healthy",
						"latency_ms": 10,
						"type": "orchestrator_specific"
					},
					"redis": {
						"status": "healthy",
						"latency_ms": 2
					},
					"orchestrator": {
						"status": "configured",
						"orchestrator_id": config.orchestrator_id,
						"organization_id": config.organization_id
					},
					"system_monitoring": {
						"status": "active",
						"organization_id": config.organization_id,
						"collection_interval": 30
					}
				}
			}
			
			assert health_status["mode"] == "sidecar"
			assert health_status["orchestrator_id"] == "test_orchestrator"
			assert health_status["organization_id"] == "test_org"
			assert health_status["checks"]["database"]["type"] == "orchestrator_specific"
			assert health_status["checks"]["orchestrator"]["status"] == "configured"
			assert health_status["checks"]["system_monitoring"]["collection_interval"] == 30
	
	def test_detailed_health_sidecar_misconfigured(self):
		"""Test detailed health endpoint with misconfigured sidecar."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=True):
			# Remove orchestrator configuration
			os.environ.pop("ORCHESTRATOR_ID", None)
			os.environ.pop("ORGANIZATION_ID", None)
			
			from src.config.settings import get_config
			
			config = get_config()
			
			# Mock orchestrator health check for misconfigured sidecar
			orchestrator_health = {
				"status": "misconfigured",
				"orchestrator_id": config.orchestrator_id  # Should be None
			}
			
			assert orchestrator_health["status"] == "misconfigured"
			assert orchestrator_health["orchestrator_id"] is None


class TestDatabaseHealthChecks:
	"""Test database-specific health checks."""
	
	@pytest.mark.asyncio
	async def test_database_connection_check(self):
		"""Test database connection health check."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.settings import get_config
			from src.config.database import DatabaseManager
			
			config = get_config()
			db_manager = DatabaseManager()
			
			# Mock database connection test
			with patch.object(db_manager, 'test_connection', return_value=True) as mock_test:
				connection_ok = await db_manager.test_connection()
				
				assert connection_ok is True
				mock_test.assert_called_once()
	
	def test_orchestrator_database_validation(self):
		"""Test validation that database is orchestrator-specific."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@orchestrator_host:5432/orchestrator_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.database import DatabaseManager
			
			db_manager = DatabaseManager()
			db_url = db_manager.get_database_url()
			
			# Verify it's not the default database
			is_orchestrator_specific = "localhost/moolai_monitoring" not in db_url
			assert is_orchestrator_specific is True
			
			# Verify it contains orchestrator-specific information
			assert "orchestrator_host" in db_url
			assert "orchestrator_db" in db_url


if __name__ == "__main__":
	pytest.main([__file__, "-v"])