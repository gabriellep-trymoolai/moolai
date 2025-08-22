"""Analytics API endpoints for dashboard metrics."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, case
from decimal import Decimal
import json

from ...config.database import get_db
from ...models.user_metrics import UserLLMRealtime, UserLLMStatistics
from ...middleware import LLMMonitoringMiddleware
from ..dependencies import get_monitoring_middleware

router = APIRouter()


@router.get("/analytics/overview")
async def get_analytics_overview(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive analytics overview for the dashboard."""
    try:
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Base conditions
        conditions = [
            UserLLMRealtime.request_timestamp >= start_date,
            UserLLMRealtime.request_timestamp <= end_date
        ]
        
        if organization_id:
            conditions.append(UserLLMRealtime.organization_id == organization_id)

        # Total API calls and cost
        total_query = select(
            func.count(UserLLMRealtime.request_id).label('total_calls'),
            func.sum(UserLLMRealtime.cost).label('total_cost'),
            func.sum(UserLLMRealtime.input_tokens + UserLLMRealtime.output_tokens).label('total_tokens'),
            func.avg(UserLLMRealtime.latency_ms).label('avg_response_time'),
            func.sum(case((UserLLMRealtime.cache_hit == True, 1), else_=0)).label('cache_hits'),
            func.sum(case((UserLLMRealtime.firewall_blocked == True, 1), else_=0)).label('firewall_blocks')
        ).where(and_(*conditions))
        
        result = await db.execute(total_query)
        totals = result.first()
        
        # Provider breakdown
        provider_query = select(
            UserLLMRealtime.model_provider,
            func.count(UserLLMRealtime.request_id).label('calls'),
            func.sum(UserLLMRealtime.cost).label('cost'),
            func.sum(UserLLMRealtime.input_tokens + UserLLMRealtime.output_tokens).label('tokens')
        ).where(and_(*conditions)).group_by(UserLLMRealtime.model_provider)
        
        provider_result = await db.execute(provider_query)
        providers = []
        for row in provider_result.all():
            providers.append({
                "provider": row.model_provider or "unknown",
                "calls": row.calls or 0,
                "cost": float(row.cost or 0),
                "tokens": row.tokens or 0
            })

        # Calculate cache hit rate
        total_requests = totals.total_calls or 0
        cache_hits = totals.cache_hits or 0
        cache_hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "overview": {
                "total_api_calls": total_requests,
                "total_cost": float(totals.total_cost or 0),
                "total_tokens": totals.total_tokens or 0,
                "avg_response_time_ms": int(totals.avg_response_time or 0),
                "cache_hit_rate": round(cache_hit_rate, 1),
                "firewall_blocks": totals.firewall_blocks or 0
            },
            "provider_breakdown": providers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/provider-breakdown")
async def get_provider_breakdown(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed provider breakdown for API calls and costs."""
    try:
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Base conditions
        conditions = [
            UserLLMRealtime.request_timestamp >= start_date,
            UserLLMRealtime.request_timestamp <= end_date
        ]
        
        if organization_id:
            conditions.append(UserLLMRealtime.organization_id == organization_id)

        # Detailed provider breakdown with model information
        query = select(
            UserLLMRealtime.model_provider,
            UserLLMRealtime.model_name,
            func.count(UserLLMRealtime.request_id).label('calls'),
            func.sum(UserLLMRealtime.cost).label('cost'),
            func.sum(UserLLMRealtime.input_tokens).label('input_tokens'),
            func.sum(UserLLMRealtime.output_tokens).label('output_tokens'),
            func.avg(UserLLMRealtime.latency_ms).label('avg_latency'),
            func.avg(UserLLMRealtime.cost / func.nullif(func.count(UserLLMRealtime.request_id), 0)).label('avg_cost_per_query')
        ).where(and_(*conditions)).group_by(
            UserLLMRealtime.model_provider,
            UserLLMRealtime.model_name
        ).order_by(desc('cost'))
        
        result = await db.execute(query)
        breakdown = []
        
        for row in result.all():
            breakdown.append({
                "provider": row.model_provider or "unknown",
                "model": row.model_name or "unknown",
                "calls": row.calls or 0,
                "cost": float(row.cost or 0),
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "total_tokens": (row.input_tokens or 0) + (row.output_tokens or 0),
                "avg_latency_ms": int(row.avg_latency or 0),
                "avg_cost_per_query": float(row.avg_cost_per_query or 0)
            })

        return {
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "provider_breakdown": breakdown
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/time-series")
async def get_time_series_data(
    metric: str = Query("cost", regex="^(cost|calls|tokens|latency)$"),
    interval: str = Query("hour", regex="^(hour|day)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get time series data for specified metric."""
    try:
        # Default to last 24 hours if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            if interval == "hour":
                start_date = end_date - timedelta(hours=24)
            else:
                start_date = end_date - timedelta(days=30)

        # Base conditions
        conditions = [
            UserLLMRealtime.request_timestamp >= start_date,
            UserLLMRealtime.request_timestamp <= end_date
        ]
        
        if organization_id:
            conditions.append(UserLLMRealtime.organization_id == organization_id)

        # Time truncation based on interval
        if interval == "hour":
            time_trunc = func.date_trunc('hour', UserLLMRealtime.request_timestamp)
        else:
            time_trunc = func.date_trunc('day', UserLLMRealtime.request_timestamp)

        # Select appropriate metric
        if metric == "cost":
            metric_func = func.sum(UserLLMRealtime.cost)
        elif metric == "calls":
            metric_func = func.count(UserLLMRealtime.request_id)
        elif metric == "tokens":
            metric_func = func.sum(UserLLMRealtime.input_tokens + UserLLMRealtime.output_tokens)
        elif metric == "latency":
            metric_func = func.avg(UserLLMRealtime.latency_ms)

        query = select(
            time_trunc.label('time_bucket'),
            metric_func.label('value')
        ).where(and_(*conditions)).group_by(time_trunc).order_by(time_trunc)
        
        result = await db.execute(query)
        time_series = []
        
        for row in result.all():
            time_series.append({
                "timestamp": row.time_bucket.isoformat(),
                "value": float(row.value or 0) if metric != "calls" else (row.value or 0)
            })

        return {
            "metric": metric,
            "interval": interval,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "data": time_series
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/cache-performance")
async def get_cache_performance(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get cache performance metrics."""
    try:
        # Default to last 7 days if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        # Base conditions
        conditions = [
            UserLLMRealtime.request_timestamp >= start_date,
            UserLLMRealtime.request_timestamp <= end_date
        ]
        
        if organization_id:
            conditions.append(UserLLMRealtime.organization_id == organization_id)

        # Cache performance query
        query = select(
            func.count(UserLLMRealtime.request_id).label('total_requests'),
            func.sum(case((UserLLMRealtime.cache_hit == True, 1), else_=0)).label('cache_hits'),
            func.avg(
                case((UserLLMRealtime.cache_hit == True, UserLLMRealtime.cache_similarity), else_=None)
            ).label('avg_similarity'),
            func.avg(
                case((UserLLMRealtime.cache_hit == True, UserLLMRealtime.latency_ms), else_=None)
            ).label('avg_cache_latency'),
            func.avg(
                case((UserLLMRealtime.cache_hit == False, UserLLMRealtime.latency_ms), else_=None)
            ).label('avg_fresh_latency')
        ).where(and_(*conditions))
        
        result = await db.execute(query)
        stats = result.first()
        
        total_requests = stats.total_requests or 0
        cache_hits = stats.cache_hits or 0
        cache_hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
        cache_miss_rate = 100 - cache_hit_rate

        # Cache performance by similarity ranges
        similarity_query = select(
            case(
                (UserLLMRealtime.cache_similarity >= 0.9, "Very High (≥90%)"),
                (UserLLMRealtime.cache_similarity >= 0.8, "High (80-89%)"),
                (UserLLMRealtime.cache_similarity >= 0.7, "Medium (70-79%)"),
                (UserLLMRealtime.cache_similarity >= 0.6, "Low (60-69%)"),
                else_="Very Low (<60%)"
            ).label('similarity_range'),
            func.count(UserLLMRealtime.request_id).label('count')
        ).where(
            and_(
                *conditions,
                UserLLMRealtime.cache_hit == True,
                UserLLMRealtime.cache_similarity.isnot(None)
            )
        ).group_by('similarity_range')
        
        similarity_result = await db.execute(similarity_query)
        similarity_breakdown = []
        
        for row in similarity_result.all():
            similarity_breakdown.append({
                "range": row.similarity_range,
                "count": row.count or 0,
                "percentage": round((row.count or 0) / cache_hits * 100, 1) if cache_hits > 0 else 0
            })

        return {
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "cache_performance": {
                "total_requests": total_requests,
                "cache_hits": cache_hits,
                "cache_misses": total_requests - cache_hits,
                "cache_hit_rate": round(cache_hit_rate, 1),
                "cache_miss_rate": round(cache_miss_rate, 1),
                "avg_similarity": round(float(stats.avg_similarity or 0), 3),
                "avg_cache_latency_ms": int(stats.avg_cache_latency or 0),
                "avg_fresh_latency_ms": int(stats.avg_fresh_latency or 0)
            },
            "similarity_breakdown": similarity_breakdown
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/firewall-activity")
async def get_firewall_activity(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get firewall blocking activity."""
    try:
        # Default to last 7 days if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        # Base conditions
        conditions = [
            UserLLMRealtime.request_timestamp >= start_date,
            UserLLMRealtime.request_timestamp <= end_date
        ]
        
        if organization_id:
            conditions.append(UserLLMRealtime.organization_id == organization_id)

        # Firewall activity query
        query = select(
            func.count(UserLLMRealtime.request_id).label('total_requests'),
            func.sum(case((UserLLMRealtime.firewall_blocked == True, 1), else_=0)).label('blocked_requests'),
            func.sum(case((UserLLMRealtime.firewall_blocked == False, 1), else_=0)).label('allowed_requests')
        ).where(and_(*conditions))
        
        result = await db.execute(query)
        stats = result.first()
        
        total_requests = stats.total_requests or 0
        blocked_requests = stats.blocked_requests or 0
        allowed_requests = stats.allowed_requests or 0
        block_rate = (blocked_requests / total_requests * 100) if total_requests > 0 else 0

        # Get blocked request details
        blocked_details_query = select(
            UserLLMRealtime.firewall_reasons
        ).where(
            and_(
                *conditions,
                UserLLMRealtime.firewall_blocked == True,
                UserLLMRealtime.firewall_reasons.isnot(None)
            )
        ).limit(100)
        
        blocked_result = await db.execute(blocked_details_query)
        block_reasons = {"pii": 0, "secrets": 0, "toxicity": 0}
        
        for row in blocked_result.all():
            if row.firewall_reasons:
                reasons = row.firewall_reasons
                if isinstance(reasons, str):
                    try:
                        reasons = json.loads(reasons)
                    except:
                        continue
                
                if isinstance(reasons, dict):
                    for scan_type in ["pii", "secrets", "toxicity"]:
                        if scan_type in reasons and reasons[scan_type].get("contains_" + scan_type, False):
                            block_reasons[scan_type] += 1

        return {
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "firewall_activity": {
                "total_requests": total_requests,
                "blocked_requests": blocked_requests,
                "allowed_requests": allowed_requests,
                "block_rate": round(block_rate, 1),
                "allow_rate": round(100 - block_rate, 1)
            },
            "block_reasons": {
                "pii_violations": block_reasons["pii"],
                "secrets_detected": block_reasons["secrets"],
                "toxicity_detected": block_reasons["toxicity"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))