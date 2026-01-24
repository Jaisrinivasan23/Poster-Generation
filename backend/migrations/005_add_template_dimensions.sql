-- Migration: Add template dimensions
-- Date: 2026-01-23
-- Purpose: Store extracted width/height from template HTML for automatic poster sizing

ALTER TABLE templates 
ADD COLUMN IF NOT EXISTS width INTEGER DEFAULT 1080,
ADD COLUMN IF NOT EXISTS height INTEGER DEFAULT 1080;

-- Add comment
COMMENT ON COLUMN templates.width IS 'Template width in pixels (extracted from HTML or default 1080)';
COMMENT ON COLUMN templates.height IS 'Template height in pixels (extracted from HTML or default 1080)';
