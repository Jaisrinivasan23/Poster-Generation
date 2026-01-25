'use client';

import { useEffect, useState } from 'react';

interface BulkProgressTrackerProps {
  phase: 'converting' | 'uploading' | 'storing' | 'complete';
  total: number;
  completed: number;
  failed?: number;
  currentItem?: string;
  startTime: number;
}

export default function BulkProgressTracker({
  phase,
  total,
  completed,
  failed = 0,
  currentItem,
  startTime,
}: BulkProgressTrackerProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Update elapsed time every second
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime]);

  // Calculate metrics
  const remaining = total - completed - failed;
  const percentComplete = total > 0 ? Math.round((completed / total) * 100) : 0;
  const successRate = total > 0 ? Math.round((completed / (completed + failed)) * 100) : 100;

  // Calculate estimated time remaining
  const avgTimePerItem = completed > 0 ? elapsedSeconds / completed : 0;
  const estimatedSecondsRemaining = Math.ceil(avgTimePerItem * remaining);

  // Format time helper
  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins < 60) return `${mins}m ${secs}s`;
    const hours = Math.floor(mins / 60);
    const remainingMins = mins % 60;
    return `${hours}h ${remainingMins}m`;
  };

  // Phase labels and colors
  const phaseConfig = {
    converting: { label: '🎨 Converting Images', color: 'blue', icon: '🖼️' },
    uploading: { label: '📤 Uploading to Storage', color: 'purple', icon: '☁️' },
    storing: { label: '💾 Saving to Database', color: 'green', icon: '🗄️' },
    complete: { label: '✅ Complete', color: 'green', icon: '🎉' },
  };

  const config = phaseConfig[phase];

  return (
    <div className="bg-white rounded-xl shadow-lg border-2 border-gray-200 p-6 space-y-6">
      {/* Header with Phase Indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center text-2xl animate-pulse ${
            phase === 'converting' ? 'bg-blue-100' :
            phase === 'uploading' ? 'bg-purple-100' :
            phase === 'storing' ? 'bg-green-100' :
            'bg-green-200'
          }`}>
            {config.icon}
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-800">{config.label}</h3>
            <p className="text-sm text-gray-500">
              {phase === 'complete' ? 'All done!' : 'Processing...'}
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-4xl font-bold text-gray-800">{percentComplete}%</div>
          <div className="text-xs text-gray-500">Complete</div>
        </div>
      </div>

      {/* Main Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-gray-600">
          <span className="font-medium">{completed} of {total} images</span>
          <span className="text-gray-500">{remaining} remaining</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-6 overflow-hidden shadow-inner">
          <div
            className={`h-full transition-all duration-500 ease-out flex items-center justify-end pr-2 ${
              phase === 'converting' ? 'bg-gradient-to-r from-blue-400 to-blue-600' :
              phase === 'uploading' ? 'bg-gradient-to-r from-purple-400 to-purple-600' :
              phase === 'storing' ? 'bg-gradient-to-r from-green-400 to-green-600' :
              'bg-gradient-to-r from-green-500 to-green-700'
            }`}
            style={{ width: `${percentComplete}%` }}
          >
            {percentComplete > 15 && (
              <span className="text-white text-xs font-bold">{percentComplete}%</span>
            )}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Total */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-gray-700">{total}</div>
          <div className="text-xs text-gray-500 mt-1">Total</div>
        </div>

        {/* Completed */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-600">{completed}</div>
          <div className="text-xs text-gray-500 mt-1">✅ Completed</div>
        </div>

        {/* Failed */}
        {failed > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-red-600">{failed}</div>
            <div className="text-xs text-gray-500 mt-1">❌ Failed</div>
          </div>
        )}

        {/* Remaining */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-blue-600">{remaining}</div>
          <div className="text-xs text-gray-500 mt-1">⏳ Remaining</div>
        </div>

        {/* Success Rate */}
        {(completed + failed) > 0 && (
          <div className={`${successRate >= 90 ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'} border rounded-lg p-3 text-center`}>
            <div className={`text-2xl font-bold ${successRate >= 90 ? 'text-green-600' : 'text-yellow-600'}`}>
              {successRate}%
            </div>
            <div className="text-xs text-gray-500 mt-1"> Success Rate</div>
          </div>
        )}
      </div>

      {/* Time Information */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Elapsed Time */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-blue-900">⏱️ Elapsed</span>
            <span className="text-lg font-bold text-blue-700">{formatTime(elapsedSeconds)}</span>
          </div>
        </div>

        {/* Estimated Remaining */}
        {remaining > 0 && completed > 0 && (
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-purple-900">🕐 Remaining</span>
              <span className="text-lg font-bold text-purple-700">
                ~{formatTime(estimatedSecondsRemaining)}
              </span>
            </div>
          </div>
        )}

        {/* Avg Time per Item */}
        {completed > 0 && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">⚡ Avg Time</span>
              <span className="text-lg font-bold text-gray-600">
                {avgTimePerItem.toFixed(1)}s/img
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Current Item */}
      {currentItem && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
          <div className="flex items-center gap-2">
            <svg className="animate-spin h-4 w-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-sm font-medium text-gray-700">Processing:</span>
            <span className="text-sm text-gray-600 truncate flex-1">{currentItem}</span>
          </div>
        </div>
      )}

      {/* Phase Progress Indicators */}
      <div className="flex items-center justify-between pt-4 border-t">
        {['converting', 'uploading', 'storing', 'complete'].map((p, idx) => {
          const isComplete = ['converting', 'uploading', 'storing', 'complete'].indexOf(phase) > idx;
          const isCurrent = phase === p;

          return (
            <div key={p} className="flex items-center">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 transition-all ${
                isCurrent
                  ? 'border-blue-500 bg-blue-500 text-white animate-pulse'
                  : isComplete
                  ? 'border-green-500 bg-green-500 text-white'
                  : 'border-gray-300 bg-gray-100 text-gray-400'
              }`}>
                {isComplete ? '✓' : idx + 1}
              </div>
              {idx < 3 && (
                <div className={`w-12 md:w-20 h-0.5 ${
                  isComplete ? 'bg-green-500' : 'bg-gray-300'
                }`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Phase Labels */}
      <div className="grid grid-cols-4 gap-1 text-center">
        <div className={`text-xs ${phase === 'converting' ? 'font-bold text-blue-600' : 'text-gray-500'}`}>
          Converting
        </div>
        <div className={`text-xs ${phase === 'uploading' ? 'font-bold text-purple-600' : 'text-gray-500'}`}>
          Uploading
        </div>
        <div className={`text-xs ${phase === 'storing' ? 'font-bold text-green-600' : 'text-gray-500'}`}>
          Storing
        </div>
        <div className={`text-xs ${phase === 'complete' ? 'font-bold text-green-600' : 'text-gray-500'}`}>
          Complete
        </div>
      </div>
    </div>
  );
}
