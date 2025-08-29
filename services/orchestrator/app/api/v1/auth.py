"""
Authentication API Endpoints
Provides authentication endpoints for Azure B2C integration
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
from datetime import datetime

# Import common models and utilities
import sys
import os
# Add workspace root to Python path
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../'))
if workspace_root not in sys.path:
    sys.path.append(workspace_root)

from common.api.models import APIResponse, User
from common.api.utils import create_success_response

# Import authentication
from ...auth.deps import get_current_user

router = APIRouter(prefix="/api/v1", tags=["Authentication"])

@router.get("/me", response_model=APIResponse[User])
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get current authenticated user information"""
    return create_success_response(
        data=User(
            user_id=str(current_user.get("id")),
            email=current_user.get("email"),
            username=current_user.get("email", "").split("@")[0],  # Use email prefix as username
            roles=current_user.get("roles", "[]"),
            is_active=True,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),
        service="orchestrator",
        message="Current user information retrieved successfully"
    )