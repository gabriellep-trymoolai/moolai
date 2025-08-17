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
BUILD_TYPE=${1:-"production"}

echo -e "${BLUE}=== MoolAI Complete System Build ===${NC}"
echo "Build Date: $BUILD_DATE"
echo "VCS Ref: $VCS_REF"
echo "Version: $VERSION"
echo "Registry: $REGISTRY"
echo "Build Type: $BUILD_TYPE"
echo ""

# Export variables for docker-compose
export BUILD_DATE VCS_REF VERSION

# Function to build with Docker Compose
build_with_compose() {
    echo -e "${YELLOW}Building all services with Docker Compose...${NC}"
    
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
    
    # Array of services and their Dockerfiles
    declare -a services=(
        "monitoring:infrastructure/docker/Dockerfile.monitoring"
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
    
    # Test monitoring service with real-time features
    if [[ -f "test_monitoring_service.py" ]]; then
        echo -e "${YELLOW}Testing monitoring service with real-time features...${NC}"
        if command -v python3 &> /dev/null; then
            python3 test_monitoring_service.py || echo -e "${YELLOW}⚠️  Monitoring service tests failed${NC}"
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
    
    # Run monitoring service tests
    if [[ -d "services/monitoring/tests" ]]; then
        echo -e "${YELLOW}Running monitoring service unit tests...${NC}"
        cd services/monitoring
        if command -v python3 &> /dev/null; then
            python3 -m pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️  Some unit tests failed${NC}"
        else
            echo -e "${YELLOW}⚠️  Python3 not found, skipping unit tests${NC}"
        fi
        cd ../..
    fi
    
    # Run Docker build tests if available
    if [[ -f "scripts/docker-verify.sh" ]]; then
        echo -e "${YELLOW}Running Docker verification...${NC}"
        chmod +x scripts/docker-verify.sh
        ./scripts/docker-verify.sh || echo -e "${YELLOW}⚠️  Docker verification had issues${NC}"
    fi
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
    if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -q "moolai\|monitoring\|orchestrator\|controller"; then
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|moolai|monitoring|orchestrator|controller)"
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
    "production"|"prod"|*)
        echo -e "${YELLOW}Building with Docker Compose (recommended for production)...${NC}"
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

# Show results
show_results

echo -e "\n${GREEN}=== Build Complete! ===${NC}"
echo -e "Services available:"
echo -e "  - Orchestrator (Org 001): http://localhost:8000"
echo -e "  - Monitoring (Org 001):   http://localhost:8001"
echo -e "    → SSE Metrics:           http://localhost:8001/api/v1/stream/metrics/organization"
echo -e "    → WebSocket Admin:       ws://localhost:8001/ws/admin/control"
echo -e "  - Orchestrator (Org 002): http://localhost:8010"
echo -e "  - Monitoring (Org 002):   http://localhost:8011"
echo -e "    → SSE Metrics:           http://localhost:8011/api/v1/stream/metrics/organization"
echo -e "    → WebSocket Admin:       ws://localhost:8011/ws/admin/control"
echo -e "  - Controller:              http://localhost:8002"
echo ""
echo -e "${BLUE}Real-time Features Available:${NC}"
echo -e "  - Server-Sent Events (SSE) for live metrics streaming"
echo -e "  - WebSocket for bidirectional admin control"
echo -e "  - Multi-tenant isolation with organization-level channels"
echo -e "  - JavaScript/React client libraries in client/js/"
echo ""
echo -e "To start the system: ${YELLOW}docker-compose up -d${NC}"
echo -e "To view logs:        ${YELLOW}docker-compose logs -f${NC}"
echo -e "To stop the system:  ${YELLOW}docker-compose down${NC}"
echo ""
echo -e "For development:     ${YELLOW}docker-compose up${NC} (without -d for live logs)"
echo -e "Test real-time:      ${YELLOW}curl -N -H \"Accept: text/event-stream\" \"http://localhost:8001/api/v1/stream/system/health\"${NC}"