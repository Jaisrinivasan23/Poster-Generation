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
  '/api/edit-poster',
  '/api/poster-chat',
  // Batch Processing with RedPanda + SSE
  '/api/batch/jobs',
  '/api/batch/health',
  // Template Management
  '/api/templates/upload',
  '/api/templates/generate',
  '/api/templates',
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

// ============ Template Management API ============

export interface TemplatePlaceholder {
  name: string;
  sample_value?: string;
  data_type?: string;
  is_required?: boolean;
}

export interface Template {
  id: string;
  section: string;
  name: string;
  version: number;
  is_active: boolean;
  html_content?: string;
  css_content?: string;
  placeholders: TemplatePlaceholder[];
  created_at: string;
  updated_at: string;
}

export interface UploadTemplateParams {
  section: string;
  name: string;
  html_content: string;
  css_content?: string;
  set_as_active?: boolean;
}

export interface GenerateFromTemplateParams {
  template_id: string;
  custom_data: Record<string, string>;
  metadata?: Record<string, unknown>;
}

export interface TemplateJobResult {
  entity_id: string;
  url: string;
  status: string;
  generation_time_ms?: number;
  error?: string;
}

export interface TemplateJobStatus {
  job_id: string;
  status: string;
  template_section: string;
  template_version: number;
  total_items: number;
  processed_items: number;
  success_count: number;
  failure_count: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  results: TemplateJobResult[];
}

/**
 * Upload a new template
 * @param params - Template upload parameters
 * @returns Uploaded template details
 */
export async function uploadTemplate(params: UploadTemplateParams): Promise<{
  template_id: string;
  version: number;
  section: string;
  placeholders: TemplatePlaceholder[];
  message: string;
}> {
  const response = await apiFetch('/api/templates/upload', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to upload template');
  }

  return response.json();
}

/**
 * List all templates with optional section filter
 * @param section - Optional section filter
 * @returns List of templates
 */
export async function listTemplates(section?: string): Promise<{
  section: string;
  templates: Template[];
  active_template?: Template;
}> {
  const params = section ? `?section=${encodeURIComponent(section)}` : '';
  const response = await apiFetch(`/api/templates${params}`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list templates');
  }

  return response.json();
}

/**
 * Generate poster from template response type
 */
export interface GenerateFromTemplateResponse {
  success: boolean;
  job_id: string;
  status: string;
  template_version: number;
  template_name: string;
  sse_endpoint: string;
  poll_endpoint: string;
  message: string;
}

/**
 * SSE event types for template generation
 */
export interface TemplateSSEProgressEvent {
  job_id: string;
  processed: number;
  total: number;
  success_count: number;
  failure_count: number;
  percent_complete: number;
  phase: string;
}

export interface TemplateSSECompletedEvent {
  job_id: string;
  success: boolean;
  url?: string;
  generation_time_ms?: number;
  template_version?: number;
  error?: string;
}

/**
 * Generate poster from template (async with SSE support)
 * @param params - Generation parameters
 * @returns Job ID and SSE endpoint for real-time progress
 */
export async function generateFromTemplate(params: GenerateFromTemplateParams): Promise<GenerateFromTemplateResponse> {
  const response = await apiFetch('/api/templates/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to generate poster');
  }

  return response.json();
}

/**
 * Connect to template generation SSE stream and wait for completion
 * @param sseEndpoint - SSE endpoint from generateFromTemplate response
 * @param onProgress - Callback for progress updates
 * @returns Promise that resolves with the completed poster URL
 */
export function subscribeToTemplateGeneration(
  sseEndpoint: string,
  onProgress?: (event: TemplateSSEProgressEvent) => void,
  onLog?: (message: string, level: string) => void
): Promise<TemplateSSECompletedEvent> {
  return new Promise((resolve, reject) => {
    const url = `${BACKEND_API_URL}${sseEndpoint}`;
    console.log('🔌 Connecting to template SSE:', url);
    
    const eventSource = new EventSource(url);
    let resolved = false;
    
    // Connection timeout
    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        eventSource.close();
        reject(new Error('SSE connection timeout'));
      }
    }, 120000); // 2 minute timeout
    
    eventSource.onopen = () => {
      console.log('✅ Template SSE connected');
      onLog?.('Connected to generation stream', 'INFO');
    };
    
    eventSource.addEventListener('status', (e) => {
      const data = JSON.parse(e.data);
      console.log(' Status:', data);
      onProgress?.({
        job_id: data.job_id,
        processed: 0,
        total: 1,
        success_count: 0,
        failure_count: 0,
        percent_complete: 0,
        phase: data.status || 'starting'
      });
    });
    
    eventSource.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data);
      console.log('📈 Progress:', data);
      onProgress?.(data);
    });
    
    eventSource.addEventListener('log', (e) => {
      const data = JSON.parse(e.data);
      console.log(`📝 [${data.level}] ${data.message}`);
      onLog?.(data.message, data.level);
    });
    
    eventSource.addEventListener('poster_completed', (e) => {
      const data: TemplateSSECompletedEvent = JSON.parse(e.data);
      console.log('🖼️ Poster completed:', data);
      clearTimeout(timeout);
      if (!resolved) {
        resolved = true;
        eventSource.close();
        if (data.success && data.url) {
          resolve(data);
        } else {
          reject(new Error(data.error || 'Generation failed'));
        }
      }
    });
    
    eventSource.addEventListener('job_completed', (e) => {
      const data = JSON.parse(e.data);
      console.log('✅ Job completed:', data);
      clearTimeout(timeout);
      if (!resolved) {
        resolved = true;
        eventSource.close();
        resolve(data);
      }
    });
    
    eventSource.addEventListener('job_failed', (e) => {
      const data = JSON.parse(e.data);
      console.error('❌ Job failed:', data);
      clearTimeout(timeout);
      if (!resolved) {
        resolved = true;
        eventSource.close();
        reject(new Error(data.error || 'Generation failed'));
      }
    });
    
    eventSource.addEventListener('heartbeat', () => {
      console.log('💓 Heartbeat');
    });
    
    eventSource.onerror = (error) => {
      console.error('❌ SSE error:', error);
      clearTimeout(timeout);
      if (!resolved) {
        // Check if it's a normal close or an error
        if (eventSource.readyState === EventSource.CLOSED) {
          // Connection closed normally, might have missed completion event
          // Don't reject immediately, let the timeout handle it
        } else {
          resolved = true;
          eventSource.close();
          reject(new Error('SSE connection error'));
        }
      }
    };
  });
}

/**
 * Generate poster from template with SSE progress tracking (convenience function)
 * @param params - Generation parameters
 * @param onProgress - Progress callback
 * @returns Promise with the final poster URL
 */
export async function generateFromTemplateWithProgress(
  params: GenerateFromTemplateParams,
  onProgress?: (percent: number, phase: string) => void,
  onLog?: (message: string, level: string) => void
): Promise<{ url: string; generation_time_ms: number; template_version: number }> {
  // Start generation and get SSE endpoint
  const response = await generateFromTemplate(params);
  
  if (!response.success || !response.sse_endpoint) {
    throw new Error('Failed to start generation');
  }
  
  // Send initial progress
  onProgress?.(0, 'starting');
  onLog?.('Generation started', 'INFO');
  
  // Connect to SSE and wait for completion
  const result = await subscribeToTemplateGeneration(
    response.sse_endpoint,
    (event) => {
      onProgress?.(event.percent_complete, event.phase);
    },
    onLog
  );
  
  if (!result.success || !result.url) {
    throw new Error(result.error || 'Generation failed');
  }
  
  onProgress?.(100, 'completed');
  
  return {
    url: result.url,
    generation_time_ms: result.generation_time_ms || 0,
    template_version: result.template_version || response.template_version
  };
}

/**
 * Get template job status
 * @param jobId - Template generation job ID
 * @returns Job status and results
 */
export async function getTemplateJobStatus(jobId: string): Promise<TemplateJobStatus> {
  const response = await apiFetch(`/api/templates/job/${jobId}`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get job status');
  }

  return response.json();
}

/**
 * Activate a specific template version
 * @param templateId - Template ID to activate
 * @returns Activated template details
 */
export async function activateTemplate(templateId: string): Promise<{
  template_id: string;
  section: string;
  version: number;
  is_active: boolean;
  message: string;
}> {
  const response = await apiFetch(`/api/templates/${templateId}/activate`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to activate template');
  }

  return response.json();
}

/**
 * Preview a template with sample data
 * @param templateId - Template ID to preview
 * @returns Template preview HTML
 */
export async function previewTemplate(templateId: string): Promise<{
  template_id: string;
  section: string;
  name: string;
  preview_html: string;
}> {
  const response = await apiFetch(`/api/templates/${templateId}/preview`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to preview template');
  }

  return response.json();
}

