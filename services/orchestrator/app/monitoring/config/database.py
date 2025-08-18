"""Database configuration for sidecar and standalone modes."""

import os
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .settings import get_config


class DatabaseManager:
	"""Manages database connections for different modes."""
	
	def __init__(self):
		self._async_engine: Optional[AsyncEngine] = None
		self._async_session_factory: Optional[sessionmaker] = None
		self._sync_engine = None
		
	def get_database_url(self) -> str:
		"""Get the appropriate database URL based on configuration."""
		config = get_config()  # Get fresh config each time
		if config.is_sidecar_mode:
			# In sidecar mode, use the orchestrator-specific database
			if not config.database_url:
				raise ValueError("DATABASE_URL is required for sidecar mode")
			return config.database_url
		else:
			# In standalone mode, use default or configured database
			return config.database_url or "postgresql+asyncpg://localhost/moolai_monitoring"
	
	def get_sync_database_url(self) -> str:
		"""Get the synchronous database URL for migrations."""
		async_url = self.get_database_url()
		# Convert async URL to sync URL for migrations
		if "postgresql+asyncpg://" in async_url:
			return async_url.replace("postgresql+asyncpg://", "postgresql://")
		elif "postgresql://" in async_url:
			return async_url
		else:
			# Handle other async drivers like aiosqlite
			if "+aio" in async_url:
				return async_url.replace("+aiosqlite", "").replace("+aio", "")
			return async_url.replace("+asyncpg", "")
	
	@property
	def async_engine(self) -> AsyncEngine:
		"""Get or create the async database engine."""
		if self._async_engine is None:
			database_url = self.get_database_url()
			print(f"Creating async engine for: {database_url.split('@')[-1] if '@' in database_url else database_url}")
			self._async_engine = create_async_engine(
				database_url,
				echo=False,  # Disable echo in production
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
	
	async def get_session(self) -> AsyncSession:
		"""Get a database session."""
		session_factory = self.async_session_factory
		session = session_factory()
		try:
			yield session
		finally:
			await session.close()
	
	async def test_connection(self) -> bool:
		"""Test database connection."""
		try:
			async with self.async_engine.begin() as conn:
				await conn.execute(text("SELECT 1"))
			return True
		except Exception as e:
			print(f"Database connection test failed: {e}")
			return False
	
	async def init_database(self):
		"""Initialize database tables."""
		# Import all models to ensure they're registered with Base.metadata
		from ..models.user_metrics import UserLLMStatistics, UserLLMRealtime, UserSession
		from ..models.system_metrics import (
			UserSystemPerformance, 
			OrchestratorVersionHistory, 
			SystemPerformanceAggregated, 
			SystemAlerts
		)
		from ..models import Base
		
		print(f"Creating database tables...")
		print(f"Registered tables: {list(Base.metadata.tables.keys())}")
		
		async with self.async_engine.begin() as conn:
			await conn.run_sync(Base.metadata.create_all)
		
		print(f"Database tables created successfully!")
	
	async def close(self):
		"""Close database connections."""
		if self._async_engine:
			await self._async_engine.dispose()
		if self._sync_engine:
			self._sync_engine.dispose()
	
	def reset(self):
		"""Reset the database manager - useful for testing."""
		if self._async_engine:
			# Don't await here as this might be called from sync context
			self._async_engine = None
		if self._sync_engine:
			try:
				self._sync_engine.dispose()
			except:
				pass  # Ignore errors during testing
			self._sync_engine = None
		self._async_session_factory = None


# Global database manager instance
db_manager = DatabaseManager()

# Base class for models
Base = declarative_base()

# Compatibility functions for existing code
async def get_db():
	"""Dependency to get database session."""
	async for session in db_manager.get_session():
		yield session

async def init_db():
	"""Initialize database tables."""
	await db_manager.init_database()