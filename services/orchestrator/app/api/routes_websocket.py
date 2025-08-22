"""Enhanced WebSocket endpoints with session management for real-time communication."""

import logging
import uuid
import json
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Session management imports
from ..utils.session_dispatch import dispatch_session_message, get_session_stats, cleanup_expired_sessions
from ..utils.session_config import session_config
from ..utils.buffer_manager import buffer_manager
from ..monitoring.config.database import get_db
from ..monitoring.config.settings import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket", "session"])

# Active WebSocket connections tracking
active_connections: Dict[str, WebSocket] = {}
session_connections: Dict[str, str] = {}  # session_id -> connection_id


async def get_session_config():
    """Get session configuration."""
    return session_config


@router.websocket("/chat")
async def websocket_chat_endpoint(
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
                    # TODO: Process through LLM and send assistant_response
                    assistant_response = {
                        "type": "assistant_response",
                        "data": {
                            "message_id": str(uuid.uuid4()),
                            "conversation_id": response.get("data", {}).get("conversation_id"),
                            "content_delta": "This is a placeholder AI response.",
                            "is_complete": True,
                            "sequence_number": 2,
                            "metadata": {"model": "placeholder"}
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await websocket.send_text(json.dumps(assistant_response))
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket chat disconnected: {session_id}")
                break
            except json.JSONDecodeError:
                error_response = {
                    "type": "error",
                    "data": {"error": "Invalid JSON format"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send_text(json.dumps(error_response))
            except Exception as e:
                logger.error(f"Error in chat WebSocket: {e}")
                error_response = {
                    "type": "error", 
                    "data": {"error": str(e)},
                    "timestamp": datetime.utcnow().isoformat()
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
                    "restored_at": datetime.utcnow().isoformat(),
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
                "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
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
                "timestamp": datetime.utcnow().isoformat()
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