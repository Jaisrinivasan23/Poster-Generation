'use client';

import { useState, useCallback } from 'react';
import { useJobSSE, SSEProgressEvent, SSEPosterCompletedEvent, SSEJobCompletedEvent, SSELogEvent } from '../hooks/useJobSSE';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

interface BatchJobResult {
  username: string;
  success: boolean;
  posterUrl?: string;
  error?: string;
}

interface BatchJobFormProps {
  htmlTemplate: string;
  posterSize: string;
  model: string;
  topmateLogo?: string;
}

export default function BatchJobWithSSE({ htmlTemplate, posterSize, model, topmateLogo }: BatchJobFormProps) {
  const [campaignName, setCampaignName] = useState('');
  const [userIdentifiers, setUserIdentifiers] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [results, setResults] = useState<BatchJobResult[]>([]);
  const [showLogs, setShowLogs] = useState(false);

  const {
    isConnected,
    isConnecting,
    error: sseError,
    progress,
    logs,
    completedPosters,
    jobResult,
    connect,
    disconnect,
  } = useJobSSE({
    onProgress: (data: SSEProgressEvent) => {
      console.log('Progress update:', data);
    },
    onPosterCompleted: (data: SSEPosterCompletedEvent) => {
      setResults(prev => [...prev, {
        username: data.username,
        success: data.success,
        posterUrl: data.poster_url,
        error: data.error,
      }]);
    },
    onJobCompleted: (data: SSEJobCompletedEvent) => {
      console.log('Job completed!', data);
      setResults(data.results.map(r => ({
        username: r.username,
        success: r.success,
        posterUrl: r.posterUrl,
        error: r.error,
      })));
    },
    onJobFailed: (data) => {
      console.error('Job failed:', data.error);
    },
    onLog: (data: SSELogEvent) => {
      console.log(`[${data.level}] ${data.message}`);
    },
  });

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!campaignName.trim() || !userIdentifiers.trim()) {
      alert('Please fill in all required fields');
      return;
    }

    if (!htmlTemplate) {
      alert('Please create a template first');
      return;
    }

    setIsSubmitting(true);
    setResults([]);
    setJobId(null);

    try {
      const response = await fetch(`${BACKEND_URL}/api/batch/jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          campaignName,
          userIdentifiers,
          htmlTemplate,
          posterSize,
          model,
          topmateLogo,
          skipOverlays: false,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to create job');
      }

      console.log('Job created:', data);
      setJobId(data.jobId);
      
      // Connect to SSE for real-time updates
      connect(data.jobId);
      
    } catch (err) {
      console.error('Error creating job:', err);
      alert(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [campaignName, userIdentifiers, htmlTemplate, posterSize, model, topmateLogo, connect]);

  const handleCancel = useCallback(async () => {
    if (!jobId) return;

    try {
      await fetch(`${BACKEND_URL}/api/batch/jobs/${jobId}/cancel`, {
        method: 'POST',
      });
      disconnect();
      setJobId(null);
    } catch (err) {
      console.error('Error cancelling job:', err);
    }
  }, [jobId, disconnect]);

  const getStatusColor = () => {
    if (sseError) return 'text-red-500';
    if (jobResult) return 'text-green-500';
    if (isConnected) return 'text-blue-500';
    return 'text-gray-500';
  };

  const getStatusText = () => {
    if (sseError) return `Error: ${sseError.message}`;
    if (jobResult) return 'Completed';
    if (isConnecting) return 'Connecting...';
    if (isConnected && progress) return `Processing (${progress.percent_complete.toFixed(1)}%)`;
    if (isConnected) return 'Connected';
    return 'Idle';
  };

  return (
    <div className="space-y-6">
      {/* Job Creation Form */}
      {!jobId && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Campaign Name
            </label>
            <input
              type="text"
              value={campaignName}
              onChange={(e) => setCampaignName(e.target.value)}
              placeholder="Q1 Marketing Campaign"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              User Identifiers
            </label>
            <textarea
              value={userIdentifiers}
              onChange={(e) => setUserIdentifiers(e.target.value)}
              placeholder="Enter usernames or user IDs, one per line or comma-separated&#10;username1&#10;username2&#10;12345"
              rows={5}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
              required
            />
            <p className="mt-1 text-sm text-gray-500">
              Enter Topmate usernames or user IDs, separated by commas or new lines
            </p>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !htmlTemplate}
            className="w-full py-3 px-4 border border-transparent rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium"
          >
            {isSubmitting ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Creating Job...
              </span>
            ) : (
              '🚀 Start Batch Generation'
            )}
          </button>
        </form>
      )}

      {/* Active Job Progress */}
      {jobId && (
        <div className="bg-white rounded-lg shadow-lg p-6 border border-gray-200">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {campaignName}
              </h3>
              <p className="text-sm text-gray-500">Job ID: {jobId}</p>
            </div>
            <div className="flex items-center space-x-2">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor()} bg-opacity-10`}>
                <span className={`w-2 h-2 rounded-full mr-1.5 ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></span>
                {getStatusText()}
              </span>
            </div>
          </div>

          {/* Progress Bar */}
          {progress && (
            <div className="mb-4">
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>{progress.processed} / {progress.total} posters</span>
                <span>{progress.percent_complete.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${progress.percent_complete}%` }}
                />
              </div>
              <div className="flex justify-between text-sm text-gray-500 mt-1">
                <span className="text-green-600">✓ {progress.success_count} success</span>
                {progress.failure_count > 0 && (
                  <span className="text-red-600">✗ {progress.failure_count} failed</span>
                )}
                {progress.current_user && (
                  <span>Processing: {progress.current_user}</span>
                )}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex space-x-3 mb-4">
            {!jobResult && (
              <button
                onClick={handleCancel}
                className="px-4 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50"
              >
                Cancel Job
              </button>
            )}
            <button
              onClick={() => setShowLogs(!showLogs)}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
            >
              {showLogs ? 'Hide Logs' : 'Show Logs'} ({logs.length})
            </button>
          </div>

          {/* Logs Panel */}
          {showLogs && logs.length > 0 && (
            <div className="mb-4 bg-gray-900 rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-xs">
              {logs.map((log, idx) => (
                <div key={idx} className={`
                  ${log.level === 'ERROR' ? 'text-red-400' : ''}
                  ${log.level === 'WARNING' ? 'text-yellow-400' : ''}
                  ${log.level === 'INFO' ? 'text-green-400' : ''}
                  ${log.level === 'DEBUG' ? 'text-gray-400' : ''}
                `}>
                  <span className="text-gray-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>{' '}
                  <span className="font-semibold">[{log.level}]</span>{' '}
                  {log.message}
                </div>
              ))}
            </div>
          )}

          {/* Results Grid */}
          {results.length > 0 && (
            <div>
              <h4 className="text-md font-medium text-gray-900 mb-3">
                Generated Posters ({results.filter(r => r.success).length} / {results.length})
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-h-96 overflow-y-auto">
                {results.map((result, idx) => (
                  <div
                    key={idx}
                    className={`relative rounded-lg overflow-hidden border-2 ${
                      result.success ? 'border-green-200' : 'border-red-200'
                    }`}
                  >
                    {result.success && result.posterUrl ? (
                      <img
                        src={result.posterUrl}
                        alt={`Poster for ${result.username}`}
                        className="w-full h-auto"
                      />
                    ) : (
                      <div className="bg-red-50 p-4 text-center">
                        <span className="text-red-500 text-sm">
                          ✗ {result.error || 'Failed'}
                        </span>
                      </div>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs p-1 text-center">
                      {result.username}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Job Completed Summary */}
          {jobResult && (
            <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
              <h4 className="text-lg font-semibold text-green-800 mb-2">
                ✅ Job Completed!
              </h4>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-green-600">{jobResult.success_count}</div>
                  <div className="text-sm text-gray-600">Successful</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-600">{jobResult.failure_count}</div>
                  <div className="text-sm text-gray-600">Failed</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-blue-600">{jobResult.total_time_seconds.toFixed(1)}s</div>
                  <div className="text-sm text-gray-600">Total Time</div>
                </div>
              </div>
              <button
                onClick={() => {
                  setJobId(null);
                  setResults([]);
                }}
                className="mt-4 w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Start New Batch
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
