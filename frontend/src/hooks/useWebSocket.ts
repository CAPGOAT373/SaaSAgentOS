import { useEffect, useRef, useCallback } from 'react';
import wsService from '../services/websocket';

export function useWebSocket(url: string, tenantId: string = '') {
  const connectedRef = useRef(false);

  useEffect(() => {
    if (!connectedRef.current) {
      wsService.connect(url, tenantId);
      connectedRef.current = true;
    }
    return () => {
      // Don't disconnect on unmount - keep connection alive
    };
  }, [url, tenantId]);

  const subscribe = useCallback((type: string, handler: (data: any) => void) => {
    return wsService.on(type, handler);
  }, []);

  const send = useCallback((data: any) => {
    wsService.send(data);
  }, []);

  return { subscribe, send, isConnected: wsService.isConnected() };
}