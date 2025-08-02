from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Union
import uvicorn
import io
import base64
from PIL import Image
import logging
import os
from datetime import datetime

from model import ModelManager, DynamicGroundingDINO
from queue_worker import task_manager, TaskManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if queue mode is enabled
ENABLE_QUEUE = os.getenv("ENABLE_QUEUE", "true").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Initialize FastAPI app
app = FastAPI(
    title="DynamicGroundingDINO API with Queue Support",
    description="Zero-shot object detection API using Grounding DINO model with Redis queue support for production scaling",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model manager
model_manager = ModelManager()


# Pydantic models for request/response
class DetectionRequest(BaseModel):
    """Request model for URL-based detection"""
    image_url: str = Field(..., description="URL of the image to analyze")
    text_queries: Union[str, List[str]] = Field(..., description="Text queries for object detection")
    box_threshold: Optional[float] = Field(0.4, ge=0.0, le=1.0, description="Confidence threshold for bounding boxes")
    text_threshold: Optional[float] = Field(0.3, ge=0.0, le=1.0, description="Confidence threshold for text matching")
    return_visualization: Optional[bool] = Field(True, description="Whether to return visualization image")
    async_processing: Optional[bool] = Field(False, description="Whether to process asynchronously using queue")
    priority: Optional[int] = Field(5, ge=0, le=9, description="Task priority (0-9, higher is more priority)")


class AsyncDetectionRequest(BaseModel):
    """Request model for async detection operations"""
    image_url: str = Field(..., description="URL of the image to analyze")
    text_queries: Union[str, List[str]] = Field(..., description="Text queries for object detection")
    box_threshold: Optional[float] = Field(0.4, ge=0.0, le=1.0, description="Confidence threshold for bounding boxes")
    text_threshold: Optional[float] = Field(0.3, ge=0.0, le=1.0, description="Confidence threshold for text matching")
    return_visualization: Optional[bool] = Field(True, description="Whether to return visualization image")
    priority: Optional[int] = Field(5, ge=0, le=9, description="Task priority (0-9, higher is more priority)")


class TaskSubmissionResponse(BaseModel):
    """Response for task submission"""
    task_id: str
    status: str
    message: str
    estimated_completion: Optional[str] = None


class QueueStatusResponse(BaseModel):
    """Response for queue status"""
    status: str
    active_tasks: int
    scheduled_tasks: int
    reserved_tasks: int
    workers: List[str]
    timestamp: str


class BoundingBox(BaseModel):
    """Bounding box coordinates"""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    width: float
    height: float


class Detection(BaseModel):
    """Single detection result"""
    id: int
    label: str
    confidence: float
    bounding_box: BoundingBox


class ImageSize(BaseModel):
    """Image dimensions"""
    width: int
    height: int


class Thresholds(BaseModel):
    """Detection thresholds"""
    box_threshold: float
    text_threshold: float


class Visualization(BaseModel):
    """Visualization data"""
    image_base64: str
    format: str


class DetectionResponse(BaseModel):
    """Response model for detection results"""
    success: bool
    num_detections: int
    detections: List[Detection]
    image_size: Optional[ImageSize] = None
    queries: Optional[List[str]] = None
    thresholds: Optional[Thresholds] = None
    visualization: Optional[Visualization] = None
    error: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Response for task status check"""
    task_id: str
    status: str
    progress: Optional[int] = None
    stage: Optional[str] = None
    message: Optional[str] = None
    result: Optional[DetectionResponse] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    model_loaded: bool
    message: str


@app.on_event("startup")
async def startup_event():
    """Initialize model on startup"""
    try:
        logger.info("Loading DynamicGroundingDINO model...")
        model_manager.get_model()
        logger.info("Model loaded successfully!")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise e


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with API information"""
    queue_status = "enabled" if ENABLE_QUEUE else "disabled"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>DynamicGroundingDINO API</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #333; }}
            .endpoint {{ margin: 20px 0; padding: 15px; border-left: 4px solid #007acc; background: #f5f5f5; }}
            .method {{ font-weight: bold; color: #007acc; }}
            .queue-status {{ padding: 10px; border-radius: 5px; margin: 15px 0; }}
            .queue-enabled {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
            .queue-disabled {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
            pre {{ background: #f0f0f0; padding: 10px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>🔍 DynamicGroundingDINO API v2.0</h1>
        <p>Zero-shot object detection API using Grounding DINO model with Redis queue support</p>
        
        <div class="queue-status queue-{'enabled' if ENABLE_QUEUE else 'disabled'}">
            <strong>Queue Processing:</strong> {queue_status.upper()}
            {f'<br><small>Redis URL: {REDIS_URL}</small>' if ENABLE_QUEUE else ''}
        </div>
        
        <h3>🚀 Detection Endpoints</h3>
        <div class="endpoint">
            <span class="method">POST</span> <strong>/detect</strong> - Detect objects from image URL (sync/async)
        </div>
        
        <div class="endpoint">
            <span class="method">POST</span> <strong>/detect/upload</strong> - Detect objects from uploaded image (sync/async)
        </div>
        
        <div class="endpoint">
            <span class="method">POST</span> <strong>/detect/async</strong> - Submit async detection task
        </div>
        
        <div class="endpoint">
            <span class="method">POST</span> <strong>/detect/async/upload</strong> - Submit async detection task with upload
        </div>
        
        <h3>📊 Queue Management</h3>
        <div class="endpoint">
            <span class="method">GET</span> <strong>/task/{{task_id}}</strong> - Get task status and result
        </div>
        
        <div class="endpoint">
            <span class="method">DELETE</span> <strong>/task/{{task_id}}</strong> - Cancel task
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <strong>/queue/status</strong> - Get queue status and statistics
        </div>
        
        <h3>🔧 System Endpoints</h3>
        <div class="endpoint">
            <span class="method">GET</span> <strong>/health</strong> - Check API health and model status
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <strong>/model/info</strong> - Get model information
        </div>
        
        <h3>📚 Documentation</h3>
        <ul>
            <li><a href="/docs">Interactive API Documentation (Swagger UI)</a></li>
            <li><a href="/redoc">API Documentation (ReDoc)</a></li>
        </ul>
        
        <h3>🚀 Quick Start Examples</h3>
        
        <h4>Synchronous Detection:</h4>
        <pre>
curl -X POST "http://localhost:8000/detect" \\
     -H "Content-Type: application/json" \\
     -d '{{
       "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
       "text_queries": ["cat", "remote", "person"],
       "async_processing": false
     }}'
        </pre>
        
        <h4>Asynchronous Detection:</h4>
        <pre>
# Submit task
curl -X POST "http://localhost:8000/detect/async" \\
     -H "Content-Type: application/json" \\
     -d '{{
       "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
       "text_queries": ["cat", "remote", "person"],
       "priority": 7
     }}'

# Check task status
curl -X GET "http://localhost:8000/task/{{task_id}}"
        </pre>
    </body>
    </html>
    """
    return html_content


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        model_loaded = model_manager.is_model_loaded()
        if model_loaded:
            return HealthResponse(
                status="healthy",
                model_loaded=True,
                message="API is running and model is loaded"
            )
        else:
            return HealthResponse(
                status="loading",
                model_loaded=False,
                message="API is running but model is still loading"
            )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            model_loaded=False,
            message=f"Health check failed: {str(e)}"
        )


@app.post("/detect", response_model=Union[DetectionResponse, TaskSubmissionResponse])
async def detect_objects_from_url(request: DetectionRequest):
    """
    Detect objects in image from URL - supports both sync and async processing
    
    - **image_url**: URL of the image to analyze
    - **text_queries**: Text descriptions of objects to detect (string or list of strings)
    - **box_threshold**: Confidence threshold for bounding boxes (0.0 to 1.0)
    - **text_threshold**: Confidence threshold for text matching (0.0 to 1.0)
    - **return_visualization**: Whether to return visualization image as base64
    - **async_processing**: Whether to process asynchronously using queue (if enabled)
    - **priority**: Task priority for async processing (0-9, higher is more priority)
    """
    try:
        # Check if async processing is requested and queue is enabled
        if request.async_processing and ENABLE_QUEUE:
            # Submit to queue
            task_id = task_manager.submit_detection_task(
                image_data=request.image_url,
                image_type="url",
                text_queries=request.text_queries,
                box_threshold=request.box_threshold,
                text_threshold=request.text_threshold,
                return_visualization=request.return_visualization,
                priority=request.priority
            )
            
            return TaskSubmissionResponse(
                task_id=task_id,
                status="submitted",
                message="Task submitted for async processing",
                estimated_completion=None
            )
        
        # Synchronous processing
        if request.async_processing and not ENABLE_QUEUE:
            logger.warning("Async processing requested but queue is disabled, processing synchronously")
        
        # Get model instance
        model = model_manager.get_model()
        
        # Process detection
        result = model.process_detection(
            image_source=request.image_url,
            text_queries=request.text_queries,
            box_threshold=request.box_threshold,
            text_threshold=request.text_threshold,
            return_visualization=request.return_visualization
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return DetectionResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {str(e)}"
        )


@app.post("/detect/upload", response_model=Union[DetectionResponse, TaskSubmissionResponse])
async def detect_objects_from_upload(
    file: UploadFile = File(..., description="Image file to analyze"),
    text_queries: str = Form(..., description="Comma-separated text queries for object detection"),
    box_threshold: float = Form(0.4, description="Confidence threshold for bounding boxes"),
    text_threshold: float = Form(0.3, description="Confidence threshold for text matching"),
    return_visualization: bool = Form(True, description="Whether to return visualization image"),
    async_processing: bool = Form(False, description="Whether to process asynchronously using queue"),
    priority: int = Form(5, description="Task priority (0-9, higher is more priority)")
):
    """
    Detect objects in uploaded image file - supports both sync and async processing
    
    - **file**: Image file (JPEG, PNG, etc.)
    - **text_queries**: Comma-separated text descriptions of objects to detect
    - **box_threshold**: Confidence threshold for bounding boxes (0.0 to 1.0)
    - **text_threshold**: Confidence threshold for text matching (0.0 to 1.0)
    - **return_visualization**: Whether to return visualization image as base64
    - **async_processing**: Whether to process asynchronously using queue (if enabled)
    - **priority**: Task priority for async processing (0-9, higher is more priority)
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Read image file
        contents = await file.read()
        
        # Parse text queries
        queries_list = [q.strip() for q in text_queries.split(",") if q.strip()]
        if not queries_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one text query is required"
            )
        
        # Validate thresholds
        if not (0.0 <= box_threshold <= 1.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="box_threshold must be between 0.0 and 1.0"
            )
        
        if not (0.0 <= text_threshold <= 1.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="text_threshold must be between 0.0 and 1.0"
            )
        
        # Check if async processing is requested and queue is enabled
        if async_processing and ENABLE_QUEUE:
            # Submit to queue
            task_id = task_manager.submit_detection_task(
                image_data=contents,
                image_type="bytes",
                text_queries=queries_list,
                box_threshold=box_threshold,
                text_threshold=text_threshold,
                return_visualization=return_visualization,
                priority=priority
            )
            
            return TaskSubmissionResponse(
                task_id=task_id,
                status="submitted",
                message="Task submitted for async processing",
                estimated_completion=None
            )
        
        # Synchronous processing
        if async_processing and not ENABLE_QUEUE:
            logger.warning("Async processing requested but queue is disabled, processing synchronously")
        
        # Get model instance
        model = model_manager.get_model()
        
        # Process detection
        result = model.process_detection(
            image_source=contents,
            text_queries=queries_list,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            return_visualization=return_visualization
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return DetectionResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload detection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {str(e)}"
        )


@app.post("/detect/async", response_model=TaskSubmissionResponse)
async def submit_async_detection_url(request: AsyncDetectionRequest):
    """
    Submit async detection task for image URL
    
    - **image_url**: URL of the image to analyze
    - **text_queries**: Text descriptions of objects to detect
    - **box_threshold**: Confidence threshold for bounding boxes (0.0 to 1.0)
    - **text_threshold**: Confidence threshold for text matching (0.0 to 1.0)
    - **return_visualization**: Whether to return visualization image as base64
    - **priority**: Task priority (0-9, higher is more priority)
    """
    if not ENABLE_QUEUE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue processing is disabled. Use synchronous endpoints instead."
        )
    
    try:
        task_id = task_manager.submit_detection_task(
            image_data=request.image_url,
            image_type="url",
            text_queries=request.text_queries,
            box_threshold=request.box_threshold,
            text_threshold=request.text_threshold,
            return_visualization=request.return_visualization,
            priority=request.priority
        )
        
        return TaskSubmissionResponse(
            task_id=task_id,
            status="submitted",
            message="Task submitted for async processing"
        )
        
    except Exception as e:
        logger.error(f"Failed to submit async task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}"
        )


@app.post("/detect/async/upload", response_model=TaskSubmissionResponse)
async def submit_async_detection_upload(
    file: UploadFile = File(..., description="Image file to analyze"),
    text_queries: str = Form(..., description="Comma-separated text queries for object detection"),
    box_threshold: float = Form(0.4, description="Confidence threshold for bounding boxes"),
    text_threshold: float = Form(0.3, description="Confidence threshold for text matching"),
    return_visualization: bool = Form(True, description="Whether to return visualization image"),
    priority: int = Form(5, description="Task priority (0-9, higher is more priority)")
):
    """
    Submit async detection task for uploaded image file
    
    - **file**: Image file (JPEG, PNG, etc.)
    - **text_queries**: Comma-separated text descriptions of objects to detect
    - **box_threshold**: Confidence threshold for bounding boxes (0.0 to 1.0)
    - **text_threshold**: Confidence threshold for text matching (0.0 to 1.0)
    - **return_visualization**: Whether to return visualization image as base64
    - **priority**: Task priority (0-9, higher is more priority)
    """
    if not ENABLE_QUEUE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue processing is disabled. Use synchronous endpoints instead."
        )
    
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Read image file
        contents = await file.read()
        
        # Parse text queries
        queries_list = [q.strip() for q in text_queries.split(",") if q.strip()]
        if not queries_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one text query is required"
            )
        
        task_id = task_manager.submit_detection_task(
            image_data=contents,
            image_type="bytes",
            text_queries=queries_list,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            return_visualization=return_visualization,
            priority=priority
        )
        
        return TaskSubmissionResponse(
            task_id=task_id,
            status="submitted",
            message="Task submitted for async processing"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit async upload task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}"
        )


@app.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get status and result of a task
    
    - **task_id**: ID of the task to check
    """
    if not ENABLE_QUEUE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue processing is disabled."
        )
    
    try:
        result = task_manager.get_task_result(task_id)
        
        # Convert result to response format
        response_data = {
            "task_id": task_id,
            "status": result["status"],
            "progress": result.get("progress"),
            "stage": result.get("stage"),
            "message": result.get("message"),
            "error": result.get("error")
        }
        
        # Add result if completed successfully
        if result["status"] == "completed" and "result" in result:
            response_data["result"] = DetectionResponse(**result["result"])
        
        return TaskStatusResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


@app.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a task
    
    - **task_id**: ID of the task to cancel
    """
    if not ENABLE_QUEUE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue processing is disabled."
        )
    
    try:
        result = task_manager.cancel_task(task_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )


@app.get("/queue/status", response_model=QueueStatusResponse)
async def get_queue_status():
    """
    Get queue status and statistics
    """
    if not ENABLE_QUEUE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue processing is disabled."
        )
    
    try:
        result = task_manager.get_queue_status()
        
        if result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return QueueStatusResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}"
        )


@app.get("/model/info")
async def get_model_info():
    """Get information about the loaded model"""
    try:
        model_loaded = model_manager.is_model_loaded()
        if model_loaded:
            model = model_manager.get_model()
            return {
                "model_loaded": True,
                "device": model.device,
                "model_id": "IDEA-Research/grounding-dino-tiny"
            }
        else:
            return {
                "model_loaded": False,
                "message": "Model not loaded yet"
            }
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model info: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
