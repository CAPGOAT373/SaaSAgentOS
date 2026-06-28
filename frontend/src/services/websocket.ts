type WSMessageHandler = (data: any) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<WSMessageHandler>> = new Map();
  private reconnectTimer: number | null = null;
  private url: string = '';
  private tenantId: string = '';

  connect(url: string, tenantId: string = '') {
    this.url = url;
    this.tenantId = tenantId;
    this._connect();
  }

  private _connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const fullUrl = this.url.startsWith('ws') ? this.url : `${protocol}//${window.location.host}${this.url}`;

    this.ws = new WebSocket(fullUrl);

    this.ws.onopen = () => {
      console.log('WS connected:', fullUrl);
      if (this.tenantId) {
        this.send({ type: 'set_tenant', tenant_id: this.tenantId });
      }
      this.emit('connection', { status: 'connected' });
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const type = data.type || 'message';
        this.emit(type, data);
        this.emit('*', data);
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    this.ws.onclose = () => {
      console.log('WS disconnected');
      this.emit('connection', { status: 'disconnected' });
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.error('WS error:', err);
      this.emit('error', { error: 'WebSocket connection error' });
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this._connect();
    }, 3000);
  }

  send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  on(type: string, handler: WSMessageHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);
    return () => this.handlers.get(type)?.delete(handler);
  }

  private emit(type: string, data: any) {
    this.handlers.get(type)?.forEach(h => h(data));
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const wsService = new WebSocketService();
export default wsService;