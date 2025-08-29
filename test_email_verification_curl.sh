#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE="http://localhost:8000"
EMAIL="test@example.com"

echo -e "${BLUE}📧 Email Verification Flow Test${NC}"
echo "=================================="
echo ""

# Check if server is running
echo -e "${YELLOW}🔍 Checking if API server is running...${NC}"
if ! curl -s "$API_BASE/health" > /dev/null 2>&1; then
    echo -e "${RED}❌ API server is not running at $API_BASE${NC}"
    echo "Start the server first:"
    echo "  cd services/orchestrator"
    echo "  source venv/bin/activate"
    echo "  export OPENAI_API_KEY='dummy_key'"
    echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

echo -e "${GREEN}✅ API server is running${NC}"
echo ""

# Allow user to change email
if [ "$1" != "" ]; then
    EMAIL="$1"
fi

echo -e "${BLUE}📧 Testing with email: $EMAIL${NC}"
echo ""

# Step 1: Send verification code
echo -e "${YELLOW}Step 1: Sending verification code...${NC}"
echo "Command:"
echo "curl -X POST '$API_BASE/api/v1/auth/send-verification-code' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"email\": \"$EMAIL\"}'"
echo ""

SEND_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/auth/send-verification-code" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\"}")

echo "Response:"
echo "$SEND_RESPONSE" | jq . 2>/dev/null || echo "$SEND_RESPONSE"
echo ""

# Check if send was successful
if echo "$SEND_RESPONSE" | grep -q '"success": *true'; then
    echo -e "${GREEN}✅ Verification code sent successfully${NC}"
    echo ""
    echo -e "${YELLOW}📧 Check the server console for the verification code!${NC}"
    echo ""
else
    echo -e "${RED}❌ Failed to send verification code${NC}"
    exit 1
fi

# Step 2: Prompt for verification code
echo -e "${YELLOW}Step 2: Enter the verification code${NC}"
read -p "Enter the 6-digit code from server console: " VERIFICATION_CODE

# Validate input
if [[ ! "$VERIFICATION_CODE" =~ ^[0-9]{6}$ ]]; then
    echo -e "${RED}❌ Invalid code format. Must be 6 digits.${NC}"
    exit 1
fi

echo ""

# Step 3: Verify the code
echo -e "${YELLOW}Step 3: Verifying code...${NC}"
echo "Command:"
echo "curl -X POST '$API_BASE/api/v1/auth/verify-code' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"email\": \"$EMAIL\", \"code\": \"$VERIFICATION_CODE\"}'"
echo ""

VERIFY_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/auth/verify-code" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"code\": \"$VERIFICATION_CODE\"}")

echo "Response:"
echo "$VERIFY_RESPONSE" | jq . 2>/dev/null || echo "$VERIFY_RESPONSE"
echo ""

# Check if verification was successful
if echo "$VERIFY_RESPONSE" | grep -q '"success": *true'; then
    echo -e "${GREEN}✅ Email verified successfully!${NC}"
    
    # Extract redirect URL if available
    REDIRECT_URL=$(echo "$VERIFY_RESPONSE" | jq -r '.redirect_url // empty' 2>/dev/null)
    if [ "$REDIRECT_URL" != "" ]; then
        echo -e "${BLUE}🔗 Redirect to: $REDIRECT_URL${NC}"
    fi
    
    # Extract user ID if available
    USER_ID=$(echo "$VERIFY_RESPONSE" | jq -r '.user_id // empty' 2>/dev/null)
    if [ "$USER_ID" != "" ]; then
        echo -e "${BLUE}👤 User ID: $USER_ID${NC}"
    fi
    
else
    echo -e "${RED}❌ Email verification failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Email verification flow completed successfully!${NC}"
echo ""

# Bonus: Show verification status
echo -e "${YELLOW}Bonus: Checking verification status...${NC}"
echo "Command:"
echo "curl '$API_BASE/api/v1/auth/verification-status/$EMAIL'"
echo ""

STATUS_RESPONSE=$(curl -s "$API_BASE/api/v1/auth/verification-status/$EMAIL")
echo "Response:"
echo "$STATUS_RESPONSE" | jq . 2>/dev/null || echo "$STATUS_RESPONSE"
echo ""

echo -e "${BLUE}📋 Summary of curl commands for integration:${NC}"
echo ""
echo "# 1. Send verification code"
echo "curl -X POST '$API_BASE/api/v1/auth/send-verification-code' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"email\": \"user@example.com\"}'"
echo ""
echo "# 2. Verify code"
echo "curl -X POST '$API_BASE/api/v1/auth/verify-code' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"email\": \"user@example.com\", \"code\": \"123456\"}'"
echo ""
echo "# 3. Check status (optional)"
echo "curl '$API_BASE/api/v1/auth/verification-status/user@example.com'"
echo ""

echo -e "${GREEN}✅ Test completed!${NC}"