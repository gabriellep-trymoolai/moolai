"""User model for orchestrator service."""

from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from datetime import datetime
from ..db.database import Base


class User(Base):
	"""User table for orchestrator service."""
	__tablename__ = "users"
	
	# Primary key
	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(String(255), unique=True, index=True)  # Format: "user_001_org_001"
	
	# Azure B2C integration
	b2c_sub = Column(String(255), unique=True, nullable=True, index=True)  # Azure B2C subject ID
	
	# Basic user information
	username = Column(String(100), unique=True, nullable=True, index=True)
	email = Column(String(255), unique=True, nullable=False, index=True)
	full_name = Column(String(255))
	
	# User roles and permissions
	roles = Column(Text, default="[]")  # JSON string of roles
	
	# User status and settings
	is_active = Column(Boolean, default=True, nullable=False)
	is_admin = Column(Boolean, default=False, nullable=False)
	
	# LLM usage preferences
	preferred_model = Column(String(100), default="gpt-3.5-turbo")
	max_tokens_per_request = Column(Integer, default=4000)
	
	# Security and privacy settings
	enable_content_filtering = Column(Boolean, default=True)
	data_retention_days = Column(Integer, default=30)
	
	# Profile information
	department = Column(String(100))
	job_title = Column(String(100))
	bio = Column(Text)
	
	# Timestamps
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	last_login = Column(DateTime)
	
	def __repr__(self):
		return f"<User(user_id={self.user_id}, username='{self.username}', email='{self.email}')>"