"""Tests for database configuration in sidecar mode."""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncEngine


class TestDatabaseConfiguration:
	"""Test database configuration for different modes."""
	
	def test_sidecar_database_url_configuration(self):
		"""Test that sidecar mode uses the configured database URL."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test_user:test_pass@test_host:5432/test_db",
			"REDIS_URL": "redis://test_redis:6379/0"
		}, clear=False):
			from src.config.settings import reset_config, MonitoringConfig
			from src.config.database import DatabaseManager
			
			reset_config()
			config = MonitoringConfig()
			db_manager = DatabaseManager()
			
			# Test database URL configuration
			db_url = db_manager.get_database_url()
			assert db_url == "postgresql+asyncpg://test_user:test_pass@test_host:5432/test_db"
			
			# Test sync URL conversion
			sync_url = db_manager.get_sync_database_url()
			assert sync_url == "postgresql://test_user:test_pass@test_host:5432/test_db"
	
	def test_standalone_database_url_configuration(self):
		"""Test that standalone mode uses default or configured database URL."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "standalone"
		}, clear=True):
			from src.config.settings import reset_config, MonitoringConfig
			from src.config.database import DatabaseManager
			
			reset_config()
			config = MonitoringConfig()
			db_manager = DatabaseManager()
			
			# Test default database URL
			db_url = db_manager.get_database_url()
			assert db_url == "postgresql+asyncpg://localhost/moolai_monitoring"
	
	def test_standalone_custom_database_url(self):
		"""Test standalone mode with custom database URL."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "standalone",
			"DATABASE_URL": "postgresql+asyncpg://custom_host:5432/custom_db"
		}, clear=False):
			from src.config.settings import reset_config, MonitoringConfig
			from src.config.database import DatabaseManager
			
			reset_config()
			config = MonitoringConfig()
			db_manager = DatabaseManager()
			
			db_url = db_manager.get_database_url()
			assert db_url == "postgresql+asyncpg://custom_host:5432/custom_db"
	
	def test_sidecar_missing_database_url_error(self):
		"""Test that sidecar mode raises error when DATABASE_URL is missing."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"REDIS_URL": "redis://test_redis:6379/0"
		}, clear=True):
			# Remove DATABASE_URL
			os.environ.pop("DATABASE_URL", None)
			
			from src.config.settings import reset_config, MonitoringConfig
			from src.config.database import DatabaseManager
			
			reset_config()
			config = MonitoringConfig()
			db_manager = DatabaseManager()
			
			with pytest.raises(ValueError) as exc_info:
				db_manager.get_database_url()
			
			assert "DATABASE_URL is required for sidecar mode" in str(exc_info.value)


class TestDatabaseManager:
	"""Test DatabaseManager functionality."""
	
	@pytest.mark.asyncio
	async def test_database_manager_properties(self):
		"""Test DatabaseManager properties initialization."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.settings import reset_config
			from src.config.database import DatabaseManager
			
			reset_config()
			db_manager = DatabaseManager()
			
			# Test that properties are initially None
			assert db_manager._async_engine is None
			assert db_manager._async_session_factory is None
			assert db_manager._sync_engine is None
			
			# Test async engine creation (mocked)
			with patch('src.config.database.create_async_engine') as mock_create_async:
				mock_engine = AsyncMock()
				mock_create_async.return_value = mock_engine
				
				engine = db_manager.async_engine
				
				# Verify engine was created with correct parameters
				mock_create_async.assert_called_once_with(
					"postgresql+asyncpg://test:test@localhost:5432/test_db",
					echo=False,
					pool_pre_ping=True,
					pool_recycle=3600,
				)
				
				# Verify engine is cached
				assert db_manager._async_engine is mock_engine
				assert db_manager.async_engine is mock_engine  # Should return cached instance
	
	@pytest.mark.asyncio
	async def test_database_connection_test(self):
		"""Test database connection testing."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.settings import reset_config
			from src.config.database import DatabaseManager
			
			reset_config()
			db_manager = DatabaseManager()
			
			# Mock the async engine and connection
			mock_engine = AsyncMock()
			mock_conn = AsyncMock()
			mock_engine.begin.return_value.__aenter__.return_value = mock_conn
			
			with patch.object(db_manager, 'async_engine', mock_engine):
				# Test successful connection
				result = await db_manager.test_connection()
				assert result is True
				mock_conn.execute.assert_called_once_with("SELECT 1")
			
			# Test failed connection
			mock_engine.begin.side_effect = Exception("Connection failed")
			
			with patch.object(db_manager, 'async_engine', mock_engine):
				result = await db_manager.test_connection()
				assert result is False
	
	@pytest.mark.asyncio
	async def test_database_initialization(self):
		"""Test database table initialization."""
		with patch.dict(os.environ, {
			"MONITORING_MODE": "sidecar",
			"ORCHESTRATOR_ID": "test_orchestrator",
			"ORGANIZATION_ID": "test_org",
			"DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
			"REDIS_URL": "redis://localhost:6379/0"
		}, clear=False):
			from src.config.settings import reset_config
			from src.config.database import DatabaseManager
			
			reset_config()
			db_manager = DatabaseManager()
			
			# Mock the async engine and connection
			mock_engine = AsyncMock()
			mock_conn = AsyncMock()
			mock_engine.begin.return_value.__aenter__.return_value = mock_conn
			
			with patch.object(db_manager, 'async_engine', mock_engine):
				await db_manager.init_database()
				
				# Verify that create_all was called
				mock_conn.run_sync.assert_called_once()
	
	def test_database_manager_reset(self):
		"""Test DatabaseManager reset functionality."""
		from src.config.database import DatabaseManager
		
		db_manager = DatabaseManager()
		
		# Set some mock values
		db_manager._async_engine = AsyncMock()
		db_manager._sync_engine = MagicMock()
		db_manager._async_session_factory = MagicMock()
		
		# Reset the manager
		db_manager.reset()
		
		# Verify everything is reset
		assert db_manager._async_engine is None
		assert db_manager._sync_engine is None
		assert db_manager._async_session_factory is None


class TestDatabaseURLConversion:
	"""Test database URL conversion logic."""
	
	def test_async_to_sync_url_conversion(self):
		"""Test conversion from async to sync database URLs."""
		from src.config.database import DatabaseManager
		
		db_manager = DatabaseManager()
		
		test_cases = [
			{
				"input": "postgresql+asyncpg://user:pass@host:5432/db",
				"expected": "postgresql://user:pass@host:5432/db"
			},
			{
				"input": "postgresql://user:pass@host:5432/db",
				"expected": "postgresql://user:pass@host:5432/db"
			},
			{
				"input": "sqlite+aiosqlite:///test.db",
				"expected": "sqlite:///test.db"
			}
		]
		
		for case in test_cases:
			with patch.object(db_manager, 'get_database_url', return_value=case["input"]):
				result = db_manager.get_sync_database_url()
				assert result == case["expected"], f"Failed for {case['input']}"


if __name__ == "__main__":
	pytest.main([__file__, "-v"])