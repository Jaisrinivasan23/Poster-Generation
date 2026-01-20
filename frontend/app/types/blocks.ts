/**
 * Block types for email template editing
 */

export type BlockType =
  | 'header'
  | 'hero'
  | 'content'
  | 'cta'
  | 'features'
  | 'testimonial'
  | 'footer'
  | 'custom';

export interface EditableImage {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  index: number;  // Position in the block HTML
}

export interface EditableText {
  content: string;
  tag: string;  // h1, h2, p, span, td, etc.
  index: number;
}

export interface EditableLink {
  href: string;
  text: string;
  index: number;
}

export interface EditableColor {
  property: string;  // background-color, color, border-color
  value: string;     // Hex color
  selector: string;  // CSS selector or description
}

export interface EmailBlock {
  id: string;
  type: BlockType;
  label: string;
  html: string;
  startIndex: number;
  endIndex: number;
  editable: {
    images: EditableImage[];
    text: EditableText[];
    links: EditableLink[];
    colors: EditableColor[];
  };
}

export interface ParsedEmail {
  blocks: EmailBlock[];
  rawHtml: string;
  preBlockHtml: string;   // HTML before first block (doctype, head, etc.)
  postBlockHtml: string;  // HTML after last block (closing tags)
}

export interface BlockUpdate {
  images?: Array<{ index: number; src: string; alt?: string }>;
  text?: Array<{ index: number; content: string }>;
  links?: Array<{ index: number; href?: string; text?: string }>;
  colors?: Array<{ selector: string; property: string; value: string }>;
  // Deletions - indices of elements to remove from the block HTML
  deleteImages?: number[];
  deleteText?: number[];
  deleteLinks?: number[];
}

// Chat message types
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  htmlSnapshot?: string;  // HTML state after this message (for assistant messages)
}

export interface ChatContext {
  brandName: string;
  emailType: string;
  tone: string;
  primaryColor: string;
  secondaryColor: string;
  accentColor?: string;
  industry?: string;
}
