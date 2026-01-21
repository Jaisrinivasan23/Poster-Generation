/**
 * API client utility for backend API calls
 * All endpoints now use FastAPI backend
 */

// Get backend API URL from environment or default to localhost:8000
const BACKEND_API_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

// All API endpoints are now migrated to FastAPI backend
const BACKEND_ENDPOINTS = [
  '/api/generate-poster',
  '/api/generate-bulk',
  '/api/save-bulk-posters',
  '/api/export-poster',
  '/api/complete-carousel',
  '/api/generate',
  '/api/chat',
  '/api/chat-sync',
  '/api/analyze-design',
  '/api/analyze-prompt',
  '/api/generate-image',
  '/api/generate-template',
  '/api/upload-s3',
  '/api/save-local',
  // Batch Processing with RedPanda + SSE
  '/api/batch/jobs',
  '/api/batch/health',
];

/**
 * Check if an endpoint is handled by the FastAPI backend
 * @param endpoint - API endpoint to check
 * @returns true if endpoint should use FastAPI backend
 */
function isBackendEndpoint(endpoint: string): boolean {
  return BACKEND_ENDPOINTS.some(be => endpoint.startsWith(be));
}

/**
 * Get the full API URL for a given endpoint
 * @param endpoint - API endpoint (e.g., '/api/generate-poster')
 * @returns Full URL (either FastAPI backend or relative Next.js path)
 */
export function getApiUrl(endpoint: string): string {
  // Remove leading slash if present
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  
  if (isBackendEndpoint(endpoint)) {
    // Use FastAPI backend
    return `${BACKEND_API_URL}/${cleanEndpoint}`;
  } else {
    // Use Next.js API route (relative path)
    return `/${cleanEndpoint}`;
  }
}

/**
 * Get the SSE endpoint URL for a batch job
 * @param jobId - The batch job ID
 * @returns Full SSE URL for streaming updates
 */
export function getBatchJobSSEUrl(jobId: string): string {
  return `${BACKEND_API_URL}/api/batch/jobs/${jobId}/stream`;
}

/**
 * Get the backend API base URL
 * @returns Backend API URL
 */
export function getBackendUrl(): string {
  return BACKEND_API_URL;
}

/**
 * Wrapper for fetch that automatically routes to the correct backend
 * @param endpoint - API endpoint (e.g., '/api/generate-poster')
 * @param options - Fetch options
 * @returns Fetch promise
 */
export async function apiFetch(endpoint: string, options?: RequestInit): Promise<Response> {
  const url = getApiUrl(endpoint);
  const target = isBackendEndpoint(endpoint) ? 'FastAPI' : 'Next.js';
  console.log(`[API] ${target} → ${url}`);
  return fetch(url, options);
}

// ============ Batch Processing API ============

export interface CreateBatchJobParams {
  campaignName: string;
  userIdentifiers: string;
  htmlTemplate: string;
  posterSize?: string;
  model?: string;
  topmateLogo?: string;
  skipOverlays?: boolean;
  metadata?: Record<string, unknown>;
}

export interface BatchJobResponse {
  success: boolean;
  jobId: string;
  status: string;
  totalItems: number;
  campaignName: string;
  createdAt: string;
  sseEndpoint: string;
}

/**
 * Create a new batch poster generation job
 * @param params - Job creation parameters
 * @returns Job details including SSE endpoint for progress tracking
 */
export async function createBatchJob(params: CreateBatchJobParams): Promise<BatchJobResponse> {
  const response = await apiFetch('/api/batch/jobs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create batch job');
  }

  return response.json();
}

/**
 * Get the status of a batch job
 * @param jobId - The batch job ID
 * @returns Current job status
 */
export async function getBatchJobStatus(jobId: string): Promise<{
  success: boolean;
  job: {
    job_id: string;
    status: string;
    campaign_name: string;
    total_items: number;
    processed_items: number;
    success_count: number;
    failure_count: number;
    percent_complete: number;
    created_at: string;
    started_at: string | null;
    completed_at: string | null;
    error_message: string | null;
  };
}> {
  const response = await apiFetch(`/api/batch/jobs/${jobId}`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get job status');
  }

  return response.json();
}

/**
 * Get results for a completed batch job
 * @param jobId - The batch job ID
 * @returns Job results with poster URLs
 */
export async function getBatchJobResults(jobId: string): Promise<{
  success: boolean;
  jobId: string;
  results: Array<{
    username: string;
    display_name?: string;
    poster_url?: string;
    success: boolean;
    error?: string;
    processing_time_ms?: number;
  }>;
  successCount: number;
  failureCount: number;
}> {
  const response = await apiFetch(`/api/batch/jobs/${jobId}/results`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get job results');
  }

  return response.json();
}

/**
 * Cancel a running batch job
 * @param jobId - The batch job ID to cancel
 * @returns Cancellation result
 */
export async function cancelBatchJob(jobId: string): Promise<{
  success: boolean;
  jobId: string;
  message: string;
}> {
  const response = await apiFetch(`/api/batch/jobs/${jobId}/cancel`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to cancel job');
  }

  return response.json();
}

/**
 * Get logs for a batch job
 * @param jobId - The batch job ID
 * @param level - Optional log level filter
 * @param limit - Maximum number of logs to return
 * @returns Job logs
 */
export async function getBatchJobLogs(jobId: string, level?: string, limit: number = 100): Promise<{
  success: boolean;
  jobId: string;
  logs: Array<{
    id: number;
    level: string;
    message: string;
    details: Record<string, unknown>;
    created_at: string;
  }>;
  count: number;
}> {
  const params = new URLSearchParams();
  if (level) params.set('level', level);
  params.set('limit', limit.toString());

  const response = await apiFetch(`/api/batch/jobs/${jobId}/logs?${params.toString()}`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get job logs');
  }

  return response.json();
}

/**
 * List all batch jobs with optional filtering
 * @param status - Optional status filter
 * @param limit - Maximum number of jobs to return
 * @param offset - Pagination offset
 * @returns List of batch jobs
 */
export async function listBatchJobs(status?: string, limit: number = 50, offset: number = 0): Promise<{
  success: boolean;
  jobs: Array<{
    id: string;
    job_id: string;
    campaign_name: string;
    status: string;
    total_items: number;
    processed_items: number;
    success_count: number;
    failure_count: number;
    created_at: string;
    completed_at: string | null;
  }>;
  total: number;
}> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  params.set('limit', limit.toString());
  params.set('offset', offset.toString());

  const response = await apiFetch(`/api/batch/jobs?${params.toString()}`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list jobs');
  }

  return response.json();
}

/**
 * Check health of batch processing services
 * @returns Health status of services
 */
export async function checkBatchHealth(): Promise<{
  success: boolean;
  services: {
    database: boolean;
    redpanda: boolean;
    sse_connections: number;
  };
}> {
  const response = await apiFetch('/api/batch/health', {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to check health');
  }

  return response.json();
}

