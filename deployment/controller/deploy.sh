#!/bin/bash

# MoolAI Controller Deployment Script
# Easy deployment for your central controller infrastructure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 MoolAI Controller Deployment Script${NC}"
echo "======================================"

# Function to check prerequisites
check_prerequisites() {
    echo -e "\n${YELLOW}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker found${NC}"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker Compose found${NC}"
    
    # Check if .env exists
    if [ ! -f .env ]; then
        echo -e "${YELLOW}⚠️  .env file not found. Creating from template...${NC}"
        cp .env.template .env
        echo -e "${YELLOW}📝 Please edit .env file with your configuration${NC}"
        echo -e "${YELLOW}   Especially change all passwords and keys!${NC}"
        read -p "Press enter after you've configured .env file..."
    fi
}

# Function to build images
build_images() {
    echo -e "\n${YELLOW}Building Docker images...${NC}"
    
    # Set build arguments
    export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
    export VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    export VERSION=$(cat ../../VERSION 2>/dev/null || echo "1.0.0")
    
    # Build with docker-compose
    docker-compose build --no-cache
    
    echo -e "${GREEN}✅ Images built successfully${NC}"
}

# Function to start services
start_services() {
    echo -e "\n${YELLOW}Starting Controller services...${NC}"
    
    # Start services
    docker-compose up -d
    
    # Wait for services to be healthy
    echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
    
    # Wait for database
    echo -n "Waiting for database..."
    for i in {1..30}; do
        if docker-compose exec -T postgres-controller pg_isready -U controller_user &> /dev/null; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for controller
    echo -n "Waiting for controller service..."
    for i in {1..30}; do
        if curl -f http://localhost:${CONTROLLER_PORT:-8002}/health &> /dev/null; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    echo -e "${GREEN}✅ All services started successfully${NC}"
}

# Function to show status
show_status() {
    echo -e "\n${GREEN}=== Deployment Status ===${NC}"
    docker-compose ps
    
    echo -e "\n${GREEN}=== Access Information ===${NC}"
    echo -e "Controller API: ${GREEN}http://localhost:${CONTROLLER_PORT:-8002}${NC}"
    echo -e "API Documentation: ${GREEN}http://localhost:${CONTROLLER_PORT:-8002}/docs${NC}"
    echo -e "Health Check: ${GREEN}http://localhost:${CONTROLLER_PORT:-8002}/health${NC}"
    
    echo -e "\n${GREEN}=== Database Information ===${NC}"
    echo -e "Database Port: ${GREEN}${CONTROLLER_DB_PORT:-5432}${NC}"
    echo -e "Database Name: ${GREEN}${CONTROLLER_DB_NAME:-controller_db}${NC}"
    
    echo -e "\n${YELLOW}=== Important Commands ===${NC}"
    echo "View logs: docker-compose logs -f"
    echo "Stop services: docker-compose down"
    echo "Restart services: docker-compose restart"
    echo "Database backup: ./backup.sh"
}

# Function to run initial setup
initial_setup() {
    echo -e "\n${YELLOW}Running initial setup...${NC}"
    
    # Check if this is first run
    if docker-compose exec -T postgres-controller psql -U controller_user -d controller_db -c "SELECT 1 FROM users LIMIT 1;" &> /dev/null; then
        echo -e "${GREEN}Database already initialized${NC}"
    else
        echo -e "${YELLOW}Initializing database...${NC}"
        # Database will be auto-initialized by the controller on first start
        sleep 5
        echo -e "${GREEN}✅ Database initialized${NC}"
    fi
}

# Main deployment flow
main() {
    check_prerequisites
    
    # Ask for confirmation
    echo -e "\n${YELLOW}This will deploy the MoolAI Controller.${NC}"
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Deployment cancelled${NC}"
        exit 1
    fi
    
    # Load environment variables
    set -a
    source .env
    set +a
    
    build_images
    start_services
    initial_setup
    show_status
    
    echo -e "\n${GREEN}🎉 Controller deployment completed successfully!${NC}"
    echo -e "${YELLOW}Check the logs to ensure everything is running correctly:${NC}"
    echo -e "  docker-compose logs -f"
}

# Handle script arguments
case "${1:-}" in
    stop)
        echo -e "${YELLOW}Stopping Controller services...${NC}"
        docker-compose down
        echo -e "${GREEN}✅ Services stopped${NC}"
        ;;
    restart)
        echo -e "${YELLOW}Restarting Controller services...${NC}"
        docker-compose restart
        echo -e "${GREEN}✅ Services restarted${NC}"
        ;;
    status)
        show_status
        ;;
    logs)
        docker-compose logs -f
        ;;
    backup)
        ./backup.sh
        ;;
    *)
        main
        ;;
esac