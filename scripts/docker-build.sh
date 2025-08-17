#!/bin/bash

# MoolAI Docker Build Script with Multi-Stage Optimization
# This script builds all services with advanced optimization techniques

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

echo -e "${BLUE}=== MoolAI Docker Multi-Stage Build ===${NC}"
echo "Build Date: $BUILD_DATE"
echo "VCS Ref: $VCS_REF"
echo "Version: $VERSION"
echo "Registry: $REGISTRY"

# Function to build with multi-stage optimization
build_service() {
    local service=$1
    local dockerfile=$2
    local context=${3:-"."}
    
    echo -e "\n${YELLOW}Building $service with multi-stage optimization...${NC}"
    
    # Build with BuildKit for advanced features
    DOCKER_BUILDKIT=1 docker build \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VCS_REF="$VCS_REF" \
        --build-arg VERSION="$VERSION" \
        --target production \
        --tag "$REGISTRY/$service:$VERSION" \
        --tag "$REGISTRY/$service:latest" \
        --file "$dockerfile" \
        --progress=plain \
        "$context"
    
    # Get image size
    local size=$(docker images "$REGISTRY/$service:$VERSION" --format "table {{.Size}}" | tail -n 1)
    echo -e "${GREEN}✓ $service built successfully - Size: $size${NC}"
}

# Function to build development version (with build tools)
build_dev_service() {
    local service=$1
    local dockerfile=$2
    local context=${3:-"."}
    
    echo -e "\n${YELLOW}Building $service development version...${NC}"
    
    DOCKER_BUILDKIT=1 docker build \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VCS_REF="$VCS_REF" \
        --build-arg VERSION="$VERSION-dev" \
        --target builder \
        --tag "$REGISTRY/$service:dev" \
        --file "$dockerfile" \
        --progress=plain \
        "$context"
    
    echo -e "${GREEN}✓ $service development version built${NC}"
}

# Build monitoring service with real-time features
echo -e "\n${BLUE}=== Building Monitoring Service (with SSE/WebSocket) ===${NC}"
build_service "monitoring" "infrastructure/docker/Dockerfile.monitoring"

# Build orchestrator service  
echo -e "\n${BLUE}=== Building Orchestrator Service ===${NC}"
build_service "orchestrator" "infrastructure/docker/Dockerfile.orchestrator"

# Build controller service with real-time analytics
echo -e "\n${BLUE}=== Building Controller Service (with Real-time Analytics) ===${NC}"
build_service "controller" "infrastructure/docker/Dockerfile.controller"

# Optional: Build development versions
if [[ "$1" == "--dev" ]]; then
    echo -e "\n${BLUE}=== Building Development Versions ===${NC}"
    build_dev_service "monitoring" "infrastructure/docker/Dockerfile.monitoring"
    build_dev_service "orchestrator" "infrastructure/docker/Dockerfile.orchestrator"
    build_dev_service "controller" "infrastructure/docker/Dockerfile.controller"
fi

# Show final image sizes
echo -e "\n${BLUE}=== Final Image Sizes ===${NC}"
docker images "$REGISTRY/*:$VERSION" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Optional: Analyze layers
if [[ "$1" == "--analyze" ]]; then
    echo -e "\n${BLUE}=== Layer Analysis ===${NC}"
    for service in monitoring orchestrator controller; do
        echo -e "\n${YELLOW}$service layers:${NC}"
        docker history "$REGISTRY/$service:$VERSION" --no-trunc
    done
fi

# Security scan (if available)
if command -v docker-scout &> /dev/null; then
    echo -e "\n${BLUE}=== Security Scanning ===${NC}"
    for service in monitoring orchestrator controller; do
        echo -e "\n${YELLOW}Scanning $service...${NC}"
        docker-scout cves "$REGISTRY/$service:$VERSION" || echo "Scout scan failed for $service"
    done
fi

echo -e "\n${GREEN}=== Build Complete! ===${NC}"
echo -e "${BLUE}Real-time features included:${NC}"
echo -e "  ✓ Server-Sent Events (SSE) infrastructure"
echo -e "  ✓ WebSocket bidirectional communication"
echo -e "  ✓ Multi-tenant channel isolation"
echo -e "  ✓ Event bus with Redis PubSub"
echo -e "  ✓ JavaScript/React client libraries"
echo ""
echo -e "Run ${YELLOW}docker-compose up${NC} to start the services"
echo -e "Test SSE: ${YELLOW}curl -N -H \"Accept: text/event-stream\" \"http://localhost:8001/api/v1/stream/system/health\"${NC}"