@echo off
REM Windows deployment script for DynamicGroundingDINO API

setlocal enabledelayedexpansion

echo ================================================
echo   DynamicGroundingDINO API Deployment Script
echo ================================================

REM Check if Docker is installed and running
echo [INFO] Checking Docker installation...
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed or not running. Please install Docker Desktop and try again.
    exit /b 1
)

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker daemon is not running. Please start Docker Desktop and try again.
    exit /b 1
)

echo [SUCCESS] Docker is running

REM Check Docker Compose
echo [INFO] Checking Docker Compose installation...
docker-compose version >nul 2>&1
if %errorlevel% neq 0 (
    docker compose version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Docker Compose is not installed. Please install Docker Compose and try again.
        exit /b 1
    )
    set COMPOSE_CMD=docker compose
) else (
    set COMPOSE_CMD=docker-compose
)

echo [SUCCESS] Docker Compose is available

REM Parse command line arguments
set COMPOSE_FILE=docker-compose.yml
set PROFILE=

:parse_args
if "%1"=="--dev" (
    set COMPOSE_FILE=docker-compose.dev.yml
    shift
    goto parse_args
)
if "%1"=="--production" (
    set PROFILE=--profile production
    shift
    goto parse_args
)
if "%1"=="--with-cache" (
    set PROFILE=--profile cache
    shift
    goto parse_args
)
if "%1"=="" goto start_services
echo [ERROR] Unknown option: %1
echo Usage: deploy.bat [--dev] [--production] [--with-cache]
exit /b 1

:start_services
echo [INFO] Building and starting services using %COMPOSE_FILE%...

REM Stop any existing containers
%COMPOSE_CMD% -f %COMPOSE_FILE% down >nul 2>&1

REM Build and start services
%COMPOSE_CMD% -f %COMPOSE_FILE% build
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build Docker images
    exit /b 1
)

%COMPOSE_CMD% -f %COMPOSE_FILE% up -d %PROFILE%
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start services
    exit /b 1
)

echo [SUCCESS] Services started successfully!

REM Wait for services to be healthy
echo [INFO] Waiting for services to be healthy...
set /a attempt=1
set /a max_attempts=30

:health_check
curl -f http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] API is healthy and ready!
    goto show_status
)

echo [INFO] Attempt %attempt%/%max_attempts% - waiting for API to be ready...
timeout /t 5 /nobreak >nul
set /a attempt+=1
if %attempt% leq %max_attempts% goto health_check

echo [ERROR] API failed to start within expected time
goto show_logs

:show_status
echo [INFO] Service Status:
%COMPOSE_CMD% ps

REM Test the API
echo [INFO] Testing API endpoints...

REM Test health endpoint
curl -f http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] Health endpoint is working
) else (
    echo [ERROR] Health endpoint failed
    goto show_logs
)

REM Test detection endpoint
echo [INFO] Testing detection endpoint...
curl -s -X POST "http://localhost:8000/detect" -H "Content-Type: application/json" -d "{\"image_url\": \"http://images.cocodataset.org/val2017/000000039769.jpg\", \"text_queries\": [\"cat\"], \"box_threshold\": 0.4, \"text_threshold\": 0.3}" >test_response.json 2>&1

findstr "success" test_response.json >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] Detection endpoint is working
    del test_response.json >nul 2>&1
    goto deployment_success
) else (
    echo [ERROR] Detection endpoint failed
    type test_response.json
    del test_response.json >nul 2>&1
    goto show_logs
)

:deployment_success
echo [SUCCESS] Deployment completed successfully!
echo.
echo 🚀 API is now running at: http://localhost:8000
echo 📚 API Documentation: http://localhost:8000/docs
echo 📖 ReDoc Documentation: http://localhost:8000/redoc
echo.
echo To view logs: %COMPOSE_CMD% logs -f grounding-dino-api
echo To stop services: %COMPOSE_CMD% down
goto end

:show_logs
echo [INFO] Recent logs:
%COMPOSE_CMD% logs --tail=50 grounding-dino-api
exit /b 1

:end
endlocal
