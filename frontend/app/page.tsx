'use client';

import { useState, useMemo } from 'react';
import ChatTab from './components/ChatTab';
import BlockList from './components/BlockList';
import BlockEditorPanel from './components/BlockEditorPanel';
import PosterCreator from './components/PosterCreator';
import { parseEmailBlocks, updateBlock, hasBlockMarkers } from './lib/blockParser';
import { apiFetch } from './lib/api';
import type { ParsedEmail, EmailBlock, BlockUpdate, ChatContext } from './types/blocks';

type CreationMode = 'email' | 'poster';

type EmailType = 'transactional' | 'marketing' | 'notification' | 'newsletter';
type BrandTone = 'professional' | 'friendly' | 'luxurious' | 'playful' | 'minimal' | 'bold';

interface DesignTokens {
  colorPalette: {
    primary: string;
    secondary: string;
    accent: string;
    background: string;
    text: string;
    mutedText: string;
  };
  typography: {
    headlineStyle: string;
    bodyStyle: string;
    headlineWeight: string;
    sizeContrast: string;
  };
  layout: {
    structure: string;
    alignment: string;
    density: string;
    heroStyle: string;
  };
  aesthetic: {
    direction: string;
    mood: string;
    distinctiveElements: string[];
  };
  components: {
    hasHeroImage: boolean;
    hasFeatureIcons: boolean;
    hasSocialLinks: boolean;
    ctaStyle: string;
    dividerStyle: string;
  };
  summary: string;
}

// API keys - these should be set in environment variables
// For Vercel: Add these in Project Settings > Environment Variables
const ANTHROPIC_API_KEY = process.env.NEXT_PUBLIC_ANTHROPIC_API_KEY || '';
const OPENROUTER_API_KEY = process.env.NEXT_PUBLIC_OPENROUTER_API_KEY || '';

type OutputMode = 'fast' | 'tasty';
type ModelProvider = 'anthropic' | 'openrouter';

// Available models for OpenRouter
// See full list at: https://openrouter.ai/models
const OPENROUTER_MODELS = [
  { id: 'google/gemini-3-pro-preview', name: 'Gemini 3 Pro', description: 'Newest & best quality' },
  { id: 'google/gemini-2.5-pro-preview-06-05', name: 'Gemini 2.5 Pro', description: 'Excellent quality' },
  { id: 'google/gemini-2.5-flash-preview-05-20', name: 'Gemini 2.5 Flash', description: 'Fast & capable' },
  { id: 'google/gemini-2.0-flash-001', name: 'Gemini 2.0 Flash', description: 'Stable release' },
  { id: 'anthropic/claude-sonnet-4', name: 'Claude Sonnet 4', description: 'Balanced' },
  { id: 'openai/gpt-4o', name: 'GPT-4o', description: 'OpenAI flagship' },
  { id: 'openai/gpt-4.1', name: 'GPT-4.1', description: 'Latest OpenAI' },
  { id: 'meta-llama/llama-3.3-70b-instruct', name: 'Llama 3.3 70B', description: 'Open source' },
];

interface GenerationResult {
  html: string;
  versions: {
    fast: string | null;
    tasty: string | null;
  };
  activeMode: OutputMode;
  variables: Array<{
    name: string;
    type: string;
    description: string;
    mockValue: string | number | boolean;
    required: boolean;
    isUrl?: boolean;
    suprsendSyntax?: string;
  }>;
  suprsendVariables?: Record<string, string | number | boolean>;
  imagePrompts: Array<{
    id: string;
    location: string;
    placeholder: string;
    dimensions: { width: number; height: number };
    aiPrompt: string;
    style: string;
    notes: string;
  }>;
  metadata: {
    sizeBytes: number;
    validationPassed: boolean;
    warnings: string[];
    errors?: string[];
    compatibleWith: string[];
    fastValidation?: { isValid: boolean; warnings: string[]; errors: string[] } | null;
    tastyValidation?: { isValid: boolean; warnings: string[]; errors: string[] } | null;
  };
}

type ActiveTab = 'preview' | 'html' | 'variables' | 'images' | 'chat';

export default function Home() {
  // Creation mode state - Default to 'poster' mode
  const [creationMode, setCreationMode] = useState<CreationMode | null>('poster');

  // Form state - colors are optional, AI will decide if not provided
  const [formData, setFormData] = useState({
    description: '',
    emailType: 'marketing' as EmailType,
    brandName: '',
    primaryColor: '',
    secondaryColor: '',
    accentColor: '',
    tone: 'professional' as BrandTone,
    industry: '',
    // Generation options
    outputMode: 'fast' as OutputMode,
    modelProvider: 'anthropic' as ModelProvider,
    openRouterModel: 'google/gemini-3-pro-preview',
  });

  // Design reference state
  const [designReference, setDesignReference] = useState<{
    imagePreview: string | null;
    tokens: DesignTokens | null;
    isAnalyzing: boolean;
    error: string | null;
  }>({
    imagePreview: null,
    tokens: null,
    isAnalyzing: false,
    error: null,
  });

  // Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [activeTab, setActiveTab] = useState<ActiveTab>('preview');
  const [previewMode, setPreviewMode] = useState<'desktop' | 'mobile'>('desktop');
  const [showForm, setShowForm] = useState(true);
  const [selectedOutputMode, setSelectedOutputMode] = useState<OutputMode>('fast');

  // Block editing state
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [editingBlockId, setEditingBlockId] = useState<string | null>(null);

  // Image generation state
  const [generatingImages, setGeneratingImages] = useState<Set<string>>(new Set());
  const [generatedImages, setGeneratedImages] = useState<Record<string, string>>({});

  // Get current HTML based on selected mode
  const currentHtml = useMemo(() => {
    if (!result) return '';
    if (selectedOutputMode === 'fast' && result.versions.fast) {
      return result.versions.fast;
    }
    if (selectedOutputMode === 'tasty' && result.versions.tasty) {
      return result.versions.tasty;
    }
    return result.html;
  }, [result, selectedOutputMode]);

  // Parse blocks from current HTML
  const parsedEmail: ParsedEmail | null = useMemo(() => {
    if (!currentHtml) return null;
    if (!hasBlockMarkers(currentHtml)) return null;
    return parseEmailBlocks(currentHtml);
  }, [currentHtml]);

  // Get the block being edited
  const editingBlock: EmailBlock | undefined = useMemo(() => {
    if (!editingBlockId || !parsedEmail) return undefined;
    return parsedEmail.blocks.find((b) => b.id === editingBlockId);
  }, [editingBlockId, parsedEmail]);

  // Chat context
  const chatContext: ChatContext = useMemo(
    () => ({
      brandName: formData.brandName,
      emailType: formData.emailType,
      tone: formData.tone,
      primaryColor: formData.primaryColor,
      secondaryColor: formData.secondaryColor,
      accentColor: formData.accentColor || undefined,
      industry: formData.industry || undefined,
    }),
    [formData]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerating(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiFetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          apiKey: ANTHROPIC_API_KEY,
          openRouterApiKey: OPENROUTER_API_KEY,
          designTokens: designReference.tokens || undefined,
          // Single mode generation
          generationMode: formData.outputMode,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Generation failed');
      }

      setResult(data);
      setSelectedOutputMode(formData.outputMode); // Set the mode to what was generated
      setActiveTab('preview');
      setShowForm(false); // Hide form after generation to show editor layout
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  // Handle design reference image upload
  const handleDesignReferenceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setDesignReference(prev => ({ ...prev, error: 'Please upload an image file' }));
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setDesignReference(prev => ({ ...prev, error: 'Image must be less than 10MB' }));
      return;
    }

    // Read file as base64
    const reader = new FileReader();
    reader.onload = async (event) => {
      const dataUrl = event.target?.result as string;
      const base64Data = dataUrl.split(',')[1]; // Remove data:image/xxx;base64, prefix

      setDesignReference({
        imagePreview: dataUrl,
        tokens: null,
        isAnalyzing: true,
        error: null,
      });

      try {
        const response = await apiFetch('/api/analyze-design', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            apiKey: ANTHROPIC_API_KEY,
            imageData: base64Data,
            imageType: file.type,
          }),
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || 'Analysis failed');
        }

        // Update form with extracted colors
        const tokens = data.designTokens as DesignTokens;
        setFormData(prev => ({
          ...prev,
          primaryColor: tokens.colorPalette.primary || prev.primaryColor,
          secondaryColor: tokens.colorPalette.secondary || prev.secondaryColor,
          accentColor: tokens.colorPalette.accent || prev.accentColor,
          tone: mapAestheticToTone(tokens.aesthetic.direction),
        }));

        setDesignReference(prev => ({
          ...prev,
          tokens,
          isAnalyzing: false,
        }));
      } catch (err) {
        setDesignReference(prev => ({
          ...prev,
          isAnalyzing: false,
          error: err instanceof Error ? err.message : 'Analysis failed',
        }));
      }
    };

    reader.readAsDataURL(file);
  };

  // Map aesthetic direction to brand tone
  const mapAestheticToTone = (direction: string): BrandTone => {
    const mapping: Record<string, BrandTone> = {
      minimal: 'minimal',
      modern: 'professional',
      elegant: 'luxurious',
      bold: 'bold',
      playful: 'playful',
      corporate: 'professional',
      editorial: 'luxurious',
      friendly: 'friendly',
    };
    return mapping[direction.toLowerCase()] || 'professional';
  };

  // Clear design reference
  const clearDesignReference = () => {
    setDesignReference({
      imagePreview: null,
      tokens: null,
      isAnalyzing: false,
      error: null,
    });
  };

  // Handle HTML updates from chat - updates the currently selected mode's version
  const handleHtmlUpdate = (newHtml: string) => {
    if (result) {
      const newVersions = { ...result.versions };

      // Update the correct version based on selected mode
      if (selectedOutputMode === 'fast') {
        newVersions.fast = newHtml;
      } else {
        newVersions.tasty = newHtml;
      }

      // Also update html to the current version for compatibility
      setResult({
        ...result,
        html: newHtml,
        versions: newVersions,
        metadata: {
          ...result.metadata,
          sizeBytes: new Blob([newHtml]).size,
        },
      });
    }
  };

  // Handle block updates
  const handleBlockSave = (blockId: string, updates: BlockUpdate) => {
    if (!result || !parsedEmail) return;

    const newHtml = updateBlock(parsedEmail, blockId, updates);
    handleHtmlUpdate(newHtml);
    setEditingBlockId(null);
  };

  // Generate image using OpenRouter (DALL-E 3)
  const handleGenerateImage = async (imageId: string, prompt: string, width: number, height: number) => {
    setGeneratingImages(prev => new Set(prev).add(imageId));

    try {
      const response = await apiFetch('/api/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          apiKey: OPENROUTER_API_KEY,
          prompt,
          width,
          height,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Image generation failed');
      }

      if (data.status === 'completed' && data.imageUrl) {
        setGeneratedImages(prev => ({ ...prev, [imageId]: data.imageUrl }));
      } else if (data.status === 'processing' && data.jobId) {
        // Poll for completion (legacy support, DALL-E is synchronous)
        const pollInterval = setInterval(async () => {
          const statusResponse = await apiFetch(
            `/api/generate-image?jobId=${data.jobId}&apiKey=${OPENROUTER_API_KEY}`
          );
          const statusData = await statusResponse.json();

          if (statusData.status === 'completed' && statusData.imageUrl) {
            setGeneratedImages(prev => ({ ...prev, [imageId]: statusData.imageUrl }));
            setGeneratingImages(prev => {
              const newSet = new Set(prev);
              newSet.delete(imageId);
              return newSet;
            });
            clearInterval(pollInterval);
          } else if (statusData.status === 'failed') {
            clearInterval(pollInterval);
            setGeneratingImages(prev => {
              const newSet = new Set(prev);
              newSet.delete(imageId);
              return newSet;
            });
          }
        }, 2000);

        // Timeout after 2 minutes
        setTimeout(() => clearInterval(pollInterval), 120000);
      }
    } catch (err) {
      console.error('Image generation error:', err);
    } finally {
      setGeneratingImages(prev => {
        const newSet = new Set(prev);
        newSet.delete(imageId);
        return newSet;
      });
    }
  };

  // Insert generated image into email HTML
  const handleInsertImage = (imageId: string, newImageUrl: string) => {
    if (!result || !currentHtml) return;

    // Find the image prompt to get the placeholder URL
    const imagePrompt = result.imagePrompts.find(img => img.id === imageId);
    if (!imagePrompt) return;

    // Replace the placeholder URL with the new image URL
    const updatedHtml = currentHtml.replace(
      new RegExp(escapeRegExp(imagePrompt.placeholder), 'g'),
      newImageUrl
    );

    handleHtmlUpdate(updatedHtml);
  };

  // Helper to escape special regex characters
  const escapeRegExp = (string: string) => {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  };

  // Handle AI edit for a specific block
  const handleBlockAiEdit = async (blockId: string, instruction: string) => {
    if (!result || !parsedEmail) return;

    const block = parsedEmail.blocks.find((b) => b.id === blockId);
    if (!block) return;

    // Use the chat API to edit just this block
    const response = await apiFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        apiKey: ANTHROPIC_API_KEY,
        currentHtml: result.html,
        messages: [],
        newMessage: `Edit the ${block.label} block (${block.type}): ${instruction}. Only modify that specific block, keep everything else the same.`,
        context: chatContext,
      }),
    });

    if (!response.ok) throw new Error('AI edit failed');

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'complete' && data.html) {
              handleHtmlUpdate(data.html);
            }
          } catch {
            // Ignore parse errors
          }
        }
      }
    }
  };

  // Render the form panel
  const renderFormPanel = () => (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-slate-900">Email Configuration</h2>
        {result && (
          <button
            onClick={() => setShowForm(false)}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            Hide
          </button>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Design Reference Upload */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Design Reference <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <p className="text-xs text-slate-500 mb-2">
            Upload a screenshot of an email design you like. AI will extract colors, typography, and layout style.
          </p>

          {!designReference.imagePreview ? (
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-slate-300 rounded-lg cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/50 transition-colors">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <svg className="w-8 h-8 mb-2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="text-sm text-slate-500">Click to upload design reference</p>
                <p className="text-xs text-slate-400">PNG, JPG up to 10MB</p>
              </div>
              <input
                type="file"
                className="hidden"
                accept="image/*"
                onChange={handleDesignReferenceUpload}
              />
            </label>
          ) : (
            <div className="relative">
              <div className="flex gap-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <img
                  src={designReference.imagePreview}
                  alt="Design reference"
                  className="w-24 h-24 object-cover rounded border border-slate-200"
                />
                <div className="flex-1 min-w-0">
                  {designReference.isAnalyzing ? (
                    <div className="flex items-center gap-2 text-sm text-indigo-600">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Analyzing design...
                    </div>
                  ) : designReference.tokens ? (
                    <div>
                      <p className="text-sm font-medium text-slate-700 mb-1">Style Extracted</p>
                      <p className="text-xs text-slate-500 line-clamp-2">{designReference.tokens.summary}</p>
                      <div className="flex gap-1 mt-2">
                        {[
                          designReference.tokens.colorPalette.primary,
                          designReference.tokens.colorPalette.secondary,
                          designReference.tokens.colorPalette.accent,
                        ].filter(Boolean).map((color, i) => (
                          <div
                            key={i}
                            className="w-5 h-5 rounded border border-slate-300"
                            style={{ backgroundColor: color }}
                            title={color}
                          />
                        ))}
                        <span className="text-xs text-slate-400 ml-1">
                          {designReference.tokens.aesthetic.direction} / {designReference.tokens.aesthetic.mood}
                        </span>
                      </div>
                    </div>
                  ) : designReference.error ? (
                    <p className="text-sm text-red-600">{designReference.error}</p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={clearDesignReference}
                  className="absolute top-2 right-2 p-1 bg-white rounded-full shadow hover:bg-slate-100"
                >
                  <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Email Description <span className="text-red-500">*</span>
          </label>
          <textarea
            name="description"
            value={formData.description}
            onChange={handleInputChange}
            placeholder="Describe the email you want to create..."
            required
            rows={3}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm resize-none"
          />
        </div>

        {/* Email Type */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Email Type <span className="text-red-500">*</span>
          </label>
          <select
            name="emailType"
            value={formData.emailType}
            onChange={handleInputChange}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
          >
            <option value="marketing">Marketing (promotions, campaigns)</option>
            <option value="transactional">Transactional (receipts, confirmations)</option>
            <option value="notification">Notification (alerts, updates)</option>
            <option value="newsletter">Newsletter (digest, content)</option>
          </select>
        </div>

        {/* Brand Name */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Brand Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            name="brandName"
            value={formData.brandName}
            onChange={handleInputChange}
            placeholder="Your Company"
            required
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
          />
        </div>

        {/* Colors - Optional */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Brand Colors <span className="text-slate-400 font-normal">(optional - AI will choose if not specified)</span>
          </label>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Primary</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  name="primaryColor"
                  value={formData.primaryColor || '#3b82f6'}
                  onChange={handleInputChange}
                  className="w-10 h-10 rounded border border-slate-300 cursor-pointer"
                />
                <input
                  type="text"
                  value={formData.primaryColor}
                  onChange={(e) => setFormData((prev) => ({ ...prev, primaryColor: e.target.value }))}
                  placeholder="#hex"
                  className="flex-1 px-2 py-1 border border-slate-300 rounded text-xs font-mono"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Secondary</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  name="secondaryColor"
                  value={formData.secondaryColor || '#f1f5f9'}
                  onChange={handleInputChange}
                  className="w-10 h-10 rounded border border-slate-300 cursor-pointer"
                />
                <input
                  type="text"
                  value={formData.secondaryColor}
                  onChange={(e) => setFormData((prev) => ({ ...prev, secondaryColor: e.target.value }))}
                  placeholder="#hex"
                  className="flex-1 px-2 py-1 border border-slate-300 rounded text-xs font-mono"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Accent</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  name="accentColor"
                  value={formData.accentColor || '#6366f1'}
                  onChange={handleInputChange}
                  className="w-10 h-10 rounded border border-slate-300 cursor-pointer"
                />
                <input
                  type="text"
                  value={formData.accentColor}
                  onChange={(e) => setFormData((prev) => ({ ...prev, accentColor: e.target.value }))}
                  placeholder="#hex"
                  className="flex-1 px-2 py-1 border border-slate-300 rounded text-xs font-mono"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Tone */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Brand Tone</label>
          <select
            name="tone"
            value={formData.tone}
            onChange={handleInputChange}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
          >
            <option value="professional">Professional</option>
            <option value="friendly">Friendly</option>
            <option value="luxurious">Luxurious</option>
            <option value="playful">Playful</option>
            <option value="minimal">Minimal</option>
            <option value="bold">Bold</option>
          </select>
        </div>

        {/* Industry */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Industry (optional)</label>
          <input
            type="text"
            name="industry"
            value={formData.industry}
            onChange={handleInputChange}
            placeholder="e.g., SaaS, E-commerce"
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
          />
        </div>

        {/* Generation Options Section */}
        <div className="pt-4 border-t border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Generation Options</h3>

          {/* Output Mode */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">Output Mode</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setFormData(prev => ({ ...prev, outputMode: 'fast' }))}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  formData.outputMode === 'fast'
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span className="font-medium text-slate-900">Fast</span>
                </div>
                <p className="text-xs text-slate-500">Minimal images, ready to use immediately</p>
              </button>
              <button
                type="button"
                onClick={() => setFormData(prev => ({ ...prev, outputMode: 'tasty' }))}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  formData.outputMode === 'tasty'
                    ? 'border-purple-500 bg-purple-50'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <span className="font-medium text-slate-900">Tasty</span>
                </div>
                <p className="text-xs text-slate-500">Rich visuals with image placeholders</p>
              </button>
            </div>
          </div>

          {/* Model Provider */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">AI Model</label>
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, modelProvider: 'anthropic' }))}
                  className={`flex-1 p-2 rounded-lg border text-sm font-medium transition-all ${
                    formData.modelProvider === 'anthropic'
                      ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  Claude (Default)
                </button>
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, modelProvider: 'openrouter' }))}
                  className={`flex-1 p-2 rounded-lg border text-sm font-medium transition-all ${
                    formData.modelProvider === 'openrouter'
                      ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  OpenRouter
                </button>
              </div>

              {/* OpenRouter Model Selection */}
              {formData.modelProvider === 'openrouter' && (
                <select
                  name="openRouterModel"
                  value={formData.openRouterModel}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-sm"
                >
                  {OPENROUTER_MODELS.map(model => (
                    <option key={model.id} value={model.id}>
                      {model.name} - {model.description}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isGenerating}
          className="w-full py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-medium rounded-lg hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {isGenerating ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Generating...
            </span>
          ) : result ? (
            'Regenerate Email'
          ) : (
            'Generate Email Template'
          )}
        </button>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}
      </form>
    </div>
  );

  // Render preview/content tabs
  const renderPreviewContent = () => {
    if (!result) {
      return (
        <div className="h-full flex items-center justify-center text-slate-400">
          <div className="text-center">
            <div className="text-5xl mb-4">✉️</div>
            <p>Configure your email and click Generate</p>
            <p className="text-sm mt-1">Your preview will appear here</p>
          </div>
        </div>
      );
    }

    switch (activeTab) {
      case 'preview':
        return (
          <div className="h-full flex flex-col">
            {/* Stats Bar */}
            <div className="flex items-center gap-4 mb-4 p-3 bg-slate-50 rounded-lg text-sm flex-wrap">
              <span className={`px-2 py-1 rounded ${result.metadata.validationPassed ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                {result.metadata.validationPassed ? '✓ Valid' : '⚠ Warnings'}
              </span>
              <span className="text-slate-600">{(new Blob([currentHtml]).size / 1024).toFixed(1)}KB</span>
              <span className="text-slate-600">{result.variables.length} variables</span>
              {result.metadata.compatibleWith?.includes('suprsend') && (
                <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded">SuprSend</span>
              )}
              {/* Preview Mode Toggle */}
              <div className="ml-auto flex items-center gap-1 bg-slate-200 rounded-lg p-1">
                <button
                  onClick={() => setPreviewMode('desktop')}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${previewMode === 'desktop' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'}`}
                >
                  Desktop
                </button>
                <button
                  onClick={() => setPreviewMode('mobile')}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${previewMode === 'mobile' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'}`}
                >
                  Mobile
                </button>
              </div>
            </div>
            {/* Email Preview */}
            <div className={`flex-1 flex justify-center ${previewMode === 'mobile' ? 'bg-slate-100 p-4 rounded-lg' : ''}`}>
              <iframe
                srcDoc={currentHtml}
                className={`border border-slate-200 rounded-lg bg-white transition-all duration-300 ${previewMode === 'mobile' ? 'w-[375px] h-[667px] shadow-lg' : 'w-full h-full min-h-[500px]'}`}
                title="Email Preview"
              />
            </div>
          </div>
        );

      case 'html':
        return (
          <div className="relative h-full">
            <button
              onClick={() => navigator.clipboard.writeText(currentHtml)}
              className="absolute top-2 right-2 px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded text-sm text-slate-600 z-10"
            >
              Copy HTML
            </button>
            <pre className="p-4 bg-slate-900 text-slate-100 rounded-lg overflow-auto text-xs leading-relaxed h-full">
              <code>{currentHtml}</code>
            </pre>
          </div>
        );

      case 'variables':
        return (
          <div className="space-y-3 overflow-auto">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="font-medium text-slate-900">Variables ({result.variables.length})</h3>
                <p className="text-xs text-slate-500 mt-0.5">Shared across Fast & Tasty modes</p>
              </div>
              <button
                onClick={() => navigator.clipboard.writeText(JSON.stringify(result.suprsendVariables || {}, null, 2))}
                className="px-3 py-1 bg-emerald-100 hover:bg-emerald-200 rounded text-sm text-emerald-700"
              >
                Copy for SuprSend
              </button>
            </div>
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
              <p className="text-sm font-medium text-emerald-800 mb-2">SuprSend Payload</p>
              <pre className="text-xs bg-white p-3 rounded border border-emerald-200 overflow-auto max-h-40">
                {JSON.stringify(result.suprsendVariables || {}, null, 2)}
              </pre>
            </div>
            {result.variables.map((v, i) => (
              <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <code className={`px-2 py-1 rounded text-sm font-mono ${v.isUrl ? 'bg-amber-100 text-amber-700' : 'bg-indigo-100 text-indigo-700'}`}>
                  {v.suprsendSyntax || `{{${v.name}}}`}
                </code>
                <p className="text-sm text-slate-600 mt-2">{v.description}</p>
              </div>
            ))}
          </div>
        );

      case 'images':
        return (
          <div className="space-y-4 overflow-auto">
            <div className="flex justify-between items-center flex-wrap gap-2">
              <div>
                <h3 className="font-medium text-slate-900">Images ({result.imagePrompts.length})</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedOutputMode === 'fast'
                    ? 'Fast mode uses minimal images'
                    : 'Tasty mode includes rich visuals'}
                </p>
              </div>
              <div className="flex gap-2">
                {result.imagePrompts.length > 0 && (
                  <button
                    onClick={() => {
                      result.imagePrompts.forEach(img => {
                        if (!generatingImages.has(img.id) && !generatedImages[img.id]) {
                          handleGenerateImage(img.id, img.aiPrompt, img.dimensions.width, img.dimensions.height);
                        }
                      });
                    }}
                    disabled={generatingImages.size > 0}
                    className="px-3 py-1 bg-purple-100 hover:bg-purple-200 rounded text-sm text-purple-700 disabled:opacity-50"
                  >
                    {generatingImages.size > 0 ? 'Generating...' : 'Generate All'}
                  </button>
                )}
                <button
                  onClick={() => navigator.clipboard.writeText(JSON.stringify(result.imagePrompts, null, 2))}
                  className="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded text-sm text-slate-600"
                >
                  Copy JSON
                </button>
              </div>
            </div>
            {result.imagePrompts.length === 0 ? (
              <div className="p-6 text-center text-slate-500 bg-slate-50 rounded-lg border border-slate-200">
                <svg className="w-12 h-12 mx-auto mb-3 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="text-sm font-medium">No placeholder images detected</p>
                <p className="text-xs mt-1">
                  {selectedOutputMode === 'fast'
                    ? 'Fast mode minimizes images for quick deployment'
                    : 'Try regenerating or switch to Tasty mode for rich visuals'}
                </p>
              </div>
            ) : (
              result.imagePrompts.map((img, i) => {
                const isGenerating = generatingImages.has(img.id);
                const generatedUrl = generatedImages[img.id];

                return (
                  <div key={i} className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{img.id}</span>
                        <span className="text-xs text-slate-500">{img.dimensions.width}x{img.dimensions.height}</span>
                      </div>
                      <div className="flex gap-2">
                        {!generatedUrl && (
                          <button
                            onClick={() => handleGenerateImage(img.id, img.aiPrompt, img.dimensions.width, img.dimensions.height)}
                            disabled={isGenerating}
                            className="px-2 py-1 bg-purple-100 hover:bg-purple-200 rounded text-xs text-purple-700 disabled:opacity-50 flex items-center gap-1"
                          >
                            {isGenerating ? (
                              <>
                                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Generating...
                              </>
                            ) : (
                              'Generate'
                            )}
                          </button>
                        )}
                        {generatedUrl && (
                          <button
                            onClick={() => handleInsertImage(img.id, generatedUrl)}
                            className="px-2 py-1 bg-green-100 hover:bg-green-200 rounded text-xs text-green-700"
                          >
                            Insert into Email
                          </button>
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-slate-700 bg-white p-2 rounded mb-2">{img.aiPrompt}</p>

                    {/* Show generated image preview */}
                    {generatedUrl && (
                      <div className="mt-3 p-2 bg-white rounded border border-slate-200">
                        <p className="text-xs text-slate-500 mb-2">Generated Image:</p>
                        <img
                          src={generatedUrl}
                          alt={img.aiPrompt}
                          className="max-w-full h-auto rounded border border-slate-200"
                          style={{ maxHeight: '200px' }}
                        />
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        );

      case 'chat':
        return (
          <ChatTab
            currentHtml={currentHtml}
            context={chatContext}
            onHtmlUpdate={handleHtmlUpdate}
            apiKey={ANTHROPIC_API_KEY}
          />
        );

      default:
        return null;
    }
  };

  // If poster mode is selected, render the PosterCreator component
  if (creationMode === 'poster') {
    return <PosterCreator onBack={() => setCreationMode(null)} />;
  }

  // Mode selection screen
  if (creationMode === null) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
        <div className="max-w-3xl w-full">
          <div className="text-center mb-12">
            <div className="w-20 h-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-indigo-200">
              <span className="text-white text-4xl">F</span>
            </div>
            <h1 className="text-4xl font-bold text-slate-900 mb-3">Creative Forge</h1>
            <p className="text-lg text-slate-600">AI-powered design generation for emails, posters, and more</p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Email Option */}
            <button
              onClick={() => setCreationMode('email')}
              className="group p-8 bg-white rounded-2xl border-2 border-slate-200 hover:border-indigo-500 hover:shadow-xl hover:shadow-indigo-100 transition-all text-left"
            >
              <div className="w-14 h-14 bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-slate-900 mb-2">Email Templates</h2>
              <p className="text-slate-600 mb-4">Create production-ready HTML email templates with SuprSend compatibility</p>
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">Marketing</span>
                <span className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">Transactional</span>
                <span className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">Newsletter</span>
              </div>
            </button>

            {/* Poster Option */}
            <button
              onClick={() => setCreationMode('poster')}
              className="group p-8 bg-white rounded-2xl border-2 border-slate-200 hover:border-purple-500 hover:shadow-xl hover:shadow-purple-100 transition-all text-left"
            >
              <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-slate-900 mb-2">Poster Creator</h2>
              <p className="text-slate-600 mb-4">Design stunning promotional posters from Topmate creator profiles</p>
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs font-medium rounded">Instagram</span>
                <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs font-medium rounded">LinkedIn</span>
                <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs font-medium rounded">Twitter</span>
              </div>
            </button>
          </div>

          <p className="text-center text-sm text-slate-500 mt-8">
            More creation modes coming soon: Videos, Social Cards, Presentations
          </p>
        </div>
      </div>
    );
  }

  // Email creation mode
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-screen-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => { setCreationMode(null); setResult(null); setShowForm(true); }}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">Email Forge</h1>
              <p className="text-xs text-slate-500">AI-Powered Email Template Editor</p>
            </div>
            <span className="ml-2 px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">
              SuprSend Ready
            </span>
          </div>
          {result && !showForm && (
            <button
              onClick={() => setShowForm(true)}
              className="px-4 py-2 text-sm bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              Edit Settings
            </button>
          )}
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto">
        {/* Show form only when no result or showForm is true */}
        {(!result || showForm) ? (
          <div className="px-4 py-8 max-w-2xl mx-auto">
            {renderFormPanel()}
          </div>
        ) : (
          /* 3-Panel Editor Layout */
          <div className="flex h-[calc(100vh-60px)]">
            {/* Left Sidebar: Block List */}
            <div className="w-64 bg-white border-r border-slate-200 overflow-auto flex-shrink-0">
              <BlockList
                blocks={parsedEmail?.blocks || []}
                selectedBlockId={selectedBlockId}
                onSelectBlock={setSelectedBlockId}
                onEditBlock={setEditingBlockId}
              />
            </div>

            {/* Center: Preview Panel */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Tabs */}
              <div className="flex border-b border-slate-200 bg-white">
                {(['preview', 'html', 'variables', 'images', 'chat'] as ActiveTab[]).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-3 text-sm font-medium transition-colors ${
                      activeTab === tab
                        ? 'text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/50'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                    }`}
                  >
                    {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    {tab === 'chat' && <span className="ml-1 text-xs">AI</span>}
                  </button>
                ))}
              </div>

              {/* Mode indicator - shows which mode was used for generation */}
              {result && (
                <div className="px-4 pt-3 bg-slate-50">
                  <div className={`p-2 rounded-lg border flex items-center gap-2 ${
                    selectedOutputMode === 'fast'
                      ? 'bg-indigo-50 border-indigo-200'
                      : 'bg-purple-50 border-purple-200'
                  }`}>
                    {selectedOutputMode === 'fast' ? (
                      <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    )}
                    <span className={`text-sm font-medium ${
                      selectedOutputMode === 'fast' ? 'text-indigo-700' : 'text-purple-700'
                    }`}>
                      {selectedOutputMode === 'fast' ? 'Fast Mode' : 'Tasty Mode'}
                    </span>
                    <span className="text-xs text-slate-500">
                      {selectedOutputMode === 'fast'
                        ? '- Minimal images, ready to use'
                        : '- Rich visuals with placeholders'}
                    </span>
                  </div>
                </div>
              )}

              {/* Tab Content */}
              <div className="flex-1 overflow-auto p-4 bg-slate-50">
                {renderPreviewContent()}
              </div>
            </div>

            {/* Right Sidebar: Block Editor (slides in) */}
            {editingBlock && (
              <div className="w-80 flex-shrink-0 animate-slide-in-right">
                <BlockEditorPanel
                  block={editingBlock}
                  context={chatContext}
                  apiKey={ANTHROPIC_API_KEY}
                  onSave={handleBlockSave}
                  onAiEdit={handleBlockAiEdit}
                  onClose={() => setEditingBlockId(null)}
                />
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
