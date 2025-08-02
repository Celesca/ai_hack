# DynamicGroundingDINO FastAPI Service

A FastAPI service for zero-shot object detection using the Grounding DINO model. This service allows users to detect objects in images using natural language text queries.

## Features

- **Zero-shot object detection**: Detect objects using natural language descriptions
- **Multiple input methods**: Support for image URLs and file uploads
- **Bounding box visualization**: Returns annotated images with detected objects
- **Configurable thresholds**: Adjustable confidence thresholds for detection
- **RESTful API**: Easy-to-use HTTP endpoints with comprehensive documentation
- **Object-Oriented Design**: Clean separation between model logic and API server

## Project Structure

```
├── model.py           # DynamicGroundingDINO model class and ModelManager
├── server.py          # FastAPI server implementation
├── requirements.txt   # Python dependencies
├── test_api.py       # API test script
└── README.md         # This file
```

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install additional dependencies** (if needed):
   ```bash
   # For CUDA support (recommended if you have a GPU)
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```

## Usage

### Starting the Server

Run the FastAPI server:

```bash
python server.py
```

The server will start on `http://localhost:8000` by default.

### API Documentation

Once the server is running, you can access:

- **Interactive API Documentation (Swagger UI)**: http://localhost:8000/docs
- **API Documentation (ReDoc)**: http://localhost:8000/redoc
- **Root page with quick info**: http://localhost:8000

### API Endpoints

#### 1. Health Check
- **GET** `/health`
- Check if the API is running and the model is loaded

#### 2. Detect Objects from URL
- **POST** `/detect`
- Detect objects in an image from a URL

**Request Body:**
```json
{
  "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
  "text_queries": ["cat", "remote control", "person"],
  "box_threshold": 0.4,
  "text_threshold": 0.3,
  "return_visualization": true
}
```

#### 3. Detect Objects from Uploaded File
- **POST** `/detect/upload`
- Detect objects in an uploaded image file

**Form Data:**
- `file`: Image file (JPEG, PNG, etc.)
- `text_queries`: Comma-separated text queries (e.g., "cat, dog, person")
- `box_threshold`: Confidence threshold for bounding boxes (0.0-1.0)
- `text_threshold`: Confidence threshold for text matching (0.0-1.0)
- `return_visualization`: Whether to return visualization image (true/false)

#### 4. Model Information
- **GET** `/model/info`
- Get information about the loaded model

### Response Format

The API returns structured JSON responses with the following format:

```json
{
  "success": true,
  "num_detections": 3,
  "detections": [
    {
      "id": 1,
      "label": "cat",
      "confidence": 0.856,
      "bounding_box": {
        "x_min": 13.23,
        "y_min": 17.45,
        "x_max": 314.78,
        "y_max": 472.89,
        "width": 301.55,
        "height": 455.44
      }
    }
  ],
  "image_size": {
    "width": 640,
    "height": 480
  },
  "queries": ["cat", "remote control", "person"],
  "thresholds": {
    "box_threshold": 0.4,
    "text_threshold": 0.3
  },
  "visualization": {
    "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "format": "png"
  }
}
```

## Testing

Run the test script to verify the API is working:

```bash
python test_api.py
```

This will test all endpoints and save visualization results.

## Examples

### Using cURL

**URL Detection:**
```bash
curl -X POST "http://localhost:8000/detect" \
     -H "Content-Type: application/json" \
     -d '{
       "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
       "text_queries": ["cat", "remote", "person"],
       "box_threshold": 0.4,
       "text_threshold": 0.3
     }'
```

**File Upload:**
```bash
curl -X POST "http://localhost:8000/detect/upload" \
     -F "file=@your_image.jpg" \
     -F "text_queries=cat, dog, person" \
     -F "box_threshold=0.4" \
     -F "text_threshold=0.3" \
     -F "return_visualization=true"
```

### Using Python Requests

```python
import requests
import base64

# URL detection
response = requests.post("http://localhost:8000/detect", json={
    "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
    "text_queries": ["cat", "remote control"],
    "box_threshold": 0.4,
    "text_threshold": 0.3,
    "return_visualization": True
})

result = response.json()
print(f"Found {result['num_detections']} objects")

# Save visualization
if result.get('visualization'):
    viz_data = base64.b64decode(result['visualization']['image_base64'])
    with open('result.png', 'wb') as f:
        f.write(viz_data)
```

## Configuration

### Model Configuration

The model can be configured in `model.py`:

- **model_id**: Change the Hugging Face model ID (default: "IDEA-Research/grounding-dino-tiny")
- **device**: Set device preference ("cuda", "cpu", or "auto")

### Server Configuration

The server can be configured in `server.py`:

- **host**: Server host address (default: "0.0.0.0")
- **port**: Server port (default: 8000)
- **CORS settings**: Configure allowed origins for cross-origin requests

## Performance Notes

- **First Request**: The initial request may take longer as the model loads
- **GPU Acceleration**: Using CUDA-enabled GPU significantly improves performance
- **Model Size**: The "tiny" model is faster but less accurate than larger variants
- **Memory Usage**: The model requires approximately 1-2GB of RAM/VRAM

## Troubleshooting

### Common Issues

1. **Model Loading Errors**:
   - Ensure you have sufficient memory (RAM/VRAM)
   - Check internet connection for downloading model weights
   - Verify PyTorch installation

2. **CUDA Issues**:
   - Install correct PyTorch version for your CUDA version
   - Check GPU memory availability

3. **Image Loading Errors**:
   - Verify image URL is accessible
   - Ensure uploaded files are valid images
   - Check file size limits

### Error Responses

The API returns detailed error messages in the response:

```json
{
  "success": false,
  "error": "Error description",
  "num_detections": 0,
  "detections": []
}
```

## Advanced Usage

### Custom Thresholds

Adjust detection sensitivity:

- **box_threshold**: Higher values = fewer, more confident detections
- **text_threshold**: Higher values = stricter text matching

### Batch Processing

For multiple images, make separate API calls or extend the service to support batch processing.

### Integration

The service can be easily integrated into:

- Web applications (using JavaScript fetch/axios)
- Mobile applications (using HTTP clients)
- Other Python services (using requests library)
- Command-line tools

## License

This project uses the Grounding DINO model which has its own licensing terms. Please check the original repository for details.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the service.
