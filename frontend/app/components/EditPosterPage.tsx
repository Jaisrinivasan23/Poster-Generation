'use client';

import { useState, useRef, useEffect } from 'react';

interface GeneratedPoster {
  html: string;
  description?: string;
  theme?: string;
  dimensions?: { width: number; height: number };
}

interface EditHistoryItem {
  timestamp: string;
  instruction: string;
  summary: string;
  previousHtml: string;
  newHtml: string;
}

interface EditMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface SelectedElement {
  selector: string;
  tag: string;
  classes: string[];
  text: string;
  outer_html: string;
  color_classes: string[];
  element: HTMLElement;
  rect: DOMRect;
}

interface EditPosterPageProps {
  initialPoster: GeneratedPoster;
  posterIndex: number;
  onBack: () => void;
  onSave: (updatedPoster: GeneratedPoster) => void;
}

export default function EditPosterPage({
  initialPoster,
  posterIndex,
  onBack,
  onSave,
}: EditPosterPageProps) {
  // Core state
  const [poster, setPoster] = useState<GeneratedPoster>(initialPoster);
  const [selectedElement, setSelectedElement] = useState<SelectedElement | null>(null);
  const [editHistory, setEditHistory] = useState<EditHistoryItem[]>([]);
  const [editMessages, setEditMessages] = useState<EditMessage[]>([]);
  const [currentHistoryIndex, setCurrentHistoryIndex] = useState(-1);

  // UI state
  const [editInstruction, setEditInstruction] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(true);

  // Floating controls state
  const [showFloatingControls, setShowFloatingControls] = useState(false);
  const [floatingControlsPosition, setFloatingControlsPosition] = useState({ x: 0, y: 0 });
  const [colorValue, setColorValue] = useState('#000000');
  const [fontSize, setFontSize] = useState('16');
  const [fontFamily, setFontFamily] = useState('inherit');
  const [isBold, setIsBold] = useState(false);
  const [previewScale, setPreviewScale] = useState(1);

  const previewRef = useRef<HTMLIFrameElement>(null);
  const previewContainerRef = useRef<HTMLDivElement>(null);
  const dimensions = poster.dimensions || { width: 1080, height: 1080 };

  // Setup iframe click listener for element selection
  useEffect(() => {
    setupIframeListener();
  }, [poster]);

  // Calculate responsive scale based on container size
  useEffect(() => {
    const calculateScale = () => {
      if (!previewContainerRef.current) return;
      
      const container = previewContainerRef.current;
      const containerWidth = container.clientWidth - 64; // padding
      const containerHeight = container.clientHeight - 64; // padding
      
      const scaleX = containerWidth / dimensions.width;
      const scaleY = containerHeight / dimensions.height;
      const scale = Math.min(scaleX, scaleY, 1); // Don't scale up, only down
      
      setPreviewScale(scale);
    };

    calculateScale();
    window.addEventListener('resize', calculateScale);
    return () => window.removeEventListener('resize', calculateScale);
  }, [dimensions.width, dimensions.height, showHistory]);

  const setupIframeListener = () => {
    const iframe = previewRef.current;
    if (!iframe || !iframe.contentDocument) return;

    const handleClick = (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const target = e.target as HTMLElement;
      if (!target || target === iframe.contentDocument!.body) return;

      // Get element's bounding rect relative to iframe
      const rect = target.getBoundingClientRect();

      // Extract element information
      const selector = generateSelector(target);
      const computedStyle = iframe.contentWindow!.getComputedStyle(target);

      const elementData: SelectedElement = {
        selector,
        tag: target.tagName.toLowerCase(),
        classes: Array.from(target.classList),
        text: target.textContent?.trim() || '',
        outer_html: target.outerHTML,
        color_classes: Array.from(target.classList).filter(cls =>
          cls.includes('bg-') || cls.includes('text-') || cls.includes('border-')
        ),
        element: target,
        rect: rect,
      };

      // Extract current styles
      setColorValue(rgbToHex(computedStyle.color));
      setFontSize(parseInt(computedStyle.fontSize).toString());
      setFontFamily(computedStyle.fontFamily.split(',')[0].replace(/['"]/g, ''));
      setIsBold(parseInt(computedStyle.fontWeight) >= 600);

      setSelectedElement(elementData);
      highlightElement(target, rect);
      showFloatingControlsPanel(rect);
    };

    iframe.contentDocument.addEventListener('click', handleClick);
    return () => {
      iframe.contentDocument?.removeEventListener('click', handleClick);
    };
  };

  const rgbToHex = (rgb: string): string => {
    if (rgb.startsWith('#')) return rgb;
    const match = rgb.match(/\d+/g);
    if (!match) return '#000000';
    const [r, g, b] = match.map(Number);
    return '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('');
  };

  const generateSelector = (element: HTMLElement): string => {
    if (element.id) return `#${element.id}`;

    let selector = element.tagName.toLowerCase();
    if (element.className) {
      const classes = Array.from(element.classList).slice(0, 3).join('.');
      if (classes) selector += `.${classes}`;
    }

    return selector;
  };

  const highlightElement = (element: HTMLElement, rect: DOMRect) => {
    const iframe = previewRef.current;
    if (!iframe || !iframe.contentDocument) return;

    // Remove previous highlights
    const prevHighlights = iframe.contentDocument.querySelectorAll('.edit-highlight-border');
    prevHighlights.forEach(h => h.remove());

    // Create highlight overlay
    const highlight = iframe.contentDocument.createElement('div');
    highlight.className = 'edit-highlight-border';

    // Get scroll position
    const scrollTop = iframe.contentDocument.documentElement.scrollTop || iframe.contentDocument.body.scrollTop;
    const scrollLeft = iframe.contentDocument.documentElement.scrollLeft || iframe.contentDocument.body.scrollLeft;

    // Calculate position relative to document
    const top = rect.top + scrollTop;
    const left = rect.left + scrollLeft;

    highlight.style.cssText = `
      position: absolute;
      top: ${top}px;
      left: ${left}px;
      width: ${rect.width}px;
      height: ${rect.height}px;
      border: 3px solid #8b5cf6;
      background: rgba(139, 92, 246, 0.1);
      pointer-events: none;
      z-index: 9999;
      box-shadow: 0 0 0 2px white, 0 0 0 5px #8b5cf6, 0 4px 12px rgba(139, 92, 246, 0.4);
      border-radius: 2px;
    `;

    iframe.contentDocument.body.appendChild(highlight);
  };

  const showFloatingControlsPanel = (rect: DOMRect) => {
    const iframe = previewRef.current;
    const container = previewContainerRef.current;
    if (!iframe || !container) return;

    // Get iframe position in the viewport
    const iframeRect = iframe.getBoundingClientRect();
    
    // Calculate scaled element position
    const scaledElementCenterX = iframeRect.left + (rect.left + rect.width / 2) * previewScale;
    const scaledElementBottom = iframeRect.top + rect.bottom * previewScale;

    setFloatingControlsPosition({ 
      x: scaledElementCenterX, 
      y: scaledElementBottom + 10 
    });
    setShowFloatingControls(true);
  };

  const handleApplyStyleChange = async (styleType: 'color' | 'fontSize' | 'fontFamily' | 'fontWeight', value: string | boolean) => {
    if (!selectedElement) return;

    setIsEditing(true);
    setError(null);

    let instruction = '';
    if (styleType === 'color') {
      instruction = `Change the text color to ${value}`;
    } else if (styleType === 'fontSize') {
      instruction = `Change the font size to ${value}px`;
    } else if (styleType === 'fontFamily') {
      instruction = `Change the font family to ${value}`;
    } else if (styleType === 'fontWeight') {
      instruction = value ? 'Make the text bold' : 'Make the text normal weight (not bold)';
    }

    try {
      const response = await fetch('http://localhost:8000/api/edit-poster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          html: poster.html,
          edit_instruction: instruction,
          selected_element: {
            selector: selectedElement.selector,
            tag: selectedElement.tag,
            classes: selectedElement.classes,
            text: selectedElement.text,
            outer_html: selectedElement.outer_html,
            color_classes: selectedElement.color_classes,
          },
          design_context: null,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Failed to apply style change');
      }

      // Create history entry
      const historyEntry: EditHistoryItem = {
        timestamp: new Date().toISOString(),
        instruction,
        summary: data.summary || 'Style applied',
        previousHtml: poster.html,
        newHtml: data.html,
      };

      // Update poster
      const updatedPoster = { ...poster, html: data.html };
      setPoster(updatedPoster);

      // Update history
      const newHistory = [...editHistory.slice(0, currentHistoryIndex + 1), historyEntry];
      setEditHistory(newHistory);
      setCurrentHistoryIndex(newHistory.length - 1);

      // Add to chat messages
      setEditMessages([
        ...editMessages,
        { role: 'user', content: instruction },
        { role: 'assistant', content: data.summary || 'Style applied' },
      ]);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply style');
    } finally {
      setIsEditing(false);
    }
  };

  const handleEditSubmit = async () => {
    if (!editInstruction.trim()) {
      setError('Please enter an edit instruction');
      return;
    }

    if (!selectedElement) {
      setError('Please select an element to edit');
      return;
    }

    setIsEditing(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/edit-poster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          html: poster.html,
          edit_instruction: editInstruction,
          selected_element: {
            selector: selectedElement.selector,
            tag: selectedElement.tag,
            classes: selectedElement.classes,
            text: selectedElement.text,
            outer_html: selectedElement.outer_html,
            color_classes: selectedElement.color_classes,
          },
          design_context: null,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Failed to edit poster');
      }

      // Create history entry
      const historyEntry: EditHistoryItem = {
        timestamp: new Date().toISOString(),
        instruction: editInstruction,
        summary: data.summary || 'Edit completed',
        previousHtml: poster.html,
        newHtml: data.html,
      };

      // Update poster
      const updatedPoster = { ...poster, html: data.html };
      setPoster(updatedPoster);

      // Update history
      const newHistory = [...editHistory.slice(0, currentHistoryIndex + 1), historyEntry];
      setEditHistory(newHistory);
      setCurrentHistoryIndex(newHistory.length - 1);

      // Add to chat messages
      setEditMessages([
        ...editMessages,
        { role: 'user', content: editInstruction },
        { role: 'assistant', content: data.summary || 'Edit completed' },
      ]);

      // Clear input
      setEditInstruction('');
      setSelectedElement(null);
      setShowFloatingControls(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to edit poster');
    } finally {
      setIsEditing(false);
    }
  };

  const handleUndo = () => {
    if (currentHistoryIndex < 0) return;

    const historyItem = editHistory[currentHistoryIndex];
    setPoster({ ...poster, html: historyItem.previousHtml });
    setCurrentHistoryIndex(currentHistoryIndex - 1);
    setSelectedElement(null);
    setShowFloatingControls(false);
  };

  const handleRedo = () => {
    if (currentHistoryIndex >= editHistory.length - 1) return;

    const historyItem = editHistory[currentHistoryIndex + 1];
    setPoster({ ...poster, html: historyItem.newHtml });
    setCurrentHistoryIndex(currentHistoryIndex + 1);
    setSelectedElement(null);
    setShowFloatingControls(false);
  };

  const handleSave = () => {
    onSave(poster);
    onBack();
  };

  const canUndo = currentHistoryIndex >= 0;
  const canRedo = currentHistoryIndex < editHistory.length - 1;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            title="Back to posters"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Edit Poster #{posterIndex + 1}</h1>
            <p className="text-sm text-slate-500">Click on elements to edit them with AI</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Undo/Redo */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
            <button
              onClick={handleUndo}
              disabled={!canUndo}
              className="p-2 rounded hover:bg-white disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              title="Undo (Ctrl+Z)"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
              </svg>
            </button>
            <button
              onClick={handleRedo}
              disabled={!canRedo}
              className="p-2 rounded hover:bg-white disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              title="Redo (Ctrl+Y)"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10h-10a8 8 0 00-8 8v2m18-10l-6 6m6-6l-6-6" />
              </svg>
            </button>
            <span className="text-xs text-slate-500 px-2">
              {currentHistoryIndex + 1}/{editHistory.length}
            </span>
          </div>

          <button
            onClick={handleSave}
            className="px-6 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-medium rounded-lg transition-all flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Save & Close
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Sidebar - History & Chat */}
        <div className={`bg-white border-r border-slate-200 flex flex-col transition-all duration-300 ${showHistory ? 'w-80' : 'w-0'}`}>
          {showHistory && (
            <>
              <div className="p-4 border-b border-slate-200 flex items-center justify-between">
                <h2 className="font-semibold text-slate-900">History & Chat</h2>
                <button
                  onClick={() => setShowHistory(false)}
                  className="p-1 hover:bg-slate-100 rounded transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                  </svg>
                </button>
              </div>

              {/* Edit History */}
              <div className="p-4 border-b border-slate-200">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Edit History ({editHistory.length})</h3>
                {editHistory.length === 0 ? (
                  <p className="text-xs text-slate-400 text-center py-4">No edits yet</p>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {editHistory.map((item, idx) => (
                      <div
                        key={idx}
                        className={`p-3 rounded-lg text-xs border transition-all cursor-pointer ${
                          idx === currentHistoryIndex
                            ? 'bg-purple-50 border-purple-200'
                            : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                        }`}
                        onClick={() => {
                          setPoster({ ...poster, html: item.newHtml });
                          setCurrentHistoryIndex(idx);
                        }}
                      >
                        <p className="font-medium text-slate-900 mb-1">{item.summary}</p>
                        <p className="text-slate-500 line-clamp-2">{item.instruction}</p>
                        <p className="text-slate-400 mt-1">
                          {new Date(item.timestamp).toLocaleTimeString()}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50">
                {editMessages.length === 0 ? (
                  <div className="text-center text-slate-400 py-12">
                    <svg className="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                    <p className="text-sm font-medium">Start editing</p>
                    <p className="text-xs mt-1">Select an element and describe your changes</p>
                  </div>
                ) : (
                  editMessages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] rounded-lg px-4 py-2 ${
                        msg.role === 'user'
                          ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white'
                          : 'bg-white text-slate-900 border border-slate-200 shadow-sm'
                      }`}>
                        <p className="text-sm leading-relaxed">{msg.content}</p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        {/* Toggle History Button */}
        {!showHistory && (
          <button
            onClick={() => setShowHistory(true)}
            className="w-8 bg-white border-r border-slate-200 hover:bg-slate-50 flex items-center justify-center transition-colors"
            title="Show history"
          >
            <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        )}

        {/* Center - Poster Preview */}
        <div ref={previewContainerRef} className="flex-1 flex flex-col overflow-hidden bg-gradient-to-br from-slate-100 to-slate-200 relative">
          <div className="flex-1 flex items-center justify-center p-4">
            <div
              className="bg-white rounded-lg shadow-2xl overflow-hidden"
              style={{
                width: dimensions.width * previewScale,
                height: dimensions.height * previewScale,
                flexShrink: 0,
              }}
            >
              <iframe
                ref={previewRef}
                srcDoc={poster.html}
                onLoad={setupIframeListener}
                style={{
                  width: dimensions.width,
                  height: dimensions.height,
                  transform: `scale(${previewScale})`,
                  transformOrigin: 'top left',
                  border: 'none',
                  display: 'block',
                }}
                className="bg-white cursor-pointer"
                title="Poster Preview"
              />
            </div>
          </div>

          {/* Floating Controls Panel */}
          {showFloatingControls && selectedElement && (
            <div
              className="fixed bg-white rounded-lg shadow-2xl border-2 border-purple-500 p-4 z-50"
              style={{
                left: `${floatingControlsPosition.x}px`,
                top: `${floatingControlsPosition.y}px`,
                transform: 'translateX(-50%)',
                minWidth: '320px',
              }}
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-slate-900">Quick Edit</h4>
                <button
                  onClick={() => {
                    setShowFloatingControls(false);
                    setSelectedElement(null);
                  }}
                  className="p-1 hover:bg-slate-100 rounded"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-3">
                {/* Color */}
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1 block">Text Color</label>
                  <div className="flex gap-2">
                    <input
                      type="color"
                      value={colorValue}
                      onChange={(e) => setColorValue(e.target.value)}
                      className="w-12 h-9 rounded border border-slate-300 cursor-pointer"
                      disabled={isEditing}
                    />
                    <input
                      type="text"
                      value={colorValue}
                      onChange={(e) => setColorValue(e.target.value)}
                      className="flex-1 px-3 py-2 border border-slate-300 rounded text-sm font-mono"
                      disabled={isEditing}
                    />
                    <button
                      onClick={() => handleApplyStyleChange('color', colorValue)}
                      disabled={isEditing}
                      className="px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 text-white text-xs font-medium rounded"
                    >
                      Apply
                    </button>
                  </div>
                </div>

                {/* Bold Toggle */}
                {selectedElement.text && (
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1 block">Text Weight</label>
                    <button
                      onClick={() => {
                        const newBoldState = !isBold;
                        setIsBold(newBoldState);
                        handleApplyStyleChange('fontWeight', newBoldState);
                      }}
                      disabled={isEditing}
                      className={`w-full px-3 py-2 border rounded text-sm font-medium transition-colors ${
                        isBold
                          ? 'bg-purple-600 text-white border-purple-600 hover:bg-purple-700'
                          : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                      } disabled:bg-slate-300 disabled:text-slate-500`}
                    >
                      <span className="flex items-center justify-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 4h8a4 4 0 014 4 4 4 0 01-4 4H6z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 12h9a4 4 0 014 4 4 4 0 01-4 4H6z" />
                        </svg>
                        {isBold ? 'Bold (On)' : 'Bold (Off)'}
                      </span>
                    </button>
                  </div>
                )}

                {/* Font Size */}
                {selectedElement.text && (
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1 block">Font Size</label>
                    <div className="flex gap-2 items-center">
                      <button
                        onClick={() => {
                          const newSize = Math.max(8, parseInt(fontSize) - 2);
                          setFontSize(newSize.toString());
                        }}
                        disabled={isEditing}
                        className="px-2 py-2 bg-slate-200 hover:bg-slate-300 disabled:bg-slate-300 rounded"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                        </svg>
                      </button>
                      <input
                        type="number"
                        value={fontSize}
                        onChange={(e) => setFontSize(e.target.value)}
                        min="8"
                        max="200"
                        className="flex-1 px-3 py-2 border border-slate-300 rounded text-sm text-center"
                        disabled={isEditing}
                      />
                      <span className="text-xs text-slate-600">px</span>
                      <button
                        onClick={() => {
                          const newSize = Math.min(200, parseInt(fontSize) + 2);
                          setFontSize(newSize.toString());
                        }}
                        disabled={isEditing}
                        className="px-2 py-2 bg-slate-200 hover:bg-slate-300 disabled:bg-slate-300 rounded"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleApplyStyleChange('fontSize', fontSize)}
                        disabled={isEditing}
                        className="px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 text-white text-xs font-medium rounded"
                      >
                        Apply
                      </button>
                    </div>
                  </div>
                )}

                {/* Font Family */}
                {selectedElement.text && (
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1 block">Font Family</label>
                    <div className="flex gap-2">
                      <select
                        value={fontFamily}
                        onChange={(e) => setFontFamily(e.target.value)}
                        className="flex-1 px-3 py-2 border border-slate-300 rounded text-sm"
                        disabled={isEditing}
                      >
                        <option value="inherit">Inherit</option>
                        <option value="Arial">Arial</option>
                        <option value="Helvetica">Helvetica</option>
                        <option value="Times New Roman">Times New Roman</option>
                        <option value="Georgia">Georgia</option>
                        <option value="Verdana">Verdana</option>
                        <option value="Courier New">Courier New</option>
                        <option value="Inter">Inter</option>
                        <option value="Roboto">Roboto</option>
                        <option value="Open Sans">Open Sans</option>
                        <option value="Montserrat">Montserrat</option>
                        <option value="Poppins">Poppins</option>
                        <option value="Playfair Display">Playfair Display</option>
                        <option value="Lato">Lato</option>
                      </select>
                      <button
                        onClick={() => handleApplyStyleChange('fontFamily', fontFamily)}
                        disabled={isEditing}
                        className="px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 text-white text-xs font-medium rounded"
                      >
                        Apply
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Sidebar - Selected Element & Controls */}
        <div className="w-96 bg-white border-l border-slate-200 flex flex-col">
          <div className="p-4 border-b border-slate-200">
            <h2 className="font-semibold text-slate-900">AI Edit</h2>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {selectedElement ? (
              <div className="space-y-4">
                {/* Element Info Card */}
                <div className="p-4 bg-gradient-to-br from-purple-50 to-pink-50 border border-purple-200 rounded-xl">
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 bg-purple-600 text-white text-xs font-medium rounded">
                          {selectedElement.tag.toUpperCase()}
                        </span>
                        {selectedElement.classes.length > 0 && (
                          <span className="text-xs text-purple-600 font-mono">
                            .{selectedElement.classes.slice(0, 2).join('.')}
                          </span>
                        )}
                      </div>
                      <p className="text-sm font-mono text-purple-900 break-all">
                        {selectedElement.selector}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedElement(null);
                        setShowFloatingControls(false);
                      }}
                      className="p-1 hover:bg-purple-100 rounded transition-colors"
                      title="Clear selection"
                    >
                      <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  {selectedElement.text && (
                    <div className="p-3 bg-white border border-purple-200 rounded-lg">
                      <p className="text-xs text-purple-700 font-medium mb-1">Content:</p>
                      <p className="text-sm text-slate-900 line-clamp-3">{selectedElement.text}</p>
                    </div>
                  )}
                </div>

                {/* Quick Actions */}
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Quick Prompts</h3>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setEditInstruction('Change the text to ')}
                      className="p-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors"
                    >
                      Change Text
                    </button>
                    <button
                      onClick={() => setEditInstruction('Make it ')}
                      className="p-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors"
                    >
                      Modify Style
                    </button>
                    <button
                      onClick={() => setEditInstruction('Make it bold')}
                      className="p-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors"
                    >
                      Make Bold
                    </button>
                    <button
                      onClick={() => setEditInstruction('Add a shadow to ')}
                      className="p-3 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition-colors"
                    >
                      Add Shadow
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <div className="w-20 h-20 bg-gradient-to-br from-purple-100 to-pink-100 rounded-2xl flex items-center justify-center mb-4">
                  <svg className="w-10 h-10 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">No Element Selected</h3>
                <p className="text-sm text-slate-500 max-w-xs">
                  Click on any element in the poster preview to select it for editing
                </p>
              </div>
            )}
          </div>

          {/* Edit Input - Fixed at bottom */}
          <div className="p-4 border-t border-slate-200 bg-slate-50">
            {error && (
              <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {error}
              </div>
            )}

            <div className="space-y-3">
              <textarea
                value={editInstruction}
                onChange={(e) => setEditInstruction(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && e.ctrlKey && !isEditing && editInstruction.trim() && selectedElement) {
                    handleEditSubmit();
                  }
                }}
                placeholder={selectedElement ? "Describe your change... (Ctrl+Enter to submit)" : "Select an element first..."}
                disabled={isEditing || !selectedElement}
                rows={3}
                className="w-full px-4 py-3 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:bg-slate-100 disabled:text-slate-400 resize-none"
              />

              <button
                onClick={handleEditSubmit}
                disabled={!editInstruction.trim() || isEditing || !selectedElement}
                className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:from-slate-300 disabled:to-slate-300 text-white font-medium rounded-lg transition-all flex items-center justify-center gap-2"
              >
                {isEditing ? (
                  <>
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Editing...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Apply AI Edit
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
