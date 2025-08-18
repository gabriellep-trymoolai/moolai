#!/bin/bash

# Docker Security Best Practices Validation Script
# Validates that all Dockerfiles follow security guidelines

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# Function to check a security practice
check_security() {
    local dockerfile=$1
    local check_name=$2
    local pattern=$3
    local should_exist=${4:-true}
    
    if [[ ! -f "$dockerfile" ]]; then
        echo -e "${RED}✗ $dockerfile not found${NC}"
        ((FAIL_COUNT++))
        return
    fi
    
    if [[ "$should_exist" == "true" ]]; then
        if grep -q "$pattern" "$dockerfile"; then
            echo -e "${GREEN}✓ $check_name${NC}"
            ((PASS_COUNT++))
        else
            echo -e "${RED}✗ $check_name - Missing: $pattern${NC}"
            ((FAIL_COUNT++))
        fi
    else
        if ! grep -q "$pattern" "$dockerfile"; then
            echo -e "${GREEN}✓ $check_name${NC}"
            ((PASS_COUNT++))
        else
            echo -e "${RED}✗ $check_name - Should not contain: $pattern${NC}"
            ((FAIL_COUNT++))
        fi
    fi
}

echo -e "${BLUE}=== Docker Security Best Practices Validation ===${NC}\n"

# List of Dockerfiles to check
dockerfiles=("infrastructure/docker/Dockerfile.orchestrator" "infrastructure/docker/Dockerfile.controller")

for dockerfile in "${dockerfiles[@]}"; do
    echo -e "${YELLOW}Checking $dockerfile:${NC}"
    
    # Security checks
    check_security "$dockerfile" "Multi-stage build (builder stage)" "FROM.*as builder"
    check_security "$dockerfile" "Multi-stage build (production stage)" "FROM.*as production"
    check_security "$dockerfile" "Non-root user created" "RUN.*groupadd.*useradd"
    check_security "$dockerfile" "Switches to non-root user" "USER.*moolai"
    check_security "$dockerfile" "File ownership set correctly" "COPY --chown=moolai:moolai"
    check_security "$dockerfile" "Removes package cache" "rm -rf /var/lib/apt/lists"
    check_security "$dockerfile" "Limited package installation" "apt-get.*clean"
    check_security "$dockerfile" "Health check configured" "HEALTHCHECK"
    check_security "$dockerfile" "Security labels present" "org.moolai"
    check_security "$dockerfile" "Environment variables set" "ENV.*PYTHONDONTWRITEBYTECODE"
    check_security "$dockerfile" "Python bytecode disabled" "PYTHONDONTWRITEBYTECODE=1"
    check_security "$dockerfile" "Python unbuffered output" "PYTHONUNBUFFERED=1"
    check_security "$dockerfile" "Minimal exposed ports" "EXPOSE.*80[0-9][0-9]"
    
    # Anti-patterns (things that should NOT be present)
    check_security "$dockerfile" "No root user in CMD" "USER root" false
    check_security "$dockerfile" "No hardcoded secrets" "password\|secret\|key.*=" false
    check_security "$dockerfile" "No unnecessary privileges" "privileged" false
    check_security "$dockerfile" "No development tools in production" "vim\|nano\|git\|wget" false
    
    echo ""
done

# Check .dockerignore
echo -e "${YELLOW}Checking .dockerignore:${NC}"
if [[ -f ".dockerignore" ]]; then
    check_security ".dockerignore" "Excludes .git directory" "\.git"
    check_security ".dockerignore" "Excludes Python cache" "__pycache__"
    check_security ".dockerignore" "Excludes environment files" "\.env"
    check_security ".dockerignore" "Excludes test files" "test.*\.py"
    check_security ".dockerignore" "Excludes logs" "\.log"
    echo -e "${GREEN}✓ .dockerignore file exists${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ .dockerignore file missing${NC}"
    ((FAIL_COUNT++))
fi

echo ""

# Additional security checks for built images
echo -e "${YELLOW}Additional Security Recommendations:${NC}"
echo -e "${BLUE}1. Image Scanning:${NC}"
echo "   - Use 'docker scout cves <image>' for vulnerability scanning"
echo "   - Use 'trivy image <image>' for comprehensive security scanning"

echo -e "${BLUE}2. Runtime Security:${NC}"
echo "   - Run containers with --read-only filesystem when possible"
echo "   - Use --user flag to override USER directive if needed"
echo "   - Limit container capabilities with --cap-drop ALL --cap-add <needed>"

echo -e "${BLUE}3. Network Security:${NC}"
echo "   - Use custom networks instead of default bridge"
echo "   - Limit container communication with network policies"
echo "   - Use secrets management for sensitive data"

echo ""

# Summary
echo -e "${BLUE}=== Security Validation Summary ===${NC}"
echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed: ${RED}$FAIL_COUNT${NC}"

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${GREEN}🔒 All security checks passed!${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Security issues found. Please review and fix.${NC}"
    exit 1
fi