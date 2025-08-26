#!/bin/bash

# MoolAI Complete System Build Script
# Production-ready build with optimization and security

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Build configuration
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
VERSION=${VERSION:-"1.0.0"}
REGISTRY=${REGISTRY:-"moolai"}
BUILD_TYPE=${1:-"development"}

echo -e "${BLUE}=== MoolAI Complete System Build ===${NC}"
echo "Build Date: $BUILD_DATE"
echo "VCS Ref: $VCS_REF"
echo "Version: $VERSION"
echo "Registry: $REGISTRY"
echo "Build Type: $BUILD_TYPE"
echo ""

# Export variables for docker-compose
export BUILD_DATE VCS_REF VERSION

# Function to build frontend locally before Docker build
build_frontend() {
    echo -e "${YELLOW}Building frontend locally...${NC}"
    
    cd services/orchestrator/app/gui/frontend
    
    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ npm not found. Please install Node.js and npm${NC}"
        exit 1
    fi
    
    # Install dependencies if node_modules doesn't exist
    if [[ ! -d "node_modules" ]]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi
    
    # Build the frontend
    echo -e "${YELLOW}Building React frontend...${NC}"
    npm run build
    
    # Verify build output
    if [[ -d "dist" ]]; then
        echo -e "${GREEN}✓ Frontend built successfully${NC}"
        echo -e "Frontend build size: $(du -sh dist | cut -f1)"
    else
        echo -e "${RED}❌ Frontend build failed - dist directory not found${NC}"
        exit 1
    fi
    
    cd - > /dev/null
}

# Function to build with Docker Compose
build_with_compose() {
    echo -e "${YELLOW}Building all services with Docker Compose...${NC}"
    
    # Build frontend first if not in production mode
    if [[ "$BUILD_TYPE" != "production" && "$BUILD_TYPE" != "prod" ]]; then
        build_frontend
    fi
    
    # Build all services
    docker-compose build \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VCS_REF="$VCS_REF" \
        --build-arg VERSION="$VERSION" \
        --parallel
    
    echo -e "${GREEN}✓ All services built with Docker Compose${NC}"
}

# Function to build individual services
build_individual_services() {
    echo -e "${YELLOW}Building individual services...${NC}"
    
    # Build frontend first for orchestrator service
    build_frontend
    
    # Array of services and their Dockerfiles
    declare -a services=(
        "orchestrator:infrastructure/docker/Dockerfile.orchestrator"
        "controller:infrastructure/docker/Dockerfile.controller"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r service dockerfile <<< "$service_info"
        
        echo -e "\n${YELLOW}Building $service...${NC}"
        
        DOCKER_BUILDKIT=1 docker build \
            --build-arg BUILD_DATE="$BUILD_DATE" \
            --build-arg VCS_REF="$VCS_REF" \
            --build-arg VERSION="$VERSION" \
            --target production \
            --tag "$REGISTRY/$service:$VERSION" \
            --tag "$REGISTRY/$service:latest" \
            --file "$dockerfile" \
            .
        
        # Get image size
        local size=$(docker images "$REGISTRY/$service:$VERSION" --format "table {{.Size}}" | tail -n 1)
        echo -e "${GREEN}✓ $service built successfully - Size: $size${NC}"
    done
}

# Function to run security validation
run_security_scan() {
    echo -e "\n${BLUE}=== Running Security Validation ===${NC}"
    
    if [[ -f "scripts/docker-security-scan.sh" ]]; then
        chmod +x scripts/docker-security-scan.sh
        ./scripts/docker-security-scan.sh
    else
        echo -e "${YELLOW}⚠️  Security scan script not found${NC}"
    fi
}

# Function to run tests
run_tests() {
    echo -e "\n${BLUE}=== Running Tests ===${NC}"
    
    # Test real-time infrastructure components
    if [[ -f "test_realtime_components.py" ]]; then
        echo -e "${YELLOW}Testing real-time infrastructure...${NC}"
        if command -v python3 &> /dev/null; then
            python3 test_realtime_components.py || echo -e "${YELLOW}⚠️  Real-time component tests failed${NC}"
        else
            echo -e "${YELLOW}⚠️  Python3 not found, skipping real-time tests${NC}"
        fi
    fi
    
    # Test embedded monitoring with real-time features
    if [[ -f "test_system_monitoring.py" ]]; then
        echo -e "${YELLOW}Testing embedded monitoring system with real-time features...${NC}"
        if command -v python3 &> /dev/null; then
            python3 test_system_monitoring.py || echo -e "${YELLOW}⚠️  Embedded monitoring tests failed${NC}"
        else
            echo -e "${YELLOW}⚠️  Python3 not found, skipping monitoring tests${NC}"
        fi
    fi
    
    # Run full system integration tests
    if [[ -f "test_full_system.py" ]]; then
        echo -e "${YELLOW}Testing full system integration...${NC}"
        if command -v python3 &> /dev/null; then
            python3 test_full_system.py || echo -e "${YELLOW}⚠️  System integration tests failed${NC}"
        else
            echo -e "${YELLOW}⚠️  Python3 not found, skipping integration tests${NC}"
        fi
    fi
    
    # Run embedded monitoring tests (within orchestrator tests)
    if [[ -d "services/orchestrator/tests" ]]; then
        echo -e "${YELLOW}Running orchestrator tests (including embedded monitoring)...${NC}"
        cd services/orchestrator
        if command -v python3 &> /dev/null; then
            python3 -m pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️  Some unit tests failed${NC}"
        else
            echo -e "${YELLOW}⚠️  Python3 not found, skipping unit tests${NC}"
        fi
        cd ../..
    else
        echo -e "${YELLOW}Note: Monitoring is now embedded in orchestrator service${NC}"
    fi
    
    # Run Docker build tests if available
    if [[ -f "scripts/docker-verify.sh" ]]; then
        echo -e "${YELLOW}Running Docker verification...${NC}"
        chmod +x scripts/docker-verify.sh
        ./scripts/docker-verify.sh || echo -e "${YELLOW}⚠️  Docker verification had issues${NC}"
    fi
}

# Function to start containers in development mode
start_development_containers() {
    echo -e "\n${BLUE}=== Starting Development Containers ===${NC}"
    
    # Stop any existing containers first
    echo -e "${YELLOW}Stopping existing containers...${NC}"
    docker-compose down 2>/dev/null || true
    
    # Start containers in development mode (with live logs)
    echo -e "${YELLOW}Starting containers in development mode...${NC}"
    docker-compose up -d
    
    # Wait a moment for containers to initialize
    sleep 3
    
    # Show container status
    echo -e "\n${GREEN}✓ Containers started in development mode${NC}"
    docker-compose ps
}

# Function to show final results
show_results() {
    echo -e "\n${BLUE}=== Build Results ===${NC}"
    
    # Show built images
    echo -e "\n${YELLOW}Built Images:${NC}"
    if [[ "$BUILD_TYPE" == "compose" ]]; then
        docker-compose images
    else
        docker images "$REGISTRY/*:$VERSION" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"
    fi
    
    # Show running containers (if any)
    echo -e "\n${YELLOW}Container Status:${NC}"
    if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -q "moolai\|monitoring\|orchestrator\|controller\|phoenix"; then
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|moolai|monitoring|orchestrator|controller|phoenix)"
    else
        echo "No MoolAI containers currently running"
    fi
}

# Main build process
case "$BUILD_TYPE" in
    "compose"|"docker-compose")
        build_with_compose
        ;;
    "individual"|"services")
        build_individual_services
        ;;
    "production"|"prod")
        echo -e "${YELLOW}Building with Docker Compose (production mode)...${NC}"
        build_with_compose
        ;;
    "development"|"dev"|*)
        echo -e "${YELLOW}Building with Docker Compose (development mode)...${NC}"
        build_with_compose
        ;;
esac

# Run additional validations
if [[ "$BUILD_TYPE" != "quick" ]]; then
    run_security_scan
    
    if [[ "$2" == "--test" || "$2" == "-t" ]]; then
        run_tests
    fi
fi

# Start containers in development mode
start_development_containers

# Show results
show_results

echo -e "\n${GREEN}=== Build Complete! System Running in Development Mode ===${NC}"
echo -e "Services are now running and available:"
echo -e "  - ${BLUE}🌐 MoolAI Frontend UI:      http://localhost:8000${NC}"
echo -e "    → Dashboard Chat:          http://localhost:8000/dashboard"
echo -e "    → Analytics:               http://localhost:8000/analytics"
echo -e "    → Configuration:           http://localhost:8000/configuration/keys"
echo -e "    → WebSocket Test:          http://localhost:8000/test-websocket"
echo -e "  - Orchestrator (Org 001):   http://localhost:8000"
echo -e "    → Health Check:            http://localhost:8000/health"
echo -e "    → Embedded Monitoring:     http://localhost:8000/api/v1/system/metrics"
echo -e "    → Cache API:               http://localhost:8000/api/v1/cache/stats"
echo -e "    → LLM API:                 http://localhost:8000/api/v1/llm/prompt"
echo -e "    → Agent API:               http://localhost:8000/api/v1/agents/prompt-response"
echo -e "    → Firewall API:            http://localhost:8000/api/v1/firewall/scan/pii"
echo -e "    → WebSocket Chat:          ws://localhost:8000/ws/chat"
echo -e "  - Orchestrator (Org 002):   http://localhost:8010"
echo -e "    → Health Check:            http://localhost:8010/health"
echo -e "    → Embedded Monitoring:     http://localhost:8010/api/v1/system/metrics"
echo -e "  - Controller:                http://localhost:9000"
echo -e "    → Health Check:            http://localhost:9000/health"
echo -e "  - ${BLUE}🔭 Phoenix AI Observability: http://localhost:6006${NC}"
echo -e "    → LLM Traces & Spans:      http://localhost:6006"
echo -e "    → Analytics Dashboard:     http://localhost:6006"
echo -e "    → OTLP gRPC Collector:     http://localhost:4317"
echo ""
echo -e "${BLUE}Development Commands:${NC}"
echo -e "  View live logs:      ${YELLOW}docker-compose logs -f${NC}"
echo -e "  View specific logs:  ${YELLOW}docker-compose logs -f orchestrator-org-001${NC}"
echo -e "  Stop the system:     ${YELLOW}docker-compose down${NC}"
echo -e "  Restart a service:   ${YELLOW}docker-compose restart orchestrator-org-001${NC}"
echo ""
echo -e "${BLUE}Quick Health Tests:${NC}"
echo -e "  Test frontend UI:    ${YELLOW}curl http://localhost:8000${NC}"
echo -e "  Test orchestrator:   ${YELLOW}curl http://localhost:8000/health${NC}"
echo -e "  Test controller:     ${YELLOW}curl http://localhost:9000/health${NC}"
echo -e "  Test monitoring:     ${YELLOW}curl http://localhost:8000/api/v1/system/health${NC}"
echo -e "  Test cache:          ${YELLOW}curl http://localhost:8000/api/v1/cache/stats${NC}"
echo -e "  Test Phoenix UI:     ${YELLOW}curl http://localhost:6006${NC}"
echo -e "  Test Phoenix Health: ${YELLOW}wget -qO- http://localhost:6006/ >/dev/null && echo 'Phoenix OK'${NC}"
echo -e ""
echo -e "${GREEN}🎉 MoolAI System with Integrated UI is Ready!${NC}"
echo -e "Open your browser to: ${BLUE}http://localhost:8000${NC}"