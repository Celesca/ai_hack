import requests
import torch
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from PIL import Image
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
import os
from urllib.parse import urlparse
import io
import base64
from typing import List, Dict, Any, Union, Tuple, Optional


class DynamicGroundingDINO:
    """
    Grounding DINO model for zero-shot object detection with text queries.
    """

    def __init__(self, model_id: str = "./models", device: str = "auto"):
        """
        Initialize the Grounding DINO model

        Args:
            model_id: Model identifier from HuggingFace
            device: Device to run on ("cuda", "cpu", or "auto")
        """
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        print(f"Loading model on {self.device}...")
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to(self.device)
        print("Model loaded successfully!")

    def load_image(self, image_source: Union[str, Image.Image]) -> Image.Image:
        """
        Load image from various sources

        Args:
            image_source: Can be URL, local file path, or PIL Image

        Returns:
            PIL Image in RGB format
        """
        if isinstance(image_source, str):
            if self._is_url(image_source):
                # Load from URL
                try:
                    response = requests.get(image_source, stream=True)
                    response.raise_for_status()
                    image = Image.open(response.raw)
                    print(f"Loaded image from URL: {image_source}")
                except Exception as e:
                    raise ValueError(f"Failed to load image from URL: {e}")
            else:
                # Load from local file
                if os.path.exists(image_source):
                    image = Image.open(image_source)
                    print(f"Loaded local image: {image_source}")
                else:
                    raise FileNotFoundError(f"Image file not found: {image_source}")
        elif isinstance(image_source, Image.Image):
            image = image_source
            print("Using provided PIL Image")
        else:
            raise ValueError("image_source must be URL, file path, or PIL Image")

        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')

        return image

    def load_image_from_bytes(self, image_bytes: bytes) -> Image.Image:
        """
        Load image from bytes data

        Args:
            image_bytes: Image data in bytes format

        Returns:
            PIL Image in RGB format
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            return image
        except Exception as e:
            raise ValueError(f"Failed to load image from bytes: {e}")

    def _is_url(self, string: str) -> bool:
        """Check if string is a valid URL"""
        try:
            result = urlparse(string)
            return all([result.scheme, result.netloc])
        except:
            return False

    def detect_objects(self, image_source: Union[str, Image.Image, bytes], 
                      text_queries: Union[str, List[str]], 
                      box_threshold: float = 0.4, 
                      text_threshold: float = 0.3) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Detect objects in image based on text queries

        Args:
            image_source: Image source (URL, file path, PIL Image, or bytes)
            text_queries: List of text descriptions to search for
            box_threshold: Confidence threshold for bounding boxes
            text_threshold: Confidence threshold for text matching

        Returns:
            Tuple of (PIL Image, detection results)
        """
        # Load image
        if isinstance(image_source, bytes):
            image = self.load_image_from_bytes(image_source)
        else:
            image = self.load_image(image_source)

        # Prepare text queries
        if isinstance(text_queries, str):
            text_queries = [text_queries]
        text_labels = [text_queries]

        print(f"Searching for: {', '.join(text_queries)}")
        print(f"Thresholds - Box: {box_threshold}, Text: {text_threshold}")

        # Process inputs
        inputs = self.processor(images=image, text=text_labels, return_tensors="pt").to(self.device)

        # Run inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Post-process results
        results = self.processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            target_sizes=[image.size[::-1]]
        )

        return image, results[0]

    def generate_colors(self, labels: List[str]) -> Dict[str, np.ndarray]:
        """Generate distinct colors for different labels"""
        unique_labels = list(set(labels))
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_labels)))
        color_map = {label: colors[i] for i, label in enumerate(unique_labels)}
        return color_map

    def create_visualization(self, image: Image.Image, results: Dict[str, Any], 
                           figsize: Tuple[int, int] = (12, 8),
                           show_confidence: bool = True, 
                           font_size: int = 12) -> Image.Image:
        """
        Create visualization with bounding boxes and return as PIL Image

        Args:
            image: PIL Image
            results: Detection results from the model
            figsize: Figure size for matplotlib
            show_confidence: Whether to show confidence scores
            font_size: Font size for labels

        Returns:
            PIL Image with visualized detection results
        """
        fig, ax = plt.subplots(1, 1, figsize=figsize)
        ax.imshow(image)

        boxes = results["boxes"]
        scores = results["scores"]
        labels = results["labels"]

        if len(boxes) == 0:
            ax.set_title('No Objects Detected', fontsize=16, fontweight='bold')
            ax.axis('off')
            plt.tight_layout()
        else:
            # Generate colors for labels
            color_map = self.generate_colors(labels)

            # Draw bounding boxes
            for i, (box, score, label) in enumerate(zip(boxes, scores, labels)):
                box = box.tolist()
                x_min, y_min, x_max, y_max = box
                confidence = round(score.item(), 3)

                # Calculate dimensions
                width = x_max - x_min
                height = y_max - y_min

                # Get color
                color = color_map[label]

                # Create rectangle
                rect = patches.Rectangle(
                    (x_min, y_min), width, height,
                    linewidth=3, edgecolor=color, facecolor='none'
                )
                ax.add_patch(rect)

                # Add label
                if show_confidence:
                    text = f'{label}: {confidence}'
                else:
                    text = label

                ax.text(
                    x_min, y_min - 10,
                    text,
                    color='white',
                    fontsize=font_size,
                    fontweight='bold',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8)
                )

            ax.set_xlim(0, image.size[0])
            ax.set_ylim(image.size[1], 0)
            ax.axis('off')
            ax.set_title(f'Detected Objects: {", ".join(set(labels))}',
                        fontsize=16, fontweight='bold')

            # Add legend
            legend_elements = [patches.Patch(color=color, label=label)
                              for label, color in color_map.items()]
            ax.legend(handles=legend_elements, loc='upper right', fontsize=10)

        plt.tight_layout()

        # Convert matplotlib figure to PIL Image
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        result_image = Image.open(buf)
        plt.close(fig)

        return result_image

    def process_detection(self, image_source: Union[str, Image.Image, bytes], 
                         text_queries: Union[str, List[str]], 
                         box_threshold: float = 0.4,
                         text_threshold: float = 0.3,
                         return_visualization: bool = True) -> Dict[str, Any]:
        """
        Complete detection pipeline with structured output for API

        Args:
            image_source: Image source (URL, file path, PIL Image, or bytes)
            text_queries: Text descriptions to search for
            box_threshold: Confidence threshold for bounding boxes
            text_threshold: Confidence threshold for text matching
            return_visualization: Whether to return visualization image

        Returns:
            Dictionary containing detection results and optional visualization
        """
        try:
            # Run detection
            image, results = self.detect_objects(
                image_source, text_queries, box_threshold, text_threshold
            )

            boxes = results["boxes"]
            scores = results["scores"]
            labels = results["labels"]

            # Format detection results
            detections = []
            for i, (box, score, label) in enumerate(zip(boxes, scores, labels)):
                box = box.tolist()
                x_min, y_min, x_max, y_max = box
                confidence = round(score.item(), 3)

                detections.append({
                    "id": i + 1,
                    "label": label,
                    "confidence": confidence,
                    "bounding_box": {
                        "x_min": round(x_min, 2),
                        "y_min": round(y_min, 2),
                        "x_max": round(x_max, 2),
                        "y_max": round(y_max, 2),
                        "width": round(x_max - x_min, 2),
                        "height": round(y_max - y_min, 2)
                    }
                })

            response_data = {
                "success": True,
                "num_detections": len(detections),
                "detections": detections,
                "image_size": {
                    "width": image.size[0],
                    "height": image.size[1]
                },
                "queries": text_queries if isinstance(text_queries, list) else [text_queries],
                "thresholds": {
                    "box_threshold": box_threshold,
                    "text_threshold": text_threshold
                }
            }

            # Add visualization if requested
            if return_visualization:
                viz_image = self.create_visualization(image, results)
                
                # Convert to base64 for API response
                buf = io.BytesIO()
                viz_image.save(buf, format='PNG')
                buf.seek(0)
                viz_base64 = base64.b64encode(buf.read()).decode('utf-8')
                
                response_data["visualization"] = {
                    "image_base64": viz_base64,
                    "format": "png"
                }

            return response_data

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "num_detections": 0,
                "detections": []
            }


class ModelManager:
    """
    Singleton class to manage the model instance
    """
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    def get_model(self, model_id: str = "./models", device: str = "auto") -> DynamicGroundingDINO:
        """Get or create model instance"""
        if self._model is None:
            self._model = DynamicGroundingDINO(model_id=model_id, device=device)
        return self._model

    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._model is not None
