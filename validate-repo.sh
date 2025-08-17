#!/bin/bash

# Repository Structure Validation Script
# Validates that all required files and directories are properly organized

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# Function to check if file/directory exists
check_exists() {
    local path=$1
    local type=${2:-"file"}
    local description=$3
    
    if [[ "$type" == "directory" ]]; then
        if [[ -d "$path" ]]; then
            echo -e "${GREEN}✓ $description${NC}"
            ((PASS_COUNT++))
        else
            echo -e "${RED}✗ $description - Missing: $path${NC}"
            ((FAIL_COUNT++))
        fi
    else
        if [[ -f "$path" ]]; then
            echo -e "${GREEN}✓ $description${NC}"
            ((PASS_COUNT++))
        else
            echo -e "${RED}✗ $description - Missing: $path${NC}"
            ((FAIL_COUNT++))
        fi
    fi
}

# Function to check file content
check_content() {
    local file=$1
    local pattern=$2
    local description=$3
    
    if [[ -f "$file" ]] && grep -q "$pattern" "$file"; then
        echo -e "${GREEN}✓ $description${NC}"
        ((PASS_COUNT++))
    else
        echo -e "${RED}✗ $description - Pattern not found: $pattern${NC}"
        ((FAIL_COUNT++))
    fi
}

echo -e "${BLUE}=== MoolAI Repository Structure Validation ===${NC}\n"

# Root level files
echo -e "${YELLOW}Root Level Files:${NC}"
check_exists "README.md" "file" "README documentation"
check_exists "docker-compose.yml" "file" "Main Docker Compose file"
check_exists "build.sh" "file" "Build script"
check_exists ".env.example" "file" "Environment configuration template"
check_exists ".gitignore" "file" "Git ignore rules"
check_exists ".dockerignore" "file" "Docker ignore rules"

echo ""

# Directory structure
echo -e "${YELLOW}Directory Structure:${NC}"
check_exists "services" "directory" "Services directory"
check_exists "services/monitoring" "directory" "Monitoring service"
check_exists "services/orchestrator" "directory" "Orchestrator service"
check_exists "services/controller" "directory" "Controller service"
check_exists "infrastructure" "directory" "Infrastructure directory"
check_exists "infrastructure/docker" "directory" "Docker configurations"
check_exists "infrastructure/compose" "directory" "Compose configurations"
check_exists "scripts" "directory" "Scripts directory"
check_exists "docs" "directory" "Documentation directory"

echo ""

# Monitoring service files
echo -e "${YELLOW}Monitoring Service Files:${NC}"
check_exists "services/monitoring/src" "directory" "Monitoring source code"
check_exists "services/monitoring/src/api" "directory" "Monitoring API"
check_exists "services/monitoring/src/config" "directory" "Monitoring configuration"
check_exists "services/monitoring/src/models" "directory" "Monitoring models"
check_exists "services/monitoring/tests" "directory" "Monitoring tests"
check_exists "services/monitoring/requirements.txt" "file" "Monitoring dependencies"

echo ""

# Infrastructure files
echo -e "${YELLOW}Infrastructure Files:${NC}"
check_exists "infrastructure/docker/Dockerfile.monitoring" "file" "Monitoring Dockerfile"
check_exists "infrastructure/docker/Dockerfile.orchestrator" "file" "Orchestrator Dockerfile"
check_exists "infrastructure/docker/Dockerfile.controller" "file" "Controller Dockerfile"

echo ""

# Scripts
echo -e "${YELLOW}Scripts:${NC}"
check_exists "scripts/docker-build.sh" "file" "Docker build script"
check_exists "scripts/docker-security-scan.sh" "file" "Security scan script"
check_exists "scripts/docker-verify.sh" "file" "Verification script"

echo ""

# Content validation
echo -e "${YELLOW}Content Validation:${NC}"
check_content "README.md" "MoolAI Monitoring System" "README has correct title"
check_content "docker-compose.yml" "version.*3.8" "Docker Compose version specified"
check_content "docker-compose.yml" "monitoring-org-001" "Organization 001 monitoring service"
check_content "docker-compose.yml" "monitoring-org-002" "Organization 002 monitoring service"
check_content "infrastructure/docker/Dockerfile.monitoring" "MONITORING_MODE=sidecar" "Monitoring Dockerfile has sidecar mode"
check_content "services/monitoring/requirements.txt" "fastapi" "Monitoring has FastAPI dependency"

echo ""

# Executable permissions
echo -e "${YELLOW}Executable Permissions:${NC}"
if [[ -x "build.sh" ]]; then
    echo -e "${GREEN}✓ build.sh is executable${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ build.sh is not executable${NC}"
    ((FAIL_COUNT++))
fi

if [[ -f "scripts/docker-build.sh" ]] && [[ -x "scripts/docker-build.sh" ]]; then
    echo -e "${GREEN}✓ docker-build.sh is executable${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ docker-build.sh is not executable or missing${NC}"
    ((FAIL_COUNT++))
fi

echo ""

# Service structure validation
echo -e "${YELLOW}Service Structure Validation:${NC}"

# Check monitoring service structure
if [[ -d "services/monitoring/src" ]]; then
    required_monitoring_files=(
        "services/monitoring/src/api/main.py"
        "services/monitoring/src/config/settings.py"
        "services/monitoring/src/config/database.py"
        "services/monitoring/src/models/__init__.py"
    )
    
    for file in "${required_monitoring_files[@]}"; do
        if [[ -f "$file" ]]; then
            echo -e "${GREEN}✓ Monitoring file: $(basename $file)${NC}"
            ((PASS_COUNT++))
        else
            echo -e "${RED}✗ Missing monitoring file: $file${NC}"
            ((FAIL_COUNT++))
        fi
    done
fi

echo ""

# Docker Compose validation
echo -e "${YELLOW}Docker Compose Validation:${NC}"
if command -v docker-compose &> /dev/null; then
    if docker-compose config > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Docker Compose configuration is valid${NC}"
        ((PASS_COUNT++))
    else
        echo -e "${RED}✗ Docker Compose configuration has errors${NC}"
        ((FAIL_COUNT++))
    fi
else
    echo -e "${YELLOW}⚠️  Docker Compose not available for validation${NC}"
fi

echo ""

# Repository best practices
echo -e "${YELLOW}Repository Best Practices:${NC}"

# Check for required documentation
docs_files=("README.md")
for doc in "${docs_files[@]}"; do
    if [[ -f "$doc" ]] && [[ $(wc -l < "$doc") -gt 50 ]]; then
        echo -e "${GREEN}✓ $doc is comprehensive (>50 lines)${NC}"
        ((PASS_COUNT++))
    else
        echo -e "${RED}✗ $doc is missing or too brief${NC}"
        ((FAIL_COUNT++))
    fi
done

# Check for security files
if [[ -f ".gitignore" ]] && grep -q ".env" ".gitignore"; then
    echo -e "${GREEN}✓ .gitignore excludes environment files${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ .gitignore doesn't exclude .env files${NC}"
    ((FAIL_COUNT++))
fi

echo ""

# Summary
echo -e "${BLUE}=== Validation Summary ===${NC}"
echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed: ${RED}$FAIL_COUNT${NC}"

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${GREEN}🎉 Repository structure validation passed!${NC}"
    echo -e "Repository is ready for development and deployment."
    exit 0
else
    echo -e "${RED}⚠️  Repository structure validation failed.${NC}"
    echo -e "Please fix the issues above before proceeding."
    exit 1
fi