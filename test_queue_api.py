#!/usr/bin/env python3
"""
Test script for DynamicGroundingDINO API Queue System
"""

import requests
import time
import json
import sys
from typing import Dict, Any
import argparse

class QueueAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def test_health(self) -> bool:
        """Test API health endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                print("✅ Health check passed")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def test_queue_status(self) -> bool:
        """Test queue status endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/queue/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print("✅ Queue status retrieved:")
                print(f"   Active tasks: {data.get('active_tasks', 0)}")
                print(f"   Pending tasks: {data.get('pending_tasks', 0)}")
                print(f"   Workers online: {data.get('workers', {}).get('online', 0)}")
                return True
            else:
                print(f"❌ Queue status failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Queue status error: {e}")
            return False
            
    def submit_async_task(self, image_url: str, text_queries: list, priority: int = 5) -> str:
        """Submit an async detection task"""
        payload = {
            "image_url": image_url,
            "text_queries": text_queries,
            "priority": priority,
            "confidence_threshold": 0.3,
            "box_threshold": 0.25
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/detect/async",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get("task_id")
                print(f"✅ Task submitted successfully: {task_id}")
                print(f"   Status: {data.get('status')}")
                print(f"   Queue position: {data.get('queue_position', 'unknown')}")
                return task_id
            else:
                print(f"❌ Task submission failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Task submission error: {e}")
            return None
    
    def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """Check task status"""
        try:
            response = self.session.get(f"{self.base_url}/task/{task_id}", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Task status check failed: {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Task status error: {e}")
            return {}
    
    def wait_for_task_completion(self, task_id: str, max_wait: int = 120) -> bool:
        """Wait for task to complete"""
        print(f"⏳ Waiting for task {task_id} to complete...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status_data = self.check_task_status(task_id)
            if not status_data:
                time.sleep(2)
                continue
                
            status = status_data.get("status", "unknown")
            progress = status_data.get("progress", 0)
            
            print(f"   Status: {status}, Progress: {progress}%")
            
            if status == "success":
                result = status_data.get("result", {})
                print("✅ Task completed successfully!")
                print(f"   Objects detected: {result.get('object_count', 0)}")
                print(f"   Processing time: {result.get('processing_time', 0):.2f}s")
                return True
            elif status == "failure":
                print(f"❌ Task failed: {status_data.get('error', 'Unknown error')}")
                return False
            elif status in ["pending", "started", "progress"]:
                time.sleep(3)
                continue
            else:
                print(f"❓ Unknown status: {status}")
                time.sleep(2)
        
        print(f"⏰ Task timeout after {max_wait} seconds")
        return False
    
    def test_sync_detection(self, image_url: str, text_queries: list) -> bool:
        """Test synchronous detection"""
        payload = {
            "image_url": image_url,
            "text_queries": text_queries,
            "async_processing": False,
            "confidence_threshold": 0.3,
            "box_threshold": 0.25
        }
        
        try:
            print("🔄 Testing synchronous detection...")
            response = self.session.post(
                f"{self.base_url}/detect",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print("✅ Sync detection successful!")
                    print(f"   Objects detected: {data.get('object_count', 0)}")
                    print(f"   Processing time: {data.get('processing_time', 0):.2f}s")
                    return True
                else:
                    print(f"❌ Sync detection failed: {data.get('error', 'Unknown error')}")
                    return False
            else:
                print(f"❌ Sync detection failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Sync detection error: {e}")
            return False
    
    def run_comprehensive_test(self) -> bool:
        """Run comprehensive API test suite"""
        print("🚀 Starting comprehensive queue system test...\n")
        
        # Test images
        test_images = [
            {
                "url": "http://images.cocodataset.org/val2017/000000039769.jpg",
                "queries": ["cat", "couch"],
                "description": "COCO cats on couch"
            },
            {
                "url": "http://images.cocodataset.org/val2017/000000397133.jpg", 
                "queries": ["person", "dog"],
                "description": "COCO person with dog"
            }
        ]
        
        all_passed = True
        
        # 1. Health check
        print("1️⃣ Testing health endpoint...")
        if not self.test_health():
            all_passed = False
        print()
        
        # 2. Queue status
        print("2️⃣ Testing queue status...")
        if not self.test_queue_status():
            all_passed = False
        print()
        
        # 3. Sync detection test
        print("3️⃣ Testing synchronous detection...")
        if not self.test_sync_detection(test_images[0]["url"], test_images[0]["queries"]):
            print("⚠️ Sync detection failed, but async might still work")
        print()
        
        # 4. Async detection tests
        print("4️⃣ Testing asynchronous detection...")
        task_ids = []
        
        for i, test_case in enumerate(test_images, 1):
            print(f"   Test {i}: {test_case['description']}")
            task_id = self.submit_async_task(
                test_case["url"], 
                test_case["queries"], 
                priority=5 + i
            )
            if task_id:
                task_ids.append(task_id)
            else:
                all_passed = False
            print()
        
        # 5. Wait for async tasks
        if task_ids:
            print("5️⃣ Waiting for async tasks to complete...")
            for task_id in task_ids:
                if not self.wait_for_task_completion(task_id):
                    all_passed = False
                print()
        
        # 6. Final queue status
        print("6️⃣ Final queue status check...")
        self.test_queue_status()
        
        print("\n" + "="*50)
        if all_passed:
            print("🎉 All tests passed! Queue system is working correctly.")
        else:
            print("⚠️ Some tests failed. Check the logs above for details.")
        print("="*50)
        
        return all_passed

def main():
    parser = argparse.ArgumentParser(description="Test DynamicGroundingDINO API Queue System")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--quick", action="store_true", help="Run quick health check only")
    parser.add_argument("--async-only", action="store_true", help="Test async endpoints only")
    
    args = parser.parse_args()
    
    tester = QueueAPITester(args.url)
    
    if args.quick:
        print("🏃 Running quick health check...")
        health_ok = tester.test_health()
        queue_ok = tester.test_queue_status()
        
        if health_ok and queue_ok:
            print("✅ Quick check passed!")
            sys.exit(0)
        else:
            print("❌ Quick check failed!")
            sys.exit(1)
    
    elif args.async_only:
        print("🔄 Testing async endpoints only...")
        
        # Test async submission
        task_id = tester.submit_async_task(
            "http://images.cocodataset.org/val2017/000000039769.jpg",
            ["cat", "couch"],
            priority=7
        )
        
        if task_id:
            success = tester.wait_for_task_completion(task_id)
            sys.exit(0 if success else 1)
        else:
            sys.exit(1)
    
    else:
        # Run comprehensive test
        success = tester.run_comprehensive_test()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
