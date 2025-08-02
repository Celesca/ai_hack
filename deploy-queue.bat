@echo off
REM Production deployment script for DynamicGroundingDINO API with Queue Support (Windows)

setlocal enabledelayedexpansion

REM Function to show usage
if "%1"=="" goto show_usage
if "%1"=="--help" goto show_usage

REM Check Docker installation
echo [INFO] Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed. Please install Docker and try again.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker daemon is not running. Please start Docker and try again.
    exit /b 1
)

echo [SUCCESS] Docker environment is ready

REM Handle command line arguments
if "%1"=="--basic" goto basic_setup
if "%1"=="--with-workers" goto workers_setup
if "%1"=="--production" goto production_setup
if "%1"=="--monitoring" goto monitoring_setup
if "%1"=="--scale" goto scale_setup
if "%1"=="--stop" goto stop_services
if "%1"=="--restart" goto restart_services
if "%1"=="--status" goto show_status
if "%1"=="--logs" goto show_logs

echo [ERROR] Unknown option: %1
goto show_usage

:basic_setup
echo [INFO] Starting basic services (API + Redis)...
docker-compose -f docker-compose.yml up -d redis grounding-dino-api
goto check_health

:workers_setup
echo [INFO] Starting services with workers...
docker-compose -f docker-compose.yml --profile workers up -d
goto check_health

:production_setup
echo [INFO] Starting production services...
docker-compose -f docker-compose.prod.yml up -d
goto check_health

:monitoring_setup
echo [INFO] Starting services with monitoring...
docker-compose -f docker-compose.yml --profile workers --profile monitoring up -d
goto check_health

:scale_setup
echo [INFO] Starting high-scale services...
docker-compose -f docker-compose.prod.yml up -d
echo [INFO] Services scaled for high load
goto check_health

:stop_services
echo [INFO] Stopping all services...
docker-compose -f docker-compose.yml down >nul 2>&1
docker-compose -f docker-compose.prod.yml down >nul 2>&1
echo [SUCCESS] All services stopped
exit /b 0

:restart_services
echo [INFO] Restarting services...
call :stop_services
timeout /t 3 /nobreak >nul
docker-compose -f docker-compose.yml --profile workers up -d
goto check_health

:show_status
echo [INFO] Service Status:
echo.
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | findstr "grounding-dino redis flower"
echo.
echo [INFO] Queue Status:
curl -s http://localhost:8000/queue/status 2>nul
if errorlevel 1 echo [WARNING] Queue status unavailable
exit /b 0

:show_logs
echo [INFO] Recent API logs:
docker logs --tail=30 grounding-dino-api 2>nul
if errorlevel 1 docker logs --tail=30 grounding-dino-api-prod 2>nul
if errorlevel 1 echo [WARNING] API logs not available

echo.
echo [INFO] Recent worker logs:
docker logs --tail=20 grounding-dino-worker-1 2>nul
if errorlevel 1 echo [WARNING] Worker logs not available

echo.
echo [INFO] Redis logs:
docker logs --tail=10 grounding-dino-redis 2>nul
if errorlevel 1 docker logs --tail=10 grounding-dino-redis-prod 2>nul
if errorlevel 1 echo [WARNING] Redis logs not available
exit /b 0

:check_health
echo [INFO] Checking service health...

REM Wait for Redis
set /a attempt=1
:redis_wait
docker exec grounding-dino-redis redis-cli ping >nul 2>&1
if not errorlevel 1 goto redis_ready
docker exec grounding-dino-redis-prod redis-cli ping >nul 2>&1
if not errorlevel 1 goto redis_ready

echo [INFO] Waiting for Redis... (%attempt%/30)
timeout /t 2 /nobreak >nul
set /a attempt+=1
if %attempt% leq 30 goto redis_wait

echo [ERROR] Redis failed to start
exit /b 1

:redis_ready
echo [SUCCESS] Redis is ready!

REM Wait for API
set /a attempt=1
:api_wait
curl -f http://localhost:8000/health >nul 2>&1
if not errorlevel 1 goto api_ready

echo [INFO] Waiting for API... (%attempt%/60)
timeout /t 3 /nobreak >nul
set /a attempt+=1
if %attempt% leq 60 goto api_wait

echo [ERROR] API failed to start properly
exit /b 1

:api_ready
echo [SUCCESS] API is healthy!

REM Check queue system
curl -s http://localhost:8000/queue/status >nul 2>&1
if not errorlevel 1 (
    echo [SUCCESS] Queue system is operational!
) else (
    echo [WARNING] Queue system may not be enabled
)

call :test_api
if errorlevel 1 exit /b 1

call :show_info
exit /b 0

:test_api
echo [INFO] Testing API functionality...

REM Test health endpoint
curl -f http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Health endpoint failed
    exit /b 1
)
echo [SUCCESS] Health endpoint OK

REM Test queue submission
curl -s -X POST "http://localhost:8000/detect/async" ^
     -H "Content-Type: application/json" ^
     -d "{\"image_url\":\"http://images.cocodataset.org/val2017/000000039769.jpg\",\"text_queries\":[\"cat\"],\"priority\":5}" >temp_response.json 2>nul

findstr "task_id" temp_response.json >nul
if not errorlevel 1 (
    echo [SUCCESS] Async detection submission OK
    del temp_response.json 2>nul
) else (
    echo [WARNING] Async detection may not be available, testing sync mode
    del temp_response.json 2>nul
    
    curl -s -X POST "http://localhost:8000/detect" ^
         -H "Content-Type: application/json" ^
         -d "{\"image_url\":\"http://images.cocodataset.org/val2017/000000039769.jpg\",\"text_queries\":[\"cat\"],\"async_processing\":false}" >temp_sync.json 2>nul
    
    findstr "success" temp_sync.json >nul
    if not errorlevel 1 (
        echo [SUCCESS] Sync detection OK
        del temp_sync.json 2>nul
    ) else (
        echo [ERROR] Both async and sync detection failed
        del temp_sync.json 2>nul
        exit /b 1
    )
)

exit /b 0

:show_info
echo.
echo ==========================================================
echo 🚀 DynamicGroundingDINO API is running!
echo ==========================================================
echo.
echo 📱 Web Interfaces:
echo    API Home:     http://localhost:8000
echo    API Docs:     http://localhost:8000/docs
echo    Health Check: http://localhost:8000/health
echo    Queue Status: http://localhost:8000/queue/status

docker ps | findstr flower >nul
if not errorlevel 1 echo    Flower UI:    http://localhost:5555

docker ps | findstr redis-commander >nul
if not errorlevel 1 echo    Redis UI:     http://localhost:8081

echo.
echo 🛠️  Management Commands:
echo    %~nx0 --status     # Check service status
echo    %~nx0 --logs       # View recent logs
echo    %~nx0 --restart    # Restart all services
echo    %~nx0 --stop       # Stop all services
echo.
echo 📊 Example API Usage:
echo    # Async detection
echo    curl -X POST http://localhost:8000/detect/async \
echo         -H "Content-Type: application/json" \
echo         -d "{\"image_url\":\"http://example.com/image.jpg\",\"text_queries\":[\"cat\",\"dog\"]}"
echo.
exit /b 0

:show_usage
echo Usage: %~nx0 [OPTIONS]
echo.
echo Options:
echo   --basic            Basic setup (API + Redis, no workers)
echo   --with-workers     Include Celery workers for queue processing
echo   --production       Full production setup with load balancing
echo   --monitoring       Include monitoring services (Flower, Redis Commander)
echo   --scale            Scale up workers for high load
echo   --stop             Stop all services
echo   --restart          Restart all services
echo   --status           Show service status
echo   --logs             Show recent logs
echo   --help             Show this help message
echo.
echo Examples:
echo   %~nx0 --basic                    # Start API and Redis only
echo   %~nx0 --with-workers             # Start with queue workers
echo   %~nx0 --production --monitoring  # Full production setup
echo   %~nx0 --scale                    # High-load setup with multiple workers
exit /b 0
