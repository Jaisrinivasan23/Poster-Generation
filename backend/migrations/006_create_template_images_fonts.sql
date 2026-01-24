-- Migration: Create Template Images and Fonts Tables
-- Date: 2026-01-23
-- Purpose: Add admin-managed template images and custom fonts

-- Template Images (for reference in poster generation)
CREATE TABLE IF NOT EXISTS template_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    url TEXT NOT NULL,
    category VARCHAR(50) DEFAULT 'minimal',
    uploaded_by VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Custom Fonts
CREATE TABLE IF NOT EXISTS custom_fonts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    font_name VARCHAR(200) NOT NULL,
    font_family VARCHAR(200) NOT NULL,
    file_url TEXT NOT NULL,
    file_format VARCHAR(20) NOT NULL,
    uploaded_by VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_font_family UNIQUE(font_family)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_template_images_active ON template_images(is_active, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_template_images_category ON template_images(category, is_active);
CREATE INDEX IF NOT EXISTS idx_custom_fonts_active ON custom_fonts(is_active, font_family);
