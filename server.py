from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Union
import uvicorn
import io
import base64
from PIL import Image
import logging

from model import ModelManager, DynamicGroundingDINO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DynamicGroundingDINO API",
    description="Zero-shot object detection API using Grounding DINO model",
    version="1.0.0",
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
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DynamicGroundingDINO API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .endpoint { margin: 20px 0; padding: 15px; border-left: 4px solid #007acc; background: #f5f5f5; }
            .method { font-weight: bold; color: #007acc; }
            pre { background: #f0f0f0; padding: 10px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>🔍 DynamicGroundingDINO API</h1>
        <p>Zero-shot object detection API using Grounding DINO model</p>
        
        <div class="endpoint">
            <span class="method">GET</span> <strong>/health</strong> - Check API health and model status
        </div>
        
        <div class="endpoint">
            <span class="method">POST</span> <strong>/detect</strong> - Detect objects from image URL
        </div>
        
        <div class="endpoint">
            <span class="method">POST</span> <strong>/detect/upload</strong> - Detect objects from uploaded image
        </div>
        
        <h3>📚 Documentation</h3>
        <ul>
            <li><a href="/docs">Interactive API Documentation (Swagger UI)</a></li>
            <li><a href="/redoc">API Documentation (ReDoc)</a></li>
        </ul>
        
        <h3>🚀 Quick Start Example</h3>
        <pre>
curl -X POST "http://localhost:8000/detect" \\
     -H "Content-Type: application/json" \\
     -d '{
       "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
       "text_queries": ["cat", "remote", "person"],
       "box_threshold": 0.4,
       "text_threshold": 0.3
     }'
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


@app.post("/detect", response_model=DetectionResponse)
async def detect_objects_from_url(request: DetectionRequest):
    """
    Detect objects in image from URL
    
    - **image_url**: URL of the image to analyze
    - **text_queries**: Text descriptions of objects to detect (string or list of strings)
    - **box_threshold**: Confidence threshold for bounding boxes (0.0 to 1.0)
    - **text_threshold**: Confidence threshold for text matching (0.0 to 1.0)
    - **return_visualization**: Whether to return visualization image as base64
    """
    try:
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


@app.post("/detect/upload", response_model=DetectionResponse)
async def detect_objects_from_upload(
    file: UploadFile = File(..., description="Image file to analyze"),
    text_queries: str = Form(..., description="Comma-separated text queries for object detection"),
    box_threshold: float = Form(0.4, description="Confidence threshold for bounding boxes"),
    text_threshold: float = Form(0.3, description="Confidence threshold for text matching"),
    return_visualization: bool = Form(True, description="Whether to return visualization image")
):
    """
    Detect objects in uploaded image file
    
    - **file**: Image file (JPEG, PNG, etc.)
    - **text_queries**: Comma-separated text descriptions of objects to detect
    - **box_threshold**: Confidence threshold for bounding boxes (0.0 to 1.0)
    - **text_threshold**: Confidence threshold for text matching (0.0 to 1.0)
    - **return_visualization**: Whether to return visualization image as base64
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
