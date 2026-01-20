'use client';

import { useState } from 'react';
import { sharePosterToMultipleUsers } from '../lib/topmate-share';
import { PosterFlowMode, PosterSize } from '../types/poster';
import { getTopmateLogo } from '../lib/topmate-logo';
import { apiFetch } from '../lib/api';

interface TopmateShareProps {
  posterHtml?: string;         // For HTML mode posters
  posterImageUrl?: string;     // For image mode posters
  profileUserId: string;       // Auto-extracted from Topmate profile
  displayName: string;         // User's display name for confirmation
  flowMode: PosterFlowMode;    // 'single' or 'bulk'
  bulkMethod?: 'prompt' | 'csv'; // Bulk generation method
  htmlTemplate?: string;       // Deprecated - not used
  htmlTemplateUsers?: string;  // Pre-filled users for bulk mode
  prompt?: string;             // For bulk mode regeneration
  selectedProfileData?: { profile: any; selectedFields: string[] };  // For bulk mode - Topmate profile data
  size?: PosterSize;           // For bulk mode regeneration
  model?: 'pro' | 'flash';     // For bulk mode regeneration
  onClose?: () => void;
}

export default function TopmateShare({
  posterHtml,
  posterImageUrl,
  profileUserId,
  displayName,
  flowMode,
  bulkMethod,
  htmlTemplate,
  htmlTemplateUsers,
  prompt,
  selectedProfileData,
  size,
  model,
  onClose
}: TopmateShareProps) {
  const [posterName, setPosterName] = useState('');
  const [shareResult, setShareResult] = useState('');
  const [isSharing, setIsSharing] = useState(false);

  // Bulk mode specific states
  const [userIdentifiers, setUserIdentifiers] = useState(htmlTemplateUsers || '');
  const [bulkProgress, setBulkProgress] = useState({ current: 0, total: 0, status: '' });
  const [bulkResults, setBulkResults] = useState<any[]>([]); // Generated posters for preview
  const [showPreview, setShowPreview] = useState(false); // Show preview before save

  // Save bulk posters after preview
  const handleSaveBulk = async () => {
    setIsSharing(true);
    setShareResult('');
    setBulkProgress({ current: 0, total: 0, status: 'Saving to database...' });

    try {
      const successfulResults = bulkResults.filter((r: any) => r.success);

      if (successfulResults.length === 0) {
        throw new Error('No successful generations to save');
      }

      const saveResponse = await apiFetch('/api/save-bulk-posters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          posters: successfulResults.map((r: any) => ({
            userId: r.userId,
            username: r.username,
            posterUrl: r.posterUrl,
          })),
          posterName: posterName.trim(),
        }),
      });

      const saveData = await saveResponse.json();

      if (!saveResponse.ok) {
        throw new Error(saveData.error || 'Failed to save posters');
      }

      // Build final results message
      let message = `✅ Bulk Save Complete!\n\n`;
      message += `💾 Saved: ${saveData.successCount}/${successfulResults.length} to database\n\n`;
      message += `Campaign: "${posterName}"\n\n`;

      message += `🎯 Results:\n`;
      saveData.results.forEach((result: any) => {
        if (result.success) {
          message += `✅ User ${result.userId}: Saved\n`;
        } else {
          message += `❌ User ${result.userId}: ${result.error}\n`;
        }
      });

      setShareResult(message);
      setShowPreview(false); // Hide preview after save
    } catch (error) {
      setShareResult(`❌ Save Error: ${error}`);
    } finally {
      setIsSharing(false);
      setBulkProgress({ current: 0, total: 0, status: '' });
    }
  };

  const handleShare = async () => {
    if (!posterName.trim()) {
      alert('Please enter a poster name');
      return;
    }

    // Bulk mode requires user identifiers
    if (flowMode === 'bulk' && !userIdentifiers.trim()) {
      alert('Please enter at least one username or user ID');
      return;
    }

    setIsSharing(true);
    setShareResult('');
    setBulkProgress({ current: 0, total: 0, status: '' });

    try {
      // BULK MODE: Generate for multiple users (show preview, then save separately)
      if (flowMode === 'bulk') {
        // Step 1: Bulk generate
        setBulkProgress({ current: 0, total: 0, status: 'Generating posters for all users...' });

        // Get hardcoded Topmate logo
        const topmateLogo = getTopmateLogo();

        const generateResponse = await apiFetch('/api/generate-bulk', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            // Only prompt mode supported - send template image URL
            selectedTemplateImageUrl: posterImageUrl,
            bulkMethod: 'prompt',
            userIdentifiers: userIdentifiers.trim(),
            posterName: posterName.trim(),
            originalPrompt: prompt || '',
            size: size || 'instagram-square',
            model: model || 'pro',
            selectedProfileData,
            topmateLogo: topmateLogo, // Include Topmate logo (hardcoded)
          }),
        });

        const generateData = await generateResponse.json();

        if (!generateResponse.ok) {
          throw new Error(generateData.error || 'Bulk generation failed');
        }

        const { results, successCount, failureCount } = generateData;

        // Store results for preview
        setBulkResults(results);
        setShowPreview(true);

        let message = `✅ Generated ${successCount}/${successCount + failureCount} posters!\n\n`;
        message += `📸 Preview the generated posters below.\n`;
        message += `Click "Save All to Database" when ready.\n`;

        setShareResult(message);
      }
      // SINGLE MODE: Use existing flow
      else {
        const userId = parseInt(profileUserId);

        if (isNaN(userId)) {
          alert('Invalid user ID from profile');
          setIsSharing(false);
          return;
        }

        const userIds = [userId];

        // If we have an image URL (image mode), we need to convert it to HTML first
        let htmlToShare = posterHtml;

        if (!htmlToShare && posterImageUrl) {
          // For image mode, convert the data URL to a blob and wrap in minimal HTML
          htmlToShare = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { margin: 0; padding: 0; width: 1080px; height: 1080px; }
    img { width: 100%; height: 100%; object-fit: contain; }
  </style>
</head>
<body>
  <img src="${posterImageUrl}" alt="Generated Poster" />
</body>
</html>`;
        }

        if (!htmlToShare) {
          alert('No poster content available to share');
          setIsSharing(false);
          return;
        }

        const results = await sharePosterToMultipleUsers({
          posterHtml: htmlToShare,
          posterName,
          userIds,
        });

        let message = `✅ Shared "${posterName}" to ${displayName}\n\n`;

        const result = results[0];
        if (result.success) {
          message += `✅ User ${displayName} (ID: ${userId}): ${result.posterUrl}\n`;
        } else {
          message += `❌ User ${displayName} (ID: ${userId}): ${result.error}\n`;
        }

        message += `\n📋 Django Admin Config:\n{"campaign": "${posterName}", "content_type": "image"}`;

        setShareResult(message);
      }
    } catch (error) {
      setShareResult(`❌ Error: ${error}`);
    } finally {
      setIsSharing(false);
      setBulkProgress({ current: 0, total: 0, status: '' });
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">Share to Topmate</h2>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Poster Name */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              📝 Poster Name *
            </label>
            <input
              type="text"
              value={posterName}
              onChange={(e) => setPosterName(e.target.value)}
              placeholder="e.g., verified-badge-jan-2024"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="text-xs text-gray-500">
              💡 Use lowercase with hyphens (e.g., "my-verified-badge")
            </p>
          </div>

          {/* Sharing Target - Single Mode */}
          {flowMode === 'single' && (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <label className="block text-sm font-medium text-blue-900 mb-2">
                👤 Sharing To:
              </label>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <p className="font-semibold text-gray-900">{displayName}</p>
                  <p className="text-sm text-gray-600">User ID: {profileUserId}</p>
                </div>
                <div className="text-green-600">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
            </div>
          )}

          {/* User Identifiers Input - Bulk Mode */}
          {flowMode === 'bulk' && (
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                👥 Target Users (Usernames or User IDs) *
              </label>
              <textarea
                value={userIdentifiers}
                onChange={(e) => setUserIdentifiers(e.target.value)}
                placeholder="Enter usernames or user IDs (comma or newline separated)&#10;Examples:&#10;john_doe, 12345, sarah_coach&#10;OR&#10;john_doe&#10;12345&#10;sarah_coach"
                rows={6}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
              />
              <p className="text-xs text-gray-500">
                💡 Mix usernames and numeric user IDs. Separate with commas or new lines.
              </p>
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-800">
                  ⚠️ This will generate personalized posters for each user using the template design above.
                </p>
              </div>
            </div>
          )}

          {/* Progress Indicator - Bulk Mode */}
          {flowMode === 'bulk' && bulkProgress.status && (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center gap-3">
                <svg className="animate-spin h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <div className="flex-1">
                  <p className="font-medium text-blue-900">{bulkProgress.status}</p>
                  {bulkProgress.total > 0 && (
                    <p className="text-sm text-blue-700">
                      {bulkProgress.current} / {bulkProgress.total}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Share/Generate Button */}
          {!showPreview && (
            <button
              onClick={handleShare}
              disabled={!posterName || isSharing || (flowMode === 'bulk' && !userIdentifiers.trim())}
              className="w-full px-6 py-4 bg-blue-600 text-white font-semibold text-lg rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg"
            >
              {isSharing ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {flowMode === 'bulk' ? 'Generating Posters...' : 'Sharing to Topmate...'}
                </span>
              ) : (
                flowMode === 'bulk' ? '🎨 Generate for All Users' : '🚀 Share to Topmate'
              )}
            </button>
          )}

          {/* Preview Grid - Bulk Mode Only */}
          {showPreview && bulkResults.length > 0 && (
            <div className="space-y-4">
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <h3 className="font-semibold text-blue-900 mb-2">📸 Preview Generated Posters</h3>
                <p className="text-sm text-blue-700">
                  Review the generated posters below. Click "Save All to Database" when ready.
                </p>
              </div>

              {/* Grid of Generated Posters */}
              <div className="grid grid-cols-2 gap-4 max-h-96 overflow-y-auto p-2 bg-slate-50 rounded-lg border border-slate-200">
                {bulkResults.map((result, idx) => (
                  <div key={idx} className="bg-white rounded-lg border border-slate-300 overflow-hidden">
                    {result.success ? (
                      <>
                        <div className="aspect-square relative">
                          <img
                            src={result.posterUrl || result.imageUrl}
                            alt={`Poster for ${result.username}`}
                            className="w-full h-full object-cover"
                          />
                          <div className="absolute top-2 right-2 px-2 py-1 bg-green-600 text-white text-xs rounded">
                            ✓
                          </div>
                        </div>
                        <div className="p-2 bg-slate-50">
                          <p className="text-sm font-medium text-gray-900">@{result.username}</p>
                          <p className="text-xs text-gray-600">ID: {result.userId}</p>
                        </div>
                      </>
                    ) : (
                      <div className="aspect-square flex flex-col items-center justify-center p-4 bg-red-50">
                        <svg className="w-12 h-12 text-red-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                        <p className="text-sm font-medium text-red-900">@{result.username}</p>
                        <p className="text-xs text-red-600 text-center mt-1">{result.error}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Save Button */}
              <button
                onClick={handleSaveBulk}
                disabled={isSharing}
                className="w-full px-6 py-4 bg-green-600 text-white font-semibold text-lg rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg"
              >
                {isSharing ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Saving to Database...
                  </span>
                ) : (
                  `💾 Save All to Database (${bulkResults.filter(r => r.success).length} posters)`
                )}
              </button>
            </div>
          )}

          {/* Results */}
          {shareResult && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <h3 className="font-semibold text-green-900 mb-2">Results</h3>
              <pre className="text-sm whitespace-pre-wrap font-mono text-gray-800">
                {shareResult}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
