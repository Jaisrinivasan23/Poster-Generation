'use client';

import { useState, useCallback, useRef } from 'react';
import { 
  generateFromTemplate, 
  subscribeToTemplateGeneration,
  GenerateFromTemplateParams,
  TemplateSSEProgressEvent,
  TemplateSSECompletedEvent
} from '../lib/api';

export interface TemplateGenerationState {
  isGenerating: boolean;
  progress: number;
  phase: string;
  logs: { message: string; level: string; timestamp: Date }[];
  result: TemplateSSECompletedEvent | null;
  error: Error | null;
}

export interface UseTemplateGenerationResult extends TemplateGenerationState {
  generate: (params: GenerateFromTemplateParams) => Promise<TemplateSSECompletedEvent>;
  reset: () => void;
}

/**
 * Hook for template-based poster generation with real-time SSE progress
 * 
 * Features:
 * - Immediate progress bar when generation starts
 * - Real-time phase updates (starting, processing, rendering, uploading, completed)
 * - Log streaming for debugging
 * - Automatic SSE connection management
 * 
 * Usage:
 * ```tsx
 * const { generate, isGenerating, progress, phase, result, error } = useTemplateGeneration();
 * 
 * const handleGenerate = async () => {
 *   try {
 *     const result = await generate({
 *       template_id: 'testimonial_latest',
 *       custom_data: { consumer_name: 'John', consumer_message: 'Great!' },
 *       metadata: { id: '123' }
 *     });
 *     console.log('Generated:', result.url);
 *   } catch (err) {
 *     console.error('Failed:', err);
 *   }
 * };
 * ```
 */
export function useTemplateGeneration(): UseTemplateGenerationResult {
  const [state, setState] = useState<TemplateGenerationState>({
    isGenerating: false,
    progress: 0,
    phase: 'idle',
    logs: [],
    result: null,
    error: null,
  });
  
  const abortControllerRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    setState({
      isGenerating: false,
      progress: 0,
      phase: 'idle',
      logs: [],
      result: null,
      error: null,
    });
  }, []);

  const generate = useCallback(async (params: GenerateFromTemplateParams): Promise<TemplateSSECompletedEvent> => {
    // Reset state and start generating
    setState({
      isGenerating: true,
      progress: 0,
      phase: 'starting',
      logs: [{ message: 'Starting generation...', level: 'INFO', timestamp: new Date() }],
      result: null,
      error: null,
    });

    try {
      // Step 1: Call generate endpoint (returns immediately with SSE endpoint)
      console.log('🚀 Starting template generation...');
      const response = await generateFromTemplate(params);
      
      if (!response.success || !response.sse_endpoint) {
        throw new Error('Failed to start generation');
      }

      // Update state - queued
      setState(prev => ({
        ...prev,
        progress: 5,
        phase: 'queued',
        logs: [...prev.logs, { 
          message: `Job ${response.job_id} queued`, 
          level: 'INFO', 
          timestamp: new Date() 
        }],
      }));

      // Step 2: Connect to SSE and wait for completion
      console.log('📡 Connecting to SSE stream:', response.sse_endpoint);
      
      const result = await subscribeToTemplateGeneration(
        response.sse_endpoint,
        // Progress callback
        (event: TemplateSSEProgressEvent) => {
          // Map phase to progress percentage
          const phaseProgress: Record<string, number> = {
            'starting': 10,
            'processing': 20,
            'fetching_template': 25,
            'processing_template': 35,
            'rendering': 60,
            'uploading': 85,
            'completed': 100,
          };
          
          const progressValue = phaseProgress[event.phase] || event.percent_complete || 0;
          
          setState(prev => ({
            ...prev,
            progress: progressValue,
            phase: event.phase,
          }));
        },
        // Log callback
        (message: string, level: string) => {
          setState(prev => ({
            ...prev,
            logs: [...prev.logs.slice(-49), { message, level, timestamp: new Date() }],
          }));
        }
      );

      // Step 3: Handle completion
      console.log('✅ Generation completed:', result);
      
      setState(prev => ({
        ...prev,
        isGenerating: false,
        progress: 100,
        phase: 'completed',
        result,
        logs: [...prev.logs, { 
          message: `Completed in ${result.generation_time_ms || 0}ms`, 
          level: 'INFO', 
          timestamp: new Date() 
        }],
      }));

      return result;

    } catch (error) {
      console.error('❌ Generation failed:', error);
      const err = error instanceof Error ? error : new Error(String(error));
      
      setState(prev => ({
        ...prev,
        isGenerating: false,
        progress: 0,
        phase: 'failed',
        error: err,
        logs: [...prev.logs, { message: `Error: ${err.message}`, level: 'ERROR', timestamp: new Date() }],
      }));

      throw err;
    }
  }, []);

  return {
    ...state,
    generate,
    reset,
  };
}

export default useTemplateGeneration;
