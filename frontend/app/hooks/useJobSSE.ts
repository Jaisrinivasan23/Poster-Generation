'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

// Event types from SSE stream
export interface SSEProgressEvent {
  job_id: string;
  processed: number;
  total: number;
  success_count: number;
  failure_count: number;
  percent_complete: number;
  current_user?: string;
  phase: string;
}

export interface SSEPosterCompletedEvent {
  job_id: string;
  username: string;
  poster_url: string;
  success: boolean;
  error?: string;
}

export interface SSEJobCompletedEvent {
  job_id: string;
  success_count: number;
  failure_count: number;
  total_time_seconds: number;
  results: Array<{
    username: string;
    success: boolean;
    posterUrl?: string;
    error?: string;
  }>;
}

export interface SSEJobFailedEvent {
  job_id: string;
  error: string;
  details?: Record<string, unknown>;
}

export interface SSELogEvent {
  job_id: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  message: string;
  details?: Record<string, unknown>;
  timestamp: string;
}

export interface SSEStatusEvent {
  job_id: string;
  status: string;
  processed: number;
  total: number;
  success_count: number;
  failure_count: number;
}

export type SSEEvent = 
  | { type: 'connected'; data: { job_id: string; connection_id: string; message: string } }
  | { type: 'status'; data: SSEStatusEvent }
  | { type: 'progress'; data: SSEProgressEvent }
  | { type: 'poster_completed'; data: SSEPosterCompletedEvent }
  | { type: 'job_completed'; data: SSEJobCompletedEvent }
  | { type: 'job_failed'; data: SSEJobFailedEvent }
  | { type: 'log'; data: SSELogEvent }
  | { type: 'heartbeat'; data: { status: string } };

export interface UseJobSSEOptions {
  onProgress?: (data: SSEProgressEvent) => void;
  onPosterCompleted?: (data: SSEPosterCompletedEvent) => void;
  onJobCompleted?: (data: SSEJobCompletedEvent) => void;
  onJobFailed?: (data: SSEJobFailedEvent) => void;
  onLog?: (data: SSELogEvent) => void;
  onError?: (error: Error) => void;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
}

export interface UseJobSSEResult {
  isConnected: boolean;
  isConnecting: boolean;
  error: Error | null;
  progress: SSEProgressEvent | null;
  logs: SSELogEvent[];
  completedPosters: SSEPosterCompletedEvent[];
  jobResult: SSEJobCompletedEvent | null;
  connect: (jobId: string) => void;
  disconnect: () => void;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

export function useJobSSE(options: UseJobSSEOptions = {}): UseJobSSEResult {
  const {
    onProgress,
    onPosterCompleted,
    onJobCompleted,
    onJobFailed,
    onLog,
    onError,
    autoReconnect = true,
    maxReconnectAttempts = 3,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [progress, setProgress] = useState<SSEProgressEvent | null>(null);
  const [logs, setLogs] = useState<SSELogEvent[]>([]);
  const [completedPosters, setCompletedPosters] = useState<SSEPosterCompletedEvent[]>([]);
  const [jobResult, setJobResult] = useState<SSEJobCompletedEvent | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const currentJobIdRef = useRef<string | null>(null);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
    currentJobIdRef.current = null;
    reconnectAttemptsRef.current = 0;
  }, []);

  const connect = useCallback((jobId: string) => {
    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Reset state
    setProgress(null);
    setLogs([]);
    setCompletedPosters([]);
    setJobResult(null);
    setError(null);
    setIsConnecting(true);

    currentJobIdRef.current = jobId;
    
    const url = `${BACKEND_URL}/api/batch/jobs/${jobId}/stream`;
    console.log('🔌 Connecting to SSE:', url);

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('✅ SSE connected');
      setIsConnected(true);
      setIsConnecting(false);
      setError(null);
      reconnectAttemptsRef.current = 0;
    };

    eventSource.onerror = (e) => {
      console.error('❌ SSE error:', e);
      setIsConnected(false);
      setIsConnecting(false);
      
      const err = new Error('SSE connection error');
      setError(err);
      onError?.(err);

      // Auto-reconnect logic
      if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts && currentJobIdRef.current) {
        reconnectAttemptsRef.current += 1;
        console.log(`🔄 Reconnecting... attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts}`);
        setTimeout(() => {
          if (currentJobIdRef.current) {
            connect(currentJobIdRef.current);
          }
        }, 2000 * reconnectAttemptsRef.current);
      }
    };

    // Handle different event types
    eventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      console.log('🔗 Connected event:', data);
    });

    eventSource.addEventListener('status', (e) => {
      const data: SSEStatusEvent = JSON.parse(e.data);
      console.log(' Status event:', data);
      setProgress({
        job_id: data.job_id,
        processed: data.processed,
        total: data.total,
        success_count: data.success_count,
        failure_count: data.failure_count,
        percent_complete: data.total > 0 ? (data.processed / data.total) * 100 : 0,
        phase: data.status,
        current_user: undefined,
      });
    });

    eventSource.addEventListener('progress', (e) => {
      const data: SSEProgressEvent = JSON.parse(e.data);
      console.log('📈 Progress event:', data);
      setProgress(data);
      onProgress?.(data);
    });

    eventSource.addEventListener('poster_completed', (e) => {
      const data: SSEPosterCompletedEvent = JSON.parse(e.data);
      console.log('🖼️ Poster completed:', data);
      setCompletedPosters(prev => [...prev, data]);
      onPosterCompleted?.(data);
    });

    eventSource.addEventListener('job_completed', (e) => {
      const data: SSEJobCompletedEvent = JSON.parse(e.data);
      console.log('✅ Job completed:', data);
      setJobResult(data);
      onJobCompleted?.(data);
      // Close connection after job completes
      disconnect();
    });

    eventSource.addEventListener('job_failed', (e) => {
      const data: SSEJobFailedEvent = JSON.parse(e.data);
      console.error('❌ Job failed:', data);
      setError(new Error(data.error));
      onJobFailed?.(data);
      disconnect();
    });

    eventSource.addEventListener('log', (e) => {
      const data: SSELogEvent = JSON.parse(e.data);
      console.log(`📝 [${data.level}] ${data.message}`);
      setLogs(prev => [...prev.slice(-99), data]); // Keep last 100 logs
      onLog?.(data);
    });

    eventSource.addEventListener('heartbeat', () => {
      console.log('💓 Heartbeat');
    });

  }, [onProgress, onPosterCompleted, onJobCompleted, onJobFailed, onLog, onError, autoReconnect, maxReconnectAttempts, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    isConnected,
    isConnecting,
    error,
    progress,
    logs,
    completedPosters,
    jobResult,
    connect,
    disconnect,
  };
}

export default useJobSSE;
