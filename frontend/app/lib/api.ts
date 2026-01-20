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
