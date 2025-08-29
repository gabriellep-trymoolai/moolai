#!/bin/bash

echo "🔒 Azure B2C Integration Test Suite"
echo "===================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}This script will help you test Azure B2C integration step by step${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "services/orchestrator/app/auth/b2c.py" ]; then
    echo -e "${RED}❌ Error: Run this script from the workspace root directory${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Available Test Methods:${NC}"
echo ""
echo "1. 🌐 Test B2C Tenant Configuration (Direct)"
echo "2. 🐍 Test Backend Token Validation (Python)"
echo "3. 🌍 Test MSAL Authentication (Browser)"
echo "4. 🚀 Test API Endpoint (Minimal Server)"
echo "5. 🔗 Run All Tests"
echo ""

read -p "Choose a test method (1-5): " choice

case $choice in
    1)
        echo -e "${BLUE}🌐 Testing B2C Tenant Configuration...${NC}"
        echo ""
        echo "1. Opening B2C OpenID configuration in browser..."
        if command -v xdg-open &> /dev/null; then
            xdg-open "https://moolaib2c.b2clogin.com/moolaib2c.onmicrosoft.com/B2C_1_susi/v2.0/.well-known/openid-configuration"
        elif command -v open &> /dev/null; then
            open "https://moolaib2c.b2clogin.com/moolaib2c.onmicrosoft.com/B2C_1_susi/v2.0/.well-known/openid-configuration"
        else
            echo "Visit: https://moolaib2c.b2clogin.com/moolaib2c.onmicrosoft.com/B2C_1_susi/v2.0/.well-known/openid-configuration"
        fi
        echo ""
        echo "2. Testing B2C login page..."
        TEST_URL="https://moolaib2c.b2clogin.com/moolaib2c.onmicrosoft.com/B2C_1_susi/oauth2/v2.0/authorize?client_id=ac41a9da-ca72-48a3-a468-d9db5b218c4d&response_type=code&redirect_uri=http://localhost:3000/verify-email&scope=openid%20api://0263d89f-754d-4861-a401-8a44a0611618/access_as_user&state=test123&nonce=test456"
        if command -v xdg-open &> /dev/null; then
            xdg-open "$TEST_URL"
        elif command -v open &> /dev/null; then
            open "$TEST_URL"
        else
            echo "Visit: $TEST_URL"
        fi
        echo -e "${GREEN}✅ B2C tenant test URLs opened in browser${NC}"
        ;;
    
    2)
        echo -e "${BLUE}🐍 Testing Backend Token Validation...${NC}"
        echo ""
        cd services/orchestrator
        
        if [ ! -d "venv" ]; then
            echo -e "${YELLOW}Creating virtual environment...${NC}"
            python3 -m venv venv
        fi
        
        echo "Activating virtual environment and installing dependencies..."
        source venv/bin/activate
        pip install -q PyJWT cachetools httpx
        
        cd ../..
        python test_b2c_validation.py
        
        echo ""
        echo -e "${YELLOW}💡 To test token validation with a real token:${NC}"
        echo "   python test_b2c_validation.py YOUR_JWT_TOKEN_HERE"
        ;;
    
    3)
        echo -e "${BLUE}🌍 Testing MSAL Authentication...${NC}"
        echo ""
        echo "Opening MSAL test page in browser..."
        if command -v xdg-open &> /dev/null; then
            xdg-open "test_msal.html"
        elif command -v open &> /dev/null; then
            open "test_msal.html"
        else
            echo "Open test_msal.html in your browser"
        fi
        
        echo ""
        echo -e "${YELLOW}📋 Follow these steps in the browser:${NC}"
        echo "1. Click 'Login with Azure B2C'"
        echo "2. Complete the B2C authentication"
        echo "3. Click 'Get Access Token'"
        echo "4. Copy the token for further testing"
        echo ""
        echo -e "${GREEN}✅ MSAL test page opened${NC}"
        ;;
    
    4)
        echo -e "${BLUE}🚀 Starting Minimal API Server...${NC}"
        echo ""
        cd services/orchestrator
        
        if [ ! -d "venv" ]; then
            echo -e "${YELLOW}Creating virtual environment...${NC}"
            python3 -m venv venv
        fi
        
        echo "Activating virtual environment and installing dependencies..."
        source venv/bin/activate
        pip install -q fastapi uvicorn PyJWT cachetools httpx
        
        cd ../..
        echo ""
        echo -e "${YELLOW}💡 Get a token first using Method 3, then test with:${NC}"
        echo "   curl -H 'Authorization: Bearer YOUR_TOKEN' http://localhost:8001/me"
        echo ""
        python test_api_minimal.py
        ;;
    
    5)
        echo -e "${BLUE}🔗 Running All Tests...${NC}"
        echo ""
        
        # Test 1: B2C Configuration
        echo -e "${YELLOW}Step 1: Testing B2C Configuration...${NC}"
        cd services/orchestrator
        if [ ! -d "venv" ]; then
            python3 -m venv venv
        fi
        source venv/bin/activate
        pip install -q PyJWT cachetools httpx fastapi uvicorn
        cd ../..
        python test_b2c_validation.py
        
        echo ""
        echo -e "${YELLOW}Step 2: Opening MSAL test page...${NC}"
        if command -v xdg-open &> /dev/null; then
            xdg-open "test_msal.html"
        elif command -v open &> /dev/null; then
            open "test_msal.html"
        else
            echo "Open test_msal.html in your browser"
        fi
        
        echo ""
        echo -e "${YELLOW}Step 3: Manual testing required${NC}"
        echo "1. Complete authentication in the browser"
        echo "2. Get an access token"
        echo "3. Come back here and press ENTER to start the API server"
        read -p "Press ENTER when ready to test the API..."
        
        echo -e "${YELLOW}Step 4: Starting API server...${NC}"
        python test_api_minimal.py
        ;;
    
    *)
        echo -e "${RED}❌ Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Test completed!${NC}"
echo ""
echo -e "${YELLOW}📋 Summary of available files:${NC}"
echo "- test_b2c_direct.md      : Manual testing instructions"
echo "- test_b2c_validation.py  : Python script for backend testing"
echo "- test_msal.html          : Browser-based MSAL testing"
echo "- test_api_minimal.py     : Minimal API server for endpoint testing"
echo "- test_b2c_complete.sh    : This comprehensive test script"