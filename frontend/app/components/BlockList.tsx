'use client';

import { useMemo } from 'react';
import type { EmailBlock } from '../types/blocks';

interface BlockListProps {
  blocks: EmailBlock[];
  selectedBlockId: string | null;
  onSelectBlock: (blockId: string) => void;
  onEditBlock: (blockId: string) => void;
}

// Categorize editable elements across all blocks
interface CategoryItem {
  blockId: string;
  blockLabel: string;
  type: 'content' | 'button' | 'image';
  index: number;
  label: string;
  preview: string;
}

export default function BlockList({
  blocks,
  selectedBlockId,
  onSelectBlock,
  onEditBlock,
}: BlockListProps) {
  // Aggregate all editable elements into 3 categories
  const categories = useMemo(() => {
    const content: CategoryItem[] = [];
    const buttons: CategoryItem[] = [];
    const images: CategoryItem[] = [];

    blocks.forEach((block) => {
      // Text content
      block.editable.text.forEach((text, idx) => {
        content.push({
          blockId: block.id,
          blockLabel: block.label,
          type: 'content',
          index: idx,
          label: text.tag.toUpperCase(),
          preview: text.content.slice(0, 50) + (text.content.length > 50 ? '...' : ''),
        });
      });

      // Links/Buttons (CTAs)
      block.editable.links.forEach((link, idx) => {
        buttons.push({
          blockId: block.id,
          blockLabel: block.label,
          type: 'button',
          index: idx,
          label: link.text || 'Button',
          preview: link.href.slice(0, 40) + (link.href.length > 40 ? '...' : ''),
        });
      });

      // Images
      block.editable.images.forEach((img, idx) => {
        images.push({
          blockId: block.id,
          blockLabel: block.label,
          type: 'image',
          index: idx,
          label: img.alt || 'Image',
          preview: img.width && img.height ? `${img.width}x${img.height}` : 'Image',
        });
      });
    });

    return { content, buttons, images };
  }, [blocks]);

  if (blocks.length === 0) {
    return (
      <div className="p-4 text-center text-slate-500">
        <p className="text-sm">No blocks detected</p>
        <p className="text-xs mt-1">Generate an email to see editable elements</p>
      </div>
    );
  }

  const renderCategory = (
    title: string,
    icon: React.ReactNode,
    items: CategoryItem[],
    emptyText: string
  ) => (
    <div className="mb-4">
      <div className="flex items-center gap-2 px-3 py-2 text-slate-700">
        {icon}
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-slate-400 ml-auto">{items.length}</span>
      </div>

      {items.length === 0 ? (
        <p className="px-3 py-2 text-xs text-slate-400 italic">{emptyText}</p>
      ) : (
        <div className="space-y-1 px-2">
          {items.map((item, i) => {
            const isSelected = item.blockId === selectedBlockId;
            return (
              <div
                key={`${item.blockId}-${item.type}-${item.index}`}
                className={`group px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-indigo-100 text-indigo-900'
                    : 'hover:bg-slate-100 text-slate-700'
                }`}
                onClick={() => {
                  onSelectBlock(item.blockId);
                  onEditBlock(item.blockId);
                }}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium truncate">{item.label}</p>
                  <span className="text-xs text-slate-400">{item.blockLabel}</span>
                </div>
                <p className="text-xs text-slate-500 truncate mt-0.5">{item.preview}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  return (
    <div className="py-2">
      <div className="px-3 py-2 mb-2">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Editable Elements
        </h3>
      </div>

      {renderCategory(
        'Content',
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>,
        categories.content,
        'No text content'
      )}

      {renderCategory(
        'Buttons',
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
        </svg>,
        categories.buttons,
        'No buttons'
      )}

      {renderCategory(
        'Images',
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>,
        categories.images,
        'No images'
      )}

      {/* Summary */}
      <div className="mt-2 pt-3 border-t border-slate-200 px-3">
        <p className="text-xs text-slate-500">
          {categories.content.length + categories.buttons.length + categories.images.length} total editable elements
        </p>
      </div>
    </div>
  );
}
