"""Metrics API endpoints."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
import json

from ...models import get_db, UserLLMRealtime, UserLLMStatistics
from ...middleware import LLMMonitoringMiddleware
from ..dependencies import get_monitoring_middleware

router = APIRouter()


@router.get("/metrics/users/{user_id}/realtime")
async def get_user_realtime_metrics(
    user_id: str,
    monitoring: LLMMonitoringMiddleware = Depends(get_monitoring_middleware)
):
    """Get real-time metrics for a specific user from Redis."""
    try:
        metrics = await monitoring.get_user_metrics(user_id)
        return {
            "user_id": user_id,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/users/{user_id}/history")
async def get_user_historical_metrics(
    user_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    time_bucket: str = Query("hour", regex="^(hour|day|month)$"),
    db: AsyncSession = Depends(get_db)
):
    """Get historical metrics for a specific user."""
    try:
        # Default to last 24 hours if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(hours=24)
        
        # Query historical data
        query = select(UserLLMStatistics).where(
            and_(
                UserLLMStatistics.user_id == user_id,
                UserLLMStatistics.timestamp >= start_date,
                UserLLMStatistics.timestamp <= end_date,
                UserLLMStatistics.time_bucket == time_bucket
            )
        ).order_by(UserLLMStatistics.timestamp)
        
        result = await db.execute(query)
        records = result.scalars().all()
        
        # Format response
        metrics = []
        for record in records:
            metrics.append({
                "timestamp": record.timestamp.isoformat(),
                "total_queries": record.total_queries,
                "successful_queries": record.successful_queries,
                "failed_queries": record.failed_queries,
                "total_cost": float(record.total_cost or 0),
                "total_input_tokens": record.total_input_tokens,
                "total_output_tokens": record.total_output_tokens,
                "avg_latency_ms": record.avg_latency_ms,
                "department": record.department,
                "agent_breakdown": record.agent_breakdown,
                "model_breakdown": record.model_breakdown
            })
        
        return {
            "user_id": user_id,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "bucket": time_bucket
            },
            "metrics": metrics,
            "total_records": len(metrics)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/users/{user_id}/requests")
async def get_user_recent_requests(
    user_id: str,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get recent requests for a specific user."""
    try:
        query = select(UserLLMRealtime).where(
            UserLLMRealtime.user_id == user_id
        ).order_by(desc(UserLLMRealtime.request_timestamp)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        records = result.scalars().all()
        
        requests = []
        for record in records:
            requests.append({
                "request_id": str(record.request_id),
                "agent_type": record.agent_type,
                "model_name": record.model_name,
                "model_provider": record.model_provider,
                "prompt_text": record.prompt_text,
                "response_text": record.response_text,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "cost": float(record.cost or 0),
                "latency_ms": record.latency_ms,
                "status": record.status,
                "error_type": record.error_type,
                "cache_hit": record.cache_hit,
                "request_timestamp": record.request_timestamp.isoformat(),
                "response_timestamp": record.response_timestamp.isoformat() if record.response_timestamp else None,
                "department": record.department
            })
        
        return {
            "user_id": user_id,
            "requests": requests,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned": len(requests)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/organization/realtime")
async def get_organization_realtime_metrics(
    monitoring: LLMMonitoringMiddleware = Depends(get_monitoring_middleware)
):
    """Get real-time organization-level metrics."""
    try:
        metrics = await monitoring.get_organization_metrics()
        return {
            "organization_id": monitoring.organization_id,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/organization/users")
async def get_organization_users_metrics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    department: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Get metrics for all users in the organization."""
    try:
        # Default to last 24 hours
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(hours=24)
        
        # Build query
        conditions = [
            UserLLMStatistics.timestamp >= start_date,
            UserLLMStatistics.timestamp <= end_date,
            UserLLMStatistics.time_bucket == "hour"  # Use hourly data for summaries
        ]
        
        if department:
            conditions.append(UserLLMStatistics.department == department)
        
        # Aggregate by user
        query = select(
            UserLLMStatistics.user_id,
            UserLLMStatistics.department,
            func.sum(UserLLMStatistics.total_queries).label('total_queries'),
            func.sum(UserLLMStatistics.total_cost).label('total_cost'),
            func.sum(UserLLMStatistics.total_input_tokens).label('total_input_tokens'),
            func.sum(UserLLMStatistics.total_output_tokens).label('total_output_tokens'),
            func.avg(UserLLMStatistics.avg_latency_ms).label('avg_latency_ms'),
            func.max(UserLLMStatistics.timestamp).label('last_activity')
        ).where(
            and_(*conditions)
        ).group_by(
            UserLLMStatistics.user_id,
            UserLLMStatistics.department
        ).order_by(desc('total_cost')).limit(limit)
        
        result = await db.execute(query)
        records = result.all()
        
        users = []
        for record in records:
            users.append({
                "user_id": str(record.user_id),
                "department": record.department,
                "total_queries": record.total_queries or 0,
                "total_cost": float(record.total_cost or 0),
                "total_input_tokens": record.total_input_tokens or 0,
                "total_output_tokens": record.total_output_tokens or 0,
                "avg_latency_ms": int(record.avg_latency_ms or 0),
                "last_activity": record.last_activity.isoformat() if record.last_activity else None
            })
        
        return {
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "filters": {
                "department": department
            },
            "users": users,
            "total_users": len(users)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/organization/summary")
async def get_organization_summary(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get organization-level summary metrics."""
    try:
        # Default to last 24 hours
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(hours=24)
        
        # Aggregate organization metrics
        query = select(
            func.count(func.distinct(UserLLMStatistics.user_id)).label('total_users'),
            func.sum(UserLLMStatistics.total_queries).label('total_queries'),
            func.sum(UserLLMStatistics.total_cost).label('total_cost'),
            func.sum(UserLLMStatistics.total_input_tokens).label('total_input_tokens'),
            func.sum(UserLLMStatistics.total_output_tokens).label('total_output_tokens'),
            func.avg(UserLLMStatistics.avg_latency_ms).label('avg_latency_ms')
        ).where(
            and_(
                UserLLMStatistics.timestamp >= start_date,
                UserLLMStatistics.timestamp <= end_date,
                UserLLMStatistics.time_bucket == "hour"
            )
        )
        
        result = await db.execute(query)
        summary = result.first()
        
        # Department breakdown
        dept_query = select(
            UserLLMStatistics.department,
            func.count(func.distinct(UserLLMStatistics.user_id)).label('users'),
            func.sum(UserLLMStatistics.total_queries).label('queries'),
            func.sum(UserLLMStatistics.total_cost).label('cost')
        ).where(
            and_(
                UserLLMStatistics.timestamp >= start_date,
                UserLLMStatistics.timestamp <= end_date,
                UserLLMStatistics.time_bucket == "hour"
            )
        ).group_by(UserLLMStatistics.department)
        
        dept_result = await db.execute(dept_query)
        departments = []
        for dept in dept_result.all():
            departments.append({
                "department": dept.department or "Unknown",
                "users": dept.users or 0,
                "queries": dept.queries or 0,
                "cost": float(dept.cost or 0)
            })
        
        return {
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_users": summary.total_users or 0,
                "total_queries": summary.total_queries or 0,
                "total_cost": float(summary.total_cost or 0),
                "total_input_tokens": summary.total_input_tokens or 0,
                "total_output_tokens": summary.total_output_tokens or 0,
                "avg_latency_ms": int(summary.avg_latency_ms or 0)
            },
            "department_breakdown": departments
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))