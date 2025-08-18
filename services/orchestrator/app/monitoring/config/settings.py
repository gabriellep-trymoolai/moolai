"""Configuration settings for MoolAI Monitoring System."""

import os
from typing import Optional


class MonitoringConfig:
	"""Configuration class for monitoring system."""
	
	def __init__(self):
		"""Initialize configuration from environment variables."""
		self.monitoring_mode = os.getenv("MONITORING_MODE", "standalone")
		self.orchestrator_id = os.getenv("ORCHESTRATOR_ID")
		self.organization_id = os.getenv("ORGANIZATION_ID", "default-org")
		self.api_port = int(os.getenv("API_PORT", 8001 if self.monitoring_mode == "sidecar" else 8000))
		self.api_host = os.getenv("API_HOST", "0.0.0.0")
		self.database_url = os.getenv("DATABASE_URL")
		self.redis_url = os.getenv("REDIS_URL")
		self.system_metrics_interval = int(os.getenv("SYSTEM_METRICS_INTERVAL", 
			"30" if self.monitoring_mode == "sidecar" else "60"))
	
	def validate_sidecar_configuration(self) -> None:
		"""Validate required environment variables for sidecar mode."""
		if self.monitoring_mode == "sidecar":
			required_vars = ["ORCHESTRATOR_ID", "ORGANIZATION_ID", "DATABASE_URL", "REDIS_URL"]
			missing_vars = []
			
			for var in required_vars:
				if not os.getenv(var):
					missing_vars.append(var)
			
			if missing_vars:
				raise ValueError(f"Sidecar mode requires these environment variables: {', '.join(missing_vars)}")
			
			print(f"Sidecar mode configuration validated for orchestrator: {self.orchestrator_id}")
		else:
			print(f"Running in {self.monitoring_mode} mode")
	
	def get_organization_id(self) -> str:
		"""Get organization ID based on mode."""
		if self.monitoring_mode == "sidecar":
			return self.organization_id
		return os.getenv("DEFAULT_ORGANIZATION_ID", "default-org")
	
	@property
	def is_sidecar_mode(self) -> bool:
		"""Check if running in sidecar mode."""
		return self.monitoring_mode == "sidecar"
	
	@property
	def is_standalone_mode(self) -> bool:
		"""Check if running in standalone mode."""
		return self.monitoring_mode == "standalone"


# Global configuration instance - will be initialized when first accessed
_config = None

def get_config() -> MonitoringConfig:
	"""Get the global configuration instance."""
	global _config
	if _config is None:
		_config = MonitoringConfig()
	return _config

def reset_config():
	"""Reset the global configuration - useful for testing."""
	global _config
	_config = None

# Create a property-like access for backward compatibility
config = get_config()