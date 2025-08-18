#!/bin/bash

# MoolAI Client Deployment Script
# Easy deployment for client organizations (Orchestrator + Monitoring Sidecar)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 MoolAI Client Deployment Script${NC}"
echo "======================================"

# Function to check prerequisites
check_prerequisites() {
    echo -e "\n${YELLOW}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        echo "Please install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker found${NC}"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not installed${NC}"
        echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker Compose found${NC}"
}

# Function to setup configuration
setup_configuration() {
    echo -e "\n${YELLOW}Setting up configuration...${NC}"
    
    # Check if .env exists
    if [ ! -f .env ]; then
        echo -e "${YELLOW}Creating .env file from template...${NC}"
        cp .env.template .env
        
        echo -e "\n${BLUE}Please provide the following information:${NC}"
        
        # Get organization ID
        read -p "Organization ID (e.g., org_001): " org_id
        sed -i.bak "s/ORGANIZATION_ID=.*/ORGANIZATION_ID=$org_id/" .env
        
        # Get organization name
        read -p "Organization Name: " org_name
        sed -i.bak "s/ORGANIZATION_NAME=.*/ORGANIZATION_NAME=\"$org_name\"/" .env
        
        # Get controller URL
        read -p "Controller URL (provided by MoolAI): " controller_url
        sed -i.bak "s|CONTROLLER_URL=.*|CONTROLLER_URL=$controller_url|" .env
        
        # Get controller API key
        read -p "Controller API Key (provided by MoolAI): " controller_key
        sed -i.bak "s/CONTROLLER_API_KEY=.*/CONTROLLER_API_KEY=$controller_key/" .env
        
        # Generate random passwords
        echo -e "\n${YELLOW}Generating secure passwords...${NC}"
        db_password=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        redis_password=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        jwt_secret=$(openssl rand -base64 48 | tr -d "=+/" | cut -c1-32)
        api_key=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        
        sed -i.bak "s/DB_PASSWORD=.*/DB_PASSWORD=$db_password/" .env
        sed -i.bak "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$redis_password/" .env
        sed -i.bak "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$jwt_secret/" .env
        sed -i.bak "s/ORCHESTRATOR_API_KEY=.*/ORCHESTRATOR_API_KEY=$api_key/" .env
        
        # Clean up backup files
        rm -f .env.bak
        
        echo -e "${GREEN}✅ Configuration created${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env to add your LLM API keys (OpenAI, Anthropic, etc.)${NC}"
        read -p "Press enter after you've added your LLM API keys..."
    else
        echo -e "${GREEN}✅ Configuration file exists${NC}"
    fi
}

# Function to create necessary directories
create_directories() {
    echo -e "\n${YELLOW}Creating necessary directories...${NC}"
    
    mkdir -p config/orchestrator
    mkdir -p config/monitoring
    mkdir -p scripts
    
    # Make scripts executable
    chmod +x scripts/*.sh 2>/dev/null || true
    
    echo -e "${GREEN}✅ Directories created${NC}"
}

# Function to build images
build_images() {
    echo -e "\n${YELLOW}Building Docker images...${NC}"
    echo -e "${YELLOW}This may take a few minutes on first run...${NC}"
    
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
    echo -e "\n${YELLOW}Starting client services...${NC}"
    
    # Start services
    docker-compose up -d
    
    # Wait for services to be healthy
    echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
    
    # Load environment variables
    set -a
    source .env
    set +a
    
    # Wait for database
    echo -n "Waiting for database..."
    for i in {1..30}; do
        if docker-compose exec -T postgres-client pg_isready -U ${DB_USER:-moolai_user} &> /dev/null; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for Redis
    echo -n "Waiting for Redis..."
    for i in {1..30}; do
        if docker-compose exec -T redis-client redis-cli ping &> /dev/null; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for orchestrator
    echo -n "Waiting for orchestrator service..."
    for i in {1..30}; do
        if curl -f http://localhost:${ORCHESTRATOR_PORT:-8000}/health &> /dev/null; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for monitoring
    echo -n "Waiting for monitoring sidecar..."
    for i in {1..30}; do
        if curl -f http://localhost:${MONITORING_PORT:-8001}/health &> /dev/null; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    echo -e "${GREEN}✅ All services started successfully${NC}"
}

# Function to verify deployment
verify_deployment() {
    echo -e "\n${YELLOW}Verifying deployment...${NC}"
    
    # Check database tables
    echo -n "Checking database initialization..."
    if docker-compose logs orchestrator 2>&1 | grep -q "Orchestrator database tables created successfully"; then
        echo -e " ${GREEN}✅${NC}"
    else
        echo -e " ${YELLOW}⚠️  Database may still be initializing${NC}"
    fi
    
    # Check monitoring collection
    echo -n "Checking monitoring collection..."
    if docker-compose logs monitoring 2>&1 | grep -q "Starting automatic collection"; then
        echo -e " ${GREEN}✅${NC}"
    else
        echo -e " ${YELLOW}⚠️  Monitoring may still be initializing${NC}"
    fi
    
    # Test API endpoints
    echo -e "\n${YELLOW}Testing API endpoints...${NC}"
    
    # Test orchestrator health
    if curl -s http://localhost:${ORCHESTRATOR_PORT:-8000}/health | grep -q "healthy"; then
        echo -e "${GREEN}✅ Orchestrator API is healthy${NC}"
    else
        echo -e "${YELLOW}⚠️  Orchestrator API may still be starting${NC}"
    fi
    
    # Test monitoring health
    if curl -s http://localhost:${MONITORING_PORT:-8001}/health | grep -q "healthy"; then
        echo -e "${GREEN}✅ Monitoring API is healthy${NC}"
    else
        echo -e "${YELLOW}⚠️  Monitoring API may still be starting${NC}"
    fi
}

# Function to show status
show_status() {
    echo -e "\n${GREEN}=== Deployment Status ===${NC}"
    docker-compose ps
    
    # Load environment variables
    set -a
    source .env
    set +a
    
    echo -e "\n${GREEN}=== Access Information ===${NC}"
    echo -e "Organization: ${GREEN}${ORGANIZATION_NAME} (${ORGANIZATION_ID})${NC}"
    echo -e "Orchestrator API: ${GREEN}http://localhost:${ORCHESTRATOR_PORT:-8000}${NC}"
    echo -e "Monitoring API: ${GREEN}http://localhost:${MONITORING_PORT:-8001}${NC}"
    echo -e "API Documentation:"
    echo -e "  - Orchestrator: ${GREEN}http://localhost:${ORCHESTRATOR_PORT:-8000}/docs${NC}"
    echo -e "  - Monitoring: ${GREEN}http://localhost:${MONITORING_PORT:-8001}/docs${NC}"
    
    echo -e "\n${GREEN}=== Health Checks ===${NC}"
    echo -e "Orchestrator Health: ${GREEN}http://localhost:${ORCHESTRATOR_PORT:-8000}/health${NC}"
    echo -e "Monitoring Health: ${GREEN}http://localhost:${MONITORING_PORT:-8001}/health${NC}"
    
    echo -e "\n${GREEN}=== Monitoring Features ===${NC}"
    echo -e "Automatic collection every ${GREEN}${METRICS_COLLECTION_INTERVAL:-30}${NC} seconds"
    echo -e "SSE Metrics Stream: ${GREEN}http://localhost:${MONITORING_PORT:-8001}/api/v1/stream/metrics/organization${NC}"
    echo -e "WebSocket Control: ${GREEN}ws://localhost:${MONITORING_PORT:-8001}/ws/admin/control${NC}"
    
    echo -e "\n${YELLOW}=== Important Commands ===${NC}"
    echo "View logs: docker-compose logs -f [service-name]"
    echo "Stop services: docker-compose down"
    echo "Restart services: docker-compose restart"
    echo "Backup data: ./backup.sh"
    echo "Update deployment: ./update.sh"
}

# Function to create backup script
create_backup_script() {
    cat > backup.sh << 'EOF'
#!/bin/bash
# MoolAI Client Backup Script

set -e
source .env

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in $BACKUP_DIR..."

# Backup databases
docker-compose exec -T postgres-client pg_dump -U $DB_USER $DB_NAME_ORCHESTRATOR > "$BACKUP_DIR/orchestrator.sql"
docker-compose exec -T postgres-client pg_dump -U $DB_USER $DB_NAME_MONITORING > "$BACKUP_DIR/monitoring.sql"

# Backup Redis
docker-compose exec -T redis-client redis-cli --rdb "$BACKUP_DIR/redis.rdb" BGSAVE

# Backup configuration
cp .env "$BACKUP_DIR/.env"
cp -r config "$BACKUP_DIR/config" 2>/dev/null || true

echo "✅ Backup completed: $BACKUP_DIR"
EOF
    chmod +x backup.sh
}

# Main deployment flow
main() {
    check_prerequisites
    setup_configuration
    create_directories
    
    # Create helper scripts
    create_backup_script
    
    echo -e "\n${YELLOW}Ready to deploy MoolAI client services.${NC}"
    echo -e "${YELLOW}This will create:${NC}"
    echo -e "  - Orchestrator service"
    echo -e "  - Monitoring sidecar service"
    echo -e "  - PostgreSQL database"
    echo -e "  - Redis cache"
    
    read -p "Continue with deployment? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Deployment cancelled${NC}"
        exit 1
    fi
    
    build_images
    start_services
    verify_deployment
    show_status
    
    echo -e "\n${GREEN}🎉 Client deployment completed successfully!${NC}"
    echo -e "${YELLOW}The monitoring sidecar is now collecting metrics every ${METRICS_COLLECTION_INTERVAL:-30} seconds.${NC}"
    echo -e "${YELLOW}Check the logs to ensure everything is running correctly:${NC}"
    echo -e "  docker-compose logs -f"
}

# Handle script arguments
case "${1:-}" in
    stop)
        echo -e "${YELLOW}Stopping client services...${NC}"
        docker-compose down
        echo -e "${GREEN}✅ Services stopped${NC}"
        ;;
    restart)
        echo -e "${YELLOW}Restarting client services...${NC}"
        docker-compose restart
        echo -e "${GREEN}✅ Services restarted${NC}"
        ;;
    status)
        show_status
        ;;
    logs)
        service=${2:-}
        if [ -z "$service" ]; then
            docker-compose logs -f
        else
            docker-compose logs -f $service
        fi
        ;;
    backup)
        ./backup.sh
        ;;
    update)
        echo -e "${YELLOW}Updating client deployment...${NC}"
        git pull
        docker-compose pull
        docker-compose up -d
        echo -e "${GREEN}✅ Update completed${NC}"
        ;;
    *)
        main
        ;;
esac