"""Enhanced WebSocket endpoints with session management for real-time communication."""

import logging
import uuid
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Session management imports
from ..utils.session_dispatch import dispatch_session_message, get_session_stats, cleanup_expired_sessions
from ..utils.session_config import session_config
from ..utils.buffer_manager import buffer_manager
from ..monitoring.config.database import get_db
from ..monitoring.config.settings import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/v1", tags=["websocket", "session"])

# Active WebSocket connections tracking
active_connections: Dict[str, WebSocket] = {}
session_connections: Dict[str, str] = {}  # session_id -> connection_id

# Analytics subscription tracking
analytics_subscribers: Dict[str, Dict] = {}  # session_id -> {user_id, connection_id, subscription_info}
analytics_broadcast_task: Optional[Any] = None
analytics_last_data: Dict[str, Any] = {}  # Cache for last analytics data


async def get_session_config():
    """Get session configuration."""
    return session_config


async def get_live_analytics_data(org_id: str) -> Dict[str, Any]:
    """Get current analytics data for broadcasting."""
    try:
        # Import analytics service and database
        from ..monitoring.api.routers.analytics import PhoenixAnalyticsService
        from ..db.database import db_manager
        
        analytics_service = PhoenixAnalyticsService()
        
        # Get data for the last 30 days for real-time metrics (matching frontend default)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        
        # Get database session from orchestrator DB manager
        async for db in db_manager.get_session():
            try:
                analytics_data = await analytics_service.get_analytics_overview_from_phoenix(
                    start_date=start_date,
                    end_date=end_date,
                    organization_id=org_id,
                    db=db
                )
                break
            finally:
                await db.close()
        
        # Transform to the format expected by the frontend
        if analytics_data and analytics_data.get('overview'):
            overview = analytics_data['overview']
            return {
                "total_api_calls": overview.get('total_api_calls', 0),
                "total_cost": overview.get('total_cost', 0.0),
                "cache_hit_rate": overview.get('cache_hit_rate', 0.0),
                "avg_response_time_ms": overview.get('avg_response_time_ms', 0),
                "firewall_blocks": overview.get('firewall_blocks', 0),
                "provider_breakdown": analytics_data.get('provider_breakdown', [])
            }
        else:
            # Return empty data structure if no analytics available
            return {
                "total_api_calls": 0,
                "total_cost": 0.0,
                "cache_hit_rate": 0.0,
                "avg_response_time_ms": 0,
                "firewall_blocks": 0,
                "provider_breakdown": []
            }
            
    except Exception as e:
        logger.error(f"Error getting live analytics data: {e}")
        # Return empty data on error
        return {
            "total_api_calls": 0,
            "total_cost": 0.0,
            "cache_hit_rate": 0.0,
            "avg_response_time_ms": 0,
            "firewall_blocks": 0,
            "provider_breakdown": []
        }


async def broadcast_analytics_to_subscribers():
    """Broadcast analytics data to all subscribed sessions."""
    if not analytics_subscribers:
        return
    
    try:
        # Get analytics data for the default organization
        config = get_config()
        org_id = config.get_organization_id() if hasattr(config, 'get_organization_id') else 'org_001'
        
        analytics_data = await get_live_analytics_data(org_id)
        
        # Cache the data
        analytics_last_data[org_id] = analytics_data
        
        # Broadcast to all subscribers
        disconnected_sessions = []
        
        for session_id, subscriber_info in analytics_subscribers.items():
            try:
                connection_id = subscriber_info.get('connection_id')
                if connection_id in active_connections:
                    websocket = active_connections[connection_id]
                    
                    response = {
                        "type": "analytics_response",
                        "data": analytics_data,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "session_id": session_id
                    }
                    
                    await websocket.send_text(json.dumps(response))
                    logger.debug(f"Analytics data sent to session {session_id}")
                else:
                    # Connection no longer active
                    disconnected_sessions.append(session_id)
                    
            except Exception as e:
                logger.error(f"Error sending analytics to session {session_id}: {e}")
                disconnected_sessions.append(session_id)
        
        # Cleanup disconnected sessions
        for session_id in disconnected_sessions:
            if session_id in analytics_subscribers:
                del analytics_subscribers[session_id]
                logger.info(f"Removed disconnected analytics subscriber: {session_id}")
                
    except Exception as e:
        logger.error(f"Error in analytics broadcasting: {e}")


async def start_analytics_broadcasting():
    """Start the periodic analytics broadcasting task."""
    global analytics_broadcast_task
    
    if analytics_broadcast_task is None:
        async def analytics_broadcast_loop():
            while True:
                try:
                    if analytics_subscribers:  # Only broadcast if there are subscribers
                        await broadcast_analytics_to_subscribers()
                    await asyncio.sleep(30)  # Broadcast every 30 seconds
                except asyncio.CancelledError:
                    logger.info("Analytics broadcasting task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in analytics broadcast loop: {e}")
                    await asyncio.sleep(30)  # Continue after error
        
        analytics_broadcast_task = asyncio.create_task(analytics_broadcast_loop())
        logger.info("Analytics broadcasting task started")


async def stop_analytics_broadcasting():
    """Stop the analytics broadcasting task."""
    global analytics_broadcast_task
    
    if analytics_broadcast_task:
        analytics_broadcast_task.cancel()
        try:
            await analytics_broadcast_task
        except asyncio.CancelledError:
            pass
        analytics_broadcast_task = None
        logger.info("Analytics broadcasting task stopped")


@router.websocket("/session")
async def websocket_unified_session_endpoint(
    websocket: WebSocket,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time chat with session management.
    
    Provides:
    - Session-aware user tracking
    - Real-time message handling
    - Conversation management
    - Automatic session cleanup
    
    Development mode: Authentication bypass (assume approved)
    """
    config = get_config()
    org_id = config.get_organization_id() if hasattr(config, 'get_organization_id') else 'org_001'
    
    # Development authentication bypass
    if not user_id:
        user_id = f"dev_user_{uuid.uuid4().hex[:8]}"
    if not session_id:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
    
    connection_id = str(uuid.uuid4())
    
    try:
        # Accept WebSocket connection
        await websocket.accept()
        
        # Register connection
        active_connections[connection_id] = websocket
        session_connections[session_id] = connection_id
        
        # Send session establishment confirmation
        session_response = await dispatch_session_message(
            {"type": "connect", "user_id": user_id, "session_id": session_id},
            user_id,
            session_id,
            session_config
        )
        await websocket.send_text(json.dumps(session_response))
        
        logger.info(f"WebSocket chat connection established: {session_id} for user {user_id}")
        
        # Message handling loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Add message ID if not present
                if "message_id" not in message:
                    message["message_id"] = str(uuid.uuid4())
                
                # Dispatch message through enhanced session system
                response = await dispatch_session_message(
                    message,
                    user_id,
                    session_id,
                    session_config
                )
                
                # Send response back to client
                await websocket.send_text(json.dumps(response))
                
                # Handle special message types
                if message.get("type") == "send_message":
                    # Process through actual agent system
                    try:
                        # Import the actual agent system
                        from ..agents import generate_llm_response
                        
                        # Extract message content and conversation ID
                        user_message = message.get("message", "")
                        conversation_id = response.get("data", {}).get("conversation_id", "default")
                        
                        if user_message.strip():
                            # Call the actual LLM agent system
                            agent_result = await generate_llm_response(
                                query=user_message,
                                session_id=conversation_id,
                                user_id=user_id
                            )
                            
                            # Format the response for WebSocket
                            assistant_response = {
                                "type": "assistant_response",
                                "data": {
                                    "message_id": str(uuid.uuid4()),
                                    "conversation_id": conversation_id,
                                    "content_delta": agent_result.get("answer", ""),
                                    "is_complete": True,
                                    "sequence_number": 2,
                                    "metadata": {
                                        "model": "gpt-3.5-turbo",
                                        "endpoint": "/ws/v1/session",
                                        "from_cache": agent_result.get("from_cache", False),
                                        "similarity": agent_result.get("similarity")
                                    }
                                },
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                            await websocket.send_text(json.dumps(assistant_response))
                    
                    except ImportError as import_error:
                        # Fallback if agent system not available
                        logger.error(f"Agent system import failed: {import_error}")
                        assistant_response = {
                            "type": "assistant_response",
                            "data": {
                                "message_id": str(uuid.uuid4()),
                                "conversation_id": response.get("data", {}).get("conversation_id"),
                                "content_delta": "Agent system unavailable - check import paths",
                                "is_complete": True,
                                "sequence_number": 2,
                                "metadata": {"model": "error", "error": "import_failed"}
                            },
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(assistant_response))
                    except Exception as e:
                        # Error handling for agent system
                        logger.error(f"Agent system error: {e}")
                        error_response = {
                            "type": "assistant_response",
                            "data": {
                                "message_id": str(uuid.uuid4()),
                                "conversation_id": response.get("data", {}).get("conversation_id"),
                                "content_delta": f"Error processing request: {str(e)}",
                                "is_complete": True,
                                "sequence_number": 2,
                                "metadata": {"model": "error", "error_type": "agent_error"}
                            },
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(error_response))
                
                # Handle analytics requests
                elif message.get("type") == "analytics_request":
                    try:
                        # Import analytics service
                        from ..monitoring.api.routers.analytics import PhoenixAnalyticsService
                        
                        analytics_service = PhoenixAnalyticsService()
                        request_data = message.get("data", {})
                        
                        # Parse dates properly
                        start_date_str = request_data.get("start_date")
                        end_date_str = request_data.get("end_date")
                        
                        # Convert ISO strings to datetime objects
                        if start_date_str and end_date_str:
                            from dateutil import parser
                            start_date = parser.parse(start_date_str) if isinstance(start_date_str, str) else start_date_str
                            end_date = parser.parse(end_date_str) if isinstance(end_date_str, str) else end_date_str
                        else:
                            # Default to last 30 days if no dates provided (matching frontend default)
                            end_date = datetime.now(timezone.utc)
                            start_date = end_date - timedelta(days=30)
                        
                        # Get analytics data with database session
                        from ..db.database import db_manager
                        async for db_session in db_manager.get_session():
                            try:
                                analytics_response = await analytics_service.get_analytics_overview_from_phoenix(
                                    start_date=start_date,
                                    end_date=end_date,
                                    organization_id=org_id,
                                    db=db_session
                                )
                                break
                            finally:
                                await db_session.close()
                        
                        # Extract the overview data for the expected format
                        if analytics_response and analytics_response.get('overview'):
                            overview = analytics_response['overview']
                            data = {
                                "total_api_calls": overview.get('total_api_calls', 0),
                                "total_cost": overview.get('total_cost', 0.0),
                                "cache_hit_rate": overview.get('cache_hit_rate', 0.0),
                                "avg_response_time_ms": overview.get('avg_response_time_ms', 0),
                                "firewall_blocks": overview.get('firewall_blocks', 0),
                                "provider_breakdown": analytics_response.get('provider_breakdown', []),
                                "data_source": analytics_response.get('data_source', 'phoenix')
                            }
                        else:
                            # Use existing data format
                            data = analytics_response
                        
                        # Send analytics response
                        response = {
                            "type": "analytics_response",
                            "data": data,
                            "correlation_id": message.get("message_id"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(response))
                        
                    except Exception as e:
                        logger.error(f"Analytics request error: {e}", exc_info=True)
                        error_response = {
                            "type": "analytics_error",
                            "data": {"error": str(e)},
                            "correlation_id": message.get("message_id"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(error_response))
                        
                # Handle analytics subscription (live updates)
                elif message.get("type") == "analytics_subscribe":
                    try:
                        # Add this session to analytics subscribers
                        analytics_subscribers[session_id] = {
                            "user_id": user_id,
                            "connection_id": connection_id,
                            "subscribed_at": datetime.now(timezone.utc).isoformat(),
                            "subscription_info": message.get("data", {})
                        }
                        
                        # Start broadcasting task if not already running
                        await start_analytics_broadcasting()
                        
                        # Send immediate analytics data
                        config = get_config()
                        current_org_id = config.get_organization_id() if hasattr(config, 'get_organization_id') else 'org_001'
                        
                        # Get cached data or fetch new data
                        if current_org_id in analytics_last_data:
                            analytics_data = analytics_last_data[current_org_id]
                        else:
                            analytics_data = await get_live_analytics_data(current_org_id)
                            analytics_last_data[current_org_id] = analytics_data
                        
                        # Send immediate analytics response (not subscription confirmation)
                        response = {
                            "type": "analytics_response",
                            "data": analytics_data,
                            "correlation_id": message.get("message_id"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(response))
                        
                        # Also send subscription confirmation
                        confirmation = {
                            "type": "analytics_subscription_confirmed",
                            "data": {"subscribed": True, "subscriber_count": len(analytics_subscribers)},
                            "correlation_id": message.get("message_id"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(confirmation))
                        
                        logger.info(f"Analytics subscription confirmed for session {session_id}. Total subscribers: {len(analytics_subscribers)}")
                        
                    except Exception as e:
                        logger.error(f"Analytics subscription error: {e}")
                        error_response = {
                            "type": "analytics_error",
                            "data": {"error": str(e)},
                            "correlation_id": message.get("message_id"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(error_response))
                        
                # Handle analytics unsubscribe
                elif message.get("type") == "analytics_unsubscribe":
                    try:
                        # Remove from analytics subscribers
                        if session_id in analytics_subscribers:
                            del analytics_subscribers[session_id]
                            
                        response = {
                            "type": "analytics_unsubscribed",
                            "data": {"subscribed": False, "subscriber_count": len(analytics_subscribers)},
                            "correlation_id": message.get("message_id"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(response))
                        
                        logger.info(f"Analytics unsubscribed for session {session_id}. Remaining subscribers: {len(analytics_subscribers)}")
                        
                        # Stop broadcasting task if no subscribers left
                        if not analytics_subscribers:
                            await stop_analytics_broadcasting()
                        
                    except Exception as e:
                        logger.error(f"Analytics unsubscribe error: {e}")
                        error_response = {
                            "type": "analytics_error",
                            "data": {"error": str(e)},
                            "correlation_id": message.get("message_id"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        await websocket.send_text(json.dumps(error_response))
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket chat disconnected: {session_id}")
                break
            except json.JSONDecodeError:
                error_response = {
                    "type": "error",
                    "data": {"error": "Invalid JSON format"},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_text(json.dumps(error_response))
            except Exception as e:
                logger.error(f"Error in chat WebSocket: {e}")
                error_response = {
                    "type": "error", 
                    "data": {"error": str(e)},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_text(json.dumps(error_response))
                
    except Exception as e:
        logger.error(f"Fatal error in chat WebSocket: {e}")
        await websocket.close()
    finally:
        # Cleanup connection
        if connection_id in active_connections:
            del active_connections[connection_id]
        if session_id in session_connections:
            del session_connections[session_id]
        
        # Cleanup analytics subscription
        if session_id in analytics_subscribers:
            del analytics_subscribers[session_id]
            logger.info(f"Removed analytics subscriber: {session_id}")
            
            # Stop broadcasting if no subscribers left
            if not analytics_subscribers:
                await stop_analytics_broadcasting()
        
        # Dispatch disconnect message
        try:
            await dispatch_session_message(
                {"type": "disconnect", "session_id": session_id},
                user_id,
                session_id,
                session_config
            )
        except Exception as e:
            logger.warning(f"Error during disconnect cleanup: {e}")


@router.websocket("/session/{session_id}")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for joining existing session.
    
    Allows reconnection to existing sessions with state restoration.
    """
    if not user_id:
        user_id = f"reconnect_user_{uuid.uuid4().hex[:8]}"
    
    connection_id = str(uuid.uuid4())
    
    try:
        await websocket.accept()
        
        # Check if session exists in buffer
        active_user = buffer_manager.get_active_user(user_id) if buffer_manager else None
        
        if active_user:
            # Restore existing session
            active_connections[connection_id] = websocket
            session_connections[session_id] = connection_id
            
            response = {
                "type": "session_restored",
                "data": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "restored_at": datetime.now(timezone.utc).isoformat(),
                    "session_data": active_user
                }
            }
            await websocket.send_text(json.dumps(response))
            
            logger.info(f"Session restored: {session_id} for user {user_id}")
        else:
            # Session not found
            error_response = {
                "type": "error",
                "data": {"error": "Session not found or expired"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket.send_text(json.dumps(error_response))
            await websocket.close()
            return
        
        # Handle messages same as chat endpoint
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                response = await dispatch_session_message(
                    message,
                    user_id,
                    session_id,
                    session_config
                )
                
                await websocket.send_text(json.dumps(response))
                
            except WebSocketDisconnect:
                logger.info(f"Session WebSocket disconnected: {session_id}")
                break
            except Exception as e:
                logger.error(f"Error in session WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Fatal error in session WebSocket: {e}")
    finally:
        # Cleanup
        if connection_id in active_connections:
            del active_connections[connection_id]
        if session_id in session_connections:
            del session_connections[session_id]


@router.get("/stats")
async def get_websocket_stats():
    """Get current WebSocket and session statistics."""
    try:
        session_stats = get_session_stats()
        connection_stats = {
            "active_websockets": len(active_connections),
            "active_sessions": len(session_connections),
            "connection_mappings": len(session_connections)
        }
        
        return {
            "websocket_stats": connection_stats,
            "session_stats": session_stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_sessions(timeout_seconds: int = 1800):
    """Manually trigger session cleanup."""
    try:
        cleaned_count = cleanup_expired_sessions(timeout_seconds)
        return {
            "cleaned_sessions": cleaned_count,
            "timeout_seconds": timeout_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/active")
async def get_active_sessions():
    """Get list of currently active sessions."""
    try:
        if buffer_manager:
            active_users = buffer_manager.get_active_users()
            return {
                "active_sessions": active_users,
                "count": len(active_users),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            return {
                "active_sessions": [],
                "count": 0,
                "error": "Buffer manager not available"
            }
    except Exception as e:
        logger.error(f"Error getting active sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def broadcast_to_session(session_id: str, message: Dict[str, Any]) -> bool:
    """
    Broadcast message to specific session.
    
    Returns True if message was sent successfully.
    """
    try:
        if session_id in session_connections:
            connection_id = session_connections[session_id]
            if connection_id in active_connections:
                websocket = active_connections[connection_id]
                await websocket.send_text(json.dumps(message))
                return True
        return False
    except Exception as e:
        logger.error(f"Error broadcasting to session {session_id}: {e}")
        return False


async def broadcast_to_all_sessions(message: Dict[str, Any]) -> int:
    """
    Broadcast message to all active sessions.
    
    Returns count of sessions that received the message.
    """
    sent_count = 0
    for session_id in list(session_connections.keys()):
        try:
            if await broadcast_to_session(session_id, message):
                sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to broadcast to session {session_id}: {e}")
    
    return sent_count