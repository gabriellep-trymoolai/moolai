/**
 * Analytics WebSocket Service for Real-time Dashboard Updates
 * Connects to the monitoring WebSocket endpoints for live analytics data
 */

export interface AnalyticsMetrics {
  total_api_calls: number;
  total_cost: number;
  cache_hit_rate: number;
  avg_response_time_ms: number;
  firewall_blocks: number;
  provider_breakdown: Array<{
    provider: string;
    calls: number;
    cost: number;
    tokens: number;
  }>;
}

export interface AnalyticsWebSocketConfig {
  baseUrl?: string;
  organizationId?: string;
  token?: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  debug?: boolean;
}

export type AnalyticsConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';

export class AnalyticsWebSocketService {
  private ws: WebSocket | null = null;
  private config: Required<AnalyticsWebSocketConfig>;
  private connectionState: AnalyticsConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private messageIdCounter = 0;
  
  // Event listeners
  private metricsListeners = new Set<(metrics: AnalyticsMetrics) => void>();
  private stateListeners = new Set<(state: AnalyticsConnectionState) => void>();
  private errorListeners = new Set<(error: string) => void>();

  constructor(config: AnalyticsWebSocketConfig = {}) {
    this.config = {
      baseUrl: config.baseUrl || this.getDefaultBaseUrl(),
      organizationId: config.organizationId || import.meta.env.VITE_ORGANIZATION_ID || 'org_001',
      token: config.token || 'analytics_token', // TODO: Get from auth context
      reconnectInterval: config.reconnectInterval || 5000,
      maxReconnectAttempts: config.maxReconnectAttempts || 10,
      debug: config.debug || import.meta.env.VITE_DEBUG === 'true'
    };

    this.log('Analytics WebSocket service initialized', this.config);
  }

  private getDefaultBaseUrl(): string {
    const envUrl = import.meta.env.VITE_WS_BASE_URL;
    if (envUrl) {
      return envUrl;
    }
    
    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${window.location.host}`;
    }
    return 'ws://localhost:8000';
  }

  private log(message: string, ...args: any[]): void {
    if (this.config.debug) {
      console.log(`[Analytics WS] ${message}`, ...args);
    }
  }

  private generateMessageId(): string {
    return `analytics_${Date.now()}_${++this.messageIdCounter}`;
  }

  private setState(state: AnalyticsConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.log(`State changed to: ${state}`);
      this.stateListeners.forEach(listener => listener(state));
    }
  }

  private emitMetrics(metrics: AnalyticsMetrics): void {
    this.metricsListeners.forEach(listener => {
      try {
        listener(metrics);
      } catch (error) {
        console.error('[Analytics WS] Error in metrics listener:', error);
      }
    });
  }

  private emitError(error: string): void {
    this.errorListeners.forEach(listener => {
      try {
        listener(error);
      } catch (err) {
        console.error('[Analytics WS] Error in error listener:', err);
      }
    });
  }

  // Public API
  public getConnectionState(): AnalyticsConnectionState {
    return this.connectionState;
  }

  public onMetricsUpdate(callback: (metrics: AnalyticsMetrics) => void): () => void {
    this.metricsListeners.add(callback);
    return () => this.metricsListeners.delete(callback);
  }

  public onStateChange(callback: (state: AnalyticsConnectionState) => void): () => void {
    this.stateListeners.add(callback);
    return () => this.stateListeners.delete(callback);
  }

  public onError(callback: (error: string) => void): () => void {
    this.errorListeners.add(callback);
    return () => this.errorListeners.delete(callback);
  }

  public async connect(): Promise<void> {
    if (this.connectionState === 'connecting' || this.connectionState === 'connected') {
      this.log('Connection already in progress or established');
      return;
    }

    this.setState('connecting');
    this.log('Connecting to analytics WebSocket...');

    try {
      // Connect to the monitoring metrics live endpoint
      const wsEndpoint = `/ws/monitoring/metrics/live`;
      const url = new URL(wsEndpoint, this.config.baseUrl);
      
      // Add query parameters
      url.searchParams.set('organization_id', this.config.organizationId);
      url.searchParams.set('token', this.config.token);
      url.searchParams.set('metrics', 'analytics'); // Subscribe specifically to analytics metrics

      this.ws = new WebSocket(url.toString());
      
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Analytics WebSocket connection timeout'));
          this.cleanup();
        }, 10000);

        this.ws!.onopen = () => {
          clearTimeout(timeout);
          this.log('Analytics WebSocket connection opened');
          this.setState('connected');
          this.reconnectAttempts = 0;
          
          // Send subscription message for analytics metrics
          this.send({
            type: 'subscribe',
            data: {
              metrics: ['analytics', 'cache', 'cost', 'performance'],
              organization_id: this.config.organizationId
            }
          });
          
          resolve();
        };

        this.ws!.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('[Analytics WS] Error parsing message:', error);
          }
        };

        this.ws!.onclose = (event) => {
          clearTimeout(timeout);
          this.log(`Analytics WebSocket closed: ${event.code} ${event.reason}`);
          this.handleDisconnection();
        };

        this.ws!.onerror = (error) => {
          clearTimeout(timeout);
          this.log('Analytics WebSocket error:', error);
          this.setState('error');
          this.emitError('WebSocket connection failed');
          reject(new Error('Analytics WebSocket connection failed'));
        };
      });
    } catch (error) {
      this.setState('error');
      throw error;
    }
  }

  public disconnect(): void {
    this.log('Disconnecting analytics WebSocket');

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.send({
        type: 'unsubscribe',
        data: {
          organization_id: this.config.organizationId
        }
      });
      
      this.ws.close(1000, 'Client disconnect');
    }

    this.cleanup();
  }

  public send(message: any): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.log('Cannot send message - WebSocket not connected');
      return;
    }

    const fullMessage = {
      message_id: this.generateMessageId(),
      timestamp: new Date().toISOString(),
      ...message
    };

    this.log('Sending message:', fullMessage);
    this.ws.send(JSON.stringify(fullMessage));
  }

  // Private methods
  private handleMessage(message: any): void {
    this.log('Received message:', message);

    switch (message.type) {
      case 'metric_update':
        this.handleMetricUpdate(message.data);
        break;
      
      case 'analytics_update':
        this.handleAnalyticsUpdate(message.data);
        break;
      
      case 'subscription_confirmed':
        this.log('Analytics subscription confirmed');
        break;
      
      case 'error':
        this.emitError(message.data?.error || 'Unknown error');
        break;
      
      default:
        this.log('Unknown message type:', message.type);
    }
  }

  private handleMetricUpdate(data: any): void {
    // Transform the received metric data into AnalyticsMetrics format
    if (data) {
      const metrics: AnalyticsMetrics = {
        total_api_calls: data.total_queries || 0,
        total_cost: parseFloat(data.total_cost || '0'),
        cache_hit_rate: parseFloat(data.cache_hit_rate || '0'),
        avg_response_time_ms: parseInt(data.avg_latency_ms || '0'),
        firewall_blocks: data.firewall_blocks || 0,
        provider_breakdown: data.provider_breakdown || []
      };
      
      this.emitMetrics(metrics);
    }
  }

  private handleAnalyticsUpdate(data: any): void {
    // Handle comprehensive analytics updates
    if (data && data.overview) {
      const metrics: AnalyticsMetrics = {
        total_api_calls: data.overview.total_api_calls || 0,
        total_cost: data.overview.total_cost || 0,
        cache_hit_rate: data.overview.cache_hit_rate || 0,
        avg_response_time_ms: data.overview.avg_response_time_ms || 0,
        firewall_blocks: data.overview.firewall_blocks || 0,
        provider_breakdown: data.provider_breakdown || []
      };
      
      this.emitMetrics(metrics);
    }
  }

  private handleDisconnection(): void {
    this.cleanup();
    
    if (this.reconnectAttempts < this.config.maxReconnectAttempts) {
      this.scheduleReconnect();
    } else {
      this.log('Max reconnection attempts reached');
      this.setState('error');
      this.emitError('Max reconnection attempts reached');
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++;
    const delay = Math.min(
      this.config.reconnectInterval * Math.pow(2, Math.min(this.reconnectAttempts - 1, 4)),
      30000
    );
    
    this.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
    this.setState('reconnecting');
    
    setTimeout(() => {
      if (this.connectionState === 'reconnecting') {
        this.connect().catch(error => {
          this.log('Reconnection failed:', error);
          this.handleDisconnection();
        });
      }
    }, delay);
  }

  private cleanup(): void {
    this.ws = null;
    this.setState('disconnected');
  }
}

// Export singleton instance
export const analyticsWebSocketService = new AnalyticsWebSocketService();