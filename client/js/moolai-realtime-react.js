/**
 * MoolAI Real-time React Hooks
 * React hooks for SSE and WebSocket communication with MoolAI monitoring system
 */

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Hook for Server-Sent Events connection
 * @param {string} endpoint - SSE endpoint path
 * @param {Object} params - Query parameters
 * @param {Object} options - Connection options
 */
export function useMoolAISSE(endpoint, params = {}, options = {}) {
	const [connectionState, setConnectionState] = useState('disconnected');
	const [connectionId, setConnectionId] = useState(null);
	const [lastMessage, setLastMessage] = useState(null);
	const [error, setError] = useState(null);
	
	const eventSourceRef = useRef(null);
	const listenersRef = useRef(new Map());
	const reconnectAttemptsRef = useRef(0);
	const lastHeartbeatRef = useRef(Date.now());
	
	const defaultOptions = {
		baseUrl: '',
		reconnectInterval: 5000,
		maxReconnectAttempts: 10,
		heartbeatTimeout: 60000,
		autoConnect: true,
		...options
	};

	// Build URL with query parameters
	const buildUrl = useCallback(() => {
		const baseUrl = defaultOptions.baseUrl || window.location.origin;
		const url = new URL(baseUrl + endpoint);
		Object.keys(params).forEach(key => {
			if (params[key] !== undefined && params[key] !== null) {
				url.searchParams.append(key, params[key]);
			}
		});
		return url.toString();
	}, [endpoint, params, defaultOptions.baseUrl]);

	// Connect to SSE endpoint
	const connect = useCallback(() => {
		if (eventSourceRef.current) {
			disconnect();
		}

		const url = buildUrl();
		console.log(`[SSE Hook] Connecting to ${url}`);
		setConnectionState('connecting');
		setError(null);
		
		const eventSource = new EventSource(url);
		eventSourceRef.current = eventSource;
		
		// Connection opened
		eventSource.onopen = () => {
			console.log('[SSE Hook] Connection established');
			setConnectionState('connected');
			reconnectAttemptsRef.current = 0;
		};

		// Error handler
		eventSource.onerror = (error) => {
			console.error('[SSE Hook] Connection error:', error);
			setConnectionState('error');
			setError('Connection error occurred');
			
			if (eventSource.readyState === EventSource.CLOSED) {
				handleDisconnection();
			}
		};

		// Default message handler
		eventSource.onmessage = (event) => {
			handleMessage('message', event.data);
		};

		// Setup specific event handlers
		setupEventHandlers(eventSource);
	}, [buildUrl]);

	// Setup event handlers
	const setupEventHandlers = (eventSource) => {
		// Connected event
		eventSource.addEventListener('connected', (event) => {
			const data = JSON.parse(event.data);
			setConnectionId(data.connection_id);
			console.log(`[SSE Hook] Connected with ID: ${data.connection_id}`);
			handleMessage('connected', data);
		});

		// Heartbeat event
		eventSource.addEventListener('heartbeat', (event) => {
			lastHeartbeatRef.current = Date.now();
			handleMessage('heartbeat', JSON.parse(event.data));
		});

		// Metrics events
		['user_metrics', 'org_metrics', 'metrics_snapshot', 'health_update', 
		 'health_status', 'llm_chunk'].forEach(eventType => {
			eventSource.addEventListener(eventType, (event) => {
				handleMessage(eventType, JSON.parse(event.data));
			});
		});

		// Disconnecting event
		eventSource.addEventListener('disconnecting', (event) => {
			console.log('[SSE Hook] Server is disconnecting');
			handleMessage('disconnecting', JSON.parse(event.data));
		});
	};

	// Handle incoming message
	const handleMessage = (type, data) => {
		const parsedData = typeof data === 'string' ? JSON.parse(data) : data;
		setLastMessage({ type, data: parsedData, timestamp: Date.now() });
		
		// Call registered listeners
		if (listenersRef.current.has(type)) {
			listenersRef.current.get(type).forEach(callback => {
				try {
					callback(parsedData);
				} catch (error) {
					console.error(`[SSE Hook] Error in listener for ${type}:`, error);
				}
			});
		}
	};

	// Register event listener
	const addEventListener = useCallback((event, callback) => {
		if (!listenersRef.current.has(event)) {
			listenersRef.current.set(event, new Set());
		}
		listenersRef.current.get(event).add(callback);
		
		// Return cleanup function
		return () => {
			if (listenersRef.current.has(event)) {
				listenersRef.current.get(event).delete(callback);
			}
		};
	}, []);

	// Handle disconnection
	const handleDisconnection = () => {
		setConnectionState('disconnected');
		
		if (reconnectAttemptsRef.current < defaultOptions.maxReconnectAttempts) {
			reconnect();
		} else {
			console.error('[SSE Hook] Max reconnection attempts reached');
			setError('Max reconnection attempts reached');
		}
	};

	// Reconnect to SSE endpoint
	const reconnect = () => {
		reconnectAttemptsRef.current++;
		console.log(`[SSE Hook] Reconnecting... (attempt ${reconnectAttemptsRef.current})`);
		setConnectionState('reconnecting');
		
		setTimeout(() => {
			connect();
		}, defaultOptions.reconnectInterval);
	};

	// Disconnect from SSE endpoint
	const disconnect = useCallback(() => {
		if (eventSourceRef.current) {
			eventSourceRef.current.close();
			eventSourceRef.current = null;
		}
		setConnectionState('disconnected');
		setConnectionId(null);
		console.log('[SSE Hook] Disconnected');
	}, []);

	// Auto-connect on mount if enabled
	useEffect(() => {
		if (defaultOptions.autoConnect) {
			connect();
		}
		
		// Cleanup on unmount
		return () => {
			disconnect();
		};
	}, []);

	// Monitor heartbeat
	useEffect(() => {
		if (connectionState !== 'connected') return;
		
		const checkHeartbeat = setInterval(() => {
			const timeSinceLastHeartbeat = Date.now() - lastHeartbeatRef.current;
			if (timeSinceLastHeartbeat > defaultOptions.heartbeatTimeout) {
				console.warn('[SSE Hook] Heartbeat timeout, reconnecting...');
				reconnect();
			}
		}, defaultOptions.heartbeatTimeout / 2);
		
		return () => clearInterval(checkHeartbeat);
	}, [connectionState, defaultOptions.heartbeatTimeout]);

	return {
		connectionState,
		connectionId,
		lastMessage,
		error,
		connect,
		disconnect,
		addEventListener
	};
}

/**
 * Hook for WebSocket connection
 * @param {string} endpoint - WebSocket endpoint path
 * @param {Object} params - Query parameters
 * @param {Object} options - Connection options
 */
export function useMoolAIWebSocket(endpoint, params = {}, options = {}) {
	const [connectionState, setConnectionState] = useState('disconnected');
	const [connectionId, setConnectionId] = useState(null);
	const [isAuthenticated, setIsAuthenticated] = useState(false);
	const [lastMessage, setLastMessage] = useState(null);
	const [error, setError] = useState(null);
	
	const websocketRef = useRef(null);
	const listenersRef = useRef(new Map());
	const messageQueueRef = useRef([]);
	const reconnectAttemptsRef = useRef(0);
	const pendingResponsesRef = useRef(new Map());
	const messageIdCounterRef = useRef(0);
	
	const defaultOptions = {
		baseUrl: '',
		reconnectInterval: 5000,
		maxReconnectAttempts: 10,
		pingInterval: 30000,
		authTimeout: 10000,
		autoConnect: true,
		...options
	};

	// Build WebSocket URL
	const buildUrl = useCallback(() => {
		const baseUrl = defaultOptions.baseUrl || 
			window.location.origin.replace('http', 'ws');
		const url = new URL(baseUrl + endpoint);
		Object.keys(params).forEach(key => {
			if (params[key] !== undefined && params[key] !== null) {
				url.searchParams.append(key, params[key]);
			}
		});
		return url.toString();
	}, [endpoint, params, defaultOptions.baseUrl]);

	// Generate unique message ID
	const generateMessageId = () => {
		return `msg_${Date.now()}_${++messageIdCounterRef.current}`;
	};

	// Connect to WebSocket endpoint
	const connect = useCallback(() => {
		if (websocketRef.current) {
			disconnect();
		}

		const url = buildUrl();
		console.log(`[WS Hook] Connecting to ${url}`);
		setConnectionState('connecting');
		setError(null);
		
		const websocket = new WebSocket(url);
		websocketRef.current = websocket;
		
		// Connection opened
		websocket.onopen = () => {
			console.log('[WS Hook] Connection established');
			setConnectionState('connected');
			reconnectAttemptsRef.current = 0;
			processMessageQueue();
		};

		// Message received
		websocket.onmessage = (event) => {
			handleMessage(event.data);
		};

		// Connection closed
		websocket.onclose = (event) => {
			console.log('[WS Hook] Connection closed:', event.code, event.reason);
			handleDisconnection();
		};

		// Error occurred
		websocket.onerror = (error) => {
			console.error('[WS Hook] Connection error:', error);
			setConnectionState('error');
			setError('WebSocket connection error');
		};
	}, [buildUrl]);

	// Send a message
	const send = useCallback((message) => {
		if (connectionState !== 'connected' || !websocketRef.current) {
			console.warn('[WS Hook] Not connected, queuing message');
			messageQueueRef.current.push(message);
			return;
		}

		const messageStr = JSON.stringify(message);
		websocketRef.current.send(messageStr);
	}, [connectionState]);

	// Send a message and wait for response
	const sendAndWait = useCallback((message, timeout = 30000) => {
		return new Promise((resolve, reject) => {
			const messageId = generateMessageId();
			message.message_id = messageId;

			// Set timeout for response
			const timeoutId = setTimeout(() => {
				pendingResponsesRef.current.delete(messageId);
				reject(new Error('Response timeout'));
			}, timeout);

			// Store pending response handler
			pendingResponsesRef.current.set(messageId, {
				resolve: (data) => {
					clearTimeout(timeoutId);
					pendingResponsesRef.current.delete(messageId);
					resolve(data);
				},
				reject: (error) => {
					clearTimeout(timeoutId);
					pendingResponsesRef.current.delete(messageId);
					reject(error);
				}
			});

			send(message);
		});
	}, [send]);

	// Authenticate the connection
	const authenticate = useCallback((token) => {
		return sendAndWait({
			type: 'auth',
			data: { token },
			timestamp: new Date().toISOString()
		}).then((response) => {
			setIsAuthenticated(true);
			return response;
		});
	}, [sendAndWait]);

	// Subscribe to channels
	const subscribe = useCallback((channels) => {
		return sendAndWait({
			type: 'subscribe',
			data: { channels },
			timestamp: new Date().toISOString()
		});
	}, [sendAndWait]);

	// Unsubscribe from channels
	const unsubscribe = useCallback((channels) => {
		return sendAndWait({
			type: 'unsubscribe',
			data: { channels },
			timestamp: new Date().toISOString()
		});
	}, [sendAndWait]);

	// Send a command
	const sendCommand = useCallback((command, params = {}) => {
		return sendAndWait({
			type: 'command',
			data: { command, params },
			timestamp: new Date().toISOString()
		});
	}, [sendAndWait]);

	// Handle incoming message
	const handleMessage = (data) => {
		try {
			const message = JSON.parse(data);
			
			// Handle response to pending request
			if (message.correlation_id && pendingResponsesRef.current.has(message.correlation_id)) {
				const handler = pendingResponsesRef.current.get(message.correlation_id);
				if (message.type === 'error') {
					handler.reject(new Error(message.data.error));
				} else {
					handler.resolve(message.data);
				}
				return;
			}

			// Update last message
			setLastMessage({ ...message, timestamp: Date.now() });

			// Handle specific message types
			switch (message.type) {
				case 'success':
					if (message.data.message === 'Connected') {
						setConnectionId(message.data.connection_id);
					} else if (message.data.message === 'Authenticated') {
						setIsAuthenticated(true);
					}
					break;

				case 'ping':
					// Respond with pong
					send({
						type: 'pong',
						data: { timestamp: new Date().toISOString() },
						timestamp: new Date().toISOString(),
						correlation_id: message.message_id
					});
					break;
			}

			// Call registered listeners
			if (listenersRef.current.has(message.type)) {
				listenersRef.current.get(message.type).forEach(callback => {
					try {
						callback(message.data);
					} catch (error) {
						console.error(`[WS Hook] Error in listener for ${message.type}:`, error);
					}
				});
			}
		} catch (error) {
			console.error('[WS Hook] Error parsing message:', error);
		}
	};

	// Register event listener
	const addEventListener = useCallback((event, callback) => {
		if (!listenersRef.current.has(event)) {
			listenersRef.current.set(event, new Set());
		}
		listenersRef.current.get(event).add(callback);
		
		// Return cleanup function
		return () => {
			if (listenersRef.current.has(event)) {
				listenersRef.current.get(event).delete(callback);
			}
		};
	}, []);

	// Process queued messages
	const processMessageQueue = () => {
		while (messageQueueRef.current.length > 0) {
			const message = messageQueueRef.current.shift();
			send(message);
		}
	};

	// Handle disconnection
	const handleDisconnection = () => {
		setConnectionState('disconnected');
		setIsAuthenticated(false);
		
		if (reconnectAttemptsRef.current < defaultOptions.maxReconnectAttempts) {
			reconnect();
		} else {
			console.error('[WS Hook] Max reconnection attempts reached');
			setError('Max reconnection attempts reached');
		}
	};

	// Reconnect to WebSocket endpoint
	const reconnect = () => {
		reconnectAttemptsRef.current++;
		console.log(`[WS Hook] Reconnecting... (attempt ${reconnectAttemptsRef.current})`);
		setConnectionState('reconnecting');
		
		setTimeout(() => {
			connect();
		}, defaultOptions.reconnectInterval);
	};

	// Disconnect from WebSocket endpoint
	const disconnect = useCallback(() => {
		if (websocketRef.current) {
			websocketRef.current.close();
			websocketRef.current = null;
		}
		setConnectionState('disconnected');
		setConnectionId(null);
		setIsAuthenticated(false);
		messageQueueRef.current = [];
		pendingResponsesRef.current.clear();
		console.log('[WS Hook] Disconnected');
	}, []);

	// Auto-connect on mount if enabled
	useEffect(() => {
		if (defaultOptions.autoConnect) {
			connect();
		}
		
		// Cleanup on unmount
		return () => {
			disconnect();
		};
	}, []);

	// Send periodic ping messages
	useEffect(() => {
		if (connectionState !== 'connected') return;
		
		const pingInterval = setInterval(() => {
			send({
				type: 'ping',
				data: { timestamp: new Date().toISOString() },
				timestamp: new Date().toISOString(),
				message_id: generateMessageId()
			});
		}, defaultOptions.pingInterval);
		
		return () => clearInterval(pingInterval);
	}, [connectionState, send, defaultOptions.pingInterval]);

	return {
		connectionState,
		connectionId,
		isAuthenticated,
		lastMessage,
		error,
		connect,
		disconnect,
		authenticate,
		send,
		sendAndWait,
		subscribe,
		unsubscribe,
		sendCommand,
		addEventListener
	};
}