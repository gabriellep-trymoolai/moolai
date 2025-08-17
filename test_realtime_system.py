#!/usr/bin/env python3
"""
Test script for the MoolAI real-time communication system.
Tests SSE, WebSocket, and monitoring service integration.
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

# Add paths for imports
sys.path.insert(0, '.')
sys.path.insert(0, 'services/monitoring/src')

# Test real-time components
def test_realtime_components():
    """Test real-time framework components."""
    print("🧪 Testing Real-time Framework Components...")
    
    try:
        from common.realtime import (
            SSEManager, WebSocketManager, EventBus, 
            MultiTenantChannelManager, EventType
        )
        
        # Test SSE Manager
        sse_manager = SSEManager(heartbeat_interval=30)
        print("✅ SSE Manager: OK")
        
        # Test WebSocket Manager  
        ws_manager = WebSocketManager(max_connections_per_org=100)
        print("✅ WebSocket Manager: OK")
        
        # Test Channel Manager
        channel_manager = MultiTenantChannelManager()
        print("✅ Channel Manager: OK")
        
        # Test Event Types
        event_types = [
            EventType.METRICS_USER_UPDATE,
            EventType.SYSTEM_HEALTH,
            EventType.LLM_STREAM_CHUNK
        ]
        print(f"✅ Event Types: {len(event_types)} types available")
        
        return True
        
    except Exception as e:
        print(f"❌ Real-time components failed: {e}")
        return False


def test_channel_isolation():
    """Test multi-tenant channel isolation."""
    print("\n🔐 Testing Multi-tenant Channel Isolation...")
    
    try:
        from common.realtime import MultiTenantChannelManager, ChannelType
        
        manager = MultiTenantChannelManager()
        
        # Create channels for different organizations
        org1_channel = manager.create_channel(
            "metrics", ChannelType.METRIC, "org-001"
        )
        org2_channel = manager.create_channel(
            "metrics", ChannelType.METRIC, "org-002"
        )
        
        # Test access control
        can_access_own = manager.can_access_channel(
            org1_channel.full_name, "org-001", "user-123"
        )
        cannot_access_other = manager.can_access_channel(
            org1_channel.full_name, "org-002", "user-456"
        )
        
        if can_access_own and not cannot_access_other:
            print("✅ Channel isolation: OK")
            return True
        else:
            print("❌ Channel isolation: FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Channel isolation test failed: {e}")
        return False


async def test_sse_manager():
    """Test SSE manager functionality."""
    print("\n📡 Testing SSE Manager...")
    
    try:
        from common.realtime import SSEManager
        
        manager = SSEManager(heartbeat_interval=5)
        await manager.start()
        
        # Create test connection
        connection = await manager.connect(
            organization_id="test-org",
            user_id="test-user",
            channels={"test-channel"}
        )
        
        print(f"✅ SSE Connection created: {connection.connection_id}")
        
        # Test message publishing
        await manager.publish(
            "test-channel",
            "test_event", 
            {"message": "Hello World"},
            id="test-123"
        )
        
        print("✅ SSE Message published")
        
        # Cleanup
        await manager.disconnect(connection.connection_id)
        await manager.stop()
        
        return True
        
    except Exception as e:
        print(f"❌ SSE Manager test failed: {e}")
        return False


async def test_websocket_manager():
    """Test WebSocket manager functionality."""
    print("\n🔌 Testing WebSocket Manager...")
    
    try:
        from common.realtime import WebSocketManager, MessageType
        
        manager = WebSocketManager(max_connections_per_org=10)
        await manager.start()
        
        # Mock WebSocket for testing
        class MockWebSocket:
            def __init__(self):
                self.messages = []
                self.closed = False
            
            async def accept(self):
                pass
            
            async def send_text(self, data):
                self.messages.append(data)
            
            async def close(self, reason=None):
                self.closed = True
        
        mock_ws = MockWebSocket()
        
        # Test connection
        connection = await manager.connect(
            websocket=mock_ws,
            organization_id="test-org",
            roles={"admin"}
        )
        
        print(f"✅ WebSocket Connection created: {connection.connection_id}")
        
        # Test authentication
        auth_success = await manager.authenticate(connection.connection_id, "test-token")
        print(f"✅ WebSocket Authentication: {auth_success}")
        
        # Cleanup
        await manager.disconnect(connection.connection_id)
        await manager.stop()
        
        return True
        
    except Exception as e:
        print(f"❌ WebSocket Manager test failed: {e}")
        return False


def test_client_libraries():
    """Test client library files exist and are valid."""
    print("\n📚 Testing Client Libraries...")
    
    try:
        # Check JavaScript client library
        js_client_path = "client/js/moolai-realtime.js"
        if os.path.exists(js_client_path):
            with open(js_client_path, 'r') as f:
                content = f.read()
                if "MoolAISSEClient" in content and "MoolAIWebSocketClient" in content:
                    print("✅ JavaScript client library: OK")
                else:
                    print("❌ JavaScript client library: Missing classes")
                    return False
        else:
            print("❌ JavaScript client library: File not found")
            return False
        
        # Check React hooks
        react_hooks_path = "client/js/moolai-realtime-react.js"
        if os.path.exists(react_hooks_path):
            with open(react_hooks_path, 'r') as f:
                content = f.read()
                if "useMoolAISSE" in content and "useMoolAIWebSocket" in content:
                    print("✅ React hooks library: OK")
                else:
                    print("❌ React hooks library: Missing hooks")
                    return False
        else:
            print("❌ React hooks library: File not found")
            return False
        
        # Check usage examples
        examples_path = "client/js/usage-examples.html"
        if os.path.exists(examples_path):
            print("✅ Usage examples: OK")
        else:
            print("❌ Usage examples: File not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Client libraries test failed: {e}")
        return False


def test_documentation():
    """Test documentation exists and is comprehensive."""
    print("\n📖 Testing Documentation...")
    
    try:
        # Check main documentation
        docs_path = "docs/REALTIME_COMMUNICATION.md"
        if os.path.exists(docs_path):
            with open(docs_path, 'r') as f:
                content = f.read()
                required_sections = [
                    "Server-Sent Events (SSE)",
                    "WebSocket Communication", 
                    "Multi-Tenant Isolation",
                    "Client Libraries",
                    "Configuration"
                ]
                
                missing_sections = []
                for section in required_sections:
                    if section not in content:
                        missing_sections.append(section)
                
                if not missing_sections:
                    print("✅ Real-time documentation: OK")
                else:
                    print(f"❌ Documentation missing sections: {missing_sections}")
                    return False
        else:
            print("❌ Real-time documentation: File not found")
            return False
        
        # Check client README
        client_readme_path = "client/README.md"
        if os.path.exists(client_readme_path):
            print("✅ Client library documentation: OK")
        else:
            print("❌ Client library documentation: File not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Documentation test failed: {e}")
        return False


async def run_all_tests():
    """Run comprehensive test suite."""
    print("🚀 Starting MoolAI Real-time System Tests\n")
    
    results = {}
    
    # Test components
    results['components'] = test_realtime_components()
    results['isolation'] = test_channel_isolation()
    results['sse'] = await test_sse_manager()
    results['websocket'] = await test_websocket_manager()
    results['client_libs'] = test_client_libraries()
    results['documentation'] = test_documentation()
    
    # Summary
    print("\n" + "="*50)
    print("🏁 TEST RESULTS SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.upper():20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Real-time system is working correctly.")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the issues above.")
        return False


if __name__ == "__main__":
    try:
        # Run async tests
        success = asyncio.run(run_all_tests())
        
        if success:
            print("\n✨ MoolAI Real-time System is ready for production!")
        else:
            print("\n🔧 Some components need attention before deployment.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)