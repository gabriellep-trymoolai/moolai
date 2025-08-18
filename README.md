# MoolAI System - Developer Manual

> **For**: Developers, technical team, system administrators
> **Last Updated**: 2025-08-18

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Quick Start Guide](#quick-start-guide)
3. [Service Deep Dive](#service-deep-dive)
4. [Development Workflow](#development-workflow)
5. [Testing Guide](#testing-guide)
6. [Deployment Guide](#deployment-guide)
7. [Troubleshooting](#troubleshooting)
8. [Integration Patterns](#integration-patterns)
9. [Performance Optimization](#performance-optimization)

## System Architecture

### High-Level Overview
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Orchestrator   │  │  Orchestrator   │  │   Controller    │
│  (Org 001)      │  │  (Org 002)      │  │                 │
│  Port: 8000     │  │  Port: 8010     │  │  Port: 9000     │
│  ┌─────────────┐│  │  ┌─────────────┐│  │                 │
│  │ Monitoring  ││  │  │ Monitoring  ││  │                 │
│  │ EMBEDDED    ││  │  │ EMBEDDED    ││  │                 │
│  └─────────────┘│  │  └─────────────┘│  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                      │                    │
         ▼                      ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ PostgreSQL      │  │ PostgreSQL      │  │ PostgreSQL      │
│ (Org 001)       │  │ (Org 002)       │  │ (Controller)    │
│ 2 databases:    │  │ 2 databases:    │  │                 │
│ - orchestrator  │  │ - orchestrator  │  │                 │
│ - monitoring    │  │ - monitoring    │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 🚨 Critical Architecture Notes
- **Dual Database Design**: Each org has 2 databases (client data + monitoring data)  
- **Port Strategy**: Monitoring APIs available on orchestrator ports (8000, 8010)
- **Service Count**: 4 total services

## Quick Start Guide

### Prerequisites
```bash
# Required software
docker >= 20.10
docker-compose >= 2.0
python >= 3.10
git
```

### 🚀 30-Second Setup
```bash
# 1. Clone and navigate
git clone <repository>
cd mool_ai_repo

# 2. Start all services
./build.sh

# 3. Verify deployment
curl http://localhost:8000/api/v1/system/health
curl http://localhost:9000/health
```

### First Integration Test
```bash
# Test embedded monitoring
python test_system_monitoring.py

# Test orchestrator APIs
curl -X POST "http://localhost:8000/api/v1/llm/chat" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'
```

## Service Deep Dive

### 🎯 Orchestrator Service (`/services/orchestrator/`)

#### Purpose & Responsibilities
- **AI Workflow Orchestration**: LLM calls, agent coordination
- **User Management**: Organization-level user isolation
- **Embedded Monitoring**: Real-time performance tracking
- **API Gateway**: RESTful and WebSocket APIs

#### Key Files & Their Purpose
```
orchestrator/
├── app/
│   ├── main.py                    # 🔹 FastAPI app entry point
│   ├── monitoring/                # 🔹 EMBEDDED monitoring framework
│   │   ├── api/routers/          # Monitoring API endpoints
│   │   ├── middleware/           # Performance tracking middleware
│   │   ├── models/               # Monitoring database models
│   │   ├── services/             # Metrics collection logic
│   │   └── config/database_adapter.py  # DB connection adapter
│   ├── api/                      # Orchestrator APIs
│   │   ├── routes_llm.py         # LLM integration endpoints
│   │   ├── routes_users.py       # User management
│   │   └── routes_settings.py    # Configuration management
│   ├── agents/                   # AI workflow agents
│   ├── db/                       # Database configuration
│   │   └── database.py           # 🔹 Dual database manager
│   └── services/                 # Core orchestrator services
└── requirements.txt               # Python dependencies
```

#### 💡 Developer Tips
**When working in orchestrator:**
- **Monitoring changes**: Work in `app/monitoring/` subdirectory
- **API changes**: Update `app/api/` routes
- **Database changes**: Update both orchestrator and monitoring models
- **Testing**: Use `python -m pytest tests/` for orchestrator tests

**Common gotchas:**
- Don't reference port 8001 (old monitoring port) - use 8000/8010
- Monitoring is embedded - don't try to run it standalone
- Database adapter redirects monitoring to orchestrator's DB connection

### 📊 Embedded Monitoring (`/services/orchestrator/app/monitoring/`)

#### Key Components
1. **`api/routers/system_metrics.py`** - Main metrics API endpoints
2. **`middleware/system_monitoring.py`** - Automatic performance tracking
3. **`services/system_metrics.py`** - Core metrics collection logic
4. **`config/database_adapter.py`** - Database connection adapter

#### API Endpoints (on orchestrator ports)
```bash
# Health check
GET /api/v1/system/health

# Force immediate collection
POST /api/v1/system/collect/immediate?organization_id=org_001

# Get organization metrics
GET /api/v1/system/metrics/organization/org_001

# Real-time streaming
GET /api/v1/stream

# WebSocket interface
WS /ws
```

#### 💡 Developer Tips
**Adding new metrics:**
1. **Model**: Add fields to `models/system_metrics.py`
2. **Collection**: Update `services/system_metrics.py`
3. **API**: Add endpoint in `api/routers/system_metrics.py`
4. **Test**: Update `../../../test_system_monitoring.py`

**Database operations:**
- Use `database_adapter.py` for all DB connections
- Never create direct monitoring database connections
- Models inherit from orchestrator's `MonitoringBase`

**Configuration requirements:**
- Settings must include `get_config()` function for router compatibility
- Use `EmbeddedMonitoringConfig` class for embedded architecture
- Import database dependencies from `...config.database`

### 🎛️ Controller Service (`/services/controller/`)

#### Purpose & Responsibilities
- **Central Management**: Cross-organization coordination
- **Analytics**: Performance aggregation across all orchestrators
- **Organization Registry**: Multi-tenant organization management

#### Key Files & Their Purpose
```
controller/
├── app/
│   ├── main.py                   # FastAPI application entry point
│   ├── api/                      # Controller APIs
│   │   ├── routes_analytics.py   # 🔹 Cross-org analytics
│   │   ├── routes_orgs.py        # Organization management
│   │   └── routes_users.py       # Central user management
│   ├── models/                   # Database models
│   │   ├── organization.py       # Organization entities
│   │   ├── user.py               # User entities
│   │   └── orchestrator.py       # Orchestrator registration
│   ├── services/                 # Business logic
│   │   ├── analytics.py          # 🔹 Analytics processing
│   │   └── database_pool.py      # Database connection pooling
│   └── db/database.py            # Database configuration
└── requirements.txt
```

#### 💡 Developer Tips
**Controller vs Orchestrator:**
- **Controller**: Central analytics, organization management
- **Orchestrator**: AI workflows, embedded monitoring
- **Data Flow**: Controller pulls data from orchestrator monitoring APIs

## Development Workflow

### Setting Up Development Environment

#### 1. Local Development Setup
```bash
# Clone repository
git clone <repository>
cd mool_ai_repo

# Install dependencies for each service
cd services/orchestrator && pip install -r requirements.txt
cd ../controller && pip install -r requirements.txt
cd ../..

# Set up environment variables
cp deployment/client/.env.template .env
# Edit .env with your configuration
```

#### 2. Database Setup
```bash
# Start databases only
docker-compose up postgres-orchestrator-001 postgres-controller -d

# Run migrations (when ready)
cd services/orchestrator && python -m alembic upgrade head
cd ../controller && python -m alembic upgrade head
```

#### 3. Service Development
```bash
# Run orchestrator in development
cd services/orchestrator
python -m uvicorn app.main:app --reload --port 8000

# Run controller in development  
cd services/controller
python -m uvicorn app.main:app --reload --port 9000
```

### 🔧 Development Best Practices

#### Code Organization
- **Follow existing patterns**: Look at existing code before adding new features
- **Use type hints**: All new code should include proper type annotations
- **Error handling**: Use structured exception handling with proper logging
- **Async/await**: All database operations and HTTP calls should be async

#### Database Best Practices
```python
# ✅ Good: Use dependency injection
@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_monitoring_db)):
    result = await db.execute(select(SystemMetrics))
    return result.scalars().all()

# ❌ Bad: Direct database connections
async def get_metrics():
    db = create_engine("postgresql://...")  # Don't do this
```

#### API Development
```python
# ✅ Good: Proper error handling
@router.post("/collect")
async def collect_metrics(org_id: str):
    try:
        result = await metrics_collector.collect(org_id)
        return {"status": "success", "data": result}
    except CollectionError as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Good: Input validation
from pydantic import BaseModel

class MetricsRequest(BaseModel):
    organization_id: str
    start_time: datetime
    end_time: datetime
```

## Testing Guide

### Test Structure
```
tests/
├── test_orchestrator.py          # Orchestrator API tests
├── test_controller.py            # Controller API tests
├── test_system_monitoring.py     # Embedded monitoring tests
├── test_integration.py           # Cross-service integration tests
├── conftest.py                   # Pytest configuration
└── fixtures/                     # Test data fixtures
```

### 🧪 Running Tests

#### Unit Tests
```bash
# Test individual services
cd services/orchestrator && python -m pytest tests/ -v
cd services/controller && python -m pytest tests/ -v

# Test embedded monitoring specifically
python test_system_monitoring.py
```

#### Integration Tests
```bash
# Start services first
./build.sh

# Run integration tests
python -m pytest tests/test_integration.py -v
```

#### Load Testing
```bash
# Test monitoring collection under load
python tests/load_test_monitoring.py

# Test LLM API performance
python tests/load_test_llm.py
```

### 💡 Testing Tips

#### Monitoring Tests
```python
# Test embedded monitoring endpoints
async def test_monitoring_health():
    async with httpx.AsyncClient() as client:
        # Note: Test on orchestrator port, not separate monitoring port
        response = await client.get("http://localhost:8000/api/v1/system/health")
        assert response.status_code == 200
```

#### Database Tests
```python
# Use test database for monitoring tests
@pytest.fixture
async def test_monitoring_db():
    # Create test monitoring database
    async with get_monitoring_db() as db:
        yield db
        # Cleanup
```

## Deployment Guide

### 🐳 Docker Deployment

#### Production Deployment
```bash
# Build all images
./scripts/docker-build.sh

# Deploy full system
docker-compose up -d

# Verify deployment
./scripts/docker-verify.sh
```

#### Client Deployment
```bash
# Use client-specific configuration
cd deployment/client
cp .env.template .env
# Configure .env for client

# Deploy single organization
docker-compose -f docker-compose.yml up -d
```

### 🔧 Configuration Management

#### Environment Variables
```bash
# Orchestrator Configuration
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/orchestrator_org_001
MONITORING_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/monitoring_org_001
ORCHESTRATOR_PORT=8000
REDIS_URL=redis://redis:6379

# Controller Configuration  
CONTROLLER_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/moolai_controller
CONTROLLER_PORT=9000

# LLM Provider Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
```

#### Database Configuration
```yaml
# Docker Compose Database Setup
postgres-orchestrator-001:
  image: postgres:15
  environment:
    POSTGRES_DB: orchestrator_org_001
    POSTGRES_USER: orchestrator_user
    POSTGRES_PASSWORD: secure_password_orch_001
  ports:
    - "5434:5432"
  volumes:
    - postgres_orchestrator_001_data:/var/lib/postgresql/data
    - ./scripts/init-monitoring-db.sql:/docker-entrypoint-initdb.d/init-monitoring-db.sql
```

### 🌐 Production Considerations

#### Performance Tuning
```python
# Database Connection Pooling
DATABASE_CONFIG = {
    "pool_size": 20,
    "max_overflow": 30,
    "pool_pre_ping": True,
    "pool_recycle": 3600
}

# Monitoring Collection Optimization
MONITORING_CONFIG = {
    "collection_interval": 30,  # seconds
    "batch_size": 100,
    "cache_ttl": 300  # 5 minutes
}
```

#### Security Configuration
```bash
# Use strong passwords
DB_PASSWORD=$(openssl rand -base64 32)
API_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -base64 64)

# Enable TLS in production
TLS_ENABLED=true
TLS_CERT_PATH=/etc/ssl/certs/server.crt
TLS_KEY_PATH=/etc/ssl/private/server.key
```

## Troubleshooting

### 🔍 Common Issues & Solutions

#### 1. Connection Refused Errors
```bash
# Symptom: ConnectionRefusedError: [Errno 111] Connection refused
# Cause: Service starting before database is ready

# Solution: Check docker-compose health checks
docker-compose ps  # Check service status
docker-compose logs postgres-orchestrator-001  # Check database logs

# Fix: Ensure proper depends_on configuration
services:
  orchestrator-org-001:
    depends_on:
      postgres-orchestrator-001:
        condition: service_healthy
```

#### 2. Monitoring API 404 Errors
```bash
# Symptom: 404 on /api/v1/system/metrics
# Cause: Trying to access on wrong port or old monitoring service

# Solution: Use orchestrator ports
curl http://localhost:8000/api/v1/system/health  # ✅ Correct
curl http://localhost:8001/api/v1/system/health  # ❌ Wrong (old port)
```

#### 3. Database Connection Issues
```python
# Symptom: "greenlet_spawn has not been called" errors
# Cause: Mixing sync and async database operations

# Solution: Use proper async patterns
# ✅ Good
async def get_metrics():
    async with get_monitoring_db() as db:
        result = await db.execute(select(SystemMetrics))
        return result.scalars().all()

# ❌ Bad  
def get_metrics():
    db = get_monitoring_db()  # Sync call in async context
    return db.query(SystemMetrics).all()
```

#### 4. Monitoring Collection Not Working
```bash
# Check background collection status
curl http://localhost:8000/api/v1/system/status/background

# Force immediate collection
curl -X POST "http://localhost:8000/api/v1/system/collect/immediate?organization_id=org_001"

# Check logs
docker-compose logs orchestrator-org-001
```

#### 5. Code Changes Require Container Rebuild ⚠️ IMPORTANT
```bash
# Symptom: Changes to Python code not reflected after docker-compose up
# Cause: Docker containers using cached images with old code

# Solution: Always rebuild after code changes
docker-compose down
./build.sh  # or docker-compose build
docker-compose up -d

# Quick rebuild for development
docker-compose build orchestrator-org-001 orchestrator-org-002
docker-compose up -d
```

### 📊 Debugging Tools

#### Health Checks
```bash
# Service health
curl http://localhost:8000/health
curl http://localhost:9000/health

# Database connectivity
curl http://localhost:8000/api/v1/system/health

# Monitoring status
curl http://localhost:8000/api/v1/system/status/background
```

#### Log Analysis
```bash
# View service logs
docker-compose logs -f orchestrator-org-001
docker-compose logs -f controller

# Monitoring-specific logs
docker-compose logs orchestrator-org-001 | grep "monitoring"
```

#### Database Debugging
```sql
-- Check monitoring data
SELECT COUNT(*) FROM user_system_performance;
SELECT * FROM user_system_performance ORDER BY timestamp DESC LIMIT 5;

-- Check collection status
SELECT organization_id, COUNT(*) as metric_count 
FROM user_system_performance 
GROUP BY organization_id;
```

## Integration Patterns

### 🔌 API Integration

#### LLM Provider Integration
```python
# Add new LLM provider
class NewProviderClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.newprovider.com"
    
    async def chat_completion(self, messages: List[dict]) -> dict:
        # Implementation
        pass

# Register in orchestrator
from app.services.llm import LLMManager
llm_manager = LLMManager()
llm_manager.register_provider("newprovider", NewProviderClient)
```

#### Custom Monitoring Metrics
```python
# Add custom metric collection
class CustomMetricsCollector:
    async def collect_custom_metrics(self, org_id: str) -> dict:
        # Your custom metrics logic
        return {
            "custom_metric_1": value1,
            "custom_metric_2": value2
        }

# Register in monitoring system
from app.monitoring.services.system_metrics import SystemMetricsCollector
collector = SystemMetricsCollector()
collector.add_custom_collector(CustomMetricsCollector())
```

#### WebSocket Integration
```javascript
// Connect to real-time monitoring
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === 'system_metrics') {
        updateDashboard(data.metrics);
    }
};

// Subscribe to specific metrics
ws.send(JSON.stringify({
    type: 'subscribe',
    topics: ['cpu_usage', 'memory_usage']
}));
```

### 🔗 External System Integration

#### Analytics Dashboard Integration
```python
# Export metrics for external dashboards
@router.get("/export/metrics")
async def export_metrics(
    org_id: str,
    start_date: datetime,
    end_date: datetime,
    format: str = "json"
):
    metrics = await get_metrics_range(org_id, start_date, end_date)
    
    if format == "prometheus":
        return export_prometheus_format(metrics)
    elif format == "grafana":
        return export_grafana_format(metrics)
    else:
        return metrics
```

#### Alerting System Integration
```python
# Custom alerting hooks
class AlertManager:
    async def check_thresholds(self, metrics: dict):
        if metrics['cpu_usage'] > 80:
            await self.send_alert(
                level="warning",
                message="High CPU usage detected",
                metrics=metrics
            )
    
    async def send_alert(self, level: str, message: str, metrics: dict):
        # Integration with Slack, PagerDuty, etc.
        pass
```

## Performance Optimization

### 🚀 Database Optimization

#### Connection Pooling
```python
# Optimized database configuration
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,           # Number of persistent connections
    max_overflow=30,        # Additional connections when needed
    pool_pre_ping=True,     # Verify connections before use
    pool_recycle=3600,      # Recycle connections after 1 hour
    echo=False              # Disable SQL logging in production
)
```

#### Query Optimization
```python
# ✅ Efficient monitoring queries
async def get_recent_metrics(org_id: str, limit: int = 100):
    query = select(SystemMetrics).where(
        SystemMetrics.organization_id == org_id
    ).order_by(
        SystemMetrics.timestamp.desc()
    ).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

# ✅ Batch inserts for metrics
async def batch_insert_metrics(metrics: List[dict]):
    stmt = insert(SystemMetrics)
    await db.execute(stmt, metrics)
    await db.commit()
```

#### Database Indexing
```sql
-- Essential indexes for monitoring
CREATE INDEX idx_system_metrics_org_timestamp 
ON user_system_performance(organization_id, timestamp DESC);

CREATE INDEX idx_system_metrics_timestamp 
ON user_system_performance(timestamp DESC);

-- Composite index for common queries
CREATE INDEX idx_system_metrics_org_type_timestamp 
ON user_system_performance(organization_id, metric_type, timestamp DESC);
```

### ⚡ Application Performance

#### Caching Strategy
```python
# Redis caching for frequent queries
import redis.asyncio as redis

class MetricsCache:
    def __init__(self):
        self.redis = redis.Redis(host='redis', port=6379, db=0)
    
    async def get_cached_metrics(self, org_id: str):
        key = f"metrics:{org_id}:latest"
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    async def cache_metrics(self, org_id: str, metrics: dict, ttl: int = 300):
        key = f"metrics:{org_id}:latest"
        await self.redis.setex(key, ttl, json.dumps(metrics))
```

#### Async Processing
```python
# Background task optimization
import asyncio
from concurrent.futures import ThreadPoolExecutor

class MetricsCollector:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def collect_all_organizations(self):
        organizations = await self.get_organizations()
        
        # Process organizations concurrently
        tasks = [
            self.collect_organization_metrics(org.id) 
            for org in organizations
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

### 📈 Monitoring Performance

#### Collection Optimization
```python
# Efficient metrics collection
class OptimizedCollector:
    async def collect_system_metrics(self):
        # Collect multiple metrics concurrently
        tasks = [
            self.get_cpu_metrics(),
            self.get_memory_metrics(),
            self.get_disk_metrics(),
            self.get_network_metrics()
        ]
        
        cpu, memory, disk, network = await asyncio.gather(*tasks)
        
        return {
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "network": network,
            "timestamp": datetime.utcnow()
        }
```

---

## 🎯 Quick Reference

### Port Guide
- **8000**: Orchestrator Org-001 (includes embedded monitoring)
- **8010**: Orchestrator Org-002 (includes embedded monitoring)  
- **9000**: Controller (analytics and management)
- **5434**: PostgreSQL Org-001 (orchestrator + monitoring databases)
- **5435**: PostgreSQL Org-002 (orchestrator + monitoring databases)
- **5436**: PostgreSQL Controller

### Key Endpoints

#### All Endpoints
```bash
# Orchestrator (includes embedded monitoring)
GET  /health                           # Service health
GET  /api/v1/system/health            # Monitoring health
POST /api/v1/system/collect/immediate # Force collection
GET  /api/v1/system/metrics           # System metrics
GET  /api/v1/stream                   # Real-time streaming
WS   /ws                              # WebSocket interface

# Controller
GET  /health                          # Service health
GET  /api/v1/organizations           # Organization list
GET  /api/v1/analytics/performance   # Performance analytics
```

### 🎯 Endpoints by Team Usage

#### 🎨 UI/Frontend Development Team
```bash
# Real-time Dashboard Data
GET  http://localhost:8000/api/v1/system/metrics/organization/org_001
GET  http://localhost:8010/api/v1/system/metrics/organization/org_002
WS   ws://localhost:8000/ws                      # Real-time updates
GET  http://localhost:8000/api/v1/stream        # Server-sent events

# System Health for Status Indicators
GET  http://localhost:8000/api/v1/system/health
GET  http://localhost:8010/api/v1/system/health
GET  http://localhost:8002/health

# Cross-Organization Analytics
GET  http://localhost:8002/api/v1/controller/overview
GET  http://localhost:8002/api/v1/controller/performance
GET  http://localhost:8002/api/v1/controller/costs

# Organization Management
GET  http://localhost:8002/api/v1/controller/organizations
GET  http://localhost:8002/api/v1/controller/orchestrators
```

#### 🔧 Infrastructure/DevOps Team
```bash
# Service Health Monitoring
GET  http://localhost:8000/health               # Orchestrator org-001
GET  http://localhost:8010/health               # Orchestrator org-002  
GET  http://localhost:8002/health               # Controller

# System Performance Monitoring
GET  http://localhost:8000/api/v1/system/status/background
POST http://localhost:8000/api/v1/system/collect/immediate?organization_id=org_001
POST http://localhost:8010/api/v1/system/collect/immediate?organization_id=org_002

# Metrics Collection Status
GET  http://localhost:8000/api/v1/system/metrics/organization/org_001
GET  http://localhost:8010/api/v1/system/metrics/organization/org_002

# Real-time System Health Stream
GET  http://localhost:8000/api/v1/stream/system/health
GET  http://localhost:8010/api/v1/stream/system/health
```

#### 🤖 AI Agent Development Team
```bash
# Agent Lifecycle Management
GET  http://localhost:8000/api/v1/orchestrators/org_001/agents
GET  http://localhost:8010/api/v1/orchestrators/org_002/agents
GET  http://localhost:8000/api/v1/orchestrators/org_001/agents/{agent_id}/status

# Prompt Execution
POST http://localhost:8000/api/v1/orchestrators/org_001/prompts
POST http://localhost:8010/api/v1/orchestrators/org_002/prompts
GET  http://localhost:8000/api/v1/orchestrators/org_001/prompts/{prompt_id}

# Task Management
POST http://localhost:8000/api/v1/orchestrators/org_001/tasks
GET  http://localhost:8000/api/v1/orchestrators/org_001/tasks/{task_id}
PUT  http://localhost:8000/api/v1/orchestrators/org_001/tasks/{task_id}/cancel

# Configuration Management
GET  http://localhost:8000/api/v1/orchestrators/org_001/config
PUT  http://localhost:8000/api/v1/orchestrators/org_001/config
POST http://localhost:8000/api/v1/orchestrators/org_001/config/validate
```

#### 🔒 Security/Compliance Team
```bash
# System Health and Integrity
GET  http://localhost:8000/api/v1/system/health
GET  http://localhost:8010/api/v1/system/health
GET  http://localhost:8002/health

# Performance Monitoring (for anomaly detection)
GET  http://localhost:8000/api/v1/system/metrics/organization/org_001
GET  http://localhost:8010/api/v1/system/metrics/organization/org_002

# Organization Access Control
GET  http://localhost:8002/api/v1/controller/organizations
GET  http://localhost:8002/api/v1/controller/orchestrators

# User Management (placeholder endpoints)
GET  http://localhost:8000/api/v1/orchestrators/org_001/users
GET  http://localhost:8010/api/v1/orchestrators/org_002/users

# API Key Management (placeholder endpoints)
GET  http://localhost:8000/api/v1/orchestrators/org_001/api-keys
POST http://localhost:8000/api/v1/orchestrators/org_001/api-keys
DELETE http://localhost:8000/api/v1/orchestrators/org_001/api-keys/{key_id}
```

#### 🌐 Network/Firewall Team
```bash
# External Ports to Allow
8000  # Orchestrator org-001 (HTTP/HTTPS)
8010  # Orchestrator org-002 (HTTP/HTTPS)
8002  # Controller (HTTP/HTTPS)

# Internal Ports (Container-to-Container)
5432  # PostgreSQL databases (multiple instances)
6379  # Redis instances

# Health Check Endpoints (for Load Balancers)
GET  http://localhost:8000/health
GET  http://localhost:8010/health
GET  http://localhost:8002/health

# WebSocket Connections
WS   ws://localhost:8000/ws
WS   ws://localhost:8010/ws
```

#### 📊 Analytics/Business Intelligence Team
```bash
# Cross-Organization Insights
GET  http://localhost:8002/api/v1/controller/overview
GET  http://localhost:8002/api/v1/controller/costs
GET  http://localhost:8002/api/v1/controller/performance
GET  http://localhost:8002/api/v1/controller/insights

# Organization-Specific Metrics
GET  http://localhost:8000/api/v1/system/metrics/organization/org_001
GET  http://localhost:8010/api/v1/system/metrics/organization/org_002

# Custom Queries and Exports
POST http://localhost:8002/api/v1/controller/query
POST http://localhost:8002/api/v1/controller/export
GET  http://localhost:8002/api/v1/controller/export/{job_id}

# Real-time Metrics Streaming
GET  http://localhost:8000/api/v1/stream/metrics/organization
GET  http://localhost:8010/api/v1/stream/metrics/organization
```

#### 🧪 QA/Testing Team
```bash
# Health Verification
GET  http://localhost:8000/health
GET  http://localhost:8010/health
GET  http://localhost:8002/health

# End-to-End Testing Endpoints
POST http://localhost:8000/api/v1/system/collect/immediate?organization_id=org_001
GET  http://localhost:8000/api/v1/system/status/background
GET  http://localhost:8000/api/v1/system/metrics/organization/org_001

# Controller Integration Tests
GET  http://localhost:8002/api/v1/controller/orchestrators
POST http://localhost:8002/api/v1/controller/orchestrators
GET  http://localhost:8002/api/v1/controller/organizations

# Real-time Feature Testing
WS   ws://localhost:8000/ws
GET  http://localhost:8000/api/v1/stream/system/health
```

### Development Commands
```bash
# Start development environment
./build.sh

# Test embedded monitoring
python test_system_monitoring.py

# Run individual service tests
cd services/orchestrator && python -m pytest tests/ -v
cd services/controller && python -m pytest tests/ -v

# Build production images
./scripts/docker-build.sh
```

### Environment Variables Template
```bash
# Core Configuration
ORGANIZATION_ID=org_001
ORCHESTRATOR_PORT=8000
CONTROLLER_PORT=9000

# Database URLs
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/orchestrator_org_001
MONITORING_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/monitoring_org_001
CONTROLLER_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/moolai_controller

# API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
ORCHESTRATOR_API_KEY=your_api_key

# Monitoring Configuration
METRICS_COLLECTION_INTERVAL=30
AUTO_COLLECT=true
```

---
