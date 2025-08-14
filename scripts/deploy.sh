#!/bin/bash

# WMS Chatbot Deployment Script
# Automated deployment for development and production environments

set -e

# Configuration
PROJECT_NAME="wms-chatbot"
VERSION="1.0.0"
REGISTRY="your-registry.com"
ENVIRONMENTS=("development" "staging" "production")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    echo "WMS Chatbot Deployment Script"
    echo ""
    echo "Usage: $0 [OPTIONS] ENVIRONMENT"
    echo ""
    echo "ENVIRONMENT:"
    echo "  development    Deploy to development environment"
    echo "  staging        Deploy to staging environment"
    echo "  production     Deploy to production environment"
    echo ""
    echo "OPTIONS:"
    echo "  -h, --help     Show this help message"
    echo "  -v, --version  Show version"
    echo "  --build        Build Docker images before deployment"
    echo "  --migrate      Run database migrations"
    echo "  --scale N      Scale API to N instances (production only)"
    echo "  --rollback     Rollback to previous version"
    echo "  --logs         Show deployment logs"
    echo ""
    echo "Examples:"
    echo "  $0 development --build"
    echo "  $0 production --scale 3"
    echo "  $0 staging --migrate"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check environment file
    if [ ! -f ".env" ]; then
        log_warning ".env file not found. Copying from .env.example"
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warning "Please configure .env file before deployment"
        else
            log_error ".env.example not found"
            exit 1
        fi
    fi
    
    log_success "Prerequisites check completed"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    
    # Build main application image
    docker build -t ${PROJECT_NAME}:${VERSION} .
    docker build -t ${PROJECT_NAME}:latest .
    
    # Tag for registry if specified
    if [ ! -z "$REGISTRY" ]; then
        docker tag ${PROJECT_NAME}:${VERSION} ${REGISTRY}/${PROJECT_NAME}:${VERSION}
        docker tag ${PROJECT_NAME}:latest ${REGISTRY}/${PROJECT_NAME}:latest
    fi
    
    log_success "Docker images built successfully"
}

# Push images to registry
push_images() {
    if [ ! -z "$REGISTRY" ]; then
        log_info "Pushing images to registry..."
        docker push ${REGISTRY}/${PROJECT_NAME}:${VERSION}
        docker push ${REGISTRY}/${PROJECT_NAME}:latest
        log_success "Images pushed to registry"
    fi
}

# Deploy to development
deploy_development() {
    log_info "Deploying to development environment..."
    
    # Start services
    docker-compose down --remove-orphans
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 30
    
    # Health check
    if check_health "http://localhost:5000"; then
        log_success "Development deployment completed successfully"
    else
        log_error "Development deployment failed health check"
        exit 1
    fi
}

# Deploy to staging
deploy_staging() {
    log_info "Deploying to staging environment..."
    
    # Use production compose file but with staging config
    docker-compose -f docker/production.docker-compose.yml down --remove-orphans
    docker-compose -f docker/production.docker-compose.yml up -d
    
    # Wait for services
    sleep 45
    
    # Health check
    if check_health "http://localhost:5000"; then
        log_success "Staging deployment completed successfully"
    else
        log_error "Staging deployment failed health check"
        exit 1
    fi
}

# Deploy to production
deploy_production() {
    log_info "Deploying to production environment..."
    
    # Confirmation prompt
    read -p "Are you sure you want to deploy to PRODUCTION? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "Production deployment cancelled"
        exit 0
    fi
    
    # Backup current deployment
    backup_production
    
    # Deploy with zero downtime
    docker-compose -f docker/production.docker-compose.yml up -d --no-deps --scale wms-chatbot=2
    
    # Health check new instances
    sleep 60
    if check_health "http://localhost:5000"; then
        # Scale down old instances
        docker-compose -f docker/production.docker-compose.yml up -d --no-deps --scale wms-chatbot=${SCALE:-2}
        log_success "Production deployment completed successfully"
    else
        log_error "Production deployment failed health check"
        log_info "Rolling back..."
        rollback_production
        exit 1
    fi
}

# Backup production
backup_production() {
    log_info "Creating production backup..."
    
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    docker-compose -f docker/production.docker-compose.yml exec -T postgres-prod \
        pg_dump -U wms_user -d wms_chatbot_prod > "$BACKUP_DIR/database.sql"
    
    # Backup vector database
    docker-compose -f docker/production.docker-compose.yml exec -T weaviate-prod \
        curl -X POST http://localhost:8080/v1/backups/filesystem > "$BACKUP_DIR/weaviate_backup.json"
    
    # Backup configuration
    cp -r docker "$BACKUP_DIR/"
    cp .env "$BACKUP_DIR/"
    
    log_success "Backup created at $BACKUP_DIR"
}

# Rollback production
rollback_production() {
    log_info "Rolling back production deployment..."
    
    # Get latest backup
    LATEST_BACKUP=$(ls -1t backups/ | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        log_error "No backup found for rollback"
        exit 1
    fi
    
    log_info "Rolling back to backup: $LATEST_BACKUP"
    
    # Restore configuration
    cp "backups/$LATEST_BACKUP/.env" .env
    cp -r "backups/$LATEST_BACKUP/docker" docker/
    
    # Restart services
    docker-compose -f docker/production.docker-compose.yml down
    docker-compose -f docker/production.docker-compose.yml up -d
    
    log_success "Rollback completed"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Wait for database to be ready
    sleep 10
    
    # Run migrations
    docker-compose exec wms-chatbot python -c "
from src.database.connection import get_database_manager
import asyncio
async def migrate():
    db = get_database_manager()
    await db.initialize()
    await db.create_all_tables()
asyncio.run(migrate())
"
    
    log_success "Database migrations completed"
}

# Health check
check_health() {
    local url=$1
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url/health/" > /dev/null; then
            return 0
        fi
        log_info "Health check attempt $attempt/$max_attempts failed, retrying..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    return 1
}

# Scale services
scale_services() {
    local replicas=$1
    local environment=$2
    
    log_info "Scaling services to $replicas replicas..."
    
    if [ "$environment" = "production" ]; then
        docker-compose -f docker/production.docker-compose.yml up -d --scale wms-chatbot=$replicas
    else
        docker-compose up -d --scale wms-chatbot=$replicas
    fi
    
    log_success "Services scaled to $replicas replicas"
}

# Show logs
show_logs() {
    local environment=$1
    
    if [ "$environment" = "production" ]; then
        docker-compose -f docker/production.docker-compose.yml logs -f wms-chatbot
    else
        docker-compose logs -f wms-chatbot
    fi
}

# Monitor deployment
monitor_deployment() {
    log_info "Starting deployment monitoring..."
    
    # Show real-time logs
    show_logs $1 &
    LOG_PID=$!
    
    # Monitor health
    while true; do
        if check_health "http://localhost:5000"; then
            echo "$(date): Health check passed"
        else
            echo "$(date): Health check failed"
        fi
        sleep 60
    done &
    MONITOR_PID=$!
    
    # Cleanup on exit
    trap "kill $LOG_PID $MONITOR_PID 2>/dev/null" EXIT
    
    wait
}

# Main deployment function
main() {
    local environment=""
    local build_images=false
    local run_migrations=false
    local scale_replicas=""
    local rollback=false
    local show_logs=false
    local monitor=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                echo "WMS Chatbot Deployment Script v${VERSION}"
                exit 0
                ;;
            --build)
                build_images=true
                shift
                ;;
            --migrate)
                run_migrations=true
                shift
                ;;
            --scale)
                scale_replicas="$2"
                shift 2
                ;;
            --rollback)
                rollback=true
                shift
                ;;
            --logs)
                show_logs=true
                shift
                ;;
            --monitor)
                monitor=true
                shift
                ;;
            development|staging|production)
                environment="$1"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Validate environment
    if [ -z "$environment" ] && [ "$show_logs" = false ] && [ "$rollback" = false ]; then
        log_error "Environment must be specified"
        show_help
        exit 1
    fi
    
    # Check if environment is valid
    if [[ ! " ${ENVIRONMENTS[@]} " =~ " ${environment} " ]] && [ ! -z "$environment" ]; then
        log_error "Invalid environment: $environment"
        log_error "Valid environments: ${ENVIRONMENTS[*]}"
        exit 1
    fi
    
    # Start deployment process
    log_info "Starting WMS Chatbot deployment..."
    log_info "Environment: $environment"
    log_info "Version: $VERSION"
    
    # Check prerequisites
    check_prerequisites
    
    # Handle special operations
    if [ "$rollback" = true ]; then
        rollback_production
        exit 0
    fi
    
    if [ "$show_logs" = true ]; then
        show_logs "$environment"
        exit 0
    fi
    
    # Build images if requested
    if [ "$build_images" = true ]; then
        build_images
        push_images
    fi
    
    # Deploy based on environment
    case $environment in
        development)
            deploy_development
            ;;
        staging)
            deploy_staging
            ;;
        production)
            deploy_production
            ;;
    esac
    
    # Run migrations if requested
    if [ "$run_migrations" = true ]; then
        run_migrations
    fi
    
    # Scale services if requested
    if [ ! -z "$scale_replicas" ]; then
        scale_services "$scale_replicas" "$environment"
    fi
    
    # Start monitoring if requested
    if [ "$monitor" = true ]; then
        monitor_deployment "$environment"
    fi
    
    log_success "Deployment completed successfully!"
    log_info "Access the application at: http://localhost:5000"
    log_info "API Documentation: http://localhost:5000/docs"
    log_info "Monitoring Dashboard: http://localhost:5001"
}

# Run main function
main "$@"