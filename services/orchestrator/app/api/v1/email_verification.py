"""
Email Verification API Endpoints
Traditional email/OTP verification system for testing
"""

import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

# In-memory storage for demo (use Redis/database in production)
verification_codes: Dict[str, Dict] = {}

router = APIRouter(prefix="/api/v1/auth", tags=["Email Verification"])

class SendCodeRequest(BaseModel):
    email: EmailStr

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str

class SendCodeResponse(BaseModel):
    success: bool
    message: str
    email: str
    expires_in: int  # seconds

class VerifyCodeResponse(BaseModel):
    success: bool
    message: str
    email: str
    user_id: Optional[str] = None
    redirect_url: Optional[str] = None

def generate_verification_code() -> str:
    """Generate a 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))

def send_email_code(email: str, code: str) -> bool:
    """
    Send verification code via email
    For demo purposes, this just prints the code
    In production, implement actual email sending
    """
    # For testing, just print the code
    print(f"\n📧 EMAIL VERIFICATION CODE")
    print(f"To: {email}")
    print(f"Code: {code}")
    print(f"Expires: 10 minutes")
    print(f"=" * 40)
    
    # TODO: Implement actual email sending
    # smtp_server = "your-smtp-server.com"
    # smtp_port = 587
    # smtp_username = "your-email@example.com"
    # smtp_password = "your-app-password"
    # 
    # msg = MimeMultipart()
    # msg['From'] = smtp_username
    # msg['To'] = email
    # msg['Subject'] = "Your Verification Code"
    # 
    # body = f"""
    # Your verification code is: {code}
    # This code will expire in 10 minutes.
    # """
    # msg.attach(MimeText(body, 'plain'))
    # 
    # try:
    #     server = smtplib.SMTP(smtp_server, smtp_port)
    #     server.starttls()
    #     server.login(smtp_username, smtp_password)
    #     text = msg.as_string()
    #     server.sendmail(smtp_username, email, text)
    #     server.quit()
    #     return True
    # except Exception as e:
    #     print(f"Email sending failed: {e}")
    #     return False
    
    return True  # Simulate successful sending

@router.post("/send-verification-code", response_model=SendCodeResponse)
async def send_verification_code(request: SendCodeRequest):
    """
    Send verification code to email address
    """
    email = request.email.lower()
    code = generate_verification_code()
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Store verification code
    verification_codes[email] = {
        "code": code,
        "expires_at": expires_at,
        "attempts": 0,
        "created_at": datetime.utcnow()
    }
    
    # Send email (for demo, just print)
    if send_email_code(email, code):
        return SendCodeResponse(
            success=True,
            message=f"Verification code sent to {email}",
            email=email,
            expires_in=600  # 10 minutes
        )
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send verification email"
        )

@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_code(request: VerifyCodeRequest):
    """
    Verify the email verification code
    """
    email = request.email.lower()
    code = request.code.strip()
    
    # Check if verification record exists
    if email not in verification_codes:
        raise HTTPException(
            status_code=400,
            detail="No verification code found for this email. Please request a new code."
        )
    
    verification_data = verification_codes[email]
    
    # Check if code has expired
    if datetime.utcnow() > verification_data["expires_at"]:
        del verification_codes[email]  # Clean up expired code
        raise HTTPException(
            status_code=400,
            detail="Verification code has expired. Please request a new code."
        )
    
    # Check attempt limit
    if verification_data["attempts"] >= 3:
        del verification_codes[email]  # Clean up after too many attempts
        raise HTTPException(
            status_code=400,
            detail="Too many failed attempts. Please request a new code."
        )
    
    # Verify the code
    if verification_data["code"] != code:
        verification_data["attempts"] += 1
        remaining_attempts = 3 - verification_data["attempts"]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid verification code. {remaining_attempts} attempts remaining."
        )
    
    # Success! Clean up the verification record
    del verification_codes[email]
    
    # In a real system, you would:
    # 1. Create or update user account
    # 2. Generate session token
    # 3. Set up user profile
    
    # For demo, simulate user creation
    user_id = f"user_{email.split('@')[0]}_{datetime.utcnow().strftime('%Y%m%d')}"
    
    return VerifyCodeResponse(
        success=True,
        message="Email verified successfully!",
        email=email,
        user_id=user_id,
        redirect_url="/profile-setup"  # Where to redirect after verification
    )

@router.get("/verification-status/{email}")
async def get_verification_status(email: str):
    """
    Check verification status for an email (for debugging)
    """
    email = email.lower()
    
    if email not in verification_codes:
        return {
            "email": email,
            "has_pending_verification": False,
            "message": "No pending verification"
        }
    
    data = verification_codes[email]
    is_expired = datetime.utcnow() > data["expires_at"]
    
    return {
        "email": email,
        "has_pending_verification": not is_expired,
        "expires_at": data["expires_at"].isoformat(),
        "attempts_used": data["attempts"],
        "attempts_remaining": max(0, 3 - data["attempts"]),
        "is_expired": is_expired
    }