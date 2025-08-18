#!/usr/bin/env python3
"""Test script to verify system monitoring data collection."""

import asyncio
import uuid
import requests
import time
from datetime import datetime

# Test configuration (monitoring embedded in orchestrator)
MONITORING_BASE_URL = "http://localhost:8000"
TEST_ORG_ID = "550e8400-e29b-41d4-a716-446655440000"  # Example UUID

def test_api_endpoint(url, method="GET", description=""):
    """Test an API endpoint and return response."""
    try:
        print(f"\n🧪 Testing: {description}")
        print(f"   URL: {method} {url}")
        
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, timeout=10)
        else:
            print(f"   ❌ Unsupported method: {method}")
            return None
            
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✅ Success")
                return data
            except:
                print(f"   ✅ Success (non-JSON response)")
                return response.text
        else:
            print(f"   ❌ Failed: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection failed - is the monitoring service running?")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def main():
    """Main test function."""
    print("=" * 80)
    print("🔍 MOOLAI SYSTEM MONITORING TEST")
    print("=" * 80)
    print(f"Testing monitoring service at: {MONITORING_BASE_URL}")
    print(f"Using test organization ID: {TEST_ORG_ID}")
    
    # Test 1: Health check
    health_data = test_api_endpoint(
        f"{MONITORING_BASE_URL}/health",
        description="Service health check"
    )
    
    if not health_data:
        print("\n❌ Service health check failed - cannot continue tests")
        return
    
    # Test 2: System metrics health
    system_health = test_api_endpoint(
        f"{MONITORING_BASE_URL}/api/v1/system/health",
        description="System metrics service health"
    )
    
    # Test 3: Background collection status
    background_status = test_api_endpoint(
        f"{MONITORING_BASE_URL}/api/v1/system/status/background",
        description="Background collection status"
    )
    
    # Test 4: Force immediate collection
    print(f"\n🚀 Triggering immediate system metrics collection...")
    collection_data = test_api_endpoint(
        f"{MONITORING_BASE_URL}/api/v1/system/collect/immediate?organization_id={TEST_ORG_ID}",
        method="POST",
        description="Force immediate metrics collection"
    )
    
    if collection_data:
        print(f"   📊 Metrics collected:")
        print(f"   - CPU Usage: {collection_data.get('cpu_usage_percent', 'N/A')}%")
        print(f"   - Memory Usage: {collection_data.get('memory_percent', 'N/A')}%")
        print(f"   - Storage Usage: {collection_data.get('storage_percent', 'N/A')}%")
        print(f"   - Collection Time: {collection_data.get('collection_duration_ms', 'N/A')}ms")
    
    # Test 5: Wait a moment then check collection status
    print(f"\n⏳ Waiting 3 seconds...")
    time.sleep(3)
    
    collection_status = test_api_endpoint(
        f"{MONITORING_BASE_URL}/api/v1/system/status/collection?organization_id={TEST_ORG_ID}",
        description="Collection status check"
    )
    
    if collection_status:
        print(f"   📈 Collection Status:")
        print(f"   - Active: {collection_status.get('collection_active', 'Unknown')}")
        print(f"   - Total Records: {collection_status.get('total_metrics_records', 'Unknown')}")
        print(f"   - Last Collection: {collection_status.get('last_collection_timestamp', 'Unknown')}")
        print(f"   - Seconds Since Last: {collection_status.get('seconds_since_last_collection', 'Unknown')}")
    
    # Test 6: Get organization metrics
    metrics_data = test_api_endpoint(
        f"{MONITORING_BASE_URL}/api/v1/system/metrics/organization/{TEST_ORG_ID}",
        description="Get organization metrics"
    )
    
    if metrics_data and isinstance(metrics_data, list) and len(metrics_data) > 0:
        print(f"   📊 Found {len(metrics_data)} metrics records")
        latest = metrics_data[0]
        print(f"   - Latest CPU: {latest.get('cpu_usage_percent', 'N/A')}%")
        print(f"   - Latest Memory: {latest.get('memory_percent', 'N/A')}%")
        print(f"   - Latest Storage: {latest.get('storage_percent', 'N/A')}%")
    
    # Test 7: CPU utilization summary
    cpu_summary = test_api_endpoint(
        f"{MONITORING_BASE_URL}/api/v1/system/metrics/summary/cpu?organization_id={TEST_ORG_ID}&hours_back=1",
        description="CPU utilization summary"
    )
    
    if cpu_summary:
        print(f"   🖥️  CPU Summary (last hour):")
        print(f"   - Average: {cpu_summary.get('avg_cpu_percent', 'N/A')}%")
        print(f"   - Maximum: {cpu_summary.get('max_cpu_percent', 'N/A')}%")
        print(f"   - Samples: {cpu_summary.get('sample_count', 'N/A')}")
    
    # Test 8: Memory utilization summary  
    memory_summary = test_api_endpoint(
        f"{MONITORING_BASE_URL}/api/v1/system/metrics/summary/memory?organization_id={TEST_ORG_ID}&hours_back=1",
        description="Memory utilization summary"
    )
    
    if memory_summary:
        print(f"   💾 Memory Summary (last hour):")
        print(f"   - Average: {memory_summary.get('avg_memory_percent', 'N/A')}%")
        print(f"   - Maximum: {memory_summary.get('max_memory_percent', 'N/A')}%")
        print(f"   - Samples: {memory_summary.get('sample_count', 'N/A')}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 TEST SUMMARY")
    print("=" * 80)
    
    tests_passed = 0
    total_tests = 8
    
    if health_data: tests_passed += 1
    if system_health: tests_passed += 1
    if background_status: tests_passed += 1
    if collection_data: tests_passed += 1
    if collection_status: tests_passed += 1
    if metrics_data: tests_passed += 1
    if cpu_summary: tests_passed += 1
    if memory_summary: tests_passed += 1
    
    print(f"✅ Tests Passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! System monitoring is working correctly.")
        print("\n💡 Next steps:")
        print("   - Monitor service logs for background collection activity")
        print("   - Check database tables are being populated")
        print("   - Verify real-time data flows via SSE endpoints")
    elif tests_passed >= 6:
        print("⚠️  Most tests passed - system is largely functional")
        print("   - Check service logs for any errors")
        print("   - Verify database connectivity")
    else:
        print("❌ Multiple tests failed - check service configuration")
        print("   - Ensure orchestrator service with embedded monitoring is running on port 8000")
        print("   - Check database connectivity")
        print("   - Review service startup logs")
    
    print(f"\n📅 Test completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()