-- Migration: Create Template Management Schema
-- Date: 2026-01-22
-- Purpose: Add template management system for external backend integration

-- Templates with versioning
CREATE TABLE IF NOT EXISTS templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section VARCHAR(50) NOT NULL,           -- 'testimonial', 'top_new_launch', etc.
    name VARCHAR(200) NOT NULL,              -- 'Modern Testimonial Design'
    html_content TEXT NOT NULL,              -- HTML with {{placeholders}}
    css_content TEXT,                        -- Optional CSS
    version INTEGER NOT NULL,                -- Auto-incremented: 1, 2, 3...
    is_active BOOLEAN DEFAULT false,         -- Only one active per section
    preview_data JSONB,                      -- Sample data for preview
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_section_version UNIQUE(section, version)
);

-- Extracted placeholders
CREATE TABLE IF NOT EXISTS template_placeholders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    placeholder_name VARCHAR(100) NOT NULL,
    sample_value TEXT,
    data_type VARCHAR(50) DEFAULT 'text',
    is_required BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Generation history
CREATE TABLE IF NOT EXISTS poster_generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id),
    user_id INTEGER NOT NULL,
    entity_id VARCHAR(100),                  -- testimonial_id, etc.
    input_data JSONB,
    output_url TEXT,
    template_version INTEGER,
    generation_time_ms INTEGER,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_templates_section_active ON templates(section, is_active);
CREATE INDEX IF NOT EXISTS idx_templates_section_version ON templates(section, version DESC);
CREATE INDEX IF NOT EXISTS idx_template_placeholders_template_id ON template_placeholders(template_id);
CREATE INDEX IF NOT EXISTS idx_poster_generations_template_id ON poster_generations(template_id);
CREATE INDEX IF NOT EXISTS idx_poster_generations_user_id ON poster_generations(user_id);
CREATE INDEX IF NOT EXISTS idx_poster_generations_created_at ON poster_generations(created_at DESC);

-- Comments
COMMENT ON TABLE templates IS 'HTML templates with versioning for poster generation';
COMMENT ON TABLE template_placeholders IS 'Extracted placeholders from HTML templates';
COMMENT ON TABLE poster_generations IS 'History of all poster generations';
COMMENT ON COLUMN templates.section IS 'Template category (testimonial, top_new_launch, etc.)';
COMMENT ON COLUMN templates.version IS 'Auto-incremented version number per section';
COMMENT ON COLUMN templates.is_active IS 'Only one template per section can be active';
