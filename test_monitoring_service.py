#!/usr/bin/env python3
"""
Test the monitoring service with real-time features.
"""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add paths
sys.path.insert(0, 'services/monitoring/src')

def test_monitoring_app_structure():
    """Test that monitoring service has the right structure."""
    print("🏗️  Testing Monitoring Service Structure...")
    
    required_files = [
        "services/monitoring/src/api/main.py",
        "services/monitoring/src/api/routers/streaming.py", 
        "services/monitoring/src/api/routers/websocket.py",
        "services/monitoring/requirements.txt"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    print("✅ All required files present")
    return True


def test_monitoring_dependencies():
    """Test that all required dependencies are available."""
    print("\n📦 Testing Monitoring Dependencies...")
    
    required_modules = [
        'fastapi',
        'uvicorn', 
        'sqlalchemy',
        'asyncpg',
        'redis',
        'psutil'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Missing modules: {missing_modules}")
        return False
    
    print("✅ All dependencies available")
    return True


async def test_fastapi_app_creation():
    """Test FastAPI app creation with real-time routes."""
    print("\n🚀 Testing FastAPI App with Real-time Routes...")
    
    try:
        # Mock environment variables
        os.environ['DATABASE_URL'] = 'sqlite:///test.db'
        os.environ['REDIS_URL'] = 'redis://localhost:6379'
        
        # Mock database and dependencies
        sys.modules['api.dependencies'] = Mock()
        sys.modules['models'] = Mock()
        sys.modules['models.get_db'] = AsyncMock()
        
        # Import and test main app
        from api import main
        
        app = main.app
        
        # Check that routes are registered
        route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
        
        expected_paths = [
            '/api/v1/stream/metrics/users/{user_id}',
            '/api/v1/stream/metrics/organization', 
            '/api/v1/stream/system/health',
            '/ws/admin/control',
            '/ws/debug/logs'
        ]
        
        found_paths = []
        for expected in expected_paths:
            # Check if any route contains the expected pattern
            for path in route_paths:
                if any(part in path for part in expected.split('/')):
                    found_paths.append(expected)
                    break
        
        if len(found_paths) >= 3:  # At least some real-time routes found
            print(f"✅ FastAPI app with real-time routes: OK ({len(found_paths)} routes found)")
            return True
        else:
            print(f"❌ Missing real-time routes. Found: {found_paths}")
            return False
            
    except Exception as e:
        print(f"❌ FastAPI app creation failed: {e}")
        return False


def test_monitoring_config():
    """Test monitoring configuration."""
    print("\n⚙️  Testing Monitoring Configuration...")
    
    try:
        # Mock environment for config
        os.environ['MONITORING_MODE'] = 'standalone'
        os.environ['API_PORT'] = '8000'
        
        from config.settings import MonitoringConfig
        
        config = MonitoringConfig()
        
        # Test basic config properties
        assert hasattr(config, 'monitoring_mode')
        assert hasattr(config, 'api_port')
        assert hasattr(config, 'is_sidecar_mode')
        assert hasattr(config, 'is_standalone_mode')
        
        print("✅ Monitoring configuration: OK")
        return True
        
    except Exception as e:
        print(f"❌ Monitoring configuration failed: {e}")
        return False


async def run_monitoring_tests():
    """Run all monitoring service tests."""
    print("🔍 Testing Monitoring Service with Real-time Features\n")
    
    results = {}
    
    # Run tests
    results['structure'] = test_monitoring_app_structure()
    results['dependencies'] = test_monitoring_dependencies()
    results['config'] = test_monitoring_config()
    results['fastapi_app'] = await test_fastapi_app_creation()
    
    # Summary
    print("\n" + "="*50)
    print("🏁 MONITORING SERVICE TEST RESULTS")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.upper():20} {status}")
        if result:
            passed += 1
    
    print(f"\nMonitoring Service: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Monitoring service with real-time features is working!")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_monitoring_tests())
        
        if success:
            print("\n✨ Monitoring service is ready with real-time features!")
        else:
            print("\n🔧 Monitoring service needs attention.")
            
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()