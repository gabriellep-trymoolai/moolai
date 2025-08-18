#!/bin/bash

# MoolAI Master Deployment Script
# Choose between Controller or Client deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ASCII Art Banner
show_banner() {
    echo -e "${CYAN}"
    cat << "EOF"
    __  __            _    _    ___ 
   |  \/  | ___  ___ | |  / \  |_ _|
   | |\/| |/ _ \/ _ \| | / _ \  | | 
   | |  | | (_) | (_) | |/ ___ \ | | 
   |_|  |_|\___/ \___/|_/_/   \_\___|
                                     
   AI Infrastructure Deployment System
EOF
    echo -e "${NC}"
}

# Function to show main menu
show_menu() {
    echo -e "${GREEN}==================================${NC}"
    echo -e "${GREEN}    MoolAI Deployment System     ${NC}"
    echo -e "${GREEN}==================================${NC}"
    echo
    echo -e "${BLUE}Please select deployment type:${NC}"
    echo
    echo -e "  ${YELLOW}1)${NC} Deploy Controller (Central Management)"
    echo -e "     ${CYAN}→ For your central infrastructure${NC}"
    echo -e "     ${CYAN}→ Manages all client orchestrators${NC}"
    echo
    echo -e "  ${YELLOW}2)${NC} Deploy Client (Orchestrator + Monitoring)"
    echo -e "     ${CYAN}→ For client organizations${NC}"
    echo -e "     ${CYAN}→ Includes monitoring sidecar${NC}"
    echo
    echo -e "  ${YELLOW}3)${NC} Development Mode (Full Local Stack)"
    echo -e "     ${CYAN}→ For development and testing${NC}"
    echo -e "     ${CYAN}→ Deploys all components locally${NC}"
    echo
    echo -e "  ${YELLOW}4)${NC} Documentation"
    echo -e "     ${CYAN}→ View deployment guides${NC}"
    echo
    echo -e "  ${YELLOW}5)${NC} Exit"
    echo
}

# Function to deploy controller
deploy_controller() {
    echo -e "\n${GREEN}Controller Deployment Selected${NC}"
    echo -e "${YELLOW}This will deploy the central management controller.${NC}"
    echo
    
    cd deployment/controller
    
    if [ ! -f deploy.sh ]; then
        echo -e "${RED}❌ Controller deployment script not found${NC}"
        echo -e "${YELLOW}Please ensure you're in the correct directory${NC}"
        exit 1
    fi
    
    chmod +x deploy.sh
    ./deploy.sh
}

# Function to deploy client
deploy_client() {
    echo -e "\n${GREEN}Client Deployment Selected${NC}"
    echo -e "${YELLOW}This will deploy orchestrator with monitoring sidecar.${NC}"
    echo
    
    cd deployment/client
    
    if [ ! -f deploy.sh ]; then
        echo -e "${RED}❌ Client deployment script not found${NC}"
        echo -e "${YELLOW}Please ensure you're in the correct directory${NC}"
        exit 1
    fi
    
    chmod +x deploy.sh
    ./deploy.sh
}

# Function to deploy development stack
deploy_development() {
    echo -e "\n${GREEN}Development Mode Selected${NC}"
    echo -e "${YELLOW}This will deploy the full stack locally for development.${NC}"
    echo
    
    # Check if docker-compose.yml exists
    if [ ! -f docker-compose.yml ]; then
        echo -e "${RED}❌ docker-compose.yml not found${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}Building all services...${NC}"
    ./build.sh
    
    echo -e "${YELLOW}Starting all services...${NC}"
    docker-compose up -d
    
    echo -e "\n${GREEN}✅ Development stack deployed!${NC}"
    echo
    echo -e "${GREEN}=== Service URLs ===${NC}"
    echo -e "Controller: ${CYAN}http://localhost:8002${NC}"
    echo -e "Orchestrator (org-001): ${CYAN}http://localhost:8000${NC}"
    echo -e "Monitoring (org-001): ${CYAN}http://localhost:8001${NC}"
    echo -e "Orchestrator (org-002): ${CYAN}http://localhost:8010${NC}"
    echo -e "Monitoring (org-002): ${CYAN}http://localhost:8011${NC}"
    echo
    echo -e "${YELLOW}View logs: docker-compose logs -f${NC}"
}

# Function to show documentation
show_documentation() {
    echo -e "\n${GREEN}=== MoolAI Deployment Documentation ===${NC}"
    echo
    echo -e "${BLUE}Controller Deployment:${NC}"
    echo -e "  The controller is the central management system that:"
    echo -e "  • Manages all client orchestrators"
    echo -e "  • Collects analytics and metrics"
    echo -e "  • Provides centralized configuration"
    echo -e "  • Monitors system health"
    echo
    echo -e "  ${YELLOW}Deploy on:${NC} Your central infrastructure"
    echo -e "  ${YELLOW}Requirements:${NC} Docker, 4GB RAM, 2 CPU cores"
    echo -e "  ${YELLOW}Configuration:${NC} deployment/controller/.env"
    echo
    echo -e "${BLUE}Client Deployment:${NC}"
    echo -e "  Each client deployment includes:"
    echo -e "  • Orchestrator service (AI workflow management)"
    echo -e "  • Monitoring sidecar (metrics collection)"
    echo -e "  • PostgreSQL database (data persistence)"
    echo -e "  • Redis cache (real-time data)"
    echo
    echo -e "  ${YELLOW}Deploy on:${NC} Client infrastructure"
    echo -e "  ${YELLOW}Requirements:${NC} Docker, 4GB RAM, 2 CPU cores"
    echo -e "  ${YELLOW}Configuration:${NC} deployment/client/.env"
    echo
    echo -e "${BLUE}Architecture Overview:${NC}"
    echo -e "  ┌─────────────┐"
    echo -e "  │ Controller  │ (Your Infrastructure)"
    echo -e "  └──────┬──────┘"
    echo -e "         │"
    echo -e "    ┌────┴────┐"
    echo -e "    │         │"
    echo -e "  ┌─▼───┐  ┌─▼───┐"
    echo -e "  │Client│  │Client│ (Client Sites)"
    echo -e "  │ Org1 │  │ Org2 │"
    echo -e "  └──────┘  └──────┘"
    echo
    echo -e "${YELLOW}For detailed documentation, see:${NC}"
    echo -e "  • README.md"
    echo -e "  • deployment/controller/README.md"
    echo -e "  • deployment/client/README.md"
    echo
    read -p "Press enter to return to menu..."
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        echo -e "${YELLOW}Please install Docker: https://docs.docker.com/get-docker/${NC}"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not installed${NC}"
        echo -e "${YELLOW}Please install Docker Compose: https://docs.docker.com/compose/install/${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Main script
main() {
    show_banner
    check_prerequisites
    
    while true; do
        show_menu
        read -p "Enter your choice (1-5): " choice
        
        case $choice in
            1)
                deploy_controller
                break
                ;;
            2)
                deploy_client
                break
                ;;
            3)
                deploy_development
                break
                ;;
            4)
                show_documentation
                ;;
            5)
                echo -e "\n${GREEN}Thank you for using MoolAI!${NC}"
                exit 0
                ;;
            *)
                echo -e "\n${RED}Invalid choice. Please select 1-5.${NC}"
                sleep 2
                ;;
        esac
    done
}

# Handle direct command arguments
if [ $# -gt 0 ]; then
    case "$1" in
        controller)
            deploy_controller
            ;;
        client)
            deploy_client
            ;;
        dev|development)
            deploy_development
            ;;
        help|--help|-h)
            echo "Usage: $0 [controller|client|dev]"
            echo "  controller  - Deploy central controller"
            echo "  client      - Deploy client (orchestrator + monitoring)"
            echo "  dev         - Deploy full development stack"
            echo "  help        - Show this help message"
            echo
            echo "Run without arguments for interactive menu."
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
else
    main
fi