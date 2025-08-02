#!/bin/bash

# Production deployment script for DynamicGroundingDINO API with Queue Support

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

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --basic            Basic setup (API + Redis, no workers)"
    echo "  --with-workers     Include Celery workers for queue processing"
    echo "  --production       Full production setup with load balancing"
    echo "  --monitoring       Include monitoring services (Flower, Redis Commander)"
    echo "  --scale            Scale up workers for high load"
    echo "  --stop             Stop all services"
    echo "  --restart          Restart all services"
    echo "  --status           Show service status"
    echo "  --logs             Show recent logs"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --basic                    # Start API and Redis only"
    echo "  $0 --with-workers             # Start with queue workers"
    echo "  $0 --production --monitoring  # Full production setup"
    echo "  $0 --scale                    # High-load setup with multiple workers"
}

# Function to check Docker
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

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose and try again."
        exit 1
    fi

    print_success "Docker environment is ready"
}

# Function to get compose command
get_compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    else
        echo "docker compose"
    fi
}

# Function to start services
start_services() {
    local setup_type="$1"
    local compose_cmd=$(get_compose_cmd)
    
    print_status "Starting services for: $setup_type"
    
    case $setup_type in
        "basic")
            $compose_cmd -f docker-compose.yml up -d redis grounding-dino-api
            ;;
        "with-workers")
            $compose_cmd -f docker-compose.yml --profile workers up -d
            ;;
        "production")
            $compose_cmd -f docker-compose.prod.yml up -d
            ;;
        "monitoring")
            $compose_cmd -f docker-compose.yml --profile workers --profile monitoring up -d
            ;;
        "scale")
            $compose_cmd -f docker-compose.prod.yml up -d
            print_status "Scaling workers..."
            # Additional scaling can be done here
            ;;
    esac
    
    print_success "Services started successfully!"
}

# Function to stop services
stop_services() {
    local compose_cmd=$(get_compose_cmd)
    
    print_status "Stopping all services..."
    $compose_cmd -f docker-compose.yml down 2>/dev/null || true
    $compose_cmd -f docker-compose.prod.yml down 2>/dev/null || true
    print_success "All services stopped"
}

# Function to restart services
restart_services() {
    stop_services
    sleep 2
    start_services "with-workers"
}

# Function to check health
check_health() {
    print_status "Checking service health..."
    local max_attempts=60
    local attempt=1
    
    # Check Redis first
    while [ $attempt -le 30 ]; do
        if docker exec grounding-dino-redis redis-cli ping > /dev/null 2>&1 || \
           docker exec grounding-dino-redis-prod redis-cli ping > /dev/null 2>&1; then
            print_success "Redis is ready!"
            break
        fi
        print_status "Waiting for Redis... ($attempt/30)"
        sleep 2
        ((attempt++))
    done
    
    # Check API
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            print_success "API is healthy!"
            
            # Check queue system
            if curl -s http://localhost:8000/queue/status > /dev/null 2>&1; then
                print_success "Queue system is operational!"
            else
                print_warning "Queue system may not be enabled"
            fi
            return 0
        fi
        
        print_status "Waiting for API... ($attempt/$max_attempts)"
        sleep 3
        ((attempt++))
    done
    
    print_error "API failed to start properly"
    return 1
}

# Function to show status
show_status() {
    local compose_cmd=$(get_compose_cmd)
    
    print_status "Service Status:"
    echo ""
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(grounding-dino|redis|flower)" || echo "No services running"
    
    echo ""
    print_status "Queue Status:"
    if curl -s http://localhost:8000/queue/status 2>/dev/null; then
        echo ""
    else
        print_warning "Queue status unavailable"
    fi
}

# Function to show logs
show_logs() {
    local compose_cmd=$(get_compose_cmd)
    
    print_status "Recent API logs:"
    docker logs --tail=30 grounding-dino-api 2>/dev/null || \
    docker logs --tail=30 grounding-dino-api-prod 2>/dev/null || \
    print_warning "API logs not available"
    
    echo ""
    print_status "Recent worker logs:"
    docker logs --tail=20 grounding-dino-worker-1 2>/dev/null || \
    print_warning "Worker logs not available"
    
    echo ""
    print_status "Redis logs:"
    docker logs --tail=10 grounding-dino-redis 2>/dev/null || \
    docker logs --tail=10 grounding-dino-redis-prod 2>/dev/null || \
    print_warning "Redis logs not available"
}

# Function to test API
test_api() {
    print_status "Testing API functionality..."
    
    # Test health
    if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
        print_error "Health endpoint failed"
        return 1
    fi
    print_success "Health endpoint OK"
    
    # Test async submission
    response=$(curl -s -X POST "http://localhost:8000/detect/async" \
        -H "Content-Type: application/json" \
        -d '{
            "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
            "text_queries": ["cat"],
            "priority": 5
        }' 2>/dev/null)
    
    if echo "$response" | grep -q "task_id"; then
        print_success "Async detection submission OK"
        task_id=$(echo "$response" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
        
        # Check task status
        sleep 2
        if curl -s "http://localhost:8000/task/$task_id" | grep -q "status"; then
            print_success "Task status retrieval OK"
        fi
    else
        print_warning "Async detection may not be available, testing sync mode"
        
        # Test sync detection
        sync_response=$(curl -s -X POST "http://localhost:8000/detect" \
            -H "Content-Type: application/json" \
            -d '{
                "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
                "text_queries": ["cat"],
                "async_processing": false
            }')
        
        if echo "$sync_response" | grep -q "success"; then
            print_success "Sync detection OK"
        else
            print_error "Both async and sync detection failed"
            return 1
        fi
    fi
    
    return 0
}

# Function to show final information
show_info() {
    echo ""
    echo "=========================================================="
    echo "🚀 DynamicGroundingDINO API is running!"
    echo "=========================================================="
    echo ""
    echo "📱 Web Interfaces:"
    echo "   API Home:     http://localhost:8000"
    echo "   API Docs:     http://localhost:8000/docs"
    echo "   Health Check: http://localhost:8000/health"
    echo "   Queue Status: http://localhost:8000/queue/status"
    
    if docker ps | grep -q flower; then
        echo "   Flower UI:    http://localhost:5555"
    fi
    
    if docker ps | grep -q redis-commander; then
        echo "   Redis UI:     http://localhost:8081"
    fi
    
    echo ""
    echo "🛠️  Management Commands:"
    echo "   $0 --status     # Check service status"
    echo "   $0 --logs       # View recent logs"
    echo "   $0 --restart    # Restart all services"
    echo "   $0 --stop       # Stop all services"
    echo ""
    echo "📊 Example API Usage:"
    echo "   # Async detection"
    echo "   curl -X POST http://localhost:8000/detect/async \\"
    echo "        -H 'Content-Type: application/json' \\"
    echo "        -d '{\"image_url\":\"http://example.com/image.jpg\",\"text_queries\":[\"cat\",\"dog\"]}'"
    echo ""
}

# Main function
main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                show_usage
                exit 0
                ;;
            --basic)
                check_docker
                start_services "basic"
                if check_health; then
                    print_success "Basic setup completed!"
                    show_info
                fi
                exit 0
                ;;
            --with-workers)
                check_docker
                start_services "with-workers"
                if check_health && test_api; then
                    print_success "Setup with workers completed!"
                    show_info
                fi
                exit 0
                ;;
            --production)
                check_docker
                start_services "production"
                if check_health && test_api; then
                    print_success "Production setup completed!"
                    show_info
                fi
                exit 0
                ;;
            --monitoring)
                check_docker
                start_services "monitoring"
                if check_health && test_api; then
                    print_success "Setup with monitoring completed!"
                    show_info
                fi
                exit 0
                ;;
            --scale)
                check_docker
                start_services "scale"
                if check_health && test_api; then
                    print_success "High-scale setup completed!"
                    show_info
                fi
                exit 0
                ;;
            --stop)
                stop_services
                exit 0
                ;;
            --restart)
                restart_services
                if check_health; then
                    print_success "Services restarted successfully!"
                    show_info
                fi
                exit 0
                ;;
            --status)
                show_status
                exit 0
                ;;
            --logs)
                show_logs
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Run main function
main "$@"
