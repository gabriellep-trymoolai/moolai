#!/bin/bash

# Docker Build Verification and Container Testing Script
# Verifies that all Docker builds work correctly and containers start properly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
TEST_CONTAINERS=()

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up test containers...${NC}"
    for container in "${TEST_CONTAINERS[@]}"; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo "Stopping and removing $container"
            docker stop "$container" 2>/dev/null || true
            docker rm "$container" 2>/dev/null || true
        fi
    done
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Function to test a build
test_build() {
    local service=$1
    local dockerfile=$2
    local tag="moolai/$service:test"
    
    echo -e "\n${YELLOW}Testing $service build...${NC}"
    
    # Build the image
    if DOCKER_BUILDKIT=1 docker build \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="test" \
        --build-arg VERSION="test" \
        --target production \
        --tag "$tag" \
        --file "$dockerfile" \
        . > /dev/null 2>&1; then
        echo -e "${GREEN}✓ $service build successful${NC}"
        ((PASS_COUNT++))
        
        # Get image details
        local size=$(docker images "$tag" --format "{{.Size}}" | head -1)
        local created=$(docker images "$tag" --format "{{.CreatedSince}}" | head -1)
        echo "  Size: $size, Created: $created"
        
        return 0
    else
        echo -e "${RED}✗ $service build failed${NC}"
        ((FAIL_COUNT++))
        return 1
    fi
}

# Function to test container startup
test_container() {
    local service=$1
    local tag="moolai/$service:test"
    local port=$2
    local env_vars=("${@:3}")
    
    echo -e "\n${YELLOW}Testing $service container startup...${NC}"
    
    local container_name="test-$service-$(date +%s)"
    TEST_CONTAINERS+=("$container_name")
    
    # Start container with provided environment variables
    local env_args=""
    for env_var in "${env_vars[@]}"; do
        env_args="$env_args -e $env_var"
    done
    
    if docker run -d \
        --name "$container_name" \
        $env_args \
        -p "$port:$port" \
        "$tag" > /dev/null 2>&1; then
        
        # Wait for container to start
        echo "  Waiting for container to start..."
        sleep 5
        
        # Check if container is running
        if docker ps --filter "name=$container_name" --format '{{.Names}}' | grep -q "$container_name"; then
            echo -e "${GREEN}✓ $service container started successfully${NC}"
            ((PASS_COUNT++))
            
            # Test health endpoint if available
            if curl -f "http://localhost:$port/health" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ $service health endpoint responding${NC}"
                ((PASS_COUNT++))
            else
                echo -e "${YELLOW}⚠ $service health endpoint not responding (may be expected)${NC}"
            fi
            
            # Show container logs (last 10 lines)
            echo "  Container logs (last 10 lines):"
            docker logs "$container_name" --tail 10 | sed 's/^/    /'
            
        else
            echo -e "${RED}✗ $service container failed to start${NC}"
            ((FAIL_COUNT++))
            docker logs "$container_name" | tail -20
        fi
    else
        echo -e "${RED}✗ $service container failed to run${NC}"
        ((FAIL_COUNT++))
    fi
}

echo -e "${BLUE}=== Docker Build and Container Verification ===${NC}"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed or not in PATH${NC}"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker daemon is not running${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is available and running${NC}"

# Test builds
echo -e "\n${BLUE}=== Testing Docker Builds ===${NC}"

test_build "monitoring" "Dockerfile.monitoring"
test_build "orchestrator" "Dockerfile.orchestrator"
test_build "controller" "Dockerfile.controller"

# Test container startups
echo -e "\n${BLUE}=== Testing Container Startups ===${NC}"

# Test monitoring service container
test_container "monitoring" 8001 \
    "MONITORING_MODE=sidecar" \
    "ORCHESTRATOR_ID=test_orchestrator" \
    "ORGANIZATION_ID=test_org" \
    "DATABASE_URL=postgresql://test:test@localhost:5432/test_db" \
    "REDIS_URL=redis://localhost:6379/0"

# Test orchestrator service container  
test_container "orchestrator" 8000 \
    "ORGANIZATION_ID=test_org" \
    "DATABASE_URL=postgresql://test:test@localhost:5432/test_db"

# Test controller service container
test_container "controller" 8002 \
    "CONTROLLER_MODE=central"

# Test image security (basic checks)
echo -e "\n${BLUE}=== Testing Image Security ===${NC}"

for service in monitoring orchestrator controller; do
    tag="moolai/$service:test"
    echo -e "\n${YELLOW}Security check for $service:${NC}"
    
    # Check if image runs as non-root
    user_id=$(docker run --rm "$tag" id -u 2>/dev/null || echo "unknown")
    if [[ "$user_id" != "0" && "$user_id" != "unknown" ]]; then
        echo -e "${GREEN}✓ $service runs as non-root user (UID: $user_id)${NC}"
        ((PASS_COUNT++))
    else
        echo -e "${RED}✗ $service may be running as root${NC}"
        ((FAIL_COUNT++))
    fi
    
    # Check image layers for best practices
    if docker history "$tag" --no-trunc | grep -q "apt-get.*clean"; then
        echo -e "${GREEN}✓ $service image includes package cleanup${NC}"
        ((PASS_COUNT++))
    else
        echo -e "${YELLOW}⚠ $service image may not include package cleanup${NC}"
    fi
done

# Performance tests
echo -e "\n${BLUE}=== Performance Tests ===${NC}"

for service in monitoring orchestrator controller; do
    tag="moolai/$service:test"
    size_mb=$(docker images "$tag" --format "{{.Size}}" | head -1)
    echo "$service image size: $size_mb"
    
    # Extract numeric size for comparison (basic check)
    if echo "$size_mb" | grep -q "MB"; then
        size_num=$(echo "$size_mb" | sed 's/MB.*//' | sed 's/\..*//')
        if [[ "$size_num" -lt 500 ]]; then
            echo -e "${GREEN}✓ $service image size is reasonable (<500MB)${NC}"
            ((PASS_COUNT++))
        else
            echo -e "${YELLOW}⚠ $service image size is large (>500MB)${NC}"
        fi
    fi
done

# Summary
echo -e "\n${BLUE}=== Verification Summary ===${NC}"
echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed: ${RED}$FAIL_COUNT${NC}"

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${GREEN}🎉 All Docker verification tests passed!${NC}"
    echo -e "Images are ready for deployment."
    exit 0
else
    echo -e "${RED}⚠️ Some verification tests failed. Please review and fix.${NC}"
    exit 1
fi