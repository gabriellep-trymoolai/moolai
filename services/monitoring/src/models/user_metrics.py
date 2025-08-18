"""User LLM metrics database models."""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, 
    DECIMAL, JSON, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from ..config.database import Base


class UserLLMStatistics(Base):
    """Aggregated user LLM statistics table."""
    __tablename__ = "user_llm_statistics"
    
    # Primary identifiers
    user_id = Column(String(255), primary_key=True)  # Format: "user_001_org_001"
    organization_id = Column(String(255), primary_key=True)  # Format: "org_001"
    timestamp = Column(DateTime, primary_key=True)
    time_bucket = Column(String(20), primary_key=True)  # 'minute', 'hour', 'day', 'month'
    
    # Core metrics
    total_queries = Column(Integer, default=0)
    successful_queries = Column(Integer, default=0)
    failed_queries = Column(Integer, default=0)
    total_cost = Column(DECIMAL(12, 6), default=0.00)
    
    # Token metrics
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    
    # Performance metrics
    avg_latency_ms = Column(Integer)
    p50_latency_ms = Column(Integer)
    p95_latency_ms = Column(Integer)
    p99_latency_ms = Column(Integer)
    
    # User context
    department = Column(String(100))
    user_role = Column(String(50))
    
    # Detailed breakdowns
    agent_breakdown = Column(JSONB)
    model_breakdown = Column(JSONB)
    feature_usage = Column(JSONB)
    error_summary = Column(JSONB)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_user_llm_stats_user_time', 'user_id', 'timestamp'),
        Index('idx_user_llm_stats_org_time', 'organization_id', 'timestamp'),
        Index('idx_user_llm_stats_dept', 'department', 'timestamp'),
        Index('idx_user_llm_stats_bucket', 'time_bucket', 'timestamp'),
    )


class UserLLMRealtime(Base):
    """Real-time buffer for user LLM requests."""
    __tablename__ = "user_llm_realtime"
    
    request_id = Column(String(255), primary_key=True)  # Format: "req_001_org_001"
    user_id = Column(String(255), nullable=False)  # Format: "user_001_org_001"
    organization_id = Column(String(255), nullable=False)  # Format: "org_001"
    
    # Request details
    agent_type = Column(String(50), nullable=False, default='prompt_response')
    model_name = Column(String(100))
    model_provider = Column(String(50))
    api_endpoint = Column(String(200))
    
    # Prompt details
    prompt_text = Column(String)  # Store first 500 chars for analysis
    prompt_tokens = Column(Integer)
    
    # Response details
    response_text = Column(String)  # Store first 500 chars for analysis
    response_tokens = Column(Integer)
    
    # Metrics
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cost = Column(DECIMAL(10, 6))
    latency_ms = Column(Integer)
    
    # Status
    status = Column(String(20))  # 'success', 'error', 'timeout'
    error_type = Column(String(100))
    error_message = Column(String)
    
    # Caching
    cache_hit = Column(Boolean, default=False)
    cache_key = Column(String(255))
    
    # Timestamps
    request_timestamp = Column(DateTime, nullable=False)
    response_timestamp = Column(DateTime)
    
    # Metadata
    department = Column(String(100))
    session_id = Column(String(255))  # Format: \"session_001_user_001\"
    trace_id = Column(String(255))  # For Langfuse integration
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_realtime_cleanup', 'created_at'),
        Index('idx_realtime_user', 'user_id', 'request_timestamp'),
        Index('idx_realtime_org', 'organization_id', 'request_timestamp'),
    )


class UserSession(Base):
    """User session tracking."""
    __tablename__ = "user_sessions"
    
    session_id = Column(String(255), primary_key=True)  # Format: "session_001_user_001"
    user_id = Column(String(255), nullable=False)  # Format: "user_001_org_001"
    organization_id = Column(String(255), nullable=False)  # Format: "org_001"
    
    # Session info
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    
    # Activity metrics
    query_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(DECIMAL(10, 4), default=0.00)
    
    # Session context
    ip_address = Column(String(45))  # Support IPv6
    user_agent = Column(String)
    department = Column(String(100))
    
    # Activity summary
    agents_used = Column(JSONB)
    models_used = Column(JSONB)
    features_accessed = Column(JSONB)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_sessions_user', 'user_id', 'start_time'),
        Index('idx_sessions_org', 'organization_id', 'start_time'),
    )