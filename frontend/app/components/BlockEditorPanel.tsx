'use client';

import { useState, useEffect } from 'react';
import type { EmailBlock, BlockUpdate, ChatContext } from '../types/blocks';

interface BlockEditorPanelProps {
  block: EmailBlock;
  context: ChatContext;
  apiKey: string;
  onSave: (blockId: string, updates: BlockUpdate) => void;
  onAiEdit: (blockId: string, instruction: string) => Promise<void>;
  onClose: () => void;
}

type EditorTab = 'images' | 'text' | 'links' | 'ai';

export default function BlockEditorPanel({
  block,
  context,
  apiKey,
  onSave,
  onAiEdit,
  onClose,
}: BlockEditorPanelProps) {
  const [activeTab, setActiveTab] = useState<EditorTab>('text');
  const [aiInstruction, setAiInstruction] = useState('');
  const [isAiProcessing, setIsAiProcessing] = useState(false);

  // Local state for edits
  const [editedImages, setEditedImages] = useState(
    block.editable.images.map((img) => ({ ...img, deleted: false }))
  );
  const [editedText, setEditedText] = useState(
    block.editable.text.map((t) => ({ ...t, deleted: false }))
  );
  const [editedLinks, setEditedLinks] = useState(
    block.editable.links.map((l) => ({ ...l, deleted: false }))
  );

  // Reset state when block changes (fixes sidebar not updating bug)
  useEffect(() => {
    setEditedImages(block.editable.images.map((img) => ({ ...img, deleted: false })));
    setEditedText(block.editable.text.map((t) => ({ ...t, deleted: false })));
    setEditedLinks(block.editable.links.map((l) => ({ ...l, deleted: false })));
    setAiInstruction('');
    // Auto-select most relevant tab based on block content
    if (block.editable.text.length > 0) {
      setActiveTab('text');
    } else if (block.editable.images.length > 0) {
      setActiveTab('images');
    } else if (block.editable.links.length > 0) {
      setActiveTab('links');
    }
  }, [block.id, block.editable.images, block.editable.text, block.editable.links]);

  const handleSave = () => {
    const updates: BlockUpdate = {};

    // Collect deletions
    const deleteImages = editedImages
      .map((img, i) => (img.deleted ? i : null))
      .filter((i): i is number => i !== null);
    const deleteText = editedText
      .map((t, i) => (t.deleted ? i : null))
      .filter((i): i is number => i !== null);
    const deleteLinks = editedLinks
      .map((l, i) => (l.deleted ? i : null))
      .filter((i): i is number => i !== null);

    if (deleteImages.length > 0) updates.deleteImages = deleteImages;
    if (deleteText.length > 0) updates.deleteText = deleteText;
    if (deleteLinks.length > 0) updates.deleteLinks = deleteLinks;

    // Check for image changes (only for non-deleted items)
    const imageChanges = editedImages
      .map((img, i) => {
        if (img.deleted) return null;
        const original = block.editable.images[i];
        if (img.src !== original.src || img.alt !== original.alt) {
          return { index: i, src: img.src, alt: img.alt };
        }
        return null;
      })
      .filter(Boolean) as BlockUpdate['images'];

    if (imageChanges && imageChanges.length > 0) {
      updates.images = imageChanges;
    }

    // Check for text changes (only for non-deleted items)
    const textChanges = editedText
      .map((t, i) => {
        if (t.deleted) return null;
        const original = block.editable.text[i];
        if (t.content !== original.content) {
          return { index: i, content: t.content };
        }
        return null;
      })
      .filter(Boolean) as BlockUpdate['text'];

    if (textChanges && textChanges.length > 0) {
      updates.text = textChanges;
    }

    // Check for link changes (only for non-deleted items)
    const linkChanges = editedLinks
      .map((l, i) => {
        if (l.deleted) return null;
        const original = block.editable.links[i];
        if (l.href !== original.href || l.text !== original.text) {
          return { index: i, href: l.href, text: l.text };
        }
        return null;
      })
      .filter(Boolean) as BlockUpdate['links'];

    if (linkChanges && linkChanges.length > 0) {
      updates.links = linkChanges;
    }

    onSave(block.id, updates);
    onClose();
  };

  const handleAiEdit = async () => {
    if (!aiInstruction.trim()) return;

    setIsAiProcessing(true);
    try {
      await onAiEdit(block.id, aiInstruction);
      setAiInstruction('');
      onClose();
    } catch (error) {
      console.error('AI edit failed:', error);
    } finally {
      setIsAiProcessing(false);
    }
  };

  const tabs: { id: EditorTab; label: string; count: number }[] = [
    { id: 'text', label: 'Text', count: editedText.filter((t) => !t.deleted).length },
    { id: 'images', label: 'Images', count: editedImages.filter((i) => !i.deleted).length },
    { id: 'links', label: 'Links', count: editedLinks.filter((l) => !l.deleted).length },
    { id: 'ai', label: 'AI Edit', count: 0 },
  ];

  return (
    <div className="h-full flex flex-col bg-white border-l border-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        <div>
          <h3 className="font-semibold text-slate-900">Edit: {block.label}</h3>
          <p className="text-xs text-slate-500">{block.type} block</p>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className="ml-1 text-xs text-slate-400">({tab.count})</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4">
        {/* Text Tab */}
        {activeTab === 'text' && (
          <div className="space-y-4">
            {editedText.filter((t) => !t.deleted).length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-4">
                No editable text in this block
              </p>
            ) : (
              editedText.map((text, index) =>
                text.deleted ? null : (
                  <div key={index} className="space-y-1 group relative">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-500 uppercase">
                        {text.tag}
                      </label>
                      <button
                        onClick={() => {
                          if (confirm('Delete this text element?')) {
                            const updated = [...editedText];
                            updated[index] = { ...updated[index], deleted: true };
                            setEditedText(updated);
                          }
                        }}
                        className="p-1 text-red-500 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete text"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                    <textarea
                      value={text.content}
                      onChange={(e) => {
                        const updated = [...editedText];
                        updated[index] = { ...updated[index], content: e.target.value };
                        setEditedText(updated);
                      }}
                      rows={2}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                )
              )
            )}
          </div>
        )}

        {/* Images Tab */}
        {activeTab === 'images' && (
          <div className="space-y-4">
            {editedImages.filter((i) => !i.deleted).length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-4">
                No images in this block
              </p>
            ) : (
              editedImages.map((img, index) =>
                img.deleted ? null : (
                  <div key={index} className="p-3 bg-slate-50 rounded-lg space-y-3 group relative">
                    <div className="flex items-center gap-3">
                      <img
                        src={img.src}
                        alt={img.alt}
                        className="w-16 h-16 object-cover rounded border border-slate-200"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'https://via.placeholder.com/64';
                        }}
                      />
                      <div className="flex-1 text-xs text-slate-500">
                        {img.width && img.height && `${img.width}x${img.height}`}
                      </div>
                      <button
                        onClick={() => {
                          if (confirm('Delete this image?')) {
                            const updated = [...editedImages];
                            updated[index] = { ...updated[index], deleted: true };
                            setEditedImages(updated);
                          }
                        }}
                        className="p-1.5 text-red-500 hover:bg-red-100 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete image"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <label className="text-xs font-medium text-slate-500">Image URL</label>
                        <input
                          type="text"
                          value={img.src}
                          onChange={(e) => {
                            const updated = [...editedImages];
                            updated[index] = { ...updated[index], src: e.target.value };
                            setEditedImages(updated);
                          }}
                          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-slate-500">Alt Text</label>
                        <input
                          type="text"
                          value={img.alt}
                          onChange={(e) => {
                            const updated = [...editedImages];
                            updated[index] = { ...updated[index], alt: e.target.value };
                            setEditedImages(updated);
                          }}
                          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </div>
                    </div>
                  </div>
                )
              )
            )}
          </div>
        )}

        {/* Links Tab */}
        {activeTab === 'links' && (
          <div className="space-y-4">
            {editedLinks.filter((l) => !l.deleted).length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-4">
                No editable links in this block
              </p>
            ) : (
              editedLinks.map((link, index) =>
                link.deleted ? null : (
                  <div key={index} className="p-3 bg-slate-50 rounded-lg space-y-2 group relative">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-slate-500">Link {index + 1}</span>
                      <button
                        onClick={() => {
                          if (confirm('Delete this link?')) {
                            const updated = [...editedLinks];
                            updated[index] = { ...updated[index], deleted: true };
                            setEditedLinks(updated);
                          }
                        }}
                        className="p-1 text-red-500 hover:bg-red-100 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete link"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-slate-500">Link Text</label>
                      <input
                        type="text"
                        value={link.text}
                        onChange={(e) => {
                          const updated = [...editedLinks];
                          updated[index] = { ...updated[index], text: e.target.value };
                          setEditedLinks(updated);
                        }}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-slate-500">URL</label>
                      <input
                        type="text"
                        value={link.href}
                        onChange={(e) => {
                          const updated = [...editedLinks];
                          updated[index] = { ...updated[index], href: e.target.value };
                          setEditedLinks(updated);
                        }}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      />
                    </div>
                  </div>
                )
              )
            )}
          </div>
        )}

        {/* AI Edit Tab */}
        {activeTab === 'ai' && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              Describe the changes you want to make to this block. AI will update it for you.
            </p>
            <textarea
              value={aiInstruction}
              onChange={(e) => setAiInstruction(e.target.value)}
              placeholder="e.g., Make the headline bigger and change the background to light blue"
              rows={4}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <button
              onClick={handleAiEdit}
              disabled={!aiInstruction.trim() || isAiProcessing}
              className="w-full py-2 px-4 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {isAiProcessing ? (
                <>
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Processing...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Apply AI Edit
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Footer with Save/Cancel */}
      {activeTab !== 'ai' && (
        <div className="flex gap-2 p-4 border-t border-slate-200">
          <button
            onClick={onClose}
            className="flex-1 py-2 px-4 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex-1 py-2 px-4 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Save Changes
          </button>
        </div>
      )}
    </div>
  );
}
