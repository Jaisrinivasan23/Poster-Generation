'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Papa from 'papaparse';
import {
  PosterConfig,
  PosterStyle,
  PosterSize,
  PosterMode,
  GenerationMode,
  POSTER_SIZE_DIMENSIONS,
  GeneratedPoster,
} from '../types/poster';
import { TEMPLATE_IMAGES, getAllTemplates, fetchCustomFonts, type Template, type CustomFont } from '../lib/templates';
import TopmateShare from './TopmateShare';
import { PosterFlowMode } from '../types/poster';
import { getTopmateLogo } from '../lib/topmate-logo';
import { fetchTopmateProfile } from '../lib/topmate';
import { apiFetch } from '../lib/api';
import { useJobSSE, SSEProgressEvent, SSEPosterCompletedEvent, SSEJobCompletedEvent, SSELogEvent } from '../hooks/useJobSSE';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

// API key is now handled server-side via environment variables

interface PosterCreatorProps {
  onBack?: () => void;
}

export default function PosterCreator({ onBack }: PosterCreatorProps) {
  const router = useRouter();

  // User mode state (Expert/Admin)
  const [userMode, setUserMode] = useState<'expert' | 'admin'>('admin');

  // Flow mode state
  const [flowMode, setFlowMode] = useState<PosterFlowMode>('single');
  const [bulkMethod] = useState<'csv'>('csv'); // Bulk generation method - CSV only

  // Simple form state
  const [topmateUsername, setTopmateUsername] = useState('');
  const [prompt, setPrompt] = useState('');
  const [htmlTemplate, setHtmlTemplate] = useState('');
  const [htmlPreview, setHtmlPreview] = useState('');
  const [htmlCampaignName, setHtmlCampaignName] = useState('');
  const [htmlTemplateUsers, setHtmlTemplateUsers] = useState('');
  const [htmlGeneratedResults, setHtmlGeneratedResults] = useState<any[]>([]);
  const [isHtmlGenerating, setIsHtmlGenerating] = useState(false);
  const [isSharing, setIsSharing] = useState(false);

  // CSV mode states
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<any[]>([]);
  const [csvColumns, setCsvColumns] = useState<string[]>([]);
  const [csvTemplate, setCsvTemplate] = useState('');
  const [csvPreview, setCsvPreview] = useState('');
  const [csvCampaignName, setCsvCampaignName] = useState('');
  const [csvGeneratedResults, setCsvGeneratedResults] = useState<any[]>([]);
  const [isCsvGenerating, setIsCsvGenerating] = useState(false);
  const [csvCustomWidth, setCsvCustomWidth] = useState(1080);
  const [csvCustomHeight, setCsvCustomHeight] = useState(1350);
  const [showConvertedTemplate, setShowConvertedTemplate] = useState(false);
  const [csvSkipOverlays, setCsvSkipOverlays] = useState(true); // Default to true since users typically include logo in template
  const [csvMissingUserId, setCsvMissingUserId] = useState(false); // Track if CSV is missing user_id column
  const [csvSaveSuccess, setCsvSaveSuccess] = useState(false);
  const [csvSavedConfig, setCsvSavedConfig] = useState<{campaign: string, content_type: string} | null>(null);
  const [csvSaveProgress, setCsvSaveProgress] = useState<{processed: number, total: number, success: number, failed: number} | null>(null);

  // Template mode states (for external backend integration)
  const [templateSection, setTemplateSection] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [templateHtml, setTemplateHtml] = useState('');
  const [templateCss, setTemplateCss] = useState('');
  const [templatePreviewData, setTemplatePreviewData] = useState('{}');
  const [templateSetActive, setTemplateSetActive] = useState(true);
  const [isUploadingTemplate, setIsUploadingTemplate] = useState(false);
  const [templateUploadSuccess, setTemplateUploadSuccess] = useState<any>(null);
  const [templateList, setTemplateList] = useState<any[]>([]);
  const [selectedTemplateSection, setSelectedTemplateSection] = useState('testimonial');

  // SSE Progress tracking for CSV mode
  const [csvJobId, setCsvJobId] = useState<string | null>(null);
  const [csvProgress, setCsvProgress] = useState({ processed: 0, total: 0, percentage: 0 });
  const [csvLogs, setCsvLogs] = useState<string[]>([]);
  const [showCsvLogs, setShowCsvLogs] = useState(false);
  
  const [htmlSaveSuccess, setHtmlSaveSuccess] = useState(false);
  const [htmlSavedConfig, setHtmlSavedConfig] = useState<{campaign: string, content_type: string} | null>(null);
  const [referenceImage, setReferenceImage] = useState<string | null>(null);
  const [referenceSource, setReferenceSource] = useState<'upload' | 'template' | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [mode, setMode] = useState<PosterMode>('single');
  const [slideCount, setSlideCount] = useState(5);
  const [selectedModel, setSelectedModel] = useState<'pro' | 'flash'>('pro');
  const [generationMode, setGenerationMode] = useState<GenerationMode>('html'); // HTML or Image generation

  // Dynamic templates and fonts
  const [allTemplates, setAllTemplates] = useState<Template[]>(TEMPLATE_IMAGES);
  const [customFonts, setCustomFonts] = useState<CustomFont[]>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);

  // Admin upload states
  const [showAdminUpload, setShowAdminUpload] = useState(false);
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  const [uploadingFont, setUploadingFont] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateCategory, setNewTemplateCategory] = useState<'minimal' | 'bold' | 'gradient' | 'photo'>('minimal');
  const [newFontName, setNewFontName] = useState('');
  const [newFontFamily, setNewFontFamily] = useState('');

  // Generation state
  const [isLoading, setIsLoading] = useState(false);
  const [generationProgress, setGenerationProgress] = useState<{ phase: string; progress: number } | null>(null);
  const [generationLogs, setGenerationLogs] = useState<string[]>([]);
  const [isCompletingCarousel, setIsCompletingCarousel] = useState(false);
  const [posters, setPosters] = useState<GeneratedPoster[]>([]);
  const [carousels, setCarousels] = useState<GeneratedPoster[][]>([]); // For carousel: array of variants
  const [selectedVariant, setSelectedVariant] = useState(0); // Which carousel variant (A, B, C, D)
  const [selectedSlide, setSelectedSlide] = useState(0); // Which slide within the variant

  // Editing state
  const [isEditMode, setIsEditMode] = useState(false); // Enable/disable editing
  const [selectedElement, setSelectedElement] = useState<any>(null); // Currently selected element
  const [editHistory, setEditHistory] = useState<any[]>([]); // Track all edits
  const [editInstruction, setEditInstruction] = useState(''); // Current edit instruction
  const [isEditing, setIsEditing] = useState(false); // Loading state for edits
  const [showEditPanel, setShowEditPanel] = useState(false); // Show/hide edit chat panel
  const [editMessages, setEditMessages] = useState<any[]>([]); // Chat-style edit history
  const [selectedIndex, setSelectedIndex] = useState(0); // For single mode
  const [error, setError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState<'png' | 'pdf' | 'all-png' | 'pdf-carousel' | null>(null);
  const [resultMode, setResultMode] = useState<'single' | 'carousel'>('single');
  const [isCarouselPreview, setIsCarouselPreview] = useState(false); // True when only first slides are shown
  const [totalSlides, setTotalSlides] = useState(5); // Total slides for carousel completion
  const [carouselProfile, setCarouselProfile] = useState<any>(null); // Store profile for completion
  const [showTopmateShare, setShowTopmateShare] = useState(false); // Topmate sharing modal

  // Topmate data discovery state (fetches directly from Topmate API)
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [discoveredProfile, setDiscoveredProfile] = useState<any>(null);
  const [relevantFields, setRelevantFields] = useState<string[]>([]); // Fields AI determined are relevant to show
  const [selectedDataFields, setSelectedDataFields] = useState<string[]>([]); // Fields user selected to include

  // Current selected poster (single mode) or slide (carousel mode)
  const poster = resultMode === 'carousel'
    ? carousels[selectedVariant]?.[selectedSlide] || null
    : posters[selectedIndex] || null;

  // Current carousel slides for the selected variant
  const currentCarouselSlides = carousels[selectedVariant] || [];

  // Preview ref
  const previewRef = useRef<HTMLIFrameElement>(null);

  // SSE hook for CSV bulk generation
  const handleCsvProgress = useCallback((event: SSEProgressEvent) => {
    console.log(' [CSV SSE] Progress:', event);
    setCsvProgress({
      processed: event.processed,
      total: event.total,
      percentage: Math.round((event.processed / event.total) * 100)
    });
  }, []);

  const handleCsvPosterCompleted = useCallback((event: SSEPosterCompletedEvent) => {
    console.log('🖼️ [CSV SSE] Poster completed:', event.username);
    setCsvGeneratedResults(prev => [...prev, {
      username: event.username,
      success: event.success,
      posterUrl: event.poster_url,
      error: event.error
    }]);
    setCsvLogs(prev => [...prev, `✅ Poster completed for ${event.username}`]);
  }, []);

  const handleCsvJobCompleted = useCallback((event: SSEJobCompletedEvent) => {
    console.log('🎉 [CSV SSE] Job completed!', event);
    setIsCsvGenerating(false);
    setCsvJobId(null);
    setCsvLogs(prev => [...prev, `🎉 All posters generated! Success: ${event.success_count}, Failed: ${event.failure_count}`]);
  }, []);

  const handleCsvLog = useCallback((event: SSELogEvent) => {
    console.log('📝 [CSV SSE] Log:', event.message);
    setCsvLogs(prev => [...prev, event.message]);
  }, []);

  const handleCsvSSEError = useCallback((error: Error) => {
    console.error('❌ [CSV SSE] Error:', error);
    setCsvLogs(prev => [...prev, `❌ Error: ${error.message}`]);
  }, []);

  const { isConnected: csvSSEConnected, connect: csvConnectSSE, disconnect: csvDisconnectSSE } = useJobSSE({
    onProgress: handleCsvProgress,
    onPosterCompleted: handleCsvPosterCompleted,
    onJobCompleted: handleCsvJobCompleted,
    onLog: handleCsvLog,
    onError: handleCsvSSEError
  });

  // Effect: When switching to expert mode, force single user mode
  useEffect(() => {
    if (userMode === 'expert') {
      setFlowMode('single');
    }
  }, [userMode]);

  // Check for edited posters returning from edit page
  useEffect(() => {
    const storedPosters = localStorage.getItem('posters');
    if (storedPosters) {
      try {
        const parsedPosters = JSON.parse(storedPosters);
        if (Array.isArray(parsedPosters) && parsedPosters.length > 0) {
          // Check if these are different from current posters
          if (JSON.stringify(parsedPosters) !== JSON.stringify(posters) && parsedPosters[0]?.html) {
            setPosters(parsedPosters);
            localStorage.removeItem('posters'); // Clean up
          }
        }
      } catch (error) {
        console.error('Failed to load edited posters:', error);
      }
    }
  }, []); // Only run on mount


  // Handle CSV file upload and parsing
  const handleCsvUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.csv')) {
      setError('Please upload a CSV file');
      return;
    }

    setCsvFile(file);

    // Parse CSV using Papa Parse (handles quoted fields, commas, and special characters)
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        if (!results.data || results.data.length === 0) {
          setError('CSV file must have at least one data row');
          setCsvMissingUserId(false);
          return;
        }

        // Extract headers from the first row's keys
        const headers = Object.keys(results.data[0] as any);
        setCsvColumns(headers);

        // user_id is now OPTIONAL - will fetch from Topmate API during generation if not provided
        const hasUserId = headers.some(h =>
          h.toLowerCase() === 'user_id' ||
          h.toLowerCase() === 'userid' ||
          h === 'User_ID'
        );

        if (!hasUserId) {
          setCsvMissingUserId(false);
          console.log('ℹ️ CSV does not have user_id - will fetch from Topmate API during generation');
        } else {
          setCsvMissingUserId(false);
          console.log('✅ CSV has user_id column - will use provided user_id');
        }
        setError(null);

        // Set the parsed data
        setCsvData(results.data as any[]);
        console.log(' [CSV] Parsed CSV with Papa Parse:', {
          headers,
          rowCount: results.data.length,
          sample: results.data[0],
          hasUserId
        });
      },
      error: (error) => {
        console.error('❌ [CSV] Parse error:', error);
        setError(`Failed to parse CSV: ${error.message}`);
        setCsvMissingUserId(false);
      }
    });
  };

  // Clear CSV and allow re-upload
  const handleClearCsv = () => {
    setCsvFile(null);
    setCsvData([]);
    setCsvColumns([]);
    setCsvTemplate('');
    setCsvPreview('');
    setCsvMissingUserId(false);
    setError(null);
  };

  // Handle image upload
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      setError('Please upload an image file');
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      setReferenceImage(event.target?.result as string);
      setReferenceSource('upload');
    };
    reader.readAsDataURL(file);
  };

  // Clear reference image
  const clearReferenceImage = () => {
    setReferenceImage(null);
    setReferenceSource(null);
  };

  // Select template image - fetch and convert to base64 for API compatibility
  const handleSelectTemplate = async (url: string) => {
    setShowTemplates(false);
    setError(null);

    try {
      // Fetch the image and convert to base64
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to load template image');

      const blob = await response.blob();
      const reader = new FileReader();

      reader.onload = (event) => {
        setReferenceImage(event.target?.result as string);
        setReferenceSource('template');
      };
      reader.onerror = () => {
        setError('Failed to load template image');
      };
      reader.readAsDataURL(blob);
    } catch (err) {
      console.error('Template load error:', err);
      setError('Failed to load template image. Try uploading instead.');
    }
  };

  // Load dynamic templates and fonts
  useEffect(() => {
    const loadResources = async () => {
      setIsLoadingTemplates(true);
      try {
        const templates = await getAllTemplates();
        const fonts = await fetchCustomFonts();
        setAllTemplates(templates);
        setCustomFonts(fonts);
      } catch (error) {
        console.error('Failed to load resources:', error);
      } finally {
        setIsLoadingTemplates(false);
      }
    };
    loadResources();
  }, []);

  // Admin: Upload template image
  const handleUploadTemplate = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file');
      return;
    }

    setUploadingTemplate(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', newTemplateName || file.name);
      formData.append('category', newTemplateCategory);
      formData.append('uploaded_by', 'admin');

      const response = await fetch(`${BACKEND_URL}/api/template-images/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (data.success) {
        // Reload templates
        const templates = await getAllTemplates();
        setAllTemplates(templates);
        setNewTemplateName('');
        alert('Template uploaded successfully!');
      } else {
        throw new Error(data.message || 'Upload failed');
      }
    } catch (error) {
      console.error('Template upload error:', error);
      alert('Failed to upload template');
    } finally {
      setUploadingTemplate(false);
    }
  };

  // Admin: Upload custom font
  const handleUploadFont = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    const validFormats = ['ttf', 'woff', 'woff2', 'otf'];
    
    if (!ext || !validFormats.includes(ext)) {
      alert(`Invalid font format. Supported: ${validFormats.join(', ')}`);
      return;
    }

    if (!newFontFamily.trim()) {
      alert('Please enter a font family name');
      return;
    }

    setUploadingFont(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('font_name', newFontName || file.name);
      formData.append('font_family', newFontFamily);
      formData.append('uploaded_by', 'admin');

      const response = await fetch(`${BACKEND_URL}/api/custom-fonts/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (data.success) {
        // Reload fonts
        const fonts = await fetchCustomFonts();
        setCustomFonts(fonts);
        setNewFontName('');
        setNewFontFamily('');
        alert('Font uploaded successfully!');
      } else {
        throw new Error(data.message || 'Upload failed');
      }
    } catch (error) {
      console.error('Font upload error:', error);
      alert('Failed to upload font');
    } finally {
      setUploadingFont(false);
    }
  };

  // Analyze prompt and fetch relevant data from Topmate API
  const handleAnalyzeData = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt first to analyze what data is needed');
      return;
    }

    if (!topmateUsername.trim()) {
      setError('Please enter a Topmate username first');
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    setDiscoveredProfile(null);
    setRelevantFields([]);
    setSelectedDataFields([]);

    try {
      // Step 1: Fetch Topmate profile data
      const profile = await fetchTopmateProfile(topmateUsername.trim());
      
      if (Object.keys(profile).length === 0) {
        setError('No profile data found for this username');
        setIsAnalyzing(false);
        return;
      }

      // Step 2: Build list of available fields with their data
      const availableFields: { field: string; value: any; description: string }[] = [];
      
      if (profile.display_name) {
        availableFields.push({ field: 'display_name', value: profile.display_name, description: 'Creator name' });
      }
      if (profile.bio) {
        availableFields.push({ field: 'bio', value: profile.bio, description: 'Bio/description' });
      }
      if (profile.total_bookings > 0) {
        availableFields.push({ field: 'total_bookings', value: profile.total_bookings, description: 'Total bookings count' });
      }
      if (profile.total_reviews > 0) {
        availableFields.push({ field: 'total_reviews', value: profile.total_reviews, description: 'Number of reviews' });
      }
      if (profile.average_rating > 0) {
        availableFields.push({ field: 'average_rating', value: profile.average_rating, description: 'Average rating' });
      }
      if (profile.services?.length > 0) {
        availableFields.push({ field: 'services', value: profile.services, description: `${profile.services.length} services offered` });
      }
      if (profile.badges?.length > 0) {
        availableFields.push({ field: 'badges', value: profile.badges, description: 'Achievement badges' });
      }
      if (profile.ai_testimonial_summary) {
        availableFields.push({ field: 'testimonials', value: profile.ai_testimonial_summary, description: 'Testimonial summary' });
      }
      if (profile.profile_pic) {
        availableFields.push({ field: 'profile_pic', value: profile.profile_pic, description: 'Profile picture URL' });
      }

      // Step 3: Use dedicated analyze-prompt endpoint to determine relevant fields
      try {
        const analyzeResponse = await apiFetch('/api/analyze-prompt', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: prompt.trim(),
            availableFields: availableFields.map(f => ({
              field: f.field,
              value: typeof f.value === 'object' ? JSON.stringify(f.value).slice(0, 100) : String(f.value).slice(0, 100),
              description: f.description
            }))
          })
        });

        if (!analyzeResponse.ok) {
          throw new Error('Failed to analyze prompt');
        }

        const analyzeData = await analyzeResponse.json();
        const validRelevantFields = analyzeData.relevantFields || [];
        
        console.log('AI Analysis result:', { 
          prompt: prompt.trim(),
          relevantFields: validRelevantFields,
          reasoning: analyzeData.reasoning 
        });

        // If no relevant fields found, default to display_name only
        if (validRelevantFields.length === 0) {
          validRelevantFields.push('display_name');
        }

        setDiscoveredProfile(profile);
        setRelevantFields(validRelevantFields); // Only these fields will be shown in UI
        setSelectedDataFields(validRelevantFields); // Pre-select all relevant fields
        
      } catch (analyzeError) {
        console.error('AI analysis error, using fallback:', analyzeError);
        // Fallback: show basic fields if AI fails
        const fallbackFields = ['display_name'];
        if (profile.bio) fallbackFields.push('bio');
        if (profile.profile_pic) fallbackFields.push('profile_pic');
        setDiscoveredProfile(profile);
        setRelevantFields(fallbackFields);
        setSelectedDataFields(fallbackFields);
      }
      
    } catch (error: any) {
      console.error('Topmate fetch error:', error);
      setError(error.message || 'Failed to fetch Topmate profile');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Toggle data field selection
  const toggleDataField = (field: string) => {
    setSelectedDataFields(prev => 
      prev.includes(field) 
        ? prev.filter(f => f !== field)
        : [...prev, field]
    );
  };

  // Generate poster
  const handleGenerate = async () => {
    // Validation: username required only in single mode
    if (flowMode === 'single' && !topmateUsername.trim()) {
      setError('Please enter a Topmate username');
      return;
    }

    // Validation for single mode
    if (flowMode === 'single' && !prompt.trim()) {
      setError('Please describe what poster you want');
      return;
    }

    setIsLoading(true);
    setError(null);

    // Get hardcoded Topmate logo
    const topmateLogo = getTopmateLogo();

    try {
      // SINGLE MODE: Generate with real profile using async SSE
      if (flowMode === 'single') {
        const config: PosterConfig = {
          topmateUsername: topmateUsername.trim(),
          style: 'professional' as PosterStyle,
          size: 'instagram-square' as PosterSize,
          mode: mode,
          carouselSlides: mode === 'carousel' ? slideCount : undefined,
          generationMode: generationMode, // HTML or Image
          prompt: prompt.trim() + (referenceImage ? '\n\nUse the uploaded reference image as design inspiration.' : ''),
          includeStats: true,
          includeBadges: true,
        };

        // Build selected profile data based on user's field selections
        const selectedProfileData = discoveredProfile && selectedDataFields.length > 0 ? {
          profile: discoveredProfile,
          selectedFields: selectedDataFields,
        } : undefined;

        // Reset progress state
        setGenerationProgress({ phase: 'starting', progress: 0 });
        setGenerationLogs(['Starting generation...']);

        // Step 1: Call API to start generation (returns immediately with SSE endpoint)
        const response = await apiFetch('/api/generate-poster', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            config,
            referenceImage: referenceImage || undefined,
            model: selectedModel, // 'pro' or 'flash'
            userMode: userMode, // 'expert' or 'admin'
            selectedProfileData: selectedProfileData,
            topmateLogo: topmateLogo, // Logo for branding
          }),
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || data.detail || 'Generation failed');
        }

        // Check if response has SSE endpoint (new async flow)
        if (data.sse_endpoint) {
          console.log('🔌 Connecting to SSE:', data.sse_endpoint);
          setGenerationLogs(prev => [...prev, 'Connecting to generation stream...']);
          
          // Connect to SSE for real-time updates
          const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';
          const sseUrl = `${BACKEND_URL}${data.sse_endpoint}`;
          const eventSource = new EventSource(sseUrl);
          
          // Handle SSE events
          await new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => {
              eventSource.close();
              reject(new Error('Generation timeout'));
            }, 180000); // 3 minute timeout
            
            eventSource.onopen = () => {
              console.log('✅ SSE connected for poster generation');
              setGenerationLogs(prev => [...prev, 'Connected! Generating variants...']);
            };
            
            eventSource.addEventListener('progress', (e) => {
              const progressData = JSON.parse(e.data);
              console.log('📈 Progress:', progressData);
              const phaseLabels: Record<string, string> = {
                'starting': 'Starting...',
                'queued': 'Queued',
                'fetching_profile': 'Fetching profile...',
                'analyzing_prompt': 'Analyzing prompt...',
                'generating': 'Generating designs...',
              };
              setGenerationProgress({
                phase: phaseLabels[progressData.phase] || progressData.phase,
                progress: Math.round((progressData.processed / progressData.total) * 100)
              });
            });
            
            eventSource.addEventListener('log', (e) => {
              const logData = JSON.parse(e.data);
              console.log(`📝 [${logData.level}] ${logData.message}`);
              if (logData.level !== 'DEBUG') {
                setGenerationLogs(prev => [...prev.slice(-9), logData.message]);
              }
            });
            
            eventSource.addEventListener('job_completed', (e) => {
              const result = JSON.parse(e.data);
              console.log('✅ Generation completed:', result);
              clearTimeout(timeout);
              eventSource.close();
              
              // Set the result
              if (result.mode === 'carousel' && result.carousels) {
                setCarousels(result.carousels);
                setSelectedVariant(0);
                setSelectedSlide(0);
                setPosters([]);
                setIsCarouselPreview(result.previewOnly || false);
                setTotalSlides(result.totalSlides || slideCount);
                if (result.carousels[0]?.[0]?.topmateProfile) {
                  setCarouselProfile(result.carousels[0][0].topmateProfile);
                }
              } else if (result.posters) {
                setPosters(result.posters);
                setSelectedIndex(0);
                setCarousels([]);
                setIsCarouselPreview(false);
              }
              setResultMode(result.mode || 'single');
              setGenerationProgress({ phase: 'Complete!', progress: 100 });
              resolve();
            });
            
            eventSource.addEventListener('job_failed', (e) => {
              const errorData = JSON.parse(e.data);
              console.error('❌ Generation failed:', errorData);
              clearTimeout(timeout);
              eventSource.close();
              reject(new Error(errorData.error || 'Generation failed'));
            });
            
            eventSource.onerror = (error) => {
              console.error('❌ SSE error:', error);
              // Don't reject immediately - might be normal close
              if (eventSource.readyState === EventSource.CLOSED) {
                // Check if we got results via polling
                setTimeout(async () => {
                  try {
                    const resultResponse = await apiFetch(`/api/generate-poster/${data.job_id}/result`, {
                      method: 'GET',
                    });
                    if (resultResponse.ok) {
                      const result = await resultResponse.json();
                      if (result.posters) {
                        setPosters(result.posters);
                        setSelectedIndex(0);
                        setCarousels([]);
                        setIsCarouselPreview(false);
                        setResultMode('single');
                        setGenerationProgress({ phase: 'Complete!', progress: 100 });
                        resolve();
                        return;
                      }
                    }
                  } catch {}
                  clearTimeout(timeout);
                  reject(new Error('Connection lost'));
                }, 1000);
              }
            };
          });
        } else {
          // Legacy sync response (fallback)
          if (data.mode === 'carousel') {
            setCarousels(data.carousels);
            setSelectedVariant(0);
            setSelectedSlide(0);
            setPosters([]);
            setIsCarouselPreview(data.previewOnly || false);
            setTotalSlides(data.totalSlides || slideCount);
            if (data.carousels[0]?.[0]?.topmateProfile) {
              setCarouselProfile(data.carousels[0][0].topmateProfile);
            }
          } else {
            setPosters(data.posters);
            setSelectedIndex(0);
            setCarousels([]);
            setIsCarouselPreview(false);
          }
          setResultMode(data.mode || 'single');
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate poster');
      setGenerationProgress(null);
    } finally {
      setIsLoading(false);
      // Clear progress after a short delay
      setTimeout(() => setGenerationProgress(null), 2000);
    }
  };

  // Copy HTML
  const handleCopyHtml = () => {
    if (poster?.html) {
      navigator.clipboard.writeText(poster.html);
    }
  };

  // Download single poster
  const handleDownload = async (format: 'png' | 'pdf') => {
    if (!poster?.html) return;

    setIsExporting(format);
    setError(null);

    try {
      const response = await apiFetch('/api/export-poster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          html: poster.html,
          format,
          width: poster.dimensions.width,
          height: poster.dimensions.height,
          scale: 2, // 2x for high-res PNG
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Export failed');
      }

      // Download the file
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const suffix = resultMode === 'carousel' ? `-slide${selectedIndex + 1}` : '';
      a.download = `poster${suffix}-${poster.dimensions.width}x${poster.dimensions.height}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(null);
    }
  };

  // Download all carousel slides as individual PNGs (for current variant)
  const handleDownloadAllPng = async () => {
    if (currentCarouselSlides.length === 0) return;

    setIsExporting('all-png');
    setError(null);

    try {
      const variantLabel = ['A', 'B', 'C', 'D'][selectedVariant] || selectedVariant + 1;
      for (let i = 0; i < currentCarouselSlides.length; i++) {
        const p = currentCarouselSlides[i];
        const response = await apiFetch('/api/export-poster', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            html: p.html,
            format: 'png',
            width: p.dimensions.width,
            height: p.dimensions.height,
            scale: 2,
          }),
        });

        if (!response.ok) continue;

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `carousel-${variantLabel}-slide-${i + 1}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        // Small delay between downloads
        await new Promise(r => setTimeout(r, 300));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(null);
    }
  };

  // Download carousel as multi-page PDF (for current variant)
  const handleDownloadCarouselPdf = async () => {
    if (currentCarouselSlides.length === 0) return;

    setIsExporting('pdf-carousel');
    setError(null);

    try {
      const variantLabel = ['A', 'B', 'C', 'D'][selectedVariant] || selectedVariant + 1;
      const response = await apiFetch('/api/export-poster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          html: currentCarouselSlides.map(p => p.html),
          format: 'pdf-multi',
          width: currentCarouselSlides[0].dimensions.width,
          height: currentCarouselSlides[0].dimensions.height,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Export failed');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `carousel-${variantLabel}-${currentCarouselSlides.length}slides.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(null);
    }
  };

  // Complete carousel - generate remaining slides for selected variant
  const handleCompleteCarousel = async () => {
    if (!isCarouselPreview || carousels.length === 0) return;

    const selectedFirstSlide = carousels[selectedVariant]?.[0];
    if (!selectedFirstSlide) return;

    setIsCompletingCarousel(true);
    setError(null);

    try {
      // Build selected profile data based on user's field selections
      const selectedProfileData = discoveredProfile && selectedDataFields.length > 0 ? {
        profile: discoveredProfile,
        selectedFields: selectedDataFields,
      } : undefined;

      const response = await apiFetch('/api/complete-carousel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          firstSlide: selectedFirstSlide.html,
          prompt: prompt.trim(),
          profile: carouselProfile || selectedFirstSlide.topmateProfile,
          totalSlides: totalSlides,
          variantIndex: selectedVariant,
          size: 'instagram-square',
          selectedProfileData: selectedProfileData,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to complete carousel');
      }

      // Update the selected carousel with all slides
      const newCarousels = [...carousels];
      newCarousels[selectedVariant] = data.slides;
      setCarousels(newCarousels);
      setIsCarouselPreview(false);
      setSelectedSlide(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete carousel');
    } finally {
      setIsCompletingCarousel(false);
    }
  };

  // ========== EDITING FUNCTIONS ==========

  // Setup iframe click listener
  const setupIframeListener = () => {
    const iframe = previewRef.current;
    if (iframe && iframe.contentDocument) {
      // Remove existing listener first
      iframe.contentDocument.removeEventListener('click', handleIframeClick as any);
      // Add new listener
      iframe.contentDocument.addEventListener('click', handleIframeClick as any);
      console.log('Iframe click listener attached');
    }
  };

  // Enable edit mode and setup iframe click listener
  const handleEnableEditMode = () => {
    setIsEditMode(true);
    setShowEditPanel(true);

    // Wait for iframe to be ready, then setup click listener
    setTimeout(() => {
      setupIframeListener();
    }, 100);
  };

  // Close edit panel (but keep edit mode active)
  const handleCloseEditPanel = () => {
    setShowEditPanel(false);
    // Don't disable edit mode - just hide the panel
  };

  // Disable edit mode completely
  const handleDisableEditMode = () => {
    setIsEditMode(false);
    setSelectedElement(null);
    setShowEditPanel(false);

    // Remove highlight
    const iframe = previewRef.current;
    if (iframe && iframe.contentDocument) {
      const existingHighlight = iframe.contentDocument.querySelector('.element-highlight');
      if (existingHighlight) {
        existingHighlight.remove();
      }

      // Remove click listener
      iframe.contentDocument.removeEventListener('click', handleIframeClick as any);
    }
  };

  // Navigate to dedicated edit page
  const handleOpenEditPage = () => {
    // Get current poster based on mode
    let currentPoster: GeneratedPoster | null = null;
    let posterIdx = 0;

    if (resultMode === 'single') {
      currentPoster = posters[selectedIndex] || null;
      posterIdx = selectedIndex;
    } else if (resultMode === 'carousel') {
      currentPoster = carousels[selectedVariant]?.[selectedSlide] || null;
      posterIdx = selectedSlide;
    }

    if (!currentPoster) {
      setError('No poster available to edit');
      return;
    }

    // Store poster data in localStorage for the edit page
    localStorage.setItem('editingPoster', JSON.stringify(currentPoster));
    localStorage.setItem('editingPosterIndex', posterIdx.toString());

    // Store all posters for saving back later
    if (resultMode === 'single') {
      localStorage.setItem('posters', JSON.stringify(posters));
    } else {
      localStorage.setItem('posters', JSON.stringify(carousels[selectedVariant] || []));
    }

    // Navigate to edit page
    router.push('/edit-poster');
  };

  // Handle click inside iframe to select element
  const handleIframeClick = (e: MouseEvent) => {
    if (!isEditMode) return;

    e.preventDefault();
    e.stopPropagation();

    const target = e.target as HTMLElement;
    if (!target || target.tagName === 'HTML' || target.tagName === 'BODY') return;

    // Extract element data
    const elementData = {
      selector: generateSelector(target),
      tag: target.tagName.toLowerCase(),
      classes: Array.from(target.classList),
      text: target.textContent?.trim().substring(0, 100) || '',
      outer_html: target.outerHTML.substring(0, 500),
      color_classes: Array.from(target.classList).filter(c =>
        c.startsWith('bg-') || c.startsWith('text-') || c.startsWith('border-')
      ),
    };

    setSelectedElement(elementData);

    // Add visual highlight
    highlightElement(target);

    console.log('Selected element:', elementData);
  };

  // Generate CSS selector for an element
  const generateSelector = (element: HTMLElement): string => {
    if (element.id) {
      return `#${element.id}`;
    }

    const path: string[] = [];
    let current: HTMLElement | null = element;

    while (current && current.tagName !== 'HTML') {
      let selector = current.tagName.toLowerCase();

      // Add classes if present
      if (current.classList.length > 0) {
        selector += '.' + Array.from(current.classList).join('.');
      }

      // Add nth-child if needed for specificity
      if (current.parentElement) {
        const siblings = Array.from(current.parentElement.children);
        const index = siblings.indexOf(current) + 1;
        if (siblings.length > 1) {
          selector += `:nth-child(${index})`;
        }
      }

      path.unshift(selector);
      current = current.parentElement;
    }

    return path.join(' > ');
  };

  // Visual highlight for selected element
  const highlightElement = (element: HTMLElement) => {
    // Remove previous highlights
    const iframe = previewRef.current;
    if (!iframe || !iframe.contentDocument) return;

    const existingHighlight = iframe.contentDocument.querySelector('.element-highlight');
    if (existingHighlight) {
      existingHighlight.remove();
    }

    // Add new highlight
    const highlight = iframe.contentDocument.createElement('div');
    highlight.className = 'element-highlight';
    highlight.style.cssText = `
      position: absolute;
      pointer-events: none;
      border: 2px solid #3b82f6;
      background: rgba(59, 130, 246, 0.1);
      z-index: 10000;
      transition: all 0.2s;
    `;

    const rect = element.getBoundingClientRect();
    highlight.style.top = `${rect.top + iframe.contentWindow!.scrollY}px`;
    highlight.style.left = `${rect.left + iframe.contentWindow!.scrollX}px`;
    highlight.style.width = `${rect.width}px`;
    highlight.style.height = `${rect.height}px`;

    iframe.contentDocument.body.appendChild(highlight);
  };

  // Handle edit submission
  const handleEditSubmit = async () => {
    if (!editInstruction.trim()) {
      setError('Please enter an edit instruction');
      return;
    }

    // Get current poster
    const currentPoster = resultMode === 'single'
      ? posters[selectedIndex]
      : carousels[selectedVariant]?.[selectedSlide];

    if (!currentPoster || !currentPoster.html) {
      setError('No poster selected to edit');
      return;
    }

    setIsEditing(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/edit-poster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          html: currentPoster.html,
          edit_instruction: editInstruction,
          selected_element: selectedElement,
          design_context: null,
        }),
      });

      // Check content type before parsing
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const text = await response.text();
        console.error('Non-JSON response:', text);
        throw new Error('Server returned non-JSON response. Check backend logs.');
      }

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Failed to edit poster');
      }

      // Update poster with edited HTML
      const updatedPoster = { ...currentPoster, html: data.html };

      // Add to edit history
      const historyEntry = {
        timestamp: new Date().toISOString(),
        instruction: editInstruction,
        summary: data.summary,
        previousHtml: currentPoster.html,
        newHtml: data.html,
      };
      setEditHistory([...editHistory, historyEntry]);

      // Add to chat messages
      setEditMessages([
        ...editMessages,
        { role: 'user', content: editInstruction },
        { role: 'assistant', content: data.summary || 'Edit completed' },
      ]);

      // Update poster
      if (resultMode === 'single') {
        const newPosters = [...posters];
        newPosters[selectedIndex] = updatedPoster;
        setPosters(newPosters);
      } else {
        const newCarousels = [...carousels];
        newCarousels[selectedVariant][selectedSlide] = updatedPoster;
        setCarousels(newCarousels);
      }

      // Clear instruction and selected element
      setEditInstruction('');
      setSelectedElement(null);

      // Re-attach iframe listener after HTML updates
      setTimeout(() => {
        setupIframeListener();
      }, 200);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to edit poster');
    } finally {
      setIsEditing(false);
    }
  };

  // Undo last edit
  const handleUndoEdit = () => {
    if (editHistory.length === 0) return;

    const lastEdit = editHistory[editHistory.length - 1];
    const updatedPoster = { ...poster, html: lastEdit.previousHtml };

    // Update poster
    if (resultMode === 'single') {
      const newPosters = [...posters];
      newPosters[selectedIndex] = updatedPoster;
      setPosters(newPosters);
    } else {
      const newCarousels = [...carousels];
      newCarousels[selectedVariant][selectedSlide] = updatedPoster;
      setCarousels(newCarousels);
    }

    // Remove from history
    setEditHistory(editHistory.slice(0, -1));
  };

  // Dimensions for preview
  const dimensions = POSTER_SIZE_DIMENSIONS['instagram-square'];
  const previewScale = Math.min(500 / dimensions.width, 500 / dimensions.height, 1);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div>
                <h1 className="text-xl font-bold text-slate-900">Poster Creator</h1>
                <p className="text-sm text-slate-500">Create posters from Topmate profiles</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Templates Button - Only show in Admin mode */}
              {userMode === 'admin' && (
                <>
                  <button
                    onClick={() => router.push('/templates')}
                    className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-lg text-sm font-medium transition-all flex items-center gap-2 shadow-sm"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Templates
                  </button>
                  
                  {/* Upload Button */}
                  <button
                    onClick={() => setShowAdminUpload(true)}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-all flex items-center gap-2 shadow-sm"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    Upload
                  </button>
                </>
              )}

              {/* User Mode Toggle */}
              <div className="flex items-center gap-2 bg-slate-100 rounded-lg p-1">
                <button
                  onClick={() => setUserMode('expert')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                    userMode === 'expert'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Expert
                </button>
                <button
                  onClick={() => setUserMode('admin')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                    userMode === 'admin'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Admin
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Flow Mode Selector - Only show in Admin mode */}
      {userMode === 'admin' && (
        <div className="max-w-5xl mx-auto px-4 pt-6 pb-2">
          <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4">
            <label className="block text-sm font-medium text-slate-700 mb-3">Generation Flow</label>
            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => setFlowMode('single')}
                className={`px-6 py-3 rounded-lg font-medium transition ${
                  flowMode === 'single'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                Single User
              </button>
              <button
                onClick={() => setFlowMode('bulk')}
                className={`px-6 py-3 rounded-lg font-medium transition ${
                  flowMode === 'bulk'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                Bulk Generation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Unified Form for Both Modes */}
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left: Form */}
          <div className="space-y-6">
            {/* Topmate Username - Only show in single mode */}
            {flowMode === 'single' && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Topmate Username
                </label>
                <div className="flex items-center">
                  <span className="px-3 py-2 bg-slate-100 border border-r-0 border-slate-300 rounded-l-lg text-slate-500 text-sm">
                    topmate.io/
                  </span>
                  <input
                    type="text"
                    value={topmateUsername}
                    onChange={(e) => setTopmateUsername(e.target.value)}
                    placeholder="username"
                    className="flex-1 px-3 py-2 border border-slate-300 rounded-r-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
              </div>
            )}

            {/* Bulk Mode Section */}
            {flowMode === 'bulk' && (
              <>
                {/* Info Banner - CSV Bulk Generation */}
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                  <div className="flex items-start">
                    <div className="flex-shrink-0">
                      <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-blue-800"> CSV Bulk Generation Flow</h3>
                      <p className="mt-1 text-sm text-blue-700">
                        <strong>Step 1:</strong> Upload CSV file with your data (must include "username" column).<br />
                        <strong>Step 2:</strong> Create HTML template using CSV column names as placeholders.<br />
                        <strong>Step 3:</strong> Preview, name your campaign, and generate posters for all rows.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}


            {/* Reference Image - Hide in bulk CSV mode */}
            {flowMode !== 'bulk' && flowMode !== 'template' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-slate-700">
                  Design Reference (Optional)
                </label>
                {referenceImage && (
                  <button
                    onClick={clearReferenceImage}
                    className="text-xs text-red-500 hover:text-red-600 font-medium"
                  >
                    Clear
                  </button>
                )}
              </div>

              {referenceImage ? (
                <div className="relative">
                  <img
                    src={referenceImage}
                    alt="Reference"
                    className="w-full h-48 object-cover rounded-lg border border-slate-200"
                  />
                  <div className="absolute top-2 left-2 px-2 py-1 bg-black/60 text-white text-xs rounded">
                    {referenceSource === 'template' ? 'Template' : 'Custom Upload'}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Upload Option */}
                  <label className="flex items-center gap-3 w-full p-3 border-2 border-dashed border-slate-300 rounded-lg cursor-pointer hover:border-indigo-500 hover:bg-indigo-50 transition-colors">
                    <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    <span className="text-sm text-slate-600">Upload your own image</span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleImageUpload}
                      className="hidden"
                    />
                  </label>

                  {/* Template Toggle */}
                  <button
                    onClick={() => setShowTemplates(!showTemplates)}
                    className="flex items-center justify-between w-full p-3 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                      </svg>
                      <span className="text-sm text-slate-600">Choose from templates</span>
                    </div>
                    <svg className={`w-5 h-5 text-slate-400 transition-transform ${showTemplates ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {/* Template Gallery */}
                  {showTemplates && (
                    <div className="grid grid-cols-4 gap-2 max-h-64 overflow-y-auto p-1">
                      {isLoadingTemplates ? (
                        <div className="col-span-4 text-center py-8 text-slate-500">
                          Loading templates...
                        </div>
                      ) : (
                        allTemplates.map((template) => (
                          <button
                            key={template.id}
                            onClick={() => handleSelectTemplate(template.url)}
                            className="aspect-square rounded-lg overflow-hidden border-2 border-transparent hover:border-indigo-500 transition-all hover:scale-105 bg-slate-100"
                          >
                            <img
                              src={template.url}
                              alt={template.name}
                              loading="lazy"
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                const target = e.target as HTMLImageElement;
                                target.style.display = 'none';
                              }}
                            />
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
            )}

            {/* Prompt - Show for single mode only */}
            {flowMode === 'single' && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  What poster do you want?
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder={mode === 'carousel'
                    ? "e.g., 5 tips for landing your first tech job..."
                    : "e.g., A bold poster promoting 1:1 mentorship sessions with dark theme and neon accents..."}
                  rows={4}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
                />

              {/* Analyze Data Button - Only in Single User Mode and Admin Mode */}
              {flowMode === 'single' && userMode === 'admin' && (
                <button
                  onClick={handleAnalyzeData}
                  disabled={isAnalyzing || !topmateUsername.trim() || !prompt.trim()}
                  className="mt-3 w-full py-2 px-4 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  {isAnalyzing ? (
                    <>
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Analyzing & Fetching Data...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                      </svg>
                      Analyze Prompt & Fetch Relevant Data
                    </>
                  )}
                </button>
              )}

              {/* Discovered Topmate Profile Data - Only in Single User Mode and Admin Mode */}
              {flowMode === 'single' && userMode === 'admin' && discoveredProfile && (
                <div className="mt-4 border-t border-slate-200 pt-4">
                  <h3 className="text-sm font-medium text-slate-700 mb-3 flex items-center gap-2">
                    <svg className="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Relevant Data for Your Poster ({selectedDataFields.length} fields selected)
                  </h3>
                  
                  {/* Profile Header */}
                  <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg mb-3">
                    {discoveredProfile.profile_pic && (
                      <img 
                        src={discoveredProfile.profile_pic} 
                        alt={discoveredProfile.display_name}
                        className="w-12 h-12 rounded-full object-cover"
                      />
                    )}
                    <div>
                      <h4 className="font-medium text-slate-800">{discoveredProfile.display_name}</h4>
                      <p className="text-xs text-slate-600">@{discoveredProfile.username}</p>
                    </div>
                  </div>

                  {/* Selectable Data Fields - Only show fields AI determined are relevant */}
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {/* Bio */}
                    {discoveredProfile.bio && relevantFields.includes('bio') && (
                      <label className={`flex items-start gap-2 p-2 rounded-lg cursor-pointer transition-all border ${
                        selectedDataFields.includes('bio') 
                          ? 'bg-emerald-50 border-emerald-300' 
                          : 'bg-white border-slate-200 hover:border-emerald-200'
                      }`}>
                        <input
                          type="checkbox"
                          checked={selectedDataFields.includes('bio')}
                          onChange={() => toggleDataField('bio')}
                          className="mt-1 w-4 h-4 accent-emerald-600"
                        />
                        <div className="flex-1">
                          <span className="text-xs font-medium text-slate-600">Bio:</span>
                          <p className="text-xs text-slate-800">{discoveredProfile.bio.substring(0, 100)}...</p>
                        </div>
                      </label>
                    )}

                    {/* Stats */}
                    {discoveredProfile.total_bookings > 0 && relevantFields.includes('total_bookings') && (
                      <label className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all border ${
                        selectedDataFields.includes('total_bookings') 
                          ? 'bg-emerald-50 border-emerald-300' 
                          : 'bg-white border-slate-200 hover:border-emerald-200'
                      }`}>
                        <input
                          type="checkbox"
                          checked={selectedDataFields.includes('total_bookings')}
                          onChange={() => toggleDataField('total_bookings')}
                          className="w-4 h-4 accent-emerald-600"
                        />
                        <span className="text-xs"><strong>Bookings:</strong> {discoveredProfile.total_bookings.toLocaleString()}</span>
                      </label>
                    )}

                    {discoveredProfile.total_reviews > 0 && relevantFields.includes('total_reviews') && (
                      <label className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all border ${
                        selectedDataFields.includes('total_reviews') 
                          ? 'bg-emerald-50 border-emerald-300' 
                          : 'bg-white border-slate-200 hover:border-emerald-200'
                      }`}>
                        <input
                          type="checkbox"
                          checked={selectedDataFields.includes('total_reviews')}
                          onChange={() => toggleDataField('total_reviews')}
                          className="w-4 h-4 accent-emerald-600"
                        />
                        <span className="text-xs"><strong>Reviews:</strong> {discoveredProfile.total_reviews} ({discoveredProfile.average_rating}/5 ⭐)</span>
                      </label>
                    )}

                    {/* Services */}
                    {discoveredProfile.services?.length > 0 && relevantFields.includes('services') && (
                      <label className={`flex items-start gap-2 p-2 rounded-lg cursor-pointer transition-all border ${
                        selectedDataFields.includes('services') 
                          ? 'bg-emerald-50 border-emerald-300' 
                          : 'bg-white border-slate-200 hover:border-emerald-200'
                      }`}>
                        <input
                          type="checkbox"
                          checked={selectedDataFields.includes('services')}
                          onChange={() => toggleDataField('services')}
                          className="mt-1 w-4 h-4 accent-emerald-600"
                        />
                        <div className="flex-1">
                          <span className="text-xs font-medium text-slate-600">Services ({discoveredProfile.services.length}):</span>
                          <p className="text-xs text-slate-800">
                            {discoveredProfile.services.slice(0, 3).map((s: any) => s.title).join(', ')}
                            {discoveredProfile.services.length > 3 && '...'}
                          </p>
                        </div>
                      </label>
                    )}

                    {/* Badges */}
                    {discoveredProfile.badges?.length > 0 && relevantFields.includes('badges') && (
                      <label className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all border ${
                        selectedDataFields.includes('badges') 
                          ? 'bg-emerald-50 border-emerald-300' 
                          : 'bg-white border-slate-200 hover:border-emerald-200'
                      }`}>
                        <input
                          type="checkbox"
                          checked={selectedDataFields.includes('badges')}
                          onChange={() => toggleDataField('badges')}
                          className="w-4 h-4 accent-emerald-600"
                        />
                        <span className="text-xs"><strong>Badges:</strong> {discoveredProfile.badges.map((b: any) => b.name).join(', ')}</span>
                      </label>
                    )}

                    {/* Testimonials */}
                    {discoveredProfile.ai_testimonial_summary && relevantFields.includes('testimonials') && (
                      <label className={`flex items-start gap-2 p-2 rounded-lg cursor-pointer transition-all border ${
                        selectedDataFields.includes('testimonials') 
                          ? 'bg-emerald-50 border-emerald-300' 
                          : 'bg-white border-slate-200 hover:border-emerald-200'
                      }`}>
                        <input
                          type="checkbox"
                          checked={selectedDataFields.includes('testimonials')}
                          onChange={() => toggleDataField('testimonials')}
                          className="mt-1 w-4 h-4 accent-emerald-600"
                        />
                        <div className="flex-1">
                          <span className="text-xs font-medium text-slate-600">Testimonial Summary:</span>
                          <p className="text-xs text-slate-800">{discoveredProfile.ai_testimonial_summary.substring(0, 100)}...</p>
                        </div>
                      </label>
                    )}
                  </div>
                  
                  <div className="mt-3 flex items-center gap-3">
                    {selectedDataFields.length > 0 && (
                      <button
                        onClick={() => setSelectedDataFields([])}
                        className="text-xs text-slate-600 hover:text-slate-800 underline"
                      >
                        Clear selection
                      </button>
                    )}
                    
                    {/* Show all fields button */}
                    {relevantFields.length < 6 && (
                      <button
                        onClick={() => {
                          const allFields: string[] = [];
                          if (discoveredProfile.bio) allFields.push('bio');
                          if (discoveredProfile.total_bookings > 0) allFields.push('total_bookings');
                          if (discoveredProfile.total_reviews > 0) allFields.push('total_reviews');
                          if (discoveredProfile.services?.length > 0) allFields.push('services');
                          if (discoveredProfile.badges?.length > 0) allFields.push('badges');
                          if (discoveredProfile.ai_testimonial_summary) allFields.push('testimonials');
                          if (discoveredProfile.profile_pic) allFields.push('profile_pic');
                          setRelevantFields(allFields);
                        }}
                        className="text-xs text-blue-600 hover:text-blue-800 underline"
                      >
                        Show all available fields
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
            )}

            {/* CSV Upload Mode - Show for bulk CSV mode */}
            {flowMode === 'bulk' && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Step 1: Upload CSV File
                </label>
                <p className="text-xs text-slate-500 mb-3">
                  CSV must include a "username" column. Other columns will be mapped to template placeholders.
                </p>

                <label className="flex items-center gap-3 w-full p-4 border-2 border-dashed border-slate-300 rounded-lg cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-colors">
                  <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <div className="flex-1">
                    {csvFile ? (
                      <div>
                        <span className="text-sm font-medium text-green-700">✅ {csvFile.name}</span>
                        <p className="text-xs text-slate-500 mt-1">
                          {csvData.length} rows, {csvColumns.length} columns: {csvColumns.join(', ')}
                        </p>
                      </div>
                    ) : (
                      <span className="text-sm text-slate-600">Click to upload CSV file</span>
                    )}
                  </div>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleCsvUpload}
                    className="hidden"
                  />
                </label>

                {/* user_id is now optional - will be fetched from Topmate API during generation */}

                {csvFile && csvData.length > 0 && (
                  <>
                    <div className="mt-4">
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Step 2: HTML Template with Placeholders
                      </label>
                      <p className="text-xs text-slate-500 mb-3">
                        Use <code className="bg-slate-100 px-1 py-0.5 rounded">{`{column_name}`}</code> syntax. Available columns: {csvColumns.map(col => <code key={col} className="bg-slate-100 px-1 py-0.5 rounded mx-1">{`{${col}}`}</code>)}
                      </p>

                      {/* Custom Dimensions */}
                      <div className="mb-3 flex gap-4">
                        <div className="flex-1">
                          <label className="block text-xs font-medium text-slate-600 mb-1">Width (px)</label>
                          <input
                            type="number"
                            value={csvCustomWidth}
                            onChange={(e) => setCsvCustomWidth(parseInt(e.target.value) || 1080)}
                            className="w-full px-2 py-1 text-sm border border-slate-300 rounded focus:ring-1 focus:ring-blue-500"
                          />
                        </div>
                        <div className="flex-1">
                          <label className="block text-xs font-medium text-slate-600 mb-1">Height (px)</label>
                          <input
                            type="number"
                            value={csvCustomHeight}
                            onChange={(e) => setCsvCustomHeight(parseInt(e.target.value) || 1350)}
                            className="w-full px-2 py-1 text-sm border border-slate-300 rounded focus:ring-1 focus:ring-blue-500"
                          />
                        </div>
                      </div>

                      {/* Skip Overlays Option */}
                      <div className="mb-3 flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                        <input
                          type="checkbox"
                          id="csvSkipOverlays"
                          checked={csvSkipOverlays}
                          onChange={(e) => setCsvSkipOverlays(e.target.checked)}
                          className="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-2 focus:ring-blue-500"
                        />
                        <label htmlFor="csvSkipOverlays" className="text-xs text-slate-700 cursor-pointer">
                          <strong>Skip automatic logo/profile overlays</strong> - Check this if your template already includes logo and profile images
                        </label>
                      </div>

                      <textarea
                        value={csvTemplate}
                        onChange={(e) => setCsvTemplate(e.target.value)}
                        placeholder={`<!DOCTYPE html>
<html>
<head>
  <style>
    .poster { width: 1080px; height: 1080px; padding: 40px; background: #667eea; color: white; font-family: Arial; }
    .profile-img { width: 100px; height: 100px; border-radius: 50%; }
    .name { font-size: 48px; font-weight: bold; margin: 20px 0; }
  </style>
</head>
<body>
  <div class="poster">
    <img class="profile-img" src="{profile_pic}" alt="Profile">
    <div class="name">{name}</div>
    <div>{email}</div>
    <div> {total_sales} Sales</div>
  </div>
</body>
</html>`}
                        rows={12}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none font-mono text-xs"
                      />

                      {/* Auto-conversion info */}
                      <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <div className="flex items-start gap-2">
                          <svg className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <div className="text-xs text-blue-800">
                            <strong>Auto-Conversion:</strong> Your HTML will be automatically processed to remove JavaScript and convert dynamic image loading to CSV placeholders. You can paste HTML with <code className="bg-blue-100 px-1 rounded">id="profilePic"</code> and it will work!
                          </div>
                        </div>
                      </div>

                      {csvTemplate.trim() && (
                        <>
                          <button
                            onClick={() => {
                              // Preview with first row data
                              const firstRow = csvData[0];
                              let preview = csvTemplate;
                              csvColumns.forEach(col => {
                                const regex = new RegExp(`\\{${col}\\}`, 'g');
                                preview = preview.replace(regex, firstRow[col] || '');
                              });
                              setCsvPreview(preview);
                            }}
                            className="mt-3 w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                            {csvPreview ? 'Update Preview' : 'Preview with First Row'}
                          </button>

                          {csvPreview && (
                            <div className="mt-4">
                              <div className="flex items-center justify-between mb-2">
                                <label className="text-sm font-medium text-slate-700">Template Preview (First Row Data)</label>
                                <button
                                  onClick={() => setCsvPreview('')}
                                  className="text-xs text-red-500 hover:text-red-600 font-medium"
                                >
                                  Hide Preview
                                </button>
                              </div>
                              <div className="border-2 border-slate-300 rounded-lg overflow-hidden bg-slate-50 p-4 flex justify-center">
                                <div style={{
                                  width: `${csvCustomWidth * 0.5}px`,
                                  height: `${csvCustomHeight * 0.5}px`,
                                  transform: 'scale(0.5)',
                                  transformOrigin: 'top left',
                                  border: '1px solid #e2e8f0'
                                }}>
                                  <iframe
                                    srcDoc={csvPreview}
                                    className="w-full h-full border-0"
                                    style={{ width: `${csvCustomWidth}px`, height: `${csvCustomHeight}px`, pointerEvents: 'none' }}
                                    title="CSV Preview"
                                    sandbox="allow-same-origin allow-scripts"
                                  />
                                </div>
                              </div>
                              <p className="mt-2 text-xs text-slate-500 text-center">
                                Preview with first row data. Will generate for all {csvData.length} rows.
                              </p>

                              {/* Campaign Name */}
                              <div className="mt-6 p-4 bg-slate-50 rounded-lg border-2 border-slate-200">
                                <label className="block text-sm font-medium text-slate-700 mb-2">
                                  Step 3: Campaign Name
                                </label>
                                <input
                                  type="text"
                                  value={csvCampaignName}
                                  onChange={(e) => setCsvCampaignName(e.target.value)}
                                  placeholder="e.g., Q4 Sales Campaign"
                                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                                />
                              </div>

                              {/* Generate Button */}
                              <button
                                onClick={async () => {
                                  if (!csvCampaignName.trim()) {
                                    alert('Please enter a campaign name');
                                    return;
                                  }

                                  setIsCsvGenerating(true);
                                  setCsvGeneratedResults([]);
                                  setCsvProgress({ processed: 0, total: csvData.length, percentage: 0 });
                                  setCsvLogs(['🚀 Starting CSV bulk generation...']);
                                  setShowCsvLogs(true);
                                  setError(null);

                                  try {
                                    const topmateLogo = getTopmateLogo();

                                    const response = await apiFetch('/api/generate-bulk', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({
                                        bulkMethod: 'csv',
                                        csvTemplate: csvTemplate,
                                        csvData: csvData,
                                        csvColumns: csvColumns,
                                        posterName: csvCampaignName.trim(),
                                        size: 'custom',
                                        customWidth: csvCustomWidth,
                                        customHeight: csvCustomHeight,
                                        skipOverlays: csvSkipOverlays,
                                        topmateLogo: csvSkipOverlays ? null : topmateLogo,
                                      }),
                                    });

                                    const data = await response.json();

                                    if (!response.ok) {
                                      throw new Error(data.error || 'Generation failed');
                                    }

                                    // Check if response has jobId (RedPanda queue mode)
                                    if (data.success && data.jobId) {
                                      console.log('🔗 [CSV] Connecting to SSE for job:', data.jobId);
                                      console.log('✅ [CSV] Setting csvJobId state:', data.jobId);
                                      setCsvJobId(data.jobId);

                                      // BACKUP: Store in localStorage to prevent loss
                                      localStorage.setItem('lastCsvJobId', data.jobId);
                                      console.log('💾 [CSV] Saved jobId to localStorage:', data.jobId);

                                      setCsvLogs(prev => [...prev, `📋 Job created: ${data.jobId}`, '📡 Connecting to SSE for real-time updates...']);
                                      
                                      // Connect to SSE for real-time progress
                                      csvConnectSSE(data.jobId);
                                    } else if (data.results) {
                                      // Fallback: Direct results (old mode)
                                      setCsvGeneratedResults(data.results);
                                      setIsCsvGenerating(false);
                                    }
                                  } catch (err) {
                                    setError(err instanceof Error ? err.message : 'Generation failed');
                                    setIsCsvGenerating(false);
                                    setCsvLogs(prev => [...prev, `❌ Error: ${err instanceof Error ? err.message : 'Generation failed'}`]);
                                  }
                                }}
                                disabled={isCsvGenerating || !csvCampaignName.trim()}
                                className="mt-4 w-full py-3 px-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                              >
                                {isCsvGenerating ? (
                                  <>
                                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    Generating for {csvData.length} rows...
                                  </>
                                ) : (
                                  <>
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Generate {csvData.length} Posters from CSV
                                  </>
                                )}
                              </button>

                              {/* Progress Bar and Logs for CSV Generation */}
                              {isCsvGenerating && (
                                <div className="mt-4 p-4 bg-slate-50 rounded-lg border-2 border-slate-200">
                                  {/* Progress Bar */}
                                  <div className="mb-3">
                                    <div className="flex justify-between text-sm text-slate-600 mb-1">
                                      <span>Processing posters...</span>
                                      <span>{csvProgress.processed} / {csvProgress.total} ({csvProgress.percentage}%)</span>
                                    </div>
                                    <div className="w-full bg-slate-200 rounded-full h-3">
                                      <div 
                                        className="bg-gradient-to-r from-purple-600 to-pink-600 h-3 rounded-full transition-all duration-300"
                                        style={{ width: `${csvProgress.percentage}%` }}
                                      />
                                    </div>
                                  </div>
                                  
                                  {/* SSE Connection Status */}
                                  <div className="flex items-center gap-2 text-xs text-slate-500 mb-2">
                                    <span className={`w-2 h-2 rounded-full ${csvSSEConnected ? 'bg-green-500' : 'bg-yellow-500'}`} />
                                    {csvSSEConnected ? 'Connected to real-time updates' : 'Connecting...'}
                                  </div>
                                  
                                  {/* Toggle Logs */}
                                  <button
                                    onClick={() => setShowCsvLogs(!showCsvLogs)}
                                    className="text-xs text-purple-600 hover:text-purple-800 flex items-center gap-1"
                                  >
                                    <svg className={`w-3 h-3 transition-transform ${showCsvLogs ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                    {showCsvLogs ? 'Hide' : 'Show'} console logs ({csvLogs.length})
                                  </button>
                                  
                                  {/* Console Logs */}
                                  {showCsvLogs && (
                                    <div className="mt-2 bg-slate-900 text-green-400 p-3 rounded-lg text-xs font-mono max-h-48 overflow-y-auto">
                                      {csvLogs.map((log, idx) => (
                                        <div key={idx} className="py-0.5">{log}</div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* CSV Generated Results */}
                              {csvGeneratedResults.length > 0 && (
                                <div className="mt-6 p-4 bg-white rounded-lg border-2 border-green-200">
                                  <h3 className="text-sm font-medium text-slate-700 mb-4">
                                    Generated Posters ({csvGeneratedResults.filter(r => r.success).length} successful)
                                  </h3>

                                  <div className="grid grid-cols-2 gap-4 max-h-96 overflow-y-auto mb-4">
                                    {csvGeneratedResults.map((result, idx) => (
                                      <div key={idx} className="border rounded-lg p-2">
                                        {result.success ? (
                                          <>
                                            <img
                                              src={result.posterUrl}
                                              alt={result.username}
                                              className="w-full rounded"
                                            />
                                            <p className="text-xs font-medium mt-2">✅ {result.username}</p>
                                          </>
                                        ) : (
                                          <div className="p-4 text-center">
                                            <p className="text-xs font-medium text-red-600">❌ {result.username}</p>
                                            <p className="text-xs text-red-500 mt-1">{result.error}</p>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>

                                  {/* Save to Database */}
                                  <button
                                    onClick={async () => {
                                      console.log('🚨🚨🚨 [SAVE BUTTON v3] NEW CODE ACTIVE - WITH SSE WAIT 🚨🚨🚨');
                                      setIsSharing(true);
                                      setCsvSaveProgress(null); // Reset progress
                                      try {
                                        // Get jobId from state or localStorage fallback
                                        const jobIdToUse = csvJobId || localStorage.getItem('lastCsvJobId');
                                        console.log(`📥 [PosterCreator v3] csvJobId state: ${csvJobId}`);
                                        console.log(`📥 [PosterCreator v3] localStorage backup: ${localStorage.getItem('lastCsvJobId')}`);
                                        console.log(`📥 [PosterCreator v3] Using jobId: ${jobIdToUse}`);

                                        if (!jobIdToUse) {
                                          alert('❌ Error: Job ID not found. Please generate posters first.');
                                          setIsSharing(false);
                                          return;
                                        }

                                        // FIXED: Fetch posters from backend WITH userId from database metadata
                                        console.log(`📥 [PosterCreator v2] Fetching posters with userId for job: ${jobIdToUse}`);

                                        const postersResponse = await apiFetch(`/api/batch/jobs/${jobIdToUse}/posters-for-save`);
                                        const postersData = await postersResponse.json();

                                        if (!postersData.success) {
                                          throw new Error(postersData.error || 'Failed to fetch posters');
                                        }

                                        const postersToSave = postersData.posters;
                                        console.log(`✅ [PosterCreator v2] Fetched ${postersToSave.length} posters with userId:`, postersToSave);

                                        if (postersToSave.length === 0) {
                                          alert('No posters available to save');
                                          setIsSharing(false);
                                          return;
                                        }

                                        // Check for missing user_id
                                        if (postersData.totalMissingUserId > 0) {
                                          const proceed = confirm(
                                            `⚠️ Warning: ${postersData.totalMissingUserId} posters are missing user_id.\n\n` +
                                            `${postersData.warning}\n\n` +
                                            `Proceed with ${postersData.totalPosters} posters that have user_id?`
                                          );
                                          if (!proceed) {
                                            setIsSharing(false);
                                            return;
                                          }
                                        }

                                        const response = await apiFetch('/api/save-bulk-posters', {
                                          method: 'POST',
                                          headers: { 'Content-Type': 'application/json' },
                                          body: JSON.stringify({
                                            posters: postersToSave,
                                            posterName: csvCampaignName.trim(),
                                          }),
                                        });

                                        const data = await response.json();

                                        if (!response.ok || !data.success || !data.jobId) {
                                          throw new Error(data.error || 'Save failed');
                                        }

                                        const saveJobId = data.jobId;
                                        console.log(`✅ [PosterCreator v3] Save job started: ${saveJobId}`);
                                        console.log(`🔌 [PosterCreator v3] Connecting to SSE: ${data.sseEndpoint}`);

                                        // Connect to SSE for real-time save progress
                                        const sseUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${data.sseEndpoint}`;
                                        const eventSource = new EventSource(sseUrl);

                                        eventSource.onopen = () => {
                                          console.log('✅ [PosterCreator v3] SSE CONNECTED - Waiting for events...');
                                        };

                                        eventSource.addEventListener('progress', (event) => {
                                          const progressData = JSON.parse(event.data);
                                          console.log(`💾 [PosterCreator v3] PROGRESS EVENT: ${progressData.processed}/${progressData.total} (${progressData.success} success, ${progressData.failed} failed)`);
                                          setCsvSaveProgress({
                                            processed: progressData.processed,
                                            total: progressData.total,
                                            success: progressData.success,
                                            failed: progressData.failed
                                          });
                                        });

                                        eventSource.addEventListener('complete', (event) => {
                                          console.log('🎉 [PosterCreator v3] COMPLETE EVENT RECEIVED!');
                                          const completeData = JSON.parse(event.data);
                                          const { success, failed, total } = completeData;

                                          eventSource.close();
                                          console.log(`✅ [PosterCreator v3] Save Complete: ${success}/${total} saved successfully, ${failed} failed`);

                                          // Only show success if at least some succeeded
                                          if (success > 0) {
                                            console.log('✅ [PosterCreator v3] Setting csvSaveSuccess = TRUE (success > 0)');
                                            setCsvSaveSuccess(true);
                                            setCsvSavedConfig({
                                              campaign: csvCampaignName.trim(),
                                              content_type: "image"
                                            });
                                          } else {
                                            console.log('❌ [PosterCreator v3] NOT setting success - all failed!');
                                            alert(`❌ Save Failed!\n\n0 out of ${total} posters were saved successfully.\nAll ${failed} posters failed.\n\nCheck backend logs for details.`);
                                          }

                                          setIsSharing(false);
                                        });

                                        eventSource.onerror = (error) => {
                                          console.error('❌ SSE error during save:', error);
                                          eventSource.close();
                                          alert('❌ Connection lost during save. Please check if posters were saved.');
                                          setIsSharing(false);
                                        };

                                      } catch (err) {
                                        alert(`❌ Error: ${err instanceof Error ? err.message : 'Save failed'}`);
                                        setIsSharing(false);
                                      }
                                    }}
                                    disabled={isSharing}
                                    className="w-full py-3 px-4 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                                  >
                                    {isSharing ? (
                                      <>
                                        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                        {csvSaveProgress ? (
                                          `Saving ${csvSaveProgress.processed}/${csvSaveProgress.total} (${csvSaveProgress.success} ✓, ${csvSaveProgress.failed} ✗)`
                                        ) : (
                                          'Saving...'
                                        )}
                                      </>
                                    ) : (
                                      <>
                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                                        </svg>
                                        Save {csvGeneratedResults.filter(r => r.success).length} Posters to Database
                                      </>
                                    )}
                                  </button>
                                </div>
                              )}

                              {/* Success Message with Configuration */}
                              {csvSaveSuccess && csvSavedConfig && (
                                <div className="mt-6 p-6 bg-green-50 border-2 border-green-500 rounded-lg">
                                  <div className="flex items-start gap-3 mb-4">
                                    <svg className="w-6 h-6 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <div className="flex-1">
                                      <h4 className="text-lg font-semibold text-green-800 mb-2">
                                        ✅ Successfully Saved to Database!
                                      </h4>
                                      <p className="text-sm text-green-700 mb-4">
                                        All posters have been saved to UserShareContent. Now copy the configuration below and paste it in Django Admin.
                                      </p>

                                      <div className="bg-white rounded-lg p-4 border border-green-300">
                                        <div className="flex items-center justify-between mb-2">
                                          <label className="text-sm font-semibold text-slate-700">
                                            📋 Django Admin Configuration
                                          </label>
                                          <button
                                            onClick={() => {
                                              navigator.clipboard.writeText(JSON.stringify(csvSavedConfig, null, 2));
                                              alert('✅ Copied to clipboard!');
                                            }}
                                            className="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
                                          >
                                            Copy
                                          </button>
                                        </div>
                                        <pre className="bg-slate-900 text-green-400 p-3 rounded text-xs overflow-x-auto font-mono">
{JSON.stringify(csvSavedConfig, null, 2)}
                                        </pre>
                                      </div>

                                      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                                        <p className="text-xs text-blue-800">
                                          <strong>Next Step:</strong> Go to Django Admin →
                                          <a href="http://localhost:8000/admin/sharing/sharingposttemplate/add/" target="_blank" className="underline ml-1">
                                            Create SharingPostTemplate
                                          </a> →
                                          Paste this in the <strong>Configuration</strong> field
                                        </p>
                                      </div>

                                      <button
                                        onClick={() => {
                                          setCsvSaveSuccess(false);
                                          setCsvSavedConfig(null);
                                          setCsvGeneratedResults([]);
                                          setCsvCampaignName('');
                                          setCsvFile(null);
                                          setCsvData([]);
                                          setCsvColumns([]);
                                          setCsvTemplate('');
                                          setCsvPreview('');
                                        }}
                                        className="mt-4 w-full py-2 px-4 bg-slate-600 hover:bg-slate-700 text-white font-medium rounded-lg transition-colors"
                                      >
                                        Create New Campaign
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* HTML Template section removed - only AI Prompt and CSV modes supported */}
            {false && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  HTML Template with Placeholders
                </label>
                <p className="text-xs text-slate-500 mb-3">
                  Use placeholders like: <code className="bg-slate-100 px-1 py-0.5 rounded">{`{display_name}`}</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">{`{username}`}</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">{`{profile_pic}`}</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">{`{bio}`}</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">{`{total_bookings}`}</code>, <code className="bg-slate-100 px-1 py-0.5 rounded">{`{average_rating}`}</code>
                </p>
                <textarea
                  value={htmlTemplate}
                  onChange={(e) => setHtmlTemplate(e.target.value)}
                  placeholder={`<!DOCTYPE html>
<html>
<head>
  <style>
    .poster { width: 1080px; height: 1080px; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; font-family: Arial; }
    .profile-img { width: 100px; height: 100px; border-radius: 50%; }
    .name { font-size: 48px; font-weight: bold; margin: 20px 0; }
    .stats { font-size: 24px; margin: 10px 0; }
  </style>
</head>
<body>
  <div class="poster">
    <img class="profile-img" src="{profile_pic}" alt="Profile">
    <div class="name">{display_name}</div>
    <div class="bio">{bio}</div>
    <div class="stats"> {total_bookings} Bookings | ⭐ {average_rating}/5</div>
  </div>
</body>
</html>`}
                  rows={12}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none font-mono text-xs"
                />

                {/* Preview Template Button */}
                {htmlTemplate.trim() && (
                  <>
                    <button
                      onClick={() => {
                        // Create preview with dummy data
                        const dummyPreviewHTML = htmlTemplate
                          .replace(/{display_name}/g, 'John Doe')
                          .replace(/{username}/g, 'johndoe')
                          .replace(/{profile_pic}/g, 'https://via.placeholder.com/150/667eea/FFFFFF?text=JD')
                          .replace(/{bio}/g, 'Professional mentor helping people achieve their goals')
                          .replace(/{total_bookings}/g, '487')
                          .replace(/{average_rating}/g, '4.9')
                          .replace(/{first_name}/g, 'John')
                          .replace(/{last_name}/g, 'Doe')
                          .replace(/{total_reviews}/g, '142')
                          .replace(/{expertise_category}/g, 'Business & Marketing');

                        setHtmlPreview(dummyPreviewHTML);
                      }}
                      className="mt-3 w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      {htmlPreview ? 'Update Preview' : 'Preview Template with Dummy Data'}
                    </button>

                    {/* Inline Preview - Scaled down fixed size */}
                    {htmlPreview && (
                      <div className="mt-4">
                        <div className="flex items-center justify-between mb-2">
                          <label className="text-sm font-medium text-slate-700">Template Preview (Dummy Data)</label>
                          <button
                            onClick={() => setHtmlPreview('')}
                            className="text-xs text-red-500 hover:text-red-600 font-medium"
                          >
                            Hide Preview
                          </button>
                        </div>
                        <div className="border-2 border-slate-300 rounded-lg overflow-hidden bg-slate-50 p-4 flex justify-center">
                          <div style={{
                            width: '540px',
                            height: '540px',
                            transform: 'scale(0.5)',
                            transformOrigin: 'top left',
                            border: '1px solid #e2e8f0'
                          }}>
                            <iframe
                              srcDoc={htmlPreview}
                              className="w-full h-full border-0"
                              style={{ width: '1080px', height: '1080px', pointerEvents: 'none' }}
                              title="HTML Preview"
                              sandbox="allow-same-origin allow-scripts"
                            />
                          </div>
                        </div>
                        <p className="mt-2 text-xs text-slate-500 text-center">
                          Preview scaled to 50%. Real data will be used during generation.
                        </p>

                        {/* Campaign Name and Users Input */}
                        <div className="mt-6 space-y-4">
                          {/* Campaign Name */}
                          <div className="p-4 bg-slate-50 rounded-lg border-2 border-slate-200">
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                              Step 2: Campaign Name
                            </label>
                            <input
                              type="text"
                              value={htmlCampaignName}
                              onChange={(e) => setHtmlCampaignName(e.target.value)}
                              placeholder="e.g., Summer Mentorship Promo"
                              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                            />
                          </div>

                          {/* User IDs */}
                          <div className="p-4 bg-slate-50 rounded-lg border-2 border-slate-200">
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                              Step 3: Enter Topmate Users
                            </label>
                            <p className="text-xs text-slate-500 mb-3">
                              Enter usernames or user IDs (comma-separated)
                            </p>
                            <textarea
                              value={htmlTemplateUsers}
                              onChange={(e) => setHtmlTemplateUsers(e.target.value)}
                              placeholder="john_doe, 12345, sarah_coach, 67890"
                              rows={3}
                              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none text-sm"
                            />
                          </div>

                          {/* Generate Button */}
                          <button
                            onClick={async () => {
                              if (!htmlCampaignName.trim()) {
                                alert('Please enter a campaign name');
                                return;
                              }
                              if (!htmlTemplateUsers.trim()) {
                                alert('Please enter at least one username or user ID');
                                return;
                              }

                              setIsHtmlGenerating(true);
                              setHtmlGeneratedResults([]);
                              setError(null);

                              try {
                                const topmateLogo = getTopmateLogo();

                                const response = await apiFetch('/api/generate-bulk', {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({
                                    htmlTemplate: htmlTemplate,
                                    bulkMethod: 'html',
                                    userIdentifiers: htmlTemplateUsers.trim(),
                                    posterName: htmlCampaignName.trim(),
                                    size: 'instagram-square',
                                    topmateLogo: topmateLogo,
                                  }),
                                });

                                const data = await response.json();

                                if (!response.ok) {
                                  throw new Error(data.error || 'Generation failed');
                                }

                                setHtmlGeneratedResults(data.results || []);
                              } catch (err) {
                                setError(err instanceof Error ? err.message : 'Generation failed');
                              } finally {
                                setIsHtmlGenerating(false);
                              }
                            }}
                            disabled={isHtmlGenerating || !htmlCampaignName.trim() || !htmlTemplateUsers.trim()}
                            className="w-full py-3 px-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                          >
                            {isHtmlGenerating ? (
                              <>
                                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                Generating...
                              </>
                            ) : (
                              <>
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                                Generate Posters
                              </>
                            )}
                          </button>
                        </div>

                        {/* Generated Posters Preview */}
                        {htmlGeneratedResults.length > 0 && (
                          <div className="mt-6 p-4 bg-white rounded-lg border-2 border-green-200">
                            <h3 className="text-sm font-medium text-slate-700 mb-4">
                              Generated Posters Preview ({htmlGeneratedResults.filter(r => r.success).length} successful)
                            </h3>

                            <div className="grid grid-cols-2 gap-4 max-h-96 overflow-y-auto mb-4">
                              {htmlGeneratedResults.map((result, idx) => (
                                <div key={idx} className="border rounded-lg p-2">
                                  {result.success ? (
                                    <>
                                      <img
                                        src={result.posterUrl}
                                        alt={result.username}
                                        className="w-full rounded"
                                      />
                                      <p className="text-xs font-medium mt-2">✅ @{result.username}</p>
                                      <p className="text-xs text-slate-500">ID: {result.userId}</p>
                                    </>
                                  ) : (
                                    <div className="p-4 text-center">
                                      <p className="text-xs font-medium text-red-600">❌ @{result.username}</p>
                                      <p className="text-xs text-red-500 mt-1">{result.error}</p>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>

                            {/* Save to Database Button */}
                            <button
                              onClick={async () => {
                                setIsSharing(true);
                                try {
                                  const successfulResults = htmlGeneratedResults.filter(r => r.success);

                                  const response = await apiFetch('/api/save-bulk-posters', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                      posters: successfulResults.map((r: any) => ({
                                        userId: r.userId,
                                        username: r.username,
                                        posterUrl: r.posterUrl,
                                      })),
                                      posterName: htmlCampaignName.trim(),
                                    }),
                                  });

                                  const data = await response.json();

                                  if (!response.ok) {
                                    throw new Error(data.error || 'Save failed');
                                  }

                                  // Show success message with configuration
                                  setHtmlSaveSuccess(true);
                                  setHtmlSavedConfig({
                                    campaign: htmlCampaignName.trim(),
                                    content_type: "image"
                                  });
                                } catch (err) {
                                  alert(`❌ Error: ${err instanceof Error ? err.message : 'Save failed'}`);
                                } finally {
                                  setIsSharing(false);
                                }
                              }}
                              disabled={isSharing}
                              className="w-full py-3 px-4 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                            >
                              {isSharing ? (
                                <>
                                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                  </svg>
                                  Saving...
                                </>
                              ) : (
                                <>
                                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                                  </svg>
                                  Save {htmlGeneratedResults.filter(r => r.success).length} Posters to Database
                                </>
                              )}
                            </button>

                            {/* Success Message with Configuration */}
                            {htmlSaveSuccess && htmlSavedConfig && (
                              <div className="mt-6 p-6 bg-green-50 border-2 border-green-500 rounded-lg">
                                <div className="flex items-start gap-3 mb-4">
                                  <svg className="w-6 h-6 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                  </svg>
                                  <div className="flex-1">
                                    <h4 className="text-lg font-semibold text-green-800 mb-2">
                                      ✅ Successfully Saved to Database!
                                    </h4>
                                    <p className="text-sm text-green-700 mb-4">
                                      All posters have been saved to UserShareContent. Now copy the configuration below and paste it in Django Admin.
                                    </p>

                                    <div className="bg-white rounded-lg p-4 border border-green-300">
                                      <div className="flex items-center justify-between mb-2">
                                        <label className="text-sm font-semibold text-slate-700">
                                          📋 Django Admin Configuration
                                        </label>
                                        <button
                                          onClick={() => {
                                            navigator.clipboard.writeText(JSON.stringify(htmlSavedConfig, null, 2));
                                            alert('✅ Copied to clipboard!');
                                          }}
                                          className="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
                                        >
                                          Copy
                                        </button>
                                      </div>
                                      <pre className="bg-slate-900 text-green-400 p-3 rounded text-xs overflow-x-auto font-mono">
{JSON.stringify(htmlSavedConfig, null, 2)}
                                      </pre>
                                    </div>

                                    <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                                      <p className="text-xs text-blue-800">
                                        <strong>Next Step:</strong> Go to Django Admin →
                                        <a href="http://localhost:8000/admin/sharing/sharingposttemplate/add/" target="_blank" className="underline ml-1">
                                          Create SharingPostTemplate
                                        </a> →
                                        Paste this in the <strong>Configuration</strong> field
                                      </p>
                                    </div>

                                    <button
                                      onClick={() => {
                                        setHtmlSaveSuccess(false);
                                        setHtmlSavedConfig(null);
                                        setHtmlGeneratedResults([]);
                                        setHtmlCampaignName('');
                                        setHtmlTemplateUsers('');
                                      }}
                                      className="mt-4 w-full py-2 px-4 bg-slate-600 hover:bg-slate-700 text-white font-medium rounded-lg transition-colors"
                                    >
                                      Create New Campaign
                                    </button>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Mode Toggle - Hide in CSV template mode and Expert mode */}
            {flowMode !== 'bulk' && userMode === 'admin' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <label className="block text-sm font-medium text-slate-700 mb-3">
                Output Type
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setMode('single')}
                  className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
                    mode === 'single'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  Single Poster
                </button>
                <button
                  onClick={() => setMode('carousel')}
                  className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
                    mode === 'carousel'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  Carousel
                </button>
              </div>

              {mode === 'carousel' && (
                <div className="mt-4">
                  <label className="block text-sm text-slate-600 mb-2">
                    Number of slides: {slideCount}
                  </label>
                  <input
                    type="range"
                    min={3}
                    max={10}
                    value={slideCount}
                    onChange={(e) => setSlideCount(Number(e.target.value))}
                    className="w-full accent-indigo-600"
                  />
                  <div className="flex justify-between text-xs text-slate-400 mt-1">
                    <span>3</span>
                    <span>10</span>
                  </div>
                </div>
              )}
            </div>
            )}

            {/* Model Selection - Hide in CSV template mode and Expert mode */}
            {flowMode !== 'bulk' && userMode === 'admin' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <label className="block text-sm font-medium text-slate-700 mb-3">
                AI Model
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setSelectedModel('pro')}
                  className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
                    selectedModel === 'pro'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  <div className="flex flex-col items-center">
                    <span>Gemini 3 Pro</span>
                    <span className="text-xs opacity-75">Best quality</span>
                  </div>
                </button>
                <button
                  onClick={() => setSelectedModel('flash')}
                  className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
                    selectedModel === 'flash'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  <div className="flex flex-col items-center">
                    <span>Gemini 3 Flash</span>
                    <span className="text-xs opacity-75">Faster</span>
                  </div>
                </button>
              </div>
            </div>
            )}

            {/* Generation Mode Toggle - Hide in CSV template mode and Expert mode */}
            {flowMode !== 'bulk' && userMode === 'admin' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <label className="block text-sm font-medium text-slate-700 mb-3">
                Generation Method
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setGenerationMode('html')}
                  className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
                    generationMode === 'html'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  <div className="flex flex-col items-center">
                    <span>HTML/CSS</span>
                    <span className="text-xs opacity-75">Classic (Gemini 3)</span>
                  </div>
                </button>
                <button
                  onClick={() => setGenerationMode('image')}
                  className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-sm transition-all ${
                    generationMode === 'image'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  <div className="flex flex-col items-center">
                    <span>Direct Image</span>
                    <span className="text-xs opacity-75">New (Nano Banana)</span>
                  </div>
                </button>
              </div>
              <p className="mt-3 text-xs text-slate-500">
                {generationMode === 'html'
                  ? 'Generates HTML/CSS code, then renders to image (slower, better typography)'
                  : 'Directly generates image using Gemini 2.5 Flash Image (faster, experimental)'}
              </p>
            </div>
            )}

            {/* Generate Button - Hide in CSV template mode (has its own flow) */}
            {flowMode !== 'bulk' && (
            <>
            <button
              onClick={handleGenerate}
              disabled={
                isLoading ||
                (flowMode === 'single' && (!topmateUsername.trim() || !prompt.trim()))
              }
              className="w-full py-4 px-6 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-xl hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  {flowMode === 'bulk'
                    ? 'Generating Templates...'
                    : mode === 'carousel'
                      ? 'Generating 3 variants...'
                      : 'Generating 3 variations...'}
                </span>
              ) : (
                flowMode === 'bulk'
                  ? 'Generate Templates'
                  : mode === 'carousel'
                    ? `Generate ${slideCount}-Slide Carousel`
                    : 'Generate Posters'
              )}
            </button>

            {/* Progress Bar - Shows during AI generation with SSE */}
            {isLoading && generationProgress && generationProgress.phase && (
              <div className="mt-4 p-4 bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-purple-700">
                    {generationProgress.phase}
                  </span>
                  <span className="text-sm font-bold text-purple-600">
                    {generationProgress.progress}%
                  </span>
                </div>
                <div className="w-full bg-purple-100 rounded-full h-3 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${generationProgress.progress}%` }}
                  />
                </div>
                {/* Show recent logs */}
                {generationLogs && generationLogs.length > 0 && (
                  <div className="mt-3 max-h-20 overflow-y-auto text-xs text-slate-600 space-y-1">
                    {generationLogs.slice(-3).map((log, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className="text-purple-400">→</span>
                        <span>{log}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {error}
              </div>
            )}
            </>
            )}
          </div>

          {/* Right: Preview and Edit Panel */}
          <div className={`${isEditMode && showEditPanel ? 'flex gap-4' : ''}`}>
            {/* Preview Container */}
            <div className={`bg-white rounded-xl shadow-sm border border-slate-200 p-6 ${isEditMode && showEditPanel ? 'flex-1' : ''}`}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">
                {resultMode === 'carousel'
                  ? `Variant ${['A', 'B', 'C', 'D'][selectedVariant]} - Slide ${selectedSlide + 1} of ${currentCarouselSlides.length}`
                  : 'Preview'}
              </h2>
              {poster && (
                <div className="flex items-center gap-2 flex-wrap justify-end">
                  {/* Single slide PNG */}
                  <button
                    onClick={() => handleDownload('png')}
                    disabled={isExporting !== null}
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
                  >
                    {isExporting === 'png' ? (
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    )}
                    PNG
                  </button>

                  {/* Carousel-specific: Download all PNGs */}
                  {resultMode === 'carousel' && (
                    <button
                      onClick={handleDownloadAllPng}
                      disabled={isExporting !== null}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      {isExporting === 'all-png' ? (
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                      )}
                      All PNGs
                    </button>
                  )}

                  {/* Carousel-specific: Multi-page PDF */}
                  {resultMode === 'carousel' && (
                    <button
                      onClick={handleDownloadCarouselPdf}
                      disabled={isExporting !== null}
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:bg-rose-400 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      {isExporting === 'pdf-carousel' ? (
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                      )}
                      PDF
                    </button>
                  )}

                  {/* Single mode: single PDF */}
                  {resultMode === 'single' && (
                    <button
                      onClick={() => handleDownload('pdf')}
                      disabled={isExporting !== null}
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:bg-rose-400 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      {isExporting === 'pdf' ? (
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                      )}
                      PDF
                    </button>
                  )}

                  {/* Edit in New Page - Production Edit Mode */}
                  {/* Edit Poster */}
                  <button
                    onClick={handleOpenEditPage}
                    className="px-3 py-1.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-sm font-medium rounded-lg transition-all shadow-md hover:shadow-lg flex items-center gap-1.5"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    Edit Poster
                  </button>

                  {/* Share to Topmate */}
                  <button
                    onClick={() => setShowTopmateShare(true)}
                    className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                    </svg>
                    Share to Topmate
                  </button>

                  <button
                    onClick={handleCopyHtml}
                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors"
                  >
                    HTML
                  </button>
                </div>
              )}
            </div>

            {/* Main Preview */}
            <div className="flex items-center justify-center bg-slate-100 rounded-lg min-h-[400px] p-4">
              {poster ? (
                <div className="shadow-2xl max-w-full max-h-full">
                  {poster.generationMode === 'image' && poster.imageUrl ? (
                    <img
                      src={poster.imageUrl}
                      alt="Generated Poster"
                      style={{
                        width: dimensions.width * previewScale,
                        height: dimensions.height * previewScale,
                        maxWidth: '100%',
                        maxHeight: '100%',
                        objectFit: 'contain',
                      }}
                      className="border-0 rounded-lg"
                    />
                  ) : poster.html ? (
                    <div
                      style={{
                        width: dimensions.width * previewScale,
                        height: dimensions.height * previewScale,
                      }}
                    >
                      <iframe
                        ref={previewRef}
                        srcDoc={poster.html}
                        onLoad={() => {
                          if (isEditMode) {
                            setupIframeListener();
                          }
                        }}
                        style={{
                          width: dimensions.width,
                          height: dimensions.height,
                          transform: `scale(${previewScale})`,
                          transformOrigin: 'top left',
                          pointerEvents: isEditMode ? 'auto' : 'none',
                          cursor: isEditMode ? 'pointer' : 'default',
                        }}
                        className={`border-0 ${isEditMode ? 'ring-2 ring-purple-500' : ''}`}
                        title="Poster Preview"
                      />
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="text-center text-slate-400 p-8">
                  <svg className="w-16 h-16 mx-auto mb-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <p className="font-medium">Your posters will appear here</p>
                </div>
              )}
            </div>

            {/* Single Mode: Variant Thumbnails */}
            {resultMode === 'single' && posters.length > 1 && (
              <div className="mt-4">
                <p className="text-sm text-slate-500 mb-2">Choose a variation:</p>
                <div className="grid gap-2 grid-cols-3">
                  {posters.map((p, index) => {
                    const thumbScale = 0.1;
                    return (
                      <button
                        key={index}
                        onClick={() => setSelectedIndex(index)}
                        className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                          selectedIndex === index
                            ? 'border-indigo-500 ring-2 ring-indigo-200'
                            : 'border-slate-200 hover:border-slate-300'
                        }`}
                        style={{
                          width: dimensions.width * thumbScale,
                          height: dimensions.height * thumbScale,
                        }}
                      >
                        {p.generationMode === 'image' && p.imageUrl ? (
                          <img
                            src={p.imageUrl}
                            alt={`Variant ${index + 1}`}
                            style={{
                              width: '100%',
                              height: '100%',
                              objectFit: 'cover',
                              pointerEvents: 'none',
                            }}
                            className="border-0"
                          />
                        ) : p.html ? (
                          <iframe
                            srcDoc={p.html}
                            style={{
                              width: dimensions.width,
                              height: dimensions.height,
                              transform: `scale(${thumbScale})`,
                              transformOrigin: 'top left',
                              pointerEvents: 'none',
                            }}
                            className="border-0"
                            title={`Variant ${index + 1}`}
                          />
                        ) : null}
                        <div className={`absolute inset-0 flex items-end justify-center pb-1 bg-gradient-to-t from-black/50 to-transparent ${
                          selectedIndex === index ? 'opacity-100' : 'opacity-0 hover:opacity-100'
                        } transition-opacity`}>
                          <span className="text-white text-xs font-medium">
                            {['A', 'B', 'C'][index]}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Carousel Mode: Variant Selection + Slide Thumbnails */}
            {resultMode === 'carousel' && carousels.length > 0 && (
              <div className="mt-4 space-y-4">
                {/* Preview Mode Notice + Complete Button */}
                {isCarouselPreview && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                    <p className="text-sm text-amber-800 mb-3">
                      <strong>Preview mode:</strong> Pick your favorite style, then generate all {totalSlides} slides.
                    </p>
                    <button
                      onClick={handleCompleteCarousel}
                      disabled={isCompletingCarousel}
                      className="w-full py-3 px-4 bg-gradient-to-r from-amber-500 to-orange-500 text-white font-semibold rounded-lg hover:from-amber-600 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                    >
                      {isCompletingCarousel ? (
                        <>
                          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          Generating {totalSlides} slides...
                        </>
                      ) : (
                        <>
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          Generate Full Carousel ({totalSlides} slides)
                        </>
                      )}
                    </button>
                  </div>
                )}

                {/* Variant Selection (A, B, C) */}
                <div>
                  <p className="text-sm text-slate-500 mb-2">
                    {isCarouselPreview ? 'Choose a style:' : 'Style Variant:'}
                  </p>
                  <div className="flex gap-2">
                    {carousels.map((_, variantIdx) => (
                      <button
                        key={variantIdx}
                        onClick={() => {
                          setSelectedVariant(variantIdx);
                          setSelectedSlide(0); // Reset to first slide
                        }}
                        className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                          selectedVariant === variantIdx
                            ? 'bg-indigo-600 text-white'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {['A', 'B', 'C'][variantIdx]}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Slide Thumbnails for Selected Variant (only show if not preview or has multiple slides) */}
                {(!isCarouselPreview || currentCarouselSlides.length > 1) && (
                <div>
                  <p className="text-sm text-slate-500 mb-2">Slides:</p>
                  <div className="grid gap-2 grid-cols-5">
                    {currentCarouselSlides.map((p, slideIdx) => {
                      const thumbScale = 0.06;
                      return (
                        <button
                          key={slideIdx}
                          onClick={() => setSelectedSlide(slideIdx)}
                          className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                            selectedSlide === slideIdx
                              ? 'border-indigo-500 ring-2 ring-indigo-200'
                              : 'border-slate-200 hover:border-slate-300'
                          }`}
                          style={{
                            width: dimensions.width * thumbScale,
                            height: dimensions.height * thumbScale,
                          }}
                        >
                          {p.generationMode === 'image' && p.imageUrl ? (
                            <img
                              src={p.imageUrl}
                              alt={`Slide ${slideIdx + 1}`}
                              style={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'cover',
                                pointerEvents: 'none',
                              }}
                              className="border-0"
                            />
                          ) : p.html ? (
                            <iframe
                              srcDoc={p.html}
                              style={{
                                width: dimensions.width,
                                height: dimensions.height,
                                transform: `scale(${thumbScale})`,
                                transformOrigin: 'top left',
                                pointerEvents: 'none',
                              }}
                              className="border-0"
                              title={`Slide ${slideIdx + 1}`}
                            />
                          ) : null}
                          <div className={`absolute inset-0 flex items-end justify-center pb-1 bg-gradient-to-t from-black/50 to-transparent ${
                            selectedSlide === slideIdx ? 'opacity-100' : 'opacity-0 hover:opacity-100'
                          } transition-opacity`}>
                            <span className="text-white text-xs font-medium">
                              {slideIdx + 1}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
                )}
              </div>
            )}
          </div>

          {/* Edit Panel - Right Side */}
          {showEditPanel && poster && (
            <div className="w-96 bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden flex-shrink-0">
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-purple-50">
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  <h3 className="font-semibold text-slate-900">Edit</h3>
                </div>
                <button
                  onClick={handleCloseEditPanel}
                  className="p-1 hover:bg-purple-100 rounded transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="flex flex-col h-[calc(100vh-300px)] max-h-[600px]">
                {/* Selected Element Info */}
                <div className="p-4 border-b border-slate-200">
                  <h4 className="text-sm font-semibold text-slate-700 mb-2">Selected Element</h4>
                  {selectedElement ? (
                    <div className="p-3 bg-indigo-50 border border-indigo-100 rounded-lg">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-indigo-900">&lt;{selectedElement.tag}&gt;</p>
                          <p className="text-xs text-indigo-700 truncate mt-1">{selectedElement.selector}</p>
                          {selectedElement.text && (
                            <p className="text-xs text-indigo-600 mt-1 truncate">"{selectedElement.text}"</p>
                          )}
                        </div>
                        <button
                          onClick={() => setSelectedElement(null)}
                          className="text-indigo-600 hover:text-indigo-800"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                      <p className="text-xs text-slate-500">Click on the poster to select an element</p>
                    </div>
                  )}

                  {/* Edit History */}
                  {editHistory.length > 0 && (
                    <div className="mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-semibold text-slate-700">History ({editHistory.length})</h4>
                        <button
                          onClick={handleUndoEdit}
                          className="text-xs text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                          </svg>
                          Undo
                        </button>
                      </div>
                      <div className="space-y-1 max-h-32 overflow-y-auto">
                        {editHistory.slice(-5).reverse().map((edit, idx) => (
                          <div key={idx} className="text-xs text-slate-600 p-2 bg-slate-50 rounded">
                            • {edit.summary}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Chat Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-slate-50">
                  {editMessages.length === 0 ? (
                    <div className="text-center text-slate-400 py-8">
                      <p className="text-xs">Describe your changes and AI will edit the selected element</p>
                    </div>
                  ) : (
                    editMessages.map((msg, idx) => (
                      <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-lg px-3 py-2 ${
                          msg.role === 'user'
                            ? 'bg-purple-600 text-white'
                            : 'bg-white text-slate-900 border border-slate-200'
                        }`}>
                          <p className="text-xs">{msg.content}</p>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Edit Input */}
                <div className="p-4 border-t border-slate-200 bg-white">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={editInstruction}
                      onChange={(e) => setEditInstruction(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter' && !isEditing && editInstruction.trim()) {
                          handleEditSubmit();
                        }
                      }}
                      placeholder={selectedElement ? "Describe your change..." : "Select an element first..."}
                      disabled={isEditing || !selectedElement}
                      className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:bg-slate-100"
                    />
                    <button
                      onClick={handleEditSubmit}
                      disabled={!editInstruction.trim() || isEditing || !selectedElement}
                      className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      {isEditing ? (
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                      )}
                    </button>
                  </div>

                  {error && (
                    <p className="text-xs text-red-600 bg-red-50 p-2 rounded mt-2">{error}</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      </div>

      {/* Topmate Share Modal */}
      {showTopmateShare && poster?.topmateProfile && (
        <TopmateShare
          posterHtml={poster.html}
          posterImageUrl={poster.imageUrl}
          profileUserId={poster.topmateProfile.user_id}
          displayName={poster.topmateProfile.display_name}
          flowMode={flowMode}
          bulkMethod={bulkMethod}
          htmlTemplate={htmlTemplate}
          htmlTemplateUsers={htmlTemplateUsers}
          prompt={prompt}
          selectedProfileData={discoveredProfile && selectedDataFields.length > 0 ? { profile: discoveredProfile, selectedFields: selectedDataFields } : undefined}
          size="instagram-square"
          model={selectedModel}
          onClose={() => setShowTopmateShare(false)}
        />
      )}

      {/* Admin Upload Modal */}
      {showAdminUpload && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">Admin Upload</h2>
              <button
                onClick={() => setShowAdminUpload(false)}
                className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Upload Template Image */}
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 hover:border-purple-500 transition-colors">
                <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  Upload Template Image
                </h3>
                
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Template Name</label>
                    <input
                      type="text"
                      value={newTemplateName}
                      onChange={(e) => setNewTemplateName(e.target.value)}
                      placeholder="e.g., Modern Gradient"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Category</label>
                    <select
                      value={newTemplateCategory}
                      onChange={(e) => setNewTemplateCategory(e.target.value as any)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="minimal">Minimal</option>
                      <option value="bold">Bold</option>
                      <option value="gradient">Gradient</option>
                      <option value="photo">Photo</option>
                    </select>
                  </div>

                  <label className="block">
                    <div className="w-full px-4 py-3 bg-purple-50 border-2 border-purple-200 rounded-lg cursor-pointer hover:bg-purple-100 transition-colors text-center">
                      <svg className="w-6 h-6 mx-auto mb-2 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                      </svg>
                      <span className="text-sm font-medium text-purple-700">
                        {uploadingTemplate ? 'Uploading...' : 'Choose Image File'}
                      </span>
                    </div>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadTemplate(file);
                      }}
                      disabled={uploadingTemplate}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>

              {/* Upload Custom Font */}
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 hover:border-emerald-500 transition-colors">
                <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  Upload Custom Font
                </h3>
                
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Font Name</label>
                    <input
                      type="text"
                      value={newFontName}
                      onChange={(e) => setNewFontName(e.target.value)}
                      placeholder="e.g., Montserrat Bold"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Font Family <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newFontFamily}
                      onChange={(e) => setNewFontFamily(e.target.value)}
                      placeholder="e.g., Montserrat"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500"
                      required
                    />
                    <p className="text-xs text-slate-500 mt-1">This will appear in the font dropdown</p>
                  </div>

                  <label className="block">
                    <div className="w-full px-4 py-3 bg-emerald-50 border-2 border-emerald-200 rounded-lg cursor-pointer hover:bg-emerald-100 transition-colors text-center">
                      <svg className="w-6 h-6 mx-auto mb-2 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                      </svg>
                      <span className="text-sm font-medium text-emerald-700">
                        {uploadingFont ? 'Uploading...' : 'Choose Font File'}
                      </span>
                      <p className="text-xs text-emerald-600 mt-1">ttf, woff, woff2, otf</p>
                    </div>
                    <input
                      type="file"
                      accept=".ttf,.woff,.woff2,.otf"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadFont(file);
                      }}
                      disabled={uploadingFont}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
