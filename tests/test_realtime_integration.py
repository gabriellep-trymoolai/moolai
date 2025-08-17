"""Integration tests for real-time communication infrastructure."""

import asyncio
import pytest
import json
import websockets
from datetime import datetime
from typing import List, Dict, Any

from fastapi.testclient import TestClient
import httpx

# Import the real-time infrastructure
from mool_ai_repo.common.realtime import (
    SSEManager,
    WebSocketManager,
    EventBus,
    Event,
    EventType,
    MultiTenantChannelManager
)


class TestSSEIntegration:
    """Integration tests for Server-Sent Events."""
    
    @pytest.fixture
    async def sse_manager(self):
        """Create SSE manager for testing."""
        manager = SSEManager(heartbeat_interval=5)
        await manager.start()
        yield manager
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_sse_connection_lifecycle(self, sse_manager):
        """Test SSE connection establishment and cleanup."""
        # Create connection
        connection = await sse_manager.connect(
            organization_id="test-org",
            user_id="test-user",
            channels={"test-channel"}
        )
        
        assert connection.connection_id is not None
        assert connection.organization_id == "test-org"
        assert connection.user_id == "test-user"
        assert "test-channel" in connection.channels
        
        # Test connection is tracked
        stats = sse_manager.get_connection_stats()
        assert stats["total_connections"] == 1
        assert "test-org" in stats["connections_by_org"]
        
        # Disconnect
        await sse_manager.disconnect(connection.connection_id)
        
        # Verify cleanup
        stats = sse_manager.get_connection_stats()
        assert stats["total_connections"] == 0
    
    @pytest.mark.asyncio
    async def test_sse_message_publishing(self, sse_manager):
        """Test SSE message publishing and delivery."""
        messages_received = []
        
        # Create connection
        connection = await sse_manager.connect(
            organization_id="test-org",
            channels={"test-channel"}
        )
        
        # Start message streaming (simulate)
        async def collect_messages():
            async for message in sse_manager.stream(connection.connection_id):
                if "test_event" in message:
                    messages_received.append(message)
                    break
        
        # Start collection task
        collection_task = asyncio.create_task(collect_messages())
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        
        # Publish test message
        await sse_manager.publish(
            "test-channel",
            "test_event",
            {"message": "hello world"},
            id="test-123"
        )
        
        # Wait for message to be received
        await asyncio.wait_for(collection_task, timeout=5.0)
        
        # Verify message was received
        assert len(messages_received) == 1
        assert "test_event" in messages_received[0]
        assert "hello world" in messages_received[0]
    
    @pytest.mark.asyncio
    async def test_sse_organization_isolation(self, sse_manager):
        """Test that organizations are properly isolated."""
        # Create connections for different organizations
        conn1 = await sse_manager.connect(
            organization_id="org-1",
            channels={"shared-channel"}
        )
        
        conn2 = await sse_manager.connect(
            organization_id="org-2",
            channels={"shared-channel"}
        )
        
        # Publish to org-1 channel
        await sse_manager.publish_to_organization(
            "org-1",
            "test_event",
            {"org": "1"}
        )
        
        # Only org-1 connection should be in the channel
        org1_channel = f"org:org-1"
        org2_channel = f"org:org-2"
        
        assert org1_channel in sse_manager.channel_connections
        assert org2_channel in sse_manager.channel_connections
        assert conn1.connection_id in sse_manager.channel_connections[org1_channel]
        assert conn2.connection_id in sse_manager.channel_connections[org2_channel]


class TestWebSocketIntegration:
    """Integration tests for WebSocket communication."""
    
    @pytest.fixture
    async def ws_manager(self):
        """Create WebSocket manager for testing."""
        manager = WebSocketManager(
            max_connections_per_org=10,
            ping_interval=5,
            auth_timeout=5
        )
        await manager.start()
        yield manager
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self, ws_manager):
        """Test WebSocket connection establishment and cleanup."""
        # Mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.messages_sent = []
                self.closed = False
            
            async def accept(self):
                pass
            
            async def send_text(self, data):
                self.messages_sent.append(data)
            
            async def close(self, reason=None):
                self.closed = True
        
        mock_ws = MockWebSocket()
        
        # Create connection
        connection = await ws_manager.connect(
            websocket=mock_ws,
            organization_id="test-org",
            user_id="test-user",
            roles={"user"}
        )
        
        assert connection.connection_id is not None
        assert connection.organization_id == "test-org"
        assert connection.user_id == "test-user"
        assert "user" in connection.roles
        
        # Verify connection message was sent
        assert len(mock_ws.messages_sent) == 1
        message = json.loads(mock_ws.messages_sent[0])
        assert message["type"] == "success"
        assert message["data"]["message"] == "Connected"
        
        # Test connection stats
        stats = ws_manager.get_connection_stats()
        assert stats["total_connections"] == 1
        assert stats["authenticated_connections"] == 0  # Not yet authenticated
        
        # Disconnect
        await ws_manager.disconnect(connection.connection_id)
        
        # Verify cleanup
        assert mock_ws.closed
        stats = ws_manager.get_connection_stats()
        assert stats["total_connections"] == 0
    
    @pytest.mark.asyncio
    async def test_websocket_authentication(self, ws_manager):
        """Test WebSocket authentication flow."""
        class MockWebSocket:
            def __init__(self):
                self.messages_sent = []
            
            async def accept(self):
                pass
            
            async def send_text(self, data):
                self.messages_sent.append(data)
            
            async def close(self, reason=None):
                pass
        
        mock_ws = MockWebSocket()
        
        # Create connection
        connection = await ws_manager.connect(
            websocket=mock_ws,
            organization_id="test-org",
            roles={"admin"}
        )
        
        # Authenticate
        success = await ws_manager.authenticate(connection.connection_id, "valid-token")
        assert success
        assert connection.is_authenticated
        
        # Verify authentication message was sent
        auth_messages = [
            msg for msg in mock_ws.messages_sent 
            if "Authenticated" in msg
        ]
        assert len(auth_messages) >= 1
    
    @pytest.mark.asyncio
    async def test_websocket_message_handling(self, ws_manager):
        """Test WebSocket message handling."""
        class MockWebSocket:
            def __init__(self):
                self.messages_sent = []
            
            async def accept(self):
                pass
            
            async def send_text(self, data):
                self.messages_sent.append(data)
            
            async def close(self, reason=None):
                pass
        
        mock_ws = MockWebSocket()
        
        # Create and authenticate connection
        connection = await ws_manager.connect(
            websocket=mock_ws,
            organization_id="test-org",
            roles={"admin"}
        )
        await ws_manager.authenticate(connection.connection_id, "valid-token")
        
        # Test ping message
        ping_message = json.dumps({
            "type": "ping",
            "data": {"timestamp": datetime.utcnow().isoformat()},
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": "ping-123"
        })
        
        await ws_manager.handle_message(connection.connection_id, ping_message)
        
        # Verify pong response
        pong_messages = [
            json.loads(msg) for msg in mock_ws.messages_sent 
            if json.loads(msg).get("type") == "pong"
        ]
        assert len(pong_messages) >= 1
        assert pong_messages[-1]["correlation_id"] == "ping-123"


class TestEventBusIntegration:
    """Integration tests for Event Bus."""
    
    @pytest.fixture
    async def redis_client(self):
        """Create Redis client for testing."""
        import redis.asyncio as redis
        client = await redis.from_url("redis://localhost:6379/1")  # Use test DB
        yield client
        await client.flushdb()  # Clean up
        await client.close()
    
    @pytest.fixture
    async def event_bus(self, redis_client):
        """Create Event Bus for testing."""
        bus = EventBus(
            redis_client=redis_client,
            service_name="test-service",
            organization_id="test-org"
        )
        await bus.start()
        yield bus
        await bus.stop()
    
    @pytest.mark.asyncio
    async def test_event_publishing_and_listening(self, event_bus):
        """Test event publishing and listening."""
        events_received = []
        
        # Register listener
        async def event_handler(event):
            events_received.append(event)
        
        event_bus.register_listener(EventType.METRICS_USER_UPDATE, event_handler)
        
        # Give listener time to register
        await asyncio.sleep(0.1)
        
        # Publish event
        test_event = Event(
            type=EventType.METRICS_USER_UPDATE,
            organization_id="test-org",
            user_id="test-user",
            data={"metric": "test_value"},
            timestamp=datetime.utcnow(),
            source="test-service"
        )
        
        await event_bus.publish(test_event)
        
        # Wait for event to be received
        await asyncio.sleep(0.5)
        
        # Verify event was received
        assert len(events_received) == 1
        received_event = events_received[0]
        assert received_event.type == EventType.METRICS_USER_UPDATE
        assert received_event.organization_id == "test-org"
        assert received_event.data["metric"] == "test_value"
    
    @pytest.mark.asyncio
    async def test_organization_event_publishing(self, event_bus):
        """Test organization-specific event publishing."""
        events_received = []
        
        # Register listener
        async def event_handler(event):
            events_received.append(event)
        
        event_bus.register_listener(EventType.METRICS_ORG_UPDATE, event_handler)
        
        # Give listener time to register
        await asyncio.sleep(0.1)
        
        # Publish to organization
        await event_bus.publish_to_organization(
            "test-org",
            EventType.METRICS_ORG_UPDATE,
            {"total_users": 100}
        )
        
        # Wait for event
        await asyncio.sleep(0.5)
        
        # Verify event was received
        assert len(events_received) == 1
        received_event = events_received[0]
        assert received_event.organization_id == "test-org"
        assert received_event.data["total_users"] == 100


class TestChannelManagerIntegration:
    """Integration tests for Channel Manager."""
    
    @pytest.fixture
    def channel_manager(self):
        """Create Channel Manager for testing."""
        return MultiTenantChannelManager()
    
    def test_channel_creation_and_access(self, channel_manager):
        """Test channel creation and access control."""
        from mool_ai_repo.common.realtime.channel_manager import ChannelType
        
        # Create organization channel
        channel = channel_manager.create_channel(
            name="metrics",
            channel_type=ChannelType.METRIC,
            organization_id="org-1"
        )
        
        assert channel.full_name == "metric:org-1:metrics"
        
        # Test access for same org user
        can_access = channel_manager.can_access_channel(
            channel.full_name,
            organization_id="org-1",
            user_id="user-1"
        )
        assert can_access
        
        # Test access denied for different org
        cannot_access = channel_manager.can_access_channel(
            channel.full_name,
            organization_id="org-2",
            user_id="user-2"
        )
        assert not cannot_access
    
    def test_user_subscription_management(self, channel_manager):
        """Test user subscription management."""
        from mool_ai_repo.common.realtime.channel_manager import ChannelType
        
        # Create channels
        channel1 = channel_manager.create_channel(
            "general", ChannelType.ORGANIZATION, "org-1"
        )
        channel2 = channel_manager.create_channel(
            "private", ChannelType.USER, "org-1", user_id="user-1"
        )
        
        # Subscribe user to channels
        subscribed, denied = channel_manager.subscribe_user(
            "org-1", "user-1", [channel1.full_name, channel2.full_name]
        )
        
        assert len(subscribed) == 2
        assert len(denied) == 0
        
        # Verify subscriptions
        user_channels = channel_manager.get_user_subscriptions("org-1", "user-1")
        assert channel1.full_name in user_channels
        assert channel2.full_name in user_channels
        
        # Test subscription to unauthorized channel
        admin_channel = channel_manager.create_channel(
            "admin", ChannelType.ADMIN, "org-1", required_roles={"admin"}
        )
        
        subscribed, denied = channel_manager.subscribe_user(
            "org-1", "user-1", [admin_channel.full_name]
        )
        
        assert len(subscribed) == 0
        assert len(denied) == 1
    
    def test_default_channels_creation(self, channel_manager):
        """Test default channels creation for organization."""
        channel_manager.create_default_channels("new-org")
        
        # Verify default channels were created
        stats = channel_manager.get_organization_stats("new-org")
        assert stats["total_channels"] >= 5  # Should have created several default channels
        
        expected_channels = ["general", "metrics", "alerts", "admin", "logs"]
        created_channels = stats["channels"]
        
        for expected in expected_channels:
            # Check if any channel contains the expected name
            found = any(expected in channel for channel in created_channels)
            assert found, f"Expected channel '{expected}' not found in {created_channels}"


@pytest.mark.integration
class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_sse_websocket_coordination(self):
        """Test coordination between SSE and WebSocket."""
        # This would test the full flow:
        # 1. WebSocket sends command
        # 2. Command triggers metric update
        # 3. Metric update is broadcast via SSE
        # 4. Both clients receive appropriate messages
        
        # TODO: Implement with actual FastAPI test client
        # and real WebSocket connections
        pass
    
    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_end_to_end(self):
        """Test complete multi-tenant isolation."""
        # This would test:
        # 1. Multiple organizations with connections
        # 2. Events published to one org don't reach others
        # 3. Admin commands are properly isolated
        # 4. User permissions are enforced
        
        # TODO: Implement with multiple concurrent connections
        pass


# Test configuration
pytest_plugins = ["pytest_asyncio"]


# Utility functions for testing
def create_test_event(event_type: EventType, org_id: str, data: Dict[str, Any]) -> Event:
    """Create a test event."""
    return Event(
        type=event_type,
        organization_id=org_id,
        data=data,
        timestamp=datetime.utcnow(),
        source="test"
    )


async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
    """Wait for a condition to become true."""
    start_time = asyncio.get_event_loop().time()
    while True:
        if condition_func():
            return True
        
        if asyncio.get_event_loop().time() - start_time > timeout:
            return False
        
        await asyncio.sleep(interval)


# Test fixtures for mock services
@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    class MockRedis:
        def __init__(self):
            self.channels = {}
            self.subscribers = {}
        
        async def publish(self, channel, message):
            if channel in self.subscribers:
                for callback in self.subscribers[channel]:
                    await callback(message)
        
        async def subscribe(self, channel):
            if channel not in self.subscribers:
                self.subscribers[channel] = []
        
        def pubsub(self):
            return self
        
        async def listen(self):
            # Mock async iterator
            yield {"type": "message", "channel": "test", "data": "test"}
    
    return MockRedis()


# Performance tests
@pytest.mark.performance
class TestPerformance:
    """Performance tests for real-time infrastructure."""
    
    @pytest.mark.asyncio
    async def test_concurrent_sse_connections(self):
        """Test performance with many concurrent SSE connections."""
        # TODO: Test with 100+ concurrent connections
        pass
    
    @pytest.mark.asyncio
    async def test_high_message_throughput(self):
        """Test performance with high message throughput."""
        # TODO: Test sending 1000+ messages per second
        pass
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """Test memory usage under load."""
        # TODO: Monitor memory usage with sustained load
        pass