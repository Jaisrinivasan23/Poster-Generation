'use client';

import { useEffect, useState, useCallback } from 'react';

interface JobStatus {
  jobId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  totalUsers: number;
  processedUsers: number;
  remainingUsers: number;
  successCount: number;
  failureCount: number;
  totalBatches: number;
  completedBatches: number;
  percentComplete: number;
  estimatedTimeRemainingMinutes: number | null;
  createdAt: number;
  startedAt: number | null;
  completedAt: number | null;
  error?: string;
  results?: any;
}

interface BulkJobProgressProps {
  jobId: string;
  onComplete?: (status: JobStatus) => void;
  onError?: (error: string) => void;
}

export default function BulkJobProgress({ jobId, onComplete, onError }: BulkJobProgressProps) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`/api/job-status/${jobId}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch job status: ${response.statusText}`);
      }

      const data = await response.json();
      setStatus(data);
      setLoading(false);

      // Trigger callbacks
      if (data.status === 'completed' && onComplete) {
        onComplete(data);
      } else if (data.status === 'failed' && onError) {
        onError(data.error || 'Job failed');
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      setLoading(false);
      if (onError) onError(errorMsg);
    }
  }, [jobId, onComplete, onError]);

  useEffect(() => {
    // Initial fetch
    fetchStatus();

    // Poll every 5 seconds while job is in progress
    const interval = setInterval(() => {
      if (status?.status === 'queued' || status?.status === 'processing') {
        fetchStatus();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchStatus, status?.status]);

  if (loading && !status) {
    return (
      <div className="w-full max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
          <div className="h-8 bg-gray-200 rounded mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full max-w-2xl mx-auto p-6 bg-red-50 border border-red-200 rounded-lg">
        <div className="flex items-center mb-2">
          <svg className="w-6 h-6 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="text-lg font-semibold text-red-800">Error Loading Job Status</h3>
        </div>
        <p className="text-red-700">{error}</p>
      </div>
    );
  }

  if (!status) return null;

  const getStatusColor = () => {
    switch (status.status) {
      case 'queued': return 'bg-yellow-500';
      case 'processing': return 'bg-blue-500';
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = () => {
    switch (status.status) {
      case 'queued':
        return (
          <svg className="w-8 h-8 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'processing':
        return (
          <svg className="w-8 h-8 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        );
      case 'completed':
        return (
          <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'failed':
        return (
          <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  const formatTime = (minutes: number | null) => {
    if (minutes === null) return 'Calculating...';
    if (minutes < 1) return 'Less than 1 minute';
    if (minutes === 1) return '1 minute';
    if (minutes < 60) return `${minutes} minutes`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg border border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          {getStatusIcon()}
          <div className="ml-3">
            <h3 className="text-xl font-bold text-gray-800 capitalize">{status.status}</h3>
            <p className="text-sm text-gray-500">Job ID: {status.jobId}</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-gray-800">{status.percentComplete}%</div>
          <div className="text-xs text-gray-500">Complete</div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-6">
        <div className="w-full bg-gray-200 rounded-full h-6 overflow-hidden">
          <div
            className={`h-full ${getStatusColor()} transition-all duration-500 ease-out flex items-center justify-center text-white text-sm font-semibold`}
            style={{ width: `${status.percentComplete}%` }}
          >
            {status.percentComplete > 10 && `${status.percentComplete}%`}
          </div>
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>{status.processedUsers} of {status.totalUsers} images</span>
          <span>{status.remainingUsers} remaining</span>
        </div>
      </div>

      {/* Statistics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-blue-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-blue-600">{status.totalUsers}</div>
          <div className="text-xs text-gray-600">Total Images</div>
        </div>
        <div className="bg-green-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-green-600">{status.successCount}</div>
          <div className="text-xs text-gray-600">Successful</div>
        </div>
        <div className="bg-red-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-red-600">{status.failureCount}</div>
          <div className="text-xs text-gray-600">Failed</div>
        </div>
        <div className="bg-purple-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-purple-600">{status.completedBatches}/{status.totalBatches}</div>
          <div className="text-xs text-gray-600">Batches</div>
        </div>
      </div>

      {/* Time Estimate */}
      {status.status === 'processing' && status.estimatedTimeRemainingMinutes !== null && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="flex items-center">
            <svg className="w-5 h-5 text-blue-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm font-medium text-blue-800">
              Estimated time remaining: {formatTime(status.estimatedTimeRemainingMinutes)}
            </span>
          </div>
        </div>
      )}

      {/* Completion Message */}
      {status.status === 'completed' && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="w-5 h-5 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm font-medium text-green-800">
              ✅ Successfully generated {status.successCount} images!
            </span>
          </div>
        </div>
      )}

      {/* Error Message */}
      {status.status === 'failed' && status.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-red-500 mr-2 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <div className="text-sm font-medium text-red-800 mb-1">Job Failed</div>
              <div className="text-sm text-red-700">{status.error}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
