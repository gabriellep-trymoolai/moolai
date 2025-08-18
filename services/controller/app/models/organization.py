"""Organization model for controller service."""

from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
from ..db.database import Base


class Organization(Base):
	"""Global organization table for controller service."""
	__tablename__ = "organizations"
	
	# Primary key
	organization_id = Column(String(255), primary_key=True)  # Format: "org_001"
	
	# Basic organization information
	name = Column(String(255), unique=True, nullable=False, index=True)
	slug = Column(String(100), unique=True, nullable=False, index=True)
	display_name = Column(String(255))
	description = Column(Text)
	
	# Organization status
	is_active = Column(Boolean, default=True, nullable=False)
	is_verified = Column(Boolean, default=False, nullable=False)
	
	# Subscription and billing
	subscription_tier = Column(String(50), default="free")  # free, pro, enterprise
	subscription_status = Column(String(50), default="active")  # active, cancelled, suspended
	billing_cycle = Column(String(20), default="monthly")  # monthly, yearly
	
	# Usage limits and quotas
	monthly_token_limit = Column(Integer, default=100000)
	daily_request_limit = Column(Integer, default=1000)
	monthly_token_usage = Column(Integer, default=0)
	daily_request_usage = Column(Integer, default=0)
	
	# Billing and costs
	monthly_cost_usd = Column(Float, default=0.0)
	total_cost_usd = Column(Float, default=0.0)
	last_billing_date = Column(DateTime)
	next_billing_date = Column(DateTime)
	
	# LLM configuration defaults
	allowed_models = Column(JSON, default=["gpt-3.5-turbo"])  # List of allowed models
	default_model = Column(String(100), default="gpt-3.5-turbo")
	max_tokens_per_request = Column(Integer, default=4000)
	
	# Content filtering and security
	enable_content_filtering = Column(Boolean, default=True)
	content_filter_level = Column(String(20), default="medium")  # low, medium, high
	enable_audit_logging = Column(Boolean, default=True)
	data_retention_days = Column(Integer, default=90)
	
	# Organization settings and configuration
	settings = Column(JSON, default={})  # Flexible settings storage
	branding = Column(JSON, default={})  # Logo, colors, custom branding
	integrations = Column(JSON, default={})  # External service integrations
	
	# Contact and business information
	admin_email = Column(String(255))
	support_email = Column(String(255))
	billing_email = Column(String(255))
	website = Column(String(255))
	industry = Column(String(100))
	company_size = Column(String(50))  # "1-10", "11-50", "51-200", etc.
	
	# Address information
	billing_address = Column(JSON, default={})  # Structured billing address
	business_address = Column(JSON, default={})  # Structured business address
	
	# Compliance and legal
	terms_accepted = Column(Boolean, default=False)
	terms_accepted_at = Column(DateTime)
	privacy_policy_accepted = Column(Boolean, default=False)
	gdpr_compliant = Column(Boolean, default=True)
	
	# Orchestrator assignments
	orchestrator_count = Column(Integer, default=0)  # Number of assigned orchestrators
	max_orchestrators = Column(Integer, default=1)  # Maximum allowed orchestrators
	
	# Administrative
	created_by = Column(String(255), ForeignKey("users.user_id"))
	managed_by = Column(String(255), ForeignKey("users.user_id"))
	
	# Timestamps
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
	deleted_at = Column(DateTime)  # Soft delete
	last_activity = Column(DateTime)
	
	def __repr__(self):
		return f"<Organization(organization_id={self.organization_id}, name='{self.name}', slug='{self.slug}')>"