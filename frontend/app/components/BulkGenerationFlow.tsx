'use client';

import { useState } from 'react';
import { PosterSize, GeneratedPoster, BulkGenerationResult, BulkProgress } from '../types/poster';
import { parseUserIdentifiers } from '../lib/topmate';
import BulkProgressTracker from './BulkProgressTracker';
import { apiFetch } from '../lib/api';

type BulkStep = 'prompt' | 'template' | 'users' | 'generating' | 'uploading' | 'storing' | 'results';
type ProgressPhase = 'converting' | 'uploading' | 'storing' | 'complete';

interface BulkGenerationFlowProps {
  size: PosterSize;
  model: 'pro' | 'flash';
}

export default function BulkGenerationFlow({ size, model }: BulkGenerationFlowProps) {
  const [currentStep, setCurrentStep] = useState<BulkStep>('prompt');
  const [prompt, setPrompt] = useState('');
  const [templates, setTemplates] = useState<GeneratedPoster[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<GeneratedPoster | null>(null);
  const [userIdentifiersInput, setUserIdentifiersInput] = useState('');
  const [campaignName, setCampaignName] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState<BulkProgress>({ total: 0, completed: 0, failed: 0 });
  const [results, setResults] = useState<BulkGenerationResult[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string>('');

  // Enhanced progress tracking
  const [progressPhase, setProgressPhase] = useState<ProgressPhase>('converting');
  const [startTime, setStartTime] = useState<number>(0);
  const [currentProcessing, setCurrentProcessing] = useState<string>('');
  const [uploadProgress, setUploadProgress] = useState({ total: 0, completed: 0, failed: 0 });
  const [storeProgress, setStoreProgress] = useState({ total: 0, completed: 0, failed: 0 });

  // Step 1: Generate Template
  const handleGenerateTemplate = async () => {
    if (!prompt.trim()) {
      alert('Please enter a prompt');
      return;
    }

    setIsGenerating(true);

    try {
      const response = await apiFetch('/api/generate-template', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          size,
          model,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setTemplates(data.templates || []);
        setCurrentStep('template');
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      alert(`Failed to generate templates: ${error}`);
    } finally {
      setIsGenerating(false);
    }
  };

  // Step 2: Select Template
  const handleSelectTemplate = (template: GeneratedPoster) => {
    setSelectedTemplate(template);
    setCurrentStep('users');
  };

  // Step 3: Bulk Generate
  const handleBulkGenerate = async () => {
    if (!selectedTemplate || !userIdentifiersInput.trim()) {
      alert('Please select a template and enter user identifiers');
      return;
    }

    // Check if template has image URL
    if (!selectedTemplate.imageUrl) {
      alert('Selected template does not have an image URL. Please regenerate templates.');
      return;
    }

    const { usernames, userIds } = parseUserIdentifiers(userIdentifiersInput);
    const totalUsers = usernames.length + userIds.length;

    if (totalUsers === 0) {
      alert('Please enter valid usernames or user IDs');
      return;
    }

    // Initialize progress tracking
    setCurrentStep('generating');
    setProgressPhase('converting');
    setStartTime(Date.now());
    setProgress({ total: totalUsers, completed: 0, failed: 0 });
    setUploadProgress({ total: totalUsers, completed: 0, failed: 0 });
    setStoreProgress({ total: totalUsers, completed: 0, failed: 0 });
    setIsGenerating(true);
    setCurrentProcessing('Starting bulk generation...');

    try {
      console.log('🚀 Sending bulk generation request:', {
        selectedTemplateImageUrl: selectedTemplate.imageUrl,
        userIdentifiers: userIdentifiersInput,
        posterName: `bulk-${Date.now()}`,
        originalPrompt: prompt,
        size,
        model,
      });

      const response = await apiFetch('/api/generate-bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selectedTemplateImageUrl: selectedTemplate.imageUrl,
          userIdentifiers: userIdentifiersInput,
          posterName: `bulk-${Date.now()}`,
          originalPrompt: prompt,
          size,
          model,
        }),
      });

      const data = await response.json();

      console.log('📊 Bulk generation response:', data);

      if (!response.ok) {
        console.error('❌ Bulk generation failed:', response.status, data);
        alert(`Error: ${data.error || 'Failed to generate posters'}`);
        setCurrentStep('users');
        setIsGenerating(false);
        return;
      }

      if (data.success) {
        // Results already contain image URLs from nano banana
        setResults(data.results);
        setProgress({
          total: totalUsers,
          completed: data.successCount,
          failed: data.failureCount
        });
        setProgressPhase('complete');
        setCurrentProcessing('');

        // Small delay before showing results
        setTimeout(() => {
          setCurrentStep('results');
          setIsGenerating(false);
        }, 500);
      } else {
        console.error('❌ Bulk generation error:', data.error);
        alert(`Error: ${data.error}`);
        setCurrentStep('users');
        setIsGenerating(false);
      }
    } catch (error) {
      console.error('❌ Bulk generation exception:', error);
      alert(`Failed to generate posters: ${error}`);
      setCurrentStep('users');
      setIsGenerating(false);
    }
  };

  // Save All to Database with detailed progress tracking
  const handleSaveAllToDatabase = async () => {
    if (!campaignName.trim()) {
      alert('Please enter a campaign name');
      return;
    }

    const successfulResults = results.filter(r => r.success && r.posterUrl);

    if (successfulResults.length === 0) {
      alert('No successful posters to save');
      return;
    }

    setIsSaving(true);
    setCurrentStep('uploading');
    setProgressPhase('uploading');
    setStartTime(Date.now());
    setUploadProgress({ total: successfulResults.length, completed: 0, failed: 0 });
    setCurrentProcessing('Preparing to upload images...');

    try {
      // Simulate upload progress tracking
      setSaveStatus('📤 Uploading images to storage...');

      const response = await apiFetch('/api/save-bulk-posters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          posters: successfulResults,
          posterName: campaignName.trim(),
        }),
      });

      // Move to storing phase
      setProgressPhase('storing');
      setCurrentStep('storing');
      setStoreProgress({ total: successfulResults.length, completed: 0, failed: 0 });
      setCurrentProcessing('Saving to database...');
      setSaveStatus('💾 Saving to database...');

      const data = await response.json();

      // Update final progress
      if (data.success) {
        setStoreProgress({
          total: successfulResults.length,
          completed: data.successCount,
          failed: data.failureCount
        });
        setProgressPhase('complete');
        setSaveStatus(`✅ Saved ${data.successCount}/${successfulResults.length} posters as campaign "${campaignName}"!`);

        // Return to results after a delay
        setTimeout(() => {
          setCurrentStep('results');
          setIsSaving(false);
        }, 2000);
      } else {
        setSaveStatus(`❌ Error: ${data.error}`);
        setCurrentStep('results');
        setIsSaving(false);
      }
    } catch (error) {
      console.error('❌ Save error:', error);
      setSaveStatus(`❌ Failed to save: ${error}`);
      setCurrentStep('results');
      setIsSaving(false);
    }
  };

  // Reset flow
  const handleReset = () => {
    setCurrentStep('prompt');
    setPrompt('');
    setTemplates([]);
    setSelectedTemplate(null);
    setUserIdentifiersInput('');
    setCampaignName('');
    setResults([]);
    setProgress({ total: 0, completed: 0, failed: 0 });
    setUploadProgress({ total: 0, completed: 0, failed: 0 });
    setStoreProgress({ total: 0, completed: 0, failed: 0 });
    setSaveStatus('');
    setProgressPhase('converting');
    setStartTime(0);
    setCurrentProcessing('');
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Step Indicator - Responsive */}
      <div className="flex items-center justify-between sm:justify-start sm:gap-2 overflow-x-auto pb-2">
        {['prompt', 'template', 'users', 'results'].map((step, idx) => (
          <div key={step} className="flex items-center flex-shrink-0">
            <div className={`w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center text-xs sm:text-sm font-medium transition-all ${
              currentStep === step ? 'bg-blue-600 text-white ring-2 ring-blue-300' :
              ['template', 'users', 'results'].indexOf(currentStep) > ['template', 'users', 'results'].indexOf(step as any) ? 'bg-green-600 text-white' :
              'bg-gray-200 text-gray-600'
            }`}>
              {currentStep === step ? (
                <span className="animate-pulse">{idx + 1}</span>
              ) : (
                idx + 1
              )}
            </div>
            {idx < 3 && <div className="w-8 sm:w-12 h-0.5 bg-gray-200 mx-1" />}
          </div>
        ))}
      </div>

      {/* Step 1: Prompt */}
      {currentStep === 'prompt' && (
        <div className="bg-white rounded-xl shadow-sm border p-4 sm:p-6 space-y-4">
          <div>
            <h3 className="text-base sm:text-lg font-semibold mb-2">Step 1: Enter Your Prompt</h3>
            <p className="text-xs sm:text-sm text-gray-600 mb-4">
              Describe the poster you want to create. This will be used as a template for all users.
            </p>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="E.g., A bold promotional poster for 1:1 mentorship sessions with vibrant colors..."
              rows={6}
              className="w-full px-3 py-2 sm:px-4 sm:py-3 text-sm sm:text-base border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <button
            onClick={handleGenerateTemplate}
            disabled={isGenerating || !prompt.trim()}
            className="w-full px-4 py-2 sm:px-6 sm:py-3 text-sm sm:text-base bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {isGenerating ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4 sm:h-5 sm:w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Generating Templates...
              </span>
            ) : (
              'Generate Template (3 variants)'
            )}
          </button>
        </div>
      )}

      {/* Step 2: Template Selection */}
      {currentStep === 'template' && (
        <div className="bg-white rounded-xl shadow-sm border p-4 sm:p-6 space-y-4">
          <div className="bg-yellow-50 border border-yellow-200 p-2 sm:p-3 rounded-lg">
            <p className="text-xs sm:text-sm text-yellow-800">
              ⚠️ <strong>PREVIEW MODE:</strong> These templates use placeholder data. Select your preferred design style.
            </p>
          </div>

          <h3 className="text-base sm:text-lg font-semibold">Step 2: Select Template Style</h3>

          {/* Template grid - using same approach as single user poster generation */}
          <div className="grid grid-cols-3 gap-4">
            {templates.map((template, idx) => {
              const dimensions = { width: 1080, height: 1080 };
              const thumbScale = 0.25; // Show at 25% size (270x270)

              return (
                <button
                  key={idx}
                  onClick={() => handleSelectTemplate(template)}
                  className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                    selectedTemplate === template
                      ? 'border-blue-500 ring-2 ring-blue-200'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  style={{
                    width: dimensions.width * thumbScale,
                    height: dimensions.height * thumbScale,
                  }}
                >
                  {template.imageUrl ? (
                    <img
                      src={template.imageUrl}
                      alt={`Variant ${idx + 1}`}
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        pointerEvents: 'none',
                      }}
                      className="border-0"
                    />
                  ) : template.html ? (
                    <iframe
                      srcDoc={template.html}
                      style={{
                        width: dimensions.width,
                        height: dimensions.height,
                        transform: `scale(${thumbScale})`,
                        transformOrigin: 'top left',
                        pointerEvents: 'none',
                      }}
                      className="border-0"
                      sandbox="allow-same-origin"
                      scrolling="no"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-400">
                      No preview
                    </div>
                  )}

                  <div className={`absolute inset-0 flex items-end justify-center pb-2 bg-gradient-to-t from-black/50 to-transparent ${
                    selectedTemplate === template ? 'opacity-100' : 'opacity-0 hover:opacity-100'
                  } transition-opacity`}>
                    <span className="text-white text-sm font-medium">
                      Variant {idx + 1}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Action buttons */}
          <div className="mt-6 space-y-3">
            {selectedTemplate && (
              <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg">
                <p className="text-sm text-blue-900 text-center">
                  ✓ Variant {templates.indexOf(selectedTemplate) + 1} selected
                </p>
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => setCurrentStep('prompt')}
                className="px-4 py-2 sm:px-6 sm:py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition text-sm sm:text-base"
              >
                ← Back
              </button>
              <button
                onClick={() => selectedTemplate && setCurrentStep('users')}
                disabled={!selectedTemplate}
                className="flex-1 px-4 py-2 sm:px-6 sm:py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition text-sm sm:text-base"
              >
                {selectedTemplate ? 'Continue to User Selection →' : 'Select a Template First'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: User Input */}
      {currentStep === 'users' && (
        <div className="bg-white rounded-xl shadow-sm border p-4 sm:p-6 space-y-4">
          <h3 className="text-base sm:text-lg font-semibold">Step 3: Enter Target Users</h3>
          <p className="text-xs sm:text-sm text-gray-600">
            Enter Topmate usernames or numeric user IDs (comma or newline separated)
          </p>

          <textarea
            value={userIdentifiersInput}
            onChange={(e) => setUserIdentifiersInput(e.target.value)}
            placeholder="john_doe, 12345, sarah_coach, 67890&#10;Or one per line:&#10;john_doe&#10;12345&#10;sarah_coach"
            rows={6}
            className="w-full px-3 py-2 sm:px-4 sm:py-3 text-sm sm:text-base border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
          />

          <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg">
            <p className="text-xs sm:text-sm text-blue-900 font-medium">
              📊 Will generate for: <span className="text-lg font-bold">{(() => {
                const { usernames, userIds } = parseUserIdentifiers(userIdentifiersInput);
                return usernames.length + userIds.length;
              })()}</span> users
            </p>
          </div>

          {/* Show selected template preview */}
          {selectedTemplate && (
            <div className="border border-gray-200 rounded-lg p-3">
              <p className="text-xs sm:text-sm text-gray-600 mb-2">Using Template:</p>
              <div className="flex items-center gap-3">
                <div
                  className="bg-gray-100 rounded overflow-hidden flex-shrink-0"
                  style={{ width: 80, height: 80 }}
                >
                  {selectedTemplate.imageUrl ? (
                    <img
                      src={selectedTemplate.imageUrl}
                      alt="Selected template"
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                      }}
                    />
                  ) : (
                    <div className="w-full h-full bg-gradient-to-br from-blue-100 to-blue-200" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs sm:text-sm font-medium truncate">
                    Variant {templates.indexOf(selectedTemplate) + 1}
                  </p>
                  <p className="text-xs text-gray-500 truncate">{prompt.slice(0, 50)}...</p>
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={() => setCurrentStep('template')}
              className="px-4 py-2 sm:px-6 sm:py-3 text-sm sm:text-base border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              ← Back
            </button>
            <button
              onClick={handleBulkGenerate}
              disabled={isGenerating || !userIdentifiersInput.trim()}
              className="flex-1 px-4 py-2 sm:px-6 sm:py-3 text-sm sm:text-base bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {isGenerating ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4 sm:h-5 sm:w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Generating...
                </span>
              ) : (
                `🚀 Generate for ${(() => {
                  const { usernames, userIds } = parseUserIdentifiers(userIdentifiersInput);
                  return usernames.length + userIds.length;
                })()} Users`
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Generating Progress */}
      {currentStep === 'generating' && (
        <BulkProgressTracker
          phase="converting"
          total={progress.total}
          completed={progress.completed}
          failed={progress.failed}
          currentItem={currentProcessing}
          startTime={startTime}
        />
      )}

      {/* Step 5: Uploading Progress */}
      {currentStep === 'uploading' && (
        <BulkProgressTracker
          phase="uploading"
          total={uploadProgress.total}
          completed={uploadProgress.completed}
          failed={uploadProgress.failed}
          currentItem={currentProcessing}
          startTime={startTime}
        />
      )}

      {/* Step 6: Storing Progress */}
      {currentStep === 'storing' && (
        <BulkProgressTracker
          phase="storing"
          total={storeProgress.total}
          completed={storeProgress.completed}
          failed={storeProgress.failed}
          currentItem={currentProcessing}
          startTime={startTime}
        />
      )}

      {/* Step 5: Results */}
      {currentStep === 'results' && (
        <div className="bg-white rounded-xl shadow-sm border p-4 sm:p-6 space-y-4">
          {/* Summary Banner */}
          <div className="bg-green-50 border border-green-200 p-3 sm:p-4 rounded-lg">
            <p className="text-sm sm:text-base font-semibold text-green-900">
              ✅ Successfully generated {progress.completed} of {progress.total} posters
            </p>
            {progress.failed > 0 && (
              <p className="text-xs sm:text-sm text-red-600 mt-1">
                ❌ {progress.failed} failed
              </p>
            )}
          </div>

          <h3 className="text-base sm:text-lg font-semibold">Generation Results</h3>

          {/* Results Grid - using same approach as single user */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[600px] overflow-y-auto">
            {results.map((result, idx) => {
              const dimensions = { width: 1080, height: 1080 };
              const thumbScale = 0.25;

              return (
                <div
                  key={idx}
                  className={`rounded-lg border-2 overflow-hidden ${
                    result.success ? 'border-green-300' : 'border-red-300'
                  }`}
                >
                  {result.success ? (
                    <>
                      <div
                        style={{
                          width: dimensions.width * thumbScale,
                          height: dimensions.height * thumbScale,
                        }}
                        className="relative overflow-hidden"
                      >
                        <img
                          src={result.posterUrl}
                          alt={`Poster for ${result.username}`}
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                          }}
                          loading="lazy"
                        />
                      </div>
                    {/* User Info */}
                    <div className="p-3 space-y-2">
                      <div className="font-medium text-green-700 flex items-center gap-2">
                        <span className="text-lg">✅</span>
                        <span className="truncate">{result.username}</span>
                      </div>
                      <a
                        href={result.posterUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline block truncate"
                        title={result.posterUrl}
                      >
                        View Full Size
                      </a>
                      {/* Download Button */}
                      <button
                        onClick={async () => {
                          try {
                            const response = await fetch(result.posterUrl);
                            const blob = await response.blob();
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `${result.username}-poster.png`;
                            a.click();
                            window.URL.revokeObjectURL(url);
                          } catch (err) {
                            alert('Failed to download image');
                          }
                        }}
                        className="w-full px-2 py-1 sm:px-3 sm:py-1.5 bg-blue-600 text-white text-xs sm:text-sm rounded hover:bg-blue-700 transition"
                      >
                        📥 Download
                      </button>
                    </div>
                  </>
                  ) : (
                    <div className="p-4">
                      <div className="font-medium text-red-700 mb-2 flex items-center gap-2">
                        <span className="text-lg">❌</span>
                        <span>{result.username}</span>
                      </div>
                      <div className="text-sm text-red-600 bg-red-100 p-2 rounded">
                        {result.error}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Campaign Name Input */}
          <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg space-y-3">
            <label className="block text-sm font-semibold text-blue-900">
              Campaign Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={campaignName}
              onChange={(e) => setCampaignName(e.target.value)}
              placeholder="e.g., monthly-recap, year-end-2025, black-friday"
              className="w-full px-3 py-2 border border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              disabled={isSaving}
            />
            <p className="text-xs text-blue-700">
              💡 This name will be used as the campaign identifier in your database
            </p>
          </div>

          {/* Save Status Message */}
          {saveStatus && (
            <div className={`p-3 rounded-lg text-sm ${
              saveStatus.startsWith('✅')
                ? 'bg-green-50 border border-green-200 text-green-900'
                : saveStatus.startsWith('❌')
                ? 'bg-red-50 border border-red-200 text-red-900'
                : 'bg-blue-50 border border-blue-200 text-blue-900'
            }`}>
              {saveStatus}
            </div>
          )}

          {/* Action Buttons - Responsive */}
          <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t">
            <button
              onClick={handleReset}
              className="flex-1 px-4 py-2 sm:px-6 sm:py-3 text-sm sm:text-base bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition order-3 sm:order-1"
            >
              🔄 Generate Another Batch
            </button>
            <button
              onClick={handleSaveAllToDatabase}
              disabled={isSaving || progress.completed === 0 || !campaignName.trim()}
              className="flex-1 sm:flex-none px-4 py-2 sm:px-6 sm:py-3 text-sm sm:text-base bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed order-1 sm:order-2"
            >
              {isSaving ? '💾 Saving...' : `💾 Save to Campaign (${progress.completed})`}
            </button>
            <button
              onClick={() => {
                // Download all successful posters
                results.filter(r => r.success).forEach(async (result, idx) => {
                  setTimeout(async () => {
                    try {
                      const response = await fetch(result.posterUrl);
                      const blob = await response.blob();
                      const url = window.URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = `${result.username}-poster.png`;
                      a.click();
                      window.URL.revokeObjectURL(url);
                    } catch (err) {
                      console.error('Failed to download:', result.username);
                    }
                  }, idx * 500);
                });
              }}
              className="flex-1 sm:flex-none px-4 py-2 sm:px-6 sm:py-3 text-sm sm:text-base border-2 border-blue-600 text-blue-600 font-semibold rounded-lg hover:bg-blue-50 transition order-2 sm:order-3"
            >
              📦 Download All ({progress.completed})
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
