/**
 * MoolAI Real-time Client Library
 * Provides SSE and WebSocket communication for MoolAI monitoring system
 */

(function(window) {
	'use strict';

	/**
	 * MoolAI SSE Client for Server-Sent Events
	 */
	class MoolAISSEClient {
		constructor(baseUrl = '', options = {}) {
			this.baseUrl = baseUrl || window.location.origin;
			this.options = {
				reconnectInterval: 5000,
				maxReconnectAttempts: 10,
				heartbeatTimeout: 60000,
				...options
			};
			this.eventSource = null;
			this.listeners = new Map();
			this.reconnectAttempts = 0;
			this.lastHeartbeat = Date.now();
			this.heartbeatTimer = null;
			this.connectionId = null;
			this.isConnected = false;
		}

		/**
		 * Connect to SSE endpoint
		 * @param {string} endpoint - SSE endpoint path
		 * @param {Object} params - Query parameters
		 */
		connect(endpoint, params = {}) {
			return new Promise((resolve, reject) => {
				if (this.eventSource) {
					this.disconnect();
				}

				// Build URL with query parameters
				const url = new URL(this.baseUrl + endpoint);
				Object.keys(params).forEach(key => {
					if (params[key] !== undefined && params[key] !== null) {
						url.searchParams.append(key, params[key]);
					}
				});

				console.log(`[SSE] Connecting to ${url.toString()}`);
				
				this.eventSource = new EventSource(url.toString());
				
				// Connection opened
				this.eventSource.onopen = () => {
					console.log('[SSE] Connection established');
					this.isConnected = true;
					this.reconnectAttempts = 0;
					this.startHeartbeatMonitor();
					resolve();
				};

				// Error handler
				this.eventSource.onerror = (error) => {
					console.error('[SSE] Connection error:', error);
					this.isConnected = false;
					
					if (this.eventSource.readyState === EventSource.CLOSED) {
						this.handleDisconnection();
						reject(new Error('SSE connection closed'));
					}
				};

				// Default message handler
				this.eventSource.onmessage = (event) => {
					this.handleMessage('message', event.data);
				};

				// Handle specific event types
				this.setupEventHandlers();
			});
		}

		/**
		 * Setup handlers for specific SSE event types
		 */
		setupEventHandlers() {
			// Connected event
			this.eventSource.addEventListener('connected', (event) => {
				const data = JSON.parse(event.data);
				this.connectionId = data.connection_id;
				console.log(`[SSE] Connected with ID: ${this.connectionId}`);
				this.emit('connected', data);
			});

			// Heartbeat event
			this.eventSource.addEventListener('heartbeat', (event) => {
				this.lastHeartbeat = Date.now();
				this.emit('heartbeat', JSON.parse(event.data));
			});

			// Metrics events
			this.eventSource.addEventListener('user_metrics', (event) => {
				this.emit('user_metrics', JSON.parse(event.data));
			});

			this.eventSource.addEventListener('org_metrics', (event) => {
				this.emit('org_metrics', JSON.parse(event.data));
			});

			this.eventSource.addEventListener('metrics_snapshot', (event) => {
				this.emit('metrics_snapshot', JSON.parse(event.data));
			});

			// Health events
			this.eventSource.addEventListener('health_update', (event) => {
				this.emit('health_update', JSON.parse(event.data));
			});

			this.eventSource.addEventListener('health_status', (event) => {
				this.emit('health_status', JSON.parse(event.data));
			});

			// LLM streaming events
			this.eventSource.addEventListener('llm_chunk', (event) => {
				this.emit('llm_chunk', JSON.parse(event.data));
			});

			// Disconnecting event
			this.eventSource.addEventListener('disconnecting', (event) => {
				console.log('[SSE] Server is disconnecting');
				this.emit('disconnecting', JSON.parse(event.data));
			});
		}

		/**
		 * Handle incoming message
		 */
		handleMessage(type, data) {
			try {
				const parsedData = typeof data === 'string' ? JSON.parse(data) : data;
				this.emit(type, parsedData);
			} catch (error) {
				console.error('[SSE] Error parsing message:', error);
			}
		}

		/**
		 * Register event listener
		 */
		on(event, callback) {
			if (!this.listeners.has(event)) {
				this.listeners.set(event, []);
			}
			this.listeners.get(event).push(callback);
			return this;
		}

		/**
		 * Remove event listener
		 */
		off(event, callback) {
			if (this.listeners.has(event)) {
				const callbacks = this.listeners.get(event);
				const index = callbacks.indexOf(callback);
				if (index !== -1) {
					callbacks.splice(index, 1);
				}
			}
			return this;
		}

		/**
		 * Emit event to listeners
		 */
		emit(event, data) {
			if (this.listeners.has(event)) {
				this.listeners.get(event).forEach(callback => {
					try {
						callback(data);
					} catch (error) {
						console.error(`[SSE] Error in event listener for ${event}:`, error);
					}
				});
			}
		}

		/**
		 * Start monitoring heartbeat
		 */
		startHeartbeatMonitor() {
			this.stopHeartbeatMonitor();
			
			this.heartbeatTimer = setInterval(() => {
				const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeat;
				if (timeSinceLastHeartbeat > this.options.heartbeatTimeout) {
					console.warn('[SSE] Heartbeat timeout, reconnecting...');
					this.reconnect();
				}
			}, this.options.heartbeatTimeout / 2);
		}

		/**
		 * Stop monitoring heartbeat
		 */
		stopHeartbeatMonitor() {
			if (this.heartbeatTimer) {
				clearInterval(this.heartbeatTimer);
				this.heartbeatTimer = null;
			}
		}

		/**
		 * Handle disconnection
		 */
		handleDisconnection() {
			this.stopHeartbeatMonitor();
			this.emit('disconnected', { connectionId: this.connectionId });
			
			if (this.reconnectAttempts < this.options.maxReconnectAttempts) {
				this.reconnect();
			} else {
				console.error('[SSE] Max reconnection attempts reached');
				this.emit('error', { type: 'max_reconnect_attempts' });
			}
		}

		/**
		 * Reconnect to SSE endpoint
		 */
		reconnect() {
			this.reconnectAttempts++;
			console.log(`[SSE] Reconnecting... (attempt ${this.reconnectAttempts})`);
			
			setTimeout(() => {
				if (this.eventSource) {
					const url = this.eventSource.url;
					this.disconnect();
					
					// Parse URL to extract endpoint and params
					const urlObj = new URL(url);
					const endpoint = urlObj.pathname;
					const params = {};
					urlObj.searchParams.forEach((value, key) => {
						params[key] = value;
					});
					
					this.connect(endpoint, params).catch(error => {
						console.error('[SSE] Reconnection failed:', error);
					});
				}
			}, this.options.reconnectInterval);
		}

		/**
		 * Disconnect from SSE endpoint
		 */
		disconnect() {
			if (this.eventSource) {
				this.eventSource.close();
				this.eventSource = null;
			}
			this.stopHeartbeatMonitor();
			this.isConnected = false;
			this.connectionId = null;
			console.log('[SSE] Disconnected');
		}
	}

	/**
	 * MoolAI WebSocket Client for bidirectional communication
	 */
	class MoolAIWebSocketClient {
		constructor(baseUrl = '', options = {}) {
			this.baseUrl = baseUrl || window.location.origin.replace('http', 'ws');
			this.options = {
				reconnectInterval: 5000,
				maxReconnectAttempts: 10,
				pingInterval: 30000,
				authTimeout: 10000,
				...options
			};
			this.websocket = null;
			this.listeners = new Map();
			this.messageQueue = [];
			this.reconnectAttempts = 0;
			this.pingTimer = null;
			this.authTimer = null;
			this.connectionId = null;
			this.isConnected = false;
			this.isAuthenticated = false;
			this.messageIdCounter = 0;
			this.pendingResponses = new Map();
		}

		/**
		 * Connect to WebSocket endpoint
		 * @param {string} endpoint - WebSocket endpoint path
		 * @param {Object} params - Query parameters
		 */
		connect(endpoint, params = {}) {
			return new Promise((resolve, reject) => {
				if (this.websocket) {
					this.disconnect();
				}

				// Build WebSocket URL
				const url = new URL(this.baseUrl + endpoint);
				Object.keys(params).forEach(key => {
					if (params[key] !== undefined && params[key] !== null) {
						url.searchParams.append(key, params[key]);
					}
				});

				console.log(`[WS] Connecting to ${url.toString()}`);
				
				this.websocket = new WebSocket(url.toString());
				
				// Connection opened
				this.websocket.onopen = () => {
					console.log('[WS] Connection established');
					this.isConnected = true;
					this.reconnectAttempts = 0;
					this.startPingTimer();
					this.processMessageQueue();
					resolve();
				};

				// Message received
				this.websocket.onmessage = (event) => {
					this.handleMessage(event.data);
				};

				// Connection closed
				this.websocket.onclose = (event) => {
					console.log('[WS] Connection closed:', event.code, event.reason);
					this.handleDisconnection();
				};

				// Error occurred
				this.websocket.onerror = (error) => {
					console.error('[WS] Connection error:', error);
					reject(error);
				};
			});
		}

		/**
		 * Authenticate the WebSocket connection
		 * @param {string} token - Authentication token
		 */
		authenticate(token) {
			return new Promise((resolve, reject) => {
				if (!this.isConnected) {
					reject(new Error('Not connected'));
					return;
				}

				const authMessage = {
					type: 'auth',
					data: { token },
					timestamp: new Date().toISOString(),
					message_id: this.generateMessageId()
				};

				// Set authentication timeout
				this.authTimer = setTimeout(() => {
					reject(new Error('Authentication timeout'));
				}, this.options.authTimeout);

				// Wait for authentication response
				this.once('authenticated', (data) => {
					clearTimeout(this.authTimer);
					this.isAuthenticated = true;
					console.log('[WS] Authenticated successfully');
					resolve(data);
				});

				this.once('auth_error', (error) => {
					clearTimeout(this.authTimer);
					reject(new Error(error.message || 'Authentication failed'));
				});

				this.send(authMessage);
			});
		}

		/**
		 * Send a message through WebSocket
		 * @param {Object} message - Message to send
		 */
		send(message) {
			if (!this.isConnected) {
				console.warn('[WS] Not connected, queuing message');
				this.messageQueue.push(message);
				return;
			}

			const messageStr = JSON.stringify(message);
			this.websocket.send(messageStr);
		}

		/**
		 * Send a message and wait for response
		 * @param {Object} message - Message to send
		 * @param {number} timeout - Response timeout in ms
		 */
		sendAndWait(message, timeout = 30000) {
			return new Promise((resolve, reject) => {
				const messageId = this.generateMessageId();
				message.message_id = messageId;

				// Set timeout for response
				const timeoutId = setTimeout(() => {
					this.pendingResponses.delete(messageId);
					reject(new Error('Response timeout'));
				}, timeout);

				// Store pending response handler
				this.pendingResponses.set(messageId, {
					resolve: (data) => {
						clearTimeout(timeoutId);
						this.pendingResponses.delete(messageId);
						resolve(data);
					},
					reject: (error) => {
						clearTimeout(timeoutId);
						this.pendingResponses.delete(messageId);
						reject(error);
					}
				});

				this.send(message);
			});
		}

		/**
		 * Subscribe to channels
		 * @param {string[]} channels - Channel names to subscribe to
		 */
		subscribe(channels) {
			return this.sendAndWait({
				type: 'subscribe',
				data: { channels },
				timestamp: new Date().toISOString()
			});
		}

		/**
		 * Unsubscribe from channels
		 * @param {string[]} channels - Channel names to unsubscribe from
		 */
		unsubscribe(channels) {
			return this.sendAndWait({
				type: 'unsubscribe',
				data: { channels },
				timestamp: new Date().toISOString()
			});
		}

		/**
		 * Send an admin command
		 * @param {string} command - Command name
		 * @param {Object} params - Command parameters
		 */
		sendCommand(command, params = {}) {
			return this.sendAndWait({
				type: 'command',
				data: { command, params },
				timestamp: new Date().toISOString()
			});
		}

		/**
		 * Handle incoming message
		 */
		handleMessage(data) {
			try {
				const message = JSON.parse(data);
				
				// Handle response to pending request
				if (message.correlation_id && this.pendingResponses.has(message.correlation_id)) {
					const handler = this.pendingResponses.get(message.correlation_id);
					if (message.type === 'error') {
						handler.reject(new Error(message.data.error));
					} else {
						handler.resolve(message.data);
					}
					return;
				}

				// Handle different message types
				switch (message.type) {
					case 'success':
						if (message.data.message === 'Connected') {
							this.connectionId = message.data.connection_id;
							this.emit('connected', message.data);
						} else if (message.data.message === 'Authenticated') {
							this.emit('authenticated', message.data);
						} else {
							this.emit('success', message.data);
						}
						break;

					case 'error':
						if (!this.isAuthenticated && message.data.error === 'Not authenticated') {
							this.emit('auth_error', message.data);
						} else {
							this.emit('error', message.data);
						}
						break;

					case 'ping':
						// Respond with pong
						this.send({
							type: 'pong',
							data: { timestamp: new Date().toISOString() },
							timestamp: new Date().toISOString(),
							correlation_id: message.message_id
						});
						break;

					case 'pong':
						// Pong received, connection is alive
						this.emit('pong', message.data);
						break;

					default:
						// Emit custom event
						this.emit(message.type, message.data);
						break;
				}
			} catch (error) {
				console.error('[WS] Error parsing message:', error);
			}
		}

		/**
		 * Register event listener
		 */
		on(event, callback) {
			if (!this.listeners.has(event)) {
				this.listeners.set(event, []);
			}
			this.listeners.get(event).push(callback);
			return this;
		}

		/**
		 * Register one-time event listener
		 */
		once(event, callback) {
			const onceWrapper = (data) => {
				this.off(event, onceWrapper);
				callback(data);
			};
			return this.on(event, onceWrapper);
		}

		/**
		 * Remove event listener
		 */
		off(event, callback) {
			if (this.listeners.has(event)) {
				const callbacks = this.listeners.get(event);
				const index = callbacks.indexOf(callback);
				if (index !== -1) {
					callbacks.splice(index, 1);
				}
			}
			return this;
		}

		/**
		 * Emit event to listeners
		 */
		emit(event, data) {
			if (this.listeners.has(event)) {
				this.listeners.get(event).forEach(callback => {
					try {
						callback(data);
					} catch (error) {
						console.error(`[WS] Error in event listener for ${event}:`, error);
					}
				});
			}
		}

		/**
		 * Start ping timer
		 */
		startPingTimer() {
			this.stopPingTimer();
			
			this.pingTimer = setInterval(() => {
				if (this.isConnected) {
					this.send({
						type: 'ping',
						data: { timestamp: new Date().toISOString() },
						timestamp: new Date().toISOString(),
						message_id: this.generateMessageId()
					});
				}
			}, this.options.pingInterval);
		}

		/**
		 * Stop ping timer
		 */
		stopPingTimer() {
			if (this.pingTimer) {
				clearInterval(this.pingTimer);
				this.pingTimer = null;
			}
		}

		/**
		 * Process queued messages
		 */
		processMessageQueue() {
			while (this.messageQueue.length > 0) {
				const message = this.messageQueue.shift();
				this.send(message);
			}
		}

		/**
		 * Generate unique message ID
		 */
		generateMessageId() {
			return `msg_${Date.now()}_${++this.messageIdCounter}`;
		}

		/**
		 * Handle disconnection
		 */
		handleDisconnection() {
			this.isConnected = false;
			this.isAuthenticated = false;
			this.stopPingTimer();
			this.emit('disconnected', { connectionId: this.connectionId });
			
			if (this.reconnectAttempts < this.options.maxReconnectAttempts) {
				this.reconnect();
			} else {
				console.error('[WS] Max reconnection attempts reached');
				this.emit('error', { type: 'max_reconnect_attempts' });
			}
		}

		/**
		 * Reconnect to WebSocket endpoint
		 */
		reconnect() {
			this.reconnectAttempts++;
			console.log(`[WS] Reconnecting... (attempt ${this.reconnectAttempts})`);
			
			setTimeout(() => {
				if (this.websocket) {
					const url = this.websocket.url;
					
					// Parse URL to extract endpoint and params
					const urlObj = new URL(url);
					const endpoint = urlObj.pathname;
					const params = {};
					urlObj.searchParams.forEach((value, key) => {
						params[key] = value;
					});
					
					this.connect(endpoint, params).catch(error => {
						console.error('[WS] Reconnection failed:', error);
					});
				}
			}, this.options.reconnectInterval);
		}

		/**
		 * Disconnect from WebSocket endpoint
		 */
		disconnect() {
			if (this.websocket) {
				this.websocket.close();
				this.websocket = null;
			}
			this.stopPingTimer();
			this.isConnected = false;
			this.isAuthenticated = false;
			this.connectionId = null;
			this.messageQueue = [];
			this.pendingResponses.clear();
			console.log('[WS] Disconnected');
		}
	}

	// Export to window
	window.MoolAI = window.MoolAI || {};
	window.MoolAI.SSEClient = MoolAISSEClient;
	window.MoolAI.WebSocketClient = MoolAIWebSocketClient;

})(window);