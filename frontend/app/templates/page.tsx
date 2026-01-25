'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  listTemplates,
  uploadTemplate,
  type Template,
} from '@/app/lib/api';

export default function TemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [sections, setSections] = useState<string[]>([]);
  const [selectedSection, setSelectedSection] = useState<string>('all');
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [placeholderValues, setPlaceholderValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(true);
  const [showUploadForm, setShowUploadForm] = useState(false);

  // Upload form state
  const [uploadSection, setUploadSection] = useState('');
  const [uploadName, setUploadName] = useState('');
  const [uploadHtml, setUploadHtml] = useState('');
  const [uploadCss, setUploadCss] = useState('');
  const [uploadSetActive, setUploadSetActive] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadPreviewValues, setUploadPreviewValues] = useState<Record<string, string>>({});

  // Edit mode state
  const [isEditMode, setIsEditMode] = useState(false);
  const [editTemplateId, setEditTemplateId] = useState<string | null>(null);

  // Fetch all templates on mount
  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    setIsLoadingTemplates(true);
    try {
      const data = await listTemplates();
      setTemplates(data.templates || []);

      // Extract unique sections
      const uniqueSections = Array.from(
        new Set(data.templates.map((t: Template) => t.section))
      ) as string[];
      setSections(uniqueSections);

      // Select first active template
      const activeTemplate = data.templates.find((t: Template) => t.is_active);
      if (activeTemplate) {
        selectTemplate(activeTemplate);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load templates');
      console.error(err);
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const selectTemplate = (template: Template) => {
    setSelectedTemplate(template);
    setError(null);

    // Initialize placeholder values with sample values or empty strings
    const initialValues: Record<string, string> = {};
    template.placeholders.forEach(p => {
      initialValues[p.name] = p.sample_value || '';
    });
    setPlaceholderValues(initialValues);
  };

  const startEditTemplate = (template: Template) => {
    setIsEditMode(true);
    setEditTemplateId(template.id);
    setUploadSection(template.section);
    setUploadName(template.name);
    setUploadHtml(template.html_content || '');
    setUploadCss(template.css_content || '');
    setUploadSetActive(template.is_active);
    setShowUploadForm(true);
    setError(null);
    setUploadSuccess(null);
  };

  const cancelEdit = () => {
    setIsEditMode(false);
    setEditTemplateId(null);
    setUploadSection('');
    setUploadName('');
    setUploadHtml('');
    setUploadCss('');
    setUploadSetActive(true);
    setShowUploadForm(false);
    setError(null);
    setUploadSuccess(null);
  };

  const handlePlaceholderChange = (name: string, value: string) => {
    setPlaceholderValues(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleUpload = async () => {
    if (!uploadSection || !uploadName || !uploadHtml) {
      setError('Please fill in section, name, and HTML content');
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadTemplate({
        section: uploadSection,
        name: uploadName,
        html_content: uploadHtml,
        css_content: uploadCss,
        set_as_active: uploadSetActive
      });

      setUploadSuccess(isEditMode 
        ? `Template updated successfully! New version: ${result.version}` 
        : `Template uploaded successfully! Version ${result.version}`);

      // Clear form
      setUploadSection('');
      setUploadName('');
      setUploadHtml('');
      setUploadCss('');
      setUploadSetActive(true);
      setIsEditMode(false);
      setEditTemplateId(null);

      // Refresh templates
      fetchTemplates();

      // Hide upload form after 2 seconds
      setTimeout(() => {
        setShowUploadForm(false);
        setUploadSuccess(null);
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'Failed to upload template');
    } finally {
      setIsUploading(false);
    }
  };

  const getPreviewHtml = () => {
    if (!selectedTemplate) return '';

    let html = selectedTemplate.html_content || '';

    // Replace all placeholders with values
    Object.keys(placeholderValues).forEach(key => {
      const value = placeholderValues[key] || `{${key}}`;
      html = html.replace(new RegExp(`\\{${key}\\}`, 'g'), value);
    });

    // Wrap with CSS if available
    if (selectedTemplate.css_content) {
      return `
        <style>${selectedTemplate.css_content}</style>
        ${html}
      `;
    }

    return html;
  };

  // Extract placeholders from upload HTML
  const extractPlaceholders = (html: string): string[] => {
    const regex = /\{([a-zA-Z_][a-zA-Z0-9_.]*)\}/g;
    const placeholders: string[] = [];
    let match;

    while ((match = regex.exec(html)) !== null) {
      const placeholder = match[1].trim();
      if (!placeholders.includes(placeholder)) {
        placeholders.push(placeholder);
      }
    }

    return placeholders;
  };

  // Get upload preview HTML
  const getUploadPreviewHtml = () => {
    if (!uploadHtml) return '';

    let html = uploadHtml;

    // Replace all placeholders with preview values
    Object.keys(uploadPreviewValues).forEach(key => {
      const value = uploadPreviewValues[key] || `{${key}}`;
      html = html.replace(new RegExp(`\\{${key}\\}`, 'g'), value);
    });

    // Wrap with CSS if available
    if (uploadCss) {
      return `
        <style>${uploadCss}</style>
        ${html}
      `;
    }

    return html;
  };

  // Update upload preview values when HTML changes
  useEffect(() => {
    if (uploadHtml) {
      const placeholders = extractPlaceholders(uploadHtml);
      const newValues: Record<string, string> = {};

      placeholders.forEach(placeholder => {
        // Keep existing values or set to empty
        newValues[placeholder] = uploadPreviewValues[placeholder] || '';
      });

      setUploadPreviewValues(newValues);
    } else {
      setUploadPreviewValues({});
    }
  }, [uploadHtml]);

  const filteredTemplates = selectedSection === 'all'
    ? templates
    : templates.filter(t => t.section === selectedSection);

  // Group templates by section and sort by version
  const groupedTemplates: Record<string, Template[]> = {};
  filteredTemplates.forEach(template => {
    if (!groupedTemplates[template.section]) {
      groupedTemplates[template.section] = [];
    }
    groupedTemplates[template.section].push(template);
  });

  // Sort each section's templates by version (descending)
  Object.keys(groupedTemplates).forEach(section => {
    groupedTemplates[section].sort((a, b) => b.version - a.version);
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50 to-pink-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-screen-2xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/')}
                className="flex items-center gap-2 text-slate-600 hover:text-slate-900 transition"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Back
              </button>
              <div className="h-6 w-px bg-slate-300" />
              <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                Template Manager
              </h1>
            </div>
            <button
              onClick={() => {
                if (showUploadForm && isEditMode) {
                  cancelEdit();
                } else {
                  setShowUploadForm(!showUploadForm);
                }
              }}
              className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-lg text-sm font-medium transition-all flex items-center gap-2 shadow-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              {showUploadForm ? 'Cancel' : 'Upload Template'}
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-screen-2xl mx-auto p-6">
        {/* Upload Form */}
        {showUploadForm && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">
                {isEditMode ? 'Edit Template' : 'Upload New Template'}
              </h2>
              {isEditMode && (
                <button
                  onClick={cancelEdit}
                  className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Cancel Edit
                </button>
              )}
            </div>

            {/* Upload Form Grid: Left = Form, Right = Preview */}
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
              {/* Left: Upload Form Fields */}
              <div className="xl:col-span-5 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Section <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={uploadSection}
                      onChange={(e) => setUploadSection(e.target.value)}
                      placeholder="e.g., testimonial"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Template Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={uploadName}
                      onChange={(e) => setUploadName(e.target.value)}
                      placeholder="e.g., Modern Design"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    HTML Content <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={uploadHtml}
                    onChange={(e) => setUploadHtml(e.target.value)}
                    placeholder="<div>{consumer_name}: {consumer_message}</div>"
                    rows={8}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Use {`{placeholder_name}`} syntax for dynamic content
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    CSS Content (Optional)
                  </label>
                  <textarea
                    value={uploadCss}
                    onChange={(e) => setUploadCss(e.target.value)}
                    placeholder="body { font-family: Arial; }"
                    rows={4}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                  />
                </div>

                <div>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={uploadSetActive}
                      onChange={(e) => setUploadSetActive(e.target.checked)}
                      className="w-4 h-4 text-purple-600 rounded focus:ring-2 focus:ring-purple-500"
                    />
                    <span className="text-sm font-medium text-slate-700">
                      Set as active template for this section
                    </span>
                  </label>
                </div>

                {error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                    {error}
                  </div>
                )}

                {uploadSuccess && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
                    {uploadSuccess}
                  </div>
                )}

                <button
                  onClick={handleUpload}
                  disabled={isUploading}
                  className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:from-slate-300 disabled:to-slate-400 text-white font-semibold rounded-lg transition-all flex items-center justify-center gap-2"
                >
                  {isUploading ? (
                    <>
                      <div className="animate-spin w-5 h-5 border-3 border-white border-t-transparent rounded-full"></div>
                      {isEditMode ? 'Saving...' : 'Uploading...'}
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        {isEditMode ? (
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        ) : (
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        )}
                      </svg>
                      {isEditMode ? 'Save Changes' : 'Upload Template'}
                    </>
                  )}
                </button>
              </div>

              {/* Right: Preview with Placeholder Inputs */}
              <div className="xl:col-span-7 space-y-4">
                {uploadHtml && extractPlaceholders(uploadHtml).length > 0 && (
                  <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                    <h3 className="text-sm font-semibold text-slate-900 mb-3">
                      Detected Placeholders ({extractPlaceholders(uploadHtml).length})
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      {extractPlaceholders(uploadHtml).map(placeholder => (
                        <div key={placeholder}>
                          <label className="block text-xs font-medium text-slate-700 mb-1">
                            {placeholder}
                          </label>
                          <input
                            type="text"
                            value={uploadPreviewValues[placeholder] || ''}
                            onChange={(e) =>
                              setUploadPreviewValues(prev => ({
                                ...prev,
                                [placeholder]: e.target.value
                              }))
                            }
                            placeholder={`Sample ${placeholder}...`}
                            className="w-full px-2 py-1.5 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <h3 className="text-sm font-semibold text-slate-900 mb-2">Live Preview</h3>
                  <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
                    {uploadHtml ? (
                      <div className="relative bg-slate-100 flex items-center justify-center p-4">
                        {/* Scaled preview container */}
                        <div 
                          className="relative bg-white shadow-lg rounded-lg overflow-hidden"
                          style={{
                            width: '300px',
                            height: '300px',
                          }}
                        >
                          <div
                            style={{
                              transform: 'scale(0.28)',
                              transformOrigin: 'top left',
                              width: '1080px',
                              height: '1080px',
                              position: 'absolute',
                              top: 0,
                              left: 0,
                            }}
                          >
                            <iframe
                              srcDoc={`<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{margin:0;padding:0;}</style></head><body>${getUploadPreviewHtml()}</body></html>`}
                              className="w-full h-full border-0"
                              style={{ width: '1080px', height: '1080px', pointerEvents: 'none' }}
                              title="Template Preview"
                              sandbox="allow-same-origin"
                            />
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-center h-[300px] text-slate-400">
                        <div className="text-center">
                          <svg className="w-12 h-12 mx-auto mb-2 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <p className="text-sm">Paste HTML to see preview</p>
                        </div>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    Preview shows template at 1080×1080px scaled to fit
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-12 gap-6">
          {/* Left Sidebar - Template List */}
          <div className="col-span-12 lg:col-span-4">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden sticky top-24">
              {/* Section Filter */}
              <div className="p-4 border-b border-slate-200 bg-slate-50">
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Filter by Section
                </label>
                <select
                  value={selectedSection}
                  onChange={(e) => setSelectedSection(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm"
                >
                  <option value="all">All Sections ({templates.length})</option>
                  {sections.map(section => (
                    <option key={section} value={section}>
                      {section.replace(/_/g, ' ').toUpperCase()} ({templates.filter(t => t.section === section).length})
                    </option>
                  ))}
                </select>
              </div>

              {/* Template List */}
              <div className="max-h-[calc(100vh-280px)] overflow-y-auto">
                {isLoadingTemplates ? (
                  <div className="p-8 text-center text-slate-400">
                    <div className="animate-spin w-8 h-8 border-4 border-purple-200 border-t-purple-600 rounded-full mx-auto mb-3"></div>
                    Loading templates...
                  </div>
                ) : Object.keys(groupedTemplates).length === 0 ? (
                  <div className="p-8 text-center text-slate-400">
                    <svg className="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    No templates found
                  </div>
                ) : (
                  <div>
                    {Object.keys(groupedTemplates).map(section => (
                      <div key={section} className="border-b border-slate-100 last:border-b-0">
                        <div className="px-4 py-2 bg-slate-50 sticky top-0">
                          <h3 className="text-sm font-semibold text-slate-700 uppercase">
                            {section.replace(/_/g, ' ')}
                          </h3>
                        </div>
                        <div className="divide-y divide-slate-100">
                          {groupedTemplates[section].map(template => (
                            <div
                              key={template.id}
                              onClick={() => selectTemplate(template)}
                              className={`p-4 cursor-pointer transition hover:bg-slate-50 ${
                                selectedTemplate?.id === template.id ? 'bg-purple-50 border-l-4 border-purple-600' : ''
                              }`}
                            >
                              <div className="flex items-start justify-between gap-2 mb-2">
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <h4 className="font-medium text-slate-900 truncate">
                                      {template.name}
                                    </h4>
                                    {template.is_active && (
                                      <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-medium rounded">
                                        Active
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-xs text-slate-500">
                                    Version {template.version}
                                  </p>
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {template.placeholders.slice(0, 3).map(p => (
                                  <span key={p.name} className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
                                    {p.name}
                                  </span>
                                ))}
                                {template.placeholders.length > 3 && (
                                  <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
                                    +{template.placeholders.length - 3}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Content - Placeholders & Preview */}
          <div className="col-span-12 lg:col-span-8">
            {selectedTemplate ? (
              <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
                {/* Placeholders Input */}
                <div className="xl:col-span-4 bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                  <h2 className="text-lg font-semibold text-slate-900 mb-4">
                    Placeholders
                  </h2>

                  {selectedTemplate.placeholders.length > 0 ? (
                    <div className="space-y-4">
                      {selectedTemplate.placeholders.map(placeholder => (
                        <div key={placeholder.name}>
                          <label className="block text-sm font-medium text-slate-700 mb-2">
                            {placeholder.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                            {placeholder.is_required && <span className="text-red-500 ml-1">*</span>}
                          </label>
                          <input
                            type="text"
                            value={placeholderValues[placeholder.name] || ''}
                            onChange={(e) => handlePlaceholderChange(placeholder.name, e.target.value)}
                            placeholder={placeholder.sample_value || `Enter ${placeholder.name}...`}
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm"
                          />
                          {placeholder.sample_value && (
                            <p className="text-xs text-slate-500 mt-1">
                              Sample: {placeholder.sample_value}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-slate-400 py-8">
                      <p className="text-sm">No placeholders detected</p>
                    </div>
                  )}

                  {/* Template Info */}
                  <div className="mt-6 pt-6 border-t border-slate-200">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium text-slate-700">Template Info</h3>
                      <button
                        onClick={() => startEditTemplate(selectedTemplate)}
                        className="text-xs px-2 py-1 bg-purple-100 text-purple-700 hover:bg-purple-200 rounded flex items-center gap-1 transition"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        Edit
                      </button>
                    </div>
                    <div className="space-y-1 text-sm text-slate-600">
                      <p><span className="font-medium">Section:</span> {selectedTemplate.section}</p>
                      <p><span className="font-medium">Version:</span> {selectedTemplate.version}</p>
                      <p><span className="font-medium">Placeholders:</span> {selectedTemplate.placeholders.length}</p>
                      <p><span className="font-medium">Status:</span> {selectedTemplate.is_active ? 'Active' : 'Inactive'}</p>
                    </div>
                  </div>
                </div>

                {/* Preview */}
                <div className="xl:col-span-8 bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                  <h2 className="text-lg font-semibold text-slate-900 mb-4">
                    Live Preview
                  </h2>

                  <div className="border border-slate-200 rounded-lg overflow-hidden bg-slate-100">
                    <div className="flex items-center justify-center p-4">
                      {/* Scaled preview container */}
                      <div 
                        className="relative bg-white shadow-lg rounded-lg overflow-hidden"
                        style={{
                          width: '400px',
                          height: '400px',
                        }}
                      >
                        <div
                          style={{
                            transform: 'scale(0.37)',
                            transformOrigin: 'top left',
                            width: '1080px',
                            height: '1080px',
                            position: 'absolute',
                            top: 0,
                            left: 0,
                          }}
                        >
                          <iframe
                            srcDoc={`<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{margin:0;padding:0;}</style></head><body>${getPreviewHtml()}</body></html>`}
                            className="w-full h-full border-0"
                            style={{ width: '1080px', height: '1080px', pointerEvents: 'none' }}
                            title="Template Preview"
                            sandbox="allow-same-origin"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 text-xs text-slate-500">
                    <p>Preview shows template at 1080×1080px scaled to fit</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
                <svg className="w-20 h-20 mx-auto mb-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 className="text-lg font-medium text-slate-900 mb-2">No Template Selected</h3>
                <p className="text-slate-600">
                  Select a template from the left sidebar to preview
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
