/**
 * Block parser utilities for email template editing
 * Parses HTML with block markers into editable components
 */

import type {
  EmailBlock,
  ParsedEmail,
  BlockType,
  EditableImage,
  EditableText,
  EditableLink,
  EditableColor,
  BlockUpdate,
} from '../types/blocks';

/**
 * Parse email HTML into blocks based on comment markers
 * Markers format: <!-- BLOCK:type -->...<!-- /BLOCK:type -->
 */
export function parseEmailBlocks(html: string): ParsedEmail {
  const blocks: EmailBlock[] = [];

  // Pattern to match block markers
  const blockPattern = /<!-- BLOCK:(\w+)(?:\s+([^>]*))? -->([\s\S]*?)<!-- \/BLOCK:\1 -->/g;

  let match;
  let lastEndIndex = 0;
  let preBlockHtml = '';

  while ((match = blockPattern.exec(html)) !== null) {
    const [fullMatch, type, _attributes, content] = match;

    // Capture pre-block HTML (before first block)
    if (blocks.length === 0) {
      preBlockHtml = html.substring(0, match.index);
    }

    const blockId = `block-${type}-${blocks.length}`;

    blocks.push({
      id: blockId,
      type: type as BlockType,
      label: formatBlockLabel(type),
      html: content.trim(),
      startIndex: match.index,
      endIndex: match.index + fullMatch.length,
      editable: extractEditableElements(content),
    });

    lastEndIndex = match.index + fullMatch.length;
  }

  // Capture post-block HTML (after last block)
  const postBlockHtml = html.substring(lastEndIndex);

  return {
    blocks,
    rawHtml: html,
    preBlockHtml,
    postBlockHtml,
  };
}

/**
 * Format block type into human-readable label
 */
function formatBlockLabel(type: string): string {
  const labels: Record<string, string> = {
    header: 'Header',
    hero: 'Hero Section',
    content: 'Content',
    cta: 'Call to Action',
    features: 'Features',
    testimonial: 'Testimonial',
    footer: 'Footer',
    custom: 'Custom Block',
  };
  return labels[type] || type.charAt(0).toUpperCase() + type.slice(1);
}

/**
 * Extract editable elements from block HTML
 */
function extractEditableElements(html: string): EmailBlock['editable'] {
  return {
    images: extractImages(html),
    text: extractTextElements(html),
    links: extractLinks(html),
    colors: extractColors(html),
  };
}

/**
 * Extract all images from HTML
 */
function extractImages(html: string): EditableImage[] {
  const images: EditableImage[] = [];
  const imgPattern = /<img[^>]*>/gi;

  let match;
  let index = 0;
  while ((match = imgPattern.exec(html)) !== null) {
    const imgTag = match[0];

    const srcMatch = imgTag.match(/src=["']([^"']+)["']/i);
    const altMatch = imgTag.match(/alt=["']([^"']*)["']/i);
    const widthMatch = imgTag.match(/width=["']?(\d+)["']?/i);
    const heightMatch = imgTag.match(/height=["']?(\d+)["']?/i);

    if (srcMatch) {
      images.push({
        src: srcMatch[1],
        alt: altMatch?.[1] || '',
        width: widthMatch ? parseInt(widthMatch[1]) : undefined,
        height: heightMatch ? parseInt(heightMatch[1]) : undefined,
        index: index++,
      });
    }
  }

  return images;
}

/**
 * Extract text elements (headings, paragraphs, etc.)
 */
function extractTextElements(html: string): EditableText[] {
  const textElements: EditableText[] = [];

  // Match common text tags
  const textPattern = /<(h[1-6]|p|span|td|th|li|a)([^>]*)>([^<]*)<\/\1>/gi;

  let match;
  let index = 0;
  while ((match = textPattern.exec(html)) !== null) {
    const [, tag, , content] = match;
    const trimmedContent = content.trim();

    // Skip empty content and Handlebars-only content
    if (trimmedContent && !trimmedContent.match(/^\{\{[^}]+\}\}$/)) {
      textElements.push({
        content: trimmedContent,
        tag: tag.toLowerCase(),
        index: index++,
      });
    }
  }

  return textElements;
}

/**
 * Extract links from HTML
 */
function extractLinks(html: string): EditableLink[] {
  const links: EditableLink[] = [];
  const linkPattern = /<a[^>]*href=["']([^"']+)["'][^>]*>([^<]*)<\/a>/gi;

  let match;
  let index = 0;
  while ((match = linkPattern.exec(html)) !== null) {
    const [, href, text] = match;
    links.push({
      href,
      text: text.trim(),
      index: index++,
    });
  }

  return links;
}

/**
 * Extract inline colors from HTML
 */
function extractColors(html: string): EditableColor[] {
  const colors: EditableColor[] = [];
  const colorPattern = /(background-color|color|border-color)\s*:\s*(#[a-fA-F0-9]{3,6}|rgb[a]?\([^)]+\))/gi;

  let match;
  const seenColors = new Set<string>();

  while ((match = colorPattern.exec(html)) !== null) {
    const [, property, value] = match;
    const key = `${property}:${value}`;

    if (!seenColors.has(key)) {
      seenColors.add(key);
      colors.push({
        property: property.toLowerCase(),
        value: value,
        selector: property,  // Simplified selector
      });
    }
  }

  return colors;
}

/**
 * Apply updates to a block's HTML
 */
export function applyBlockUpdates(block: EmailBlock, updates: BlockUpdate): string {
  let html = block.html;

  // Process deletions first (in reverse order to maintain indices)
  // Delete images
  if (updates.deleteImages && updates.deleteImages.length > 0) {
    const sortedIndices = [...updates.deleteImages].sort((a, b) => b - a);
    for (const idx of sortedIndices) {
      const image = block.editable.images[idx];
      if (image) {
        // Remove the entire <img> tag
        const imgPattern = new RegExp(
          `<img[^>]*src=["']${escapeRegex(image.src)}["'][^>]*>`,
          'i'
        );
        html = html.replace(imgPattern, '');
      }
    }
  }

  // Delete text elements
  if (updates.deleteText && updates.deleteText.length > 0) {
    const sortedIndices = [...updates.deleteText].sort((a, b) => b - a);
    for (const idx of sortedIndices) {
      const textEl = block.editable.text[idx];
      if (textEl) {
        // Remove the entire element with its tag
        const textPattern = new RegExp(
          `<${textEl.tag}[^>]*>${escapeRegex(textEl.content)}</${textEl.tag}>`,
          'i'
        );
        html = html.replace(textPattern, '');
      }
    }
  }

  // Delete links
  if (updates.deleteLinks && updates.deleteLinks.length > 0) {
    const sortedIndices = [...updates.deleteLinks].sort((a, b) => b - a);
    for (const idx of sortedIndices) {
      const link = block.editable.links[idx];
      if (link) {
        // Remove the entire <a> tag
        const linkPattern = new RegExp(
          `<a[^>]*href=["']${escapeRegex(link.href)}["'][^>]*>${escapeRegex(link.text)}</a>`,
          'i'
        );
        html = html.replace(linkPattern, '');
      }
    }
  }

  // Update images
  if (updates.images) {
    for (const imgUpdate of updates.images) {
      const image = block.editable.images[imgUpdate.index];
      if (image) {
        // Replace src
        html = html.replace(
          new RegExp(`src=["']${escapeRegex(image.src)}["']`, 'i'),
          `src="${imgUpdate.src}"`
        );
        // Replace alt if provided
        if (imgUpdate.alt !== undefined) {
          html = html.replace(
            new RegExp(`alt=["']${escapeRegex(image.alt)}["']`, 'i'),
            `alt="${imgUpdate.alt}"`
          );
        }
      }
    }
  }

  // Update text (more complex - need to be careful with replacements)
  if (updates.text) {
    for (const textUpdate of updates.text) {
      const textEl = block.editable.text[textUpdate.index];
      if (textEl) {
        // Replace text content within its tag
        const pattern = new RegExp(
          `(<${textEl.tag}[^>]*>)${escapeRegex(textEl.content)}(</${textEl.tag}>)`,
          'i'
        );
        html = html.replace(pattern, `$1${textUpdate.content}$2`);
      }
    }
  }

  // Update links
  if (updates.links) {
    for (const linkUpdate of updates.links) {
      const link = block.editable.links[linkUpdate.index];
      if (link) {
        if (linkUpdate.href) {
          html = html.replace(
            new RegExp(`href=["']${escapeRegex(link.href)}["']`, 'i'),
            `href="${linkUpdate.href}"`
          );
        }
        if (linkUpdate.text) {
          html = html.replace(
            new RegExp(`>${escapeRegex(link.text)}</a>`, 'i'),
            `>${linkUpdate.text}</a>`
          );
        }
      }
    }
  }

  // Update colors (global replace within block)
  if (updates.colors) {
    for (const colorUpdate of updates.colors) {
      const pattern = new RegExp(
        `${escapeRegex(colorUpdate.property)}\\s*:\\s*[^;]+`,
        'gi'
      );
      html = html.replace(pattern, `${colorUpdate.property}: ${colorUpdate.value}`);
    }
  }

  return html;
}

/**
 * Reconstruct full HTML from parsed email with updated blocks
 */
export function reconstructHtml(parsed: ParsedEmail, updatedBlocks?: EmailBlock[]): string {
  const blocks = updatedBlocks || parsed.blocks;

  let html = parsed.preBlockHtml;

  for (const block of blocks) {
    html += `<!-- BLOCK:${block.type} -->\n${block.html}\n<!-- /BLOCK:${block.type} -->\n`;
  }

  html += parsed.postBlockHtml;

  return html;
}

/**
 * Update a single block in parsed email and return new HTML
 */
export function updateBlock(
  parsed: ParsedEmail,
  blockId: string,
  updates: BlockUpdate
): string {
  const updatedBlocks = parsed.blocks.map((block) => {
    if (block.id === blockId) {
      return {
        ...block,
        html: applyBlockUpdates(block, updates),
        editable: extractEditableElements(applyBlockUpdates(block, updates)),
      };
    }
    return block;
  });

  return reconstructHtml({ ...parsed, blocks: updatedBlocks });
}

/**
 * Replace a block's HTML entirely (used for AI edits)
 */
export function replaceBlockHtml(
  parsed: ParsedEmail,
  blockId: string,
  newHtml: string
): string {
  const updatedBlocks = parsed.blocks.map((block) => {
    if (block.id === blockId) {
      return {
        ...block,
        html: newHtml,
        editable: extractEditableElements(newHtml),
      };
    }
    return block;
  });

  return reconstructHtml({ ...parsed, blocks: updatedBlocks });
}

/**
 * Escape special regex characters
 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Check if HTML has block markers
 */
export function hasBlockMarkers(html: string): boolean {
  return /<!-- BLOCK:\w+ -->/.test(html);
}

/**
 * Get block by ID
 */
export function getBlockById(parsed: ParsedEmail, blockId: string): EmailBlock | undefined {
  return parsed.blocks.find((b) => b.id === blockId);
}

/**
 * Delete a block from parsed email and return new HTML
 */
export function deleteBlock(parsed: ParsedEmail, blockId: string): string {
  const filteredBlocks = parsed.blocks.filter((block) => block.id !== blockId);
  return reconstructHtml({ ...parsed, blocks: filteredBlocks });
}
