#!/bin/bash

# Docker deployment script for DynamicGroundingDINO API

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    print_status "Checking Docker installation..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker and try again."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker and try again."
        exit 1
    fi

    print_success "Docker is running"
}

# Function to check if Docker Compose is available
check_docker_compose() {
    print_status "Checking Docker Compose installation..."
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose and try again."
        exit 1
    fi
    print_success "Docker Compose is available"
}

# Function to build and start services
start_services() {
    local compose_file="docker-compose.yml"
    local profile=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dev)
                compose_file="docker-compose.dev.yml"
                shift
                ;;
            --production)
                profile="--profile production"
                shift
                ;;
            --with-cache)
                profile="--profile cache"
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Usage: $0 [--dev] [--production] [--with-cache]"
                exit 1
                ;;
        esac
    done

    print_status "Building and starting services using $compose_file..."
    
    # Stop any existing containers
    if command -v docker-compose &> /dev/null; then
        docker-compose -f $compose_file down 2>/dev/null || true
        docker-compose -f $compose_file build
        docker-compose -f $compose_file up -d $profile
    else
        docker compose -f $compose_file down 2>/dev/null || true
        docker compose -f $compose_file build
        docker compose -f $compose_file up -d $profile
    fi
    
    print_success "Services started successfully!"
}

# Function to check service health
check_health() {
    print_status "Waiting for services to be healthy..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            print_success "API is healthy and ready!"
            return 0
        fi
        
        print_status "Attempt $attempt/$max_attempts - waiting for API to be ready..."
        sleep 5
        ((attempt++))
    done
    
    print_error "API failed to start within expected time"
    return 1
}

# Function to show service status
show_status() {
    print_status "Service Status:"
    if command -v docker-compose &> /dev/null; then
        docker-compose ps
    else
        docker compose ps
    fi
}

# Function to show logs
show_logs() {
    print_status "Recent logs:"
    if command -v docker-compose &> /dev/null; then
        docker-compose logs --tail=50 grounding-dino-api
    else
        docker compose logs --tail=50 grounding-dino-api
    fi
}

# Function to test the API
test_api() {
    print_status "Testing API endpoints..."
    
    # Test health endpoint
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Health endpoint is working"
    else
        print_error "Health endpoint failed"
        return 1
    fi
    
    # Test detection endpoint with sample image
    print_status "Testing detection endpoint..."
    response=$(curl -s -X POST "http://localhost:8000/detect" \
        -H "Content-Type: application/json" \
        -d '{
            "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
            "text_queries": ["cat"],
            "box_threshold": 0.4,
            "text_threshold": 0.3
        }')
    
    if echo "$response" | grep -q "success"; then
        print_success "Detection endpoint is working"
        echo "Sample response: $response" | head -c 200
        echo "..."
    else
        print_error "Detection endpoint failed"
        echo "Response: $response"
        return 1
    fi
}

# Main execution
main() {
    echo "================================================"
    echo "  DynamicGroundingDINO API Deployment Script"
    echo "================================================"
    
    check_docker
    check_docker_compose
    
    # Parse arguments and start services
    start_services "$@"
    
    # Wait for services to be ready
    if check_health; then
        show_status
        
        # Run API tests
        if test_api; then
            print_success "Deployment completed successfully!"
            echo ""
            echo "🚀 API is now running at: http://localhost:8000"
            echo "📚 API Documentation: http://localhost:8000/docs"
            echo "📖 ReDoc Documentation: http://localhost:8000/redoc"
            echo ""
            echo "To view logs: docker-compose logs -f grounding-dino-api"
            echo "To stop services: docker-compose down"
        else
            print_warning "Deployment completed but API tests failed"
            show_logs
        fi
    else
        print_error "Deployment failed - services are not healthy"
        show_logs
        exit 1
    fi
}

# Run main function with all arguments
main "$@"
