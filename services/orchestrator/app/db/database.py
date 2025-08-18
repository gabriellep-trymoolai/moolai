"""Database configuration for orchestrator service."""

import os
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


class DatabaseManager:
	"""Manages database connections for orchestrator service."""
	
	def __init__(self):
		# Orchestrator database (client-facing data)
		self._async_engine: Optional[AsyncEngine] = None
		self._async_session_factory: Optional[sessionmaker] = None
		self._sync_engine = None
		
		# Monitoring database (system performance data)
		self._monitoring_async_engine: Optional[AsyncEngine] = None
		self._monitoring_async_session_factory: Optional[sessionmaker] = None
		self._monitoring_sync_engine = None
		
	def get_database_url(self) -> str:
		"""Get the orchestrator database URL from environment."""
		database_url = os.getenv("DATABASE_URL")
		if not database_url:
			# Default database URL for orchestrator
			database_url = "postgresql+asyncpg://localhost/moolai_orchestrator"
		return database_url
	
	def get_monitoring_database_url(self) -> str:
		"""Get the monitoring database URL from environment."""
		monitoring_url = os.getenv("MONITORING_DATABASE_URL")
		if not monitoring_url:
			# Generate monitoring URL based on orchestrator URL
			base_url = self.get_database_url()
			# Replace the database name with monitoring database
			if "orchestrator_org_001" in base_url:
				monitoring_url = base_url.replace("orchestrator_org_001", "monitoring_org_001")
			elif "orchestrator_org_002" in base_url:
				monitoring_url = base_url.replace("orchestrator_org_002", "monitoring_org_002")
			else:
				# Default monitoring database
				monitoring_url = base_url.replace("/moolai_orchestrator", "/moolai_monitoring")
		return monitoring_url
	
	def get_sync_database_url(self) -> str:
		"""Get the synchronous database URL for migrations."""
		async_url = self.get_database_url()
		# Convert async URL to sync URL for migrations
		if "postgresql+asyncpg://" in async_url:
			return async_url.replace("postgresql+asyncpg://", "postgresql://")
		elif "postgresql://" in async_url:
			return async_url
		else:
			# Handle other async drivers
			if "+aio" in async_url:
				return async_url.replace("+aiosqlite", "").replace("+aio", "")
			return async_url.replace("+asyncpg", "")
	
	@property
	def async_engine(self) -> AsyncEngine:
		"""Get or create the async database engine."""
		if self._async_engine is None:
			database_url = self.get_database_url()
			print(f"Creating orchestrator async engine for: {database_url.split('@')[-1] if '@' in database_url else database_url}")
			self._async_engine = create_async_engine(
				database_url,
				echo=False,
				pool_pre_ping=True,
				pool_recycle=3600,
			)
		return self._async_engine
	
	@property
	def sync_engine(self):
		"""Get or create the sync database engine."""
		if self._sync_engine is None:
			sync_url = self.get_sync_database_url()
			self._sync_engine = create_engine(
				sync_url,
				echo=False,
				pool_pre_ping=True,
				pool_recycle=3600,
			)
		return self._sync_engine
	
	@property
	def async_session_factory(self) -> sessionmaker:
		"""Get or create the async session factory."""
		if self._async_session_factory is None:
			self._async_session_factory = sessionmaker(
				self.async_engine,
				class_=AsyncSession,
				expire_on_commit=False
			)
		return self._async_session_factory
	
	@property
	def monitoring_async_engine(self) -> AsyncEngine:
		"""Get or create the monitoring async database engine."""
		if self._monitoring_async_engine is None:
			monitoring_url = self.get_monitoring_database_url()
			print(f"Creating monitoring async engine for: {monitoring_url.split('@')[-1] if '@' in monitoring_url else monitoring_url}")
			self._monitoring_async_engine = create_async_engine(
				monitoring_url,
				echo=False,
				pool_pre_ping=True,
				pool_recycle=3600,
			)
		return self._monitoring_async_engine
	
	@property
	def monitoring_async_session_factory(self) -> sessionmaker:
		"""Get or create the monitoring async session factory."""
		if self._monitoring_async_session_factory is None:
			self._monitoring_async_session_factory = sessionmaker(
				self.monitoring_async_engine,
				class_=AsyncSession,
				expire_on_commit=False
			)
		return self._monitoring_async_session_factory
	
	async def get_session(self) -> AsyncSession:
		"""Get an orchestrator database session."""
		session_factory = self.async_session_factory
		session = session_factory()
		try:
			yield session
		finally:
			await session.close()
	
	async def get_monitoring_session(self) -> AsyncSession:
		"""Get a monitoring database session."""
		session_factory = self.monitoring_async_session_factory
		session = session_factory()
		try:
			yield session
		finally:
			await session.close()
	
	async def test_connection(self) -> bool:
		"""Test orchestrator database connection."""
		try:
			async with self.async_engine.begin() as conn:
				await conn.execute(text("SELECT 1"))
			return True
		except Exception as e:
			print(f"Orchestrator database connection test failed: {e}")
			return False
	
	async def test_monitoring_connection(self) -> bool:
		"""Test monitoring database connection."""
		try:
			async with self.monitoring_async_engine.begin() as conn:
				await conn.execute(text("SELECT 1"))
			return True
		except Exception as e:
			print(f"Monitoring database connection test failed: {e}")
			return False
	
	async def init_database(self):
		"""Initialize orchestrator database tables."""
		# Import orchestrator models to ensure they're registered with OrchestratorBase.metadata
		from ..models.user import User
		from ..models.org import Organization  
		from ..models.llm_config import LLMConfig
		from ..models.prompt import Prompt
		from ..models.prompt_execution import PromptExecution
		from ..models.firewall_log import FirewallLog
		
		print(f"Creating orchestrator database tables...")
		print(f"Registered orchestrator tables: {list(OrchestratorBase.metadata.tables.keys())}")
		
		async with self.async_engine.begin() as conn:
			await conn.run_sync(OrchestratorBase.metadata.create_all)
		
		print(f"Orchestrator database tables created successfully!")
	
	async def init_monitoring_database(self):
		"""Initialize monitoring database tables."""
		# Import monitoring models to ensure they're registered with MonitoringBase.metadata
		from ..monitoring.models.system_metrics import UserSystemPerformance, OrchestratorVersionHistory, SystemPerformanceAggregated, SystemAlert
		from ..monitoring.models.user_metrics import UserLLMStatistics, UserLLMRealtime, UserSession
		
		print(f"Creating monitoring database tables...")
		print(f"Registered monitoring tables: {list(MonitoringBase.metadata.tables.keys())}")
		
		async with self.monitoring_async_engine.begin() as conn:
			await conn.run_sync(MonitoringBase.metadata.create_all)
		
		print(f"Monitoring database tables created successfully!")
	
	async def close(self):
		"""Close database connections."""
		if self._async_engine:
			await self._async_engine.dispose()
		if self._sync_engine:
			self._sync_engine.dispose()
		if self._monitoring_async_engine:
			await self._monitoring_async_engine.dispose()
		if self._monitoring_sync_engine:
			self._monitoring_sync_engine.dispose()
	
	def reset(self):
		"""Reset the database manager - useful for testing."""
		if self._async_engine:
			self._async_engine = None
		if self._sync_engine:
			try:
				self._sync_engine.dispose()
			except:
				pass
			self._sync_engine = None
		self._async_session_factory = None


# Global database manager instance
db_manager = DatabaseManager()

# Base classes for different databases
OrchestratorBase = declarative_base()
MonitoringBase = declarative_base()

# Legacy compatibility - use OrchestratorBase for main database
Base = OrchestratorBase

# Dependency functions
async def get_db():
	"""Dependency to get orchestrator database session."""
	async for session in db_manager.get_session():
		yield session

async def get_monitoring_db():
	"""Dependency to get monitoring database session."""
	async for session in db_manager.get_monitoring_session():
		yield session

async def init_db():
	"""Initialize both orchestrator and monitoring database tables."""
	await db_manager.init_database()
	await db_manager.init_monitoring_database()