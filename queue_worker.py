from celery import Celery
from celery.result import AsyncResult
import os
import logging
from typing import Dict, Any, Union, List
import json
import base64
from datetime import datetime, timedelta

from model import ModelManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Initialize Celery app
celery_app = Celery(
    "grounding_dino_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["queue_worker"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Only fetch one task at a time
    task_acks_late=True,           # Acknowledge task after completion
    worker_max_tasks_per_child=100, # Restart worker after 100 tasks to prevent memory leaks
    
    # Task routing
    task_routes={
        'queue_worker.detect_objects_task': {'queue': 'detection'},
        'queue_worker.health_check_task': {'queue': 'health'},
    },
    
    # Result expiration
    result_expires=3600,  # Results expire after 1 hour
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=360,       # 6 minutes hard limit
    
    # Error handling
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Global model manager instance
model_manager = ModelManager()


@celery_app.task(bind=True, name="queue_worker.detect_objects_task")
def detect_objects_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task for object detection
    
    Args:
        task_data: Dictionary containing detection parameters
            - image_data: Base64 encoded image or URL
            - image_type: "url", "base64", or "bytes"
            - text_queries: List of text queries
            - box_threshold: Confidence threshold for boxes
            - text_threshold: Confidence threshold for text
            - return_visualization: Whether to return visualization
            - task_id: Unique task identifier
    
    Returns:
        Dictionary with detection results
    """
    try:
        logger.info(f"Starting detection task: {self.request.id}")
        
        # Update task state to PROGRESS
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'Loading model and processing image',
                'progress': 10,
                'stage': 'initialization'
            }
        )
        
        # Get model instance
        model = model_manager.get_model()
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'Model loaded, preparing image',
                'progress': 30,
                'stage': 'model_loaded'
            }
        )
        
        # Prepare image source based on type
        image_source = None
        image_type = task_data.get("image_type", "url")
        
        if image_type == "url":
            image_source = task_data["image_data"]
        elif image_type == "base64":
            # Decode base64 image
            image_bytes = base64.b64decode(task_data["image_data"])
            image_source = image_bytes
        elif image_type == "bytes":
            image_source = task_data["image_data"]
        else:
            raise ValueError(f"Unsupported image type: {image_type}")
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'Running object detection',
                'progress': 50,
                'stage': 'detection'
            }
        )
        
        # Extract parameters
        text_queries = task_data.get("text_queries", [])
        box_threshold = task_data.get("box_threshold", 0.4)
        text_threshold = task_data.get("text_threshold", 0.3)
        return_visualization = task_data.get("return_visualization", True)
        
        # Run detection
        result = model.process_detection(
            image_source=image_source,
            text_queries=text_queries,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            return_visualization=return_visualization
        )
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'Processing complete',
                'progress': 90,
                'stage': 'finalizing'
            }
        )
        
        # Add task metadata
        result["task_info"] = {
            "task_id": self.request.id,
            "started_at": datetime.utcnow().isoformat(),
            "worker_id": self.request.hostname,
            "processing_time": None  # Will be calculated by the API
        }
        
        logger.info(f"Detection task completed: {self.request.id}")
        return result
        
    except Exception as e:
        logger.error(f"Detection task failed: {self.request.id} - {str(e)}")
        
        # Update task state to FAILURE with error details
        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'task_id': self.request.id,
                'stage': 'error'
            }
        )
        
        return {
            "success": False,
            "error": str(e),
            "num_detections": 0,
            "detections": [],
            "task_info": {
                "task_id": self.request.id,
                "failed_at": datetime.utcnow().isoformat(),
                "worker_id": self.request.hostname,
                "error": str(e)
            }
        }


@celery_app.task(name="queue_worker.health_check_task")
def health_check_task() -> Dict[str, Any]:
    """
    Health check task for monitoring worker status
    """
    try:
        # Check if model is loaded
        model_loaded = model_manager.is_model_loaded()
        
        # Get model if not loaded
        if not model_loaded:
            model = model_manager.get_model()
            model_loaded = True
        
        return {
            "status": "healthy",
            "model_loaded": model_loaded,
            "timestamp": datetime.utcnow().isoformat(),
            "worker_ready": True
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "model_loaded": False,
            "timestamp": datetime.utcnow().isoformat(),
            "worker_ready": False,
            "error": str(e)
        }


class TaskManager:
    """
    Manager class for handling Celery tasks
    """
    
    @staticmethod
    def submit_detection_task(
        image_data: Union[str, bytes],
        image_type: str,
        text_queries: Union[str, List[str]],
        box_threshold: float = 0.4,
        text_threshold: float = 0.3,
        return_visualization: bool = True,
        priority: int = 5
    ) -> str:
        """
        Submit detection task to queue
        
        Args:
            image_data: Image data (URL string or bytes)
            image_type: Type of image data ("url", "base64", "bytes")
            text_queries: Text queries for detection
            box_threshold: Box confidence threshold
            text_threshold: Text confidence threshold
            return_visualization: Whether to return visualization
            priority: Task priority (0-9, higher is more priority)
        
        Returns:
            Task ID
        """
        # Prepare task data
        if isinstance(image_data, bytes):
            # Convert bytes to base64 for JSON serialization
            image_data = base64.b64encode(image_data).decode('utf-8')
            if image_type == "bytes":
                image_type = "base64"
        
        task_data = {
            "image_data": image_data,
            "image_type": image_type,
            "text_queries": text_queries if isinstance(text_queries, list) else [text_queries],
            "box_threshold": box_threshold,
            "text_threshold": text_threshold,
            "return_visualization": return_visualization
        }
        
        # Submit task with priority
        task = detect_objects_task.apply_async(
            args=[task_data],
            priority=priority,
            queue='detection'
        )
        
        return task.id
    
    @staticmethod
    def get_task_result(task_id: str) -> Dict[str, Any]:
        """
        Get task result by ID
        
        Args:
            task_id: Task ID
            
        Returns:
            Dictionary with task status and result
        """
        try:
            result = AsyncResult(task_id, app=celery_app)
            
            if result.ready():
                if result.successful():
                    return {
                        "status": "completed",
                        "result": result.result,
                        "task_id": task_id
                    }
                else:
                    return {
                        "status": "failed",
                        "error": str(result.result),
                        "task_id": task_id
                    }
            else:
                # Task is still processing
                state = result.state
                info = result.info or {}
                
                return {
                    "status": state.lower(),
                    "progress": info.get("progress", 0),
                    "stage": info.get("stage", "unknown"),
                    "message": info.get("status", "Processing..."),
                    "task_id": task_id
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "task_id": task_id
            }
    
    @staticmethod
    def cancel_task(task_id: str) -> Dict[str, Any]:
        """
        Cancel a task
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            Cancellation status
        """
        try:
            celery_app.control.revoke(task_id, terminate=True)
            return {
                "status": "cancelled",
                "task_id": task_id,
                "message": "Task cancellation requested"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "task_id": task_id
            }
    
    @staticmethod
    def get_queue_status() -> Dict[str, Any]:
        """
        Get queue status and statistics
        
        Returns:
            Queue status information
        """
        try:
            # Get worker stats
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            scheduled_tasks = inspect.scheduled()
            reserved_tasks = inspect.reserved()
            
            # Calculate totals
            total_active = sum(len(tasks) for tasks in (active_tasks or {}).values())
            total_scheduled = sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
            total_reserved = sum(len(tasks) for tasks in (reserved_tasks or {}).values())
            
            return {
                "status": "healthy",
                "active_tasks": total_active,
                "scheduled_tasks": total_scheduled,
                "reserved_tasks": total_reserved,
                "workers": list((active_tasks or {}).keys()),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def health_check() -> Dict[str, Any]:
        """
        Submit health check task
        
        Returns:
            Health check task ID
        """
        task = health_check_task.apply_async(queue='health')
        return {"task_id": task.id}


# Initialize task manager
task_manager = TaskManager()

if __name__ == "__main__":
    # This allows running the worker directly
    celery_app.start()
