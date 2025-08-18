"""Dashboard API endpoints for super user interface."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
import json

from ...config.database import get_db
from ...models.user_metrics import UserLLMRealtime, UserLLMStatistics
from ...middleware import LLMMonitoringMiddleware
from ..dependencies import get_monitoring_middleware

router = APIRouter()


@router.get("/dashboard/overview")
async def get_dashboard_overview(
    monitoring: LLMMonitoringMiddleware = Depends(get_monitoring_middleware),
    db: AsyncSession = Depends(get_db)
):
    """Get executive dashboard overview."""
    try:
        # Real-time metrics from Redis
        org_metrics = await monitoring.get_organization_metrics()
        
        # Historical data for trends (last 24 hours)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=24)
        
        # Get historical summary
        query = select(
            func.count(func.distinct(UserLLMStatistics.user_id)).label('active_users'),
            func.sum(UserLLMStatistics.total_queries).label('total_queries'),
            func.sum(UserLLMStatistics.total_cost).label('total_cost'),
            func.sum(UserLLMStatistics.successful_queries).label('successful_queries'),
            func.sum(UserLLMStatistics.failed_queries).label('failed_queries'),
            func.avg(UserLLMStatistics.avg_latency_ms).label('avg_latency_ms')
        ).where(
            and_(
                UserLLMStatistics.timestamp >= start_date,
                UserLLMStatistics.timestamp <= end_date,
                UserLLMStatistics.time_bucket == "hour"
            )
        )
        
        result = await db.execute(query)
        historical = result.first()
        
        # Calculate success rate
        total_requests = (historical.successful_queries or 0) + (historical.failed_queries or 0)
        success_rate = (historical.successful_queries / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "organization_id": monitoring.organization_id,
            "timestamp": datetime.utcnow().isoformat(),
            "health_score": min(success_rate, 100),  # Simple health score based on success rate
            "metrics": {
                "realtime": {
                    "total_queries": int(org_metrics.get("total_queries", 0)),
                    "total_cost": float(org_metrics.get("total_cost", 0)),
                    "active_users_now": len(org_metrics.get("active_users", [])) if "active_users" in org_metrics else 0
                },
                "last_24h": {
                    "active_users": historical.active_users or 0,
                    "total_queries": historical.total_queries or 0,
                    "total_cost": float(historical.total_cost or 0),
                    "success_rate": round(success_rate, 2),
                    "avg_latency_ms": int(historical.avg_latency_ms or 0)
                }
            },
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/users")
async def get_dashboard_users(
    sort_by: str = Query("cost", regex="^(cost|queries|tokens|activity)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    department: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    time_range: str = Query("24h", regex="^(1h|6h|24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db)
):
    """Get user analytics for dashboard table view."""
    try:
        # Convert time_range to timedelta
        time_ranges = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6), 
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        
        end_date = datetime.utcnow()
        start_date = end_date - time_ranges[time_range]
        
        # Build query conditions
        conditions = [
            UserLLMStatistics.timestamp >= start_date,
            UserLLMStatistics.timestamp <= end_date,
            UserLLMStatistics.time_bucket == "hour"
        ]
        
        if department:
            conditions.append(UserLLMStatistics.department == department)
        
        # Map sort columns
        sort_columns = {
            "cost": func.sum(UserLLMStatistics.total_cost),
            "queries": func.sum(UserLLMStatistics.total_queries),
            "tokens": func.sum(UserLLMStatistics.total_input_tokens + UserLLMStatistics.total_output_tokens),
            "activity": func.max(UserLLMStatistics.timestamp)
        }
        
        order_by = sort_columns[sort_by]
        if order == "desc":
            order_by = desc(order_by)
        
        # Main query with aggregation
        query = select(
            UserLLMStatistics.user_id,
            UserLLMStatistics.department,
            UserLLMStatistics.user_role,
            func.sum(UserLLMStatistics.total_queries).label('total_queries'),
            func.sum(UserLLMStatistics.successful_queries).label('successful_queries'),
            func.sum(UserLLMStatistics.failed_queries).label('failed_queries'),
            func.sum(UserLLMStatistics.total_cost).label('total_cost'),
            func.sum(UserLLMStatistics.total_input_tokens).label('total_input_tokens'),
            func.sum(UserLLMStatistics.total_output_tokens).label('total_output_tokens'),
            func.avg(UserLLMStatistics.avg_latency_ms).label('avg_latency_ms'),
            func.max(UserLLMStatistics.timestamp).label('last_activity'),
            func.count(UserLLMStatistics.timestamp).label('active_hours')
        ).where(
            and_(*conditions)
        ).group_by(
            UserLLMStatistics.user_id,
            UserLLMStatistics.department,
            UserLLMStatistics.user_role
        ).order_by(order_by).limit(limit).offset(offset)
        
        result = await db.execute(query)
        records = result.all()
        
        users = []
        for record in records:
            total_requests = (record.successful_queries or 0) + (record.failed_queries or 0)
            success_rate = (record.successful_queries / total_requests * 100) if total_requests > 0 else 0
            
            users.append({
                "user_id": str(record.user_id),
                "department": record.department or "Unknown",
                "user_role": record.user_role,
                "total_queries": record.total_queries or 0,
                "success_rate": round(success_rate, 1),
                "total_cost": float(record.total_cost or 0),
                "total_tokens": (record.total_input_tokens or 0) + (record.total_output_tokens or 0),
                "avg_cost_per_query": float(record.total_cost / record.total_queries) if record.total_queries and record.total_cost else 0,
                "avg_tokens_per_query": int((record.total_input_tokens + record.total_output_tokens) / record.total_queries) if record.total_queries else 0,
                "avg_latency_ms": int(record.avg_latency_ms or 0),
                "last_activity": record.last_activity.isoformat() if record.last_activity else None,
                "active_hours": record.active_hours or 0
            })
        
        # Get total count for pagination
        count_query = select(func.count(func.distinct(UserLLMStatistics.user_id))).where(and_(*conditions))
        count_result = await db.execute(count_query)
        total_users = count_result.scalar()
        
        return {
            "users": users,
            "pagination": {
                "total": total_users,
                "limit": limit,
                "offset": offset,
                "has_next": offset + limit < total_users
            },
            "filters": {
                "time_range": time_range,
                "department": department,
                "sort_by": sort_by,
                "order": order
            },
            "time_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/user/{user_id}")
async def get_dashboard_user_detail(
    user_id: str,
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed view for a specific user."""
    try:
        # Time range conversion
        time_ranges = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        
        end_date = datetime.utcnow()
        start_date = end_date - time_ranges[time_range]
        
        # User profile and aggregated metrics
        profile_query = select(
            UserLLMStatistics.user_id,
            UserLLMStatistics.department,
            UserLLMStatistics.user_role,
            func.sum(UserLLMStatistics.total_queries).label('total_queries'),
            func.sum(UserLLMStatistics.total_cost).label('total_cost'),
            func.sum(UserLLMStatistics.total_input_tokens).label('total_input_tokens'),
            func.sum(UserLLMStatistics.total_output_tokens).label('total_output_tokens'),
            func.avg(UserLLMStatistics.avg_latency_ms).label('avg_latency_ms'),
            func.max(UserLLMStatistics.timestamp).label('last_activity')
        ).where(
            and_(
                UserLLMStatistics.user_id == user_id,
                UserLLMStatistics.timestamp >= start_date,
                UserLLMStatistics.timestamp <= end_date,
                UserLLMStatistics.time_bucket == "hour"
            )
        ).group_by(
            UserLLMStatistics.user_id,
            UserLLMStatistics.department,
            UserLLMStatistics.user_role
        )
        
        profile_result = await db.execute(profile_query)
        profile = profile_result.first()
        
        if not profile:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Time series data for charts
        timeseries_query = select(
            UserLLMStatistics.timestamp,
            UserLLMStatistics.total_queries,
            UserLLMStatistics.total_cost,
            UserLLMStatistics.avg_latency_ms,
            UserLLMStatistics.agent_breakdown,
            UserLLMStatistics.model_breakdown
        ).where(
            and_(
                UserLLMStatistics.user_id == user_id,
                UserLLMStatistics.timestamp >= start_date,
                UserLLMStatistics.timestamp <= end_date,
                UserLLMStatistics.time_bucket == "hour"
            )
        ).order_by(UserLLMStatistics.timestamp)
        
        timeseries_result = await db.execute(timeseries_query)
        timeseries = timeseries_result.all()
        
        # Recent requests
        recent_query = select(UserLLMRealtime).where(
            and_(
                UserLLMRealtime.user_id == user_id,
                UserLLMRealtime.request_timestamp >= start_date
            )
        ).order_by(desc(UserLLMRealtime.request_timestamp)).limit(20)
        
        recent_result = await db.execute(recent_query)
        recent_requests = recent_result.scalars().all()
        
        # Format response
        return {
            "user_profile": {
                "user_id": str(profile.user_id),
                "department": profile.department,
                "user_role": profile.user_role,
                "total_queries": profile.total_queries or 0,
                "total_cost": float(profile.total_cost or 0),
                "total_tokens": (profile.total_input_tokens or 0) + (profile.total_output_tokens or 0),
                "avg_latency_ms": int(profile.avg_latency_ms or 0),
                "last_activity": profile.last_activity.isoformat() if profile.last_activity else None
            },
            "time_series": [
                {
                    "timestamp": record.timestamp.isoformat(),
                    "queries": record.total_queries or 0,
                    "cost": float(record.total_cost or 0),
                    "latency_ms": record.avg_latency_ms,
                    "agent_breakdown": record.agent_breakdown,
                    "model_breakdown": record.model_breakdown
                }
                for record in timeseries
            ],
            "recent_requests": [
                {
                    "request_id": str(req.request_id),
                    "agent_type": req.agent_type,
                    "model_name": req.model_name,
                    "cost": float(req.cost or 0),
                    "latency_ms": req.latency_ms,
                    "status": req.status,
                    "timestamp": req.request_timestamp.isoformat()
                }
                for req in recent_requests
            ],
            "time_range": time_range,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    except Exception as e:
        if "User not found" in str(e):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/analytics")
async def get_dashboard_analytics(
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db)
):
    """Get analytics data for charts and insights."""
    try:
        # Time range conversion
        time_ranges = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        
        end_date = datetime.utcnow()
        start_date = end_date - time_ranges[time_range]
        
        # Cost trend over time
        cost_trend_query = select(
            func.date_trunc('day' if time_range in ['7d', '30d'] else 'hour', UserLLMStatistics.timestamp).label('period'),
            func.sum(UserLLMStatistics.total_cost).label('cost'),
            func.sum(UserLLMStatistics.total_queries).label('queries')
        ).where(
            and_(
                UserLLMStatistics.timestamp >= start_date,
                UserLLMStatistics.timestamp <= end_date,
                UserLLMStatistics.time_bucket == "hour"
            )
        ).group_by('period').order_by('period')
        
        cost_trend_result = await db.execute(cost_trend_query)
        cost_trend = [
            {
                "period": record.period.isoformat(),
                "cost": float(record.cost or 0),
                "queries": record.queries or 0
            }
            for record in cost_trend_result.all()
        ]
        
        # Department breakdown
        dept_query = select(
            UserLLMStatistics.department,
            func.sum(UserLLMStatistics.total_queries).label('queries'),
            func.sum(UserLLMStatistics.total_cost).label('cost'),
            func.count(func.distinct(UserLLMStatistics.user_id)).label('users')
        ).where(
            and_(
                UserLLMStatistics.timestamp >= start_date,
                UserLLMStatistics.timestamp <= end_date,
                UserLLMStatistics.time_bucket == "hour"
            )
        ).group_by(UserLLMStatistics.department)
        
        dept_result = await db.execute(dept_query)
        departments = [
            {
                "department": record.department or "Unknown",
                "queries": record.queries or 0,
                "cost": float(record.cost or 0),
                "users": record.users or 0
            }
            for record in dept_result.all()
        ]
        
        return {
            "cost_trend": cost_trend,
            "department_breakdown": departments,
            "time_range": time_range,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))