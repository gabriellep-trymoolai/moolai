"""Integration tests for the FastAPI application with sidecar mode."""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# Pytest fixtures to reset configuration
@pytest.fixture(autouse=True)
def reset_config():
	"""Reset configuration before each test."""
	from src.config.settings import reset_config
	reset_config()
	yield
	reset_config()


class TestAppConfiguration:
	"""Test application configuration with different modes."""
	
	def test_app_loads_in_standalone_mode(self):
		"""Test that app loads correctly in standalone mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "standalone",
			"API_PORT": "8000"
		}, clear=False):
			# Import configuration directly
			from src.config.settings import MonitoringConfig
			
			test_config = MonitoringConfig()
			assert test_config.monitoring_mode == "standalone"
			assert test_config.api_port == 8000
			
			# Import app after setting env vars
			from src.api.main import app
			
			# Basic test that the app exists and has routes
			assert app is not None
			assert len(app.routes) > 0
	
	def test_app_validates_sidecar_mode_configuration(self):
		"""Test that app validates sidecar mode configuration."""
		# Test with missing required variables
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar"
		}, clear=True):
			# Should raise an error due to missing required vars
			from src.config.settings import MonitoringConfig
			
			test_config = MonitoringConfig()
			
			with pytest.raises(ValueError) as exc_info:
				test_config.validate_sidecar_configuration()
			
			assert "requires these environment variables" in str(exc_info.value)
	
	def test_app_configures_sidecar_mode_correctly(self):
		"""Test that app configures sidecar mode with all required variables."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org", 
			"DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0",
			"API_PORT": "8001"
		}, clear=False):
			# Import configuration directly
			from src.config.settings import MonitoringConfig
			
			test_config = MonitoringConfig()
			assert test_config.monitoring_mode == "sidecar"
			assert test_config.api_port == 8001
			assert test_config.orchestrator_id == "test_orchestrator"
			assert test_config.organization_id == "test_org"


class TestHealthEndpoint:
	"""Test health endpoint with different configurations."""
	
	def test_health_endpoint_standalone_mode(self):
		"""Test health endpoint response in standalone mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "standalone"
		}, clear=False):
			from src.api.main import app
			
			with TestClient(app) as client:
				response = client.get("/health")
				assert response.status_code == 200
				
				data = response.json()
				assert data["mode"] == "standalone"
				assert "services" in data
	
	def test_health_endpoint_sidecar_mode(self):
		"""Test health endpoint response in sidecar mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql://test:test@localhost:5432/test_db", 
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			# Reset config to pick up new environment
			from src.config.settings import reset_config, get_config
			reset_config()
			config = get_config()
			
			# Verify config is set correctly
			assert config.monitoring_mode == "sidecar"
			assert config.orchestrator_id == "test_orchestrator"
			
			# Test creating a new app with the configuration
			# Note: Since the app uses the global config, we need to import after reset
			import importlib
			import src.api.main
			importlib.reload(src.api.main)
			from src.api.main import app
			
			with TestClient(app) as client:
				response = client.get("/health")
				assert response.status_code == 200
				
				data = response.json()
				assert data["mode"] == "sidecar"
				assert data["orchestrator_id"] == "test_orchestrator"
				assert data["organization_id"] == "test_org"
				assert "services" in data


class TestPortConfiguration:
	"""Test port configuration based on mode."""
	
	def test_default_port_standalone_mode(self):
		"""Test default port for standalone mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "standalone"
		}, clear=True):
			# Clear API_PORT to test default
			os.environ.pop("API_PORT", None)
			
			from src.config.settings import MonitoringConfig
			test_config = MonitoringConfig()
			assert test_config.api_port == 8000
	
	def test_default_port_sidecar_mode(self):
		"""Test default port for sidecar mode."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=True):
			# Clear API_PORT to test default
			os.environ.pop("API_PORT", None)
			
			from src.config.settings import MonitoringConfig
			test_config = MonitoringConfig()
			assert test_config.api_port == 8001
	
	def test_custom_port_override(self):
		"""Test that custom port overrides default."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"API_PORT": "9999",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.settings import MonitoringConfig
			test_config = MonitoringConfig()
			assert test_config.api_port == 9999


if __name__ == "__main__":
	pytest.main([__file__, "-v"])