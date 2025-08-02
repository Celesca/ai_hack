import requests
import json
import base64
from PIL import Image
import io

# API base URL
BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print("-" * 50)

def test_url_detection():
    """Test detection with image URL"""
    print("Testing URL detection...")
    
    payload = {
        "image_url": "http://images.cocodataset.org/val2017/000000039769.jpg",
        "text_queries": ["cat", "remote control", "person"],
        "box_threshold": 0.4,
        "text_threshold": 0.3,
        "return_visualization": True
    }
    
    response = requests.post(f"{BASE_URL}/detect", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Success: {result['success']}")
        print(f"Number of detections: {result['num_detections']}")
        
        for detection in result['detections']:
            print(f"  - {detection['label']}: {detection['confidence']} at {detection['bounding_box']}")
        
        # Save visualization if available
        if result.get('visualization'):
            viz_data = base64.b64decode(result['visualization']['image_base64'])
            with open('detection_result.png', 'wb') as f:
                f.write(viz_data)
            print("Visualization saved as 'detection_result.png'")
    else:
        print(f"Error: {response.text}")
    
    print("-" * 50)

def test_file_upload():
    """Test detection with file upload"""
    print("Testing file upload detection...")
    
    # Create a simple test image or use an existing one
    try:
        # Try to use an existing image file
        with open('test_image.jpg', 'rb') as f:
            files = {'file': ('test_image.jpg', f, 'image/jpeg')}
            data = {
                'text_queries': 'cat, dog, person, car',
                'box_threshold': 0.4,
                'text_threshold': 0.3,
                'return_visualization': True
            }
            
            response = requests.post(f"{BASE_URL}/detect/upload", files=files, data=data)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Success: {result['success']}")
                print(f"Number of detections: {result['num_detections']}")
                
                for detection in result['detections']:
                    print(f"  - {detection['label']}: {detection['confidence']}")
            else:
                print(f"Error: {response.text}")
                
    except FileNotFoundError:
        print("No test image file found. Skipping file upload test.")
        print("To test file upload, place a test image named 'test_image.jpg' in the current directory.")
    
    print("-" * 50)

def test_model_info():
    """Test model info endpoint"""
    print("Testing model info endpoint...")
    response = requests.get(f"{BASE_URL}/model/info")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print("-" * 50)

if __name__ == "__main__":
    print("=" * 50)
    print("DynamicGroundingDINO API Test Script")
    print("=" * 50)
    
    try:
        test_health()
        test_model_info()
        test_url_detection()
        test_file_upload()
        
        print("All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API server.")
        print("Make sure the server is running on http://localhost:8000")
        print("Start the server with: python server.py")
    except Exception as e:
        print(f"Test failed with error: {e}")
