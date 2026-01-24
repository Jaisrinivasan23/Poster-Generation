-- Template Jobs and Logs Schema
-- For parallel processing of template-based poster generation

-- Template Generation Jobs Table
CREATE TABLE IF NOT EXISTS template_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(100) UNIQUE NOT NULL,
    template_id UUID REFERENCES templates(id),
    template_section VARCHAR(50) NOT NULL,
    template_version INTEGER NOT NULL,
    status job_status DEFAULT 'pending',
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    input_data JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Template Generation Logs Table
CREATE TABLE IF NOT EXISTS template_generation_logs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL,
    level log_level DEFAULT 'INFO',
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Individual Template Poster Results Table
CREATE TABLE IF NOT EXISTS template_poster_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(100) NOT NULL,
    template_id UUID REFERENCES templates(id),
    entity_id VARCHAR(255),
    custom_data JSONB NOT NULL,
    output_url VARCHAR(500),
    s3_key VARCHAR(500),
    status job_status DEFAULT 'pending',
    template_version INTEGER,
    generation_time_ms INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_template_jobs_status ON template_generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_template_jobs_job_id ON template_generation_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_template_jobs_created_at ON template_generation_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_template_jobs_template_id ON template_generation_jobs(template_id);
CREATE INDEX IF NOT EXISTS idx_template_jobs_section ON template_generation_jobs(template_section);

CREATE INDEX IF NOT EXISTS idx_template_logs_job_id ON template_generation_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_template_logs_created_at ON template_generation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_template_logs_level ON template_generation_logs(level);

CREATE INDEX IF NOT EXISTS idx_template_results_job_id ON template_poster_results(job_id);
CREATE INDEX IF NOT EXISTS idx_template_results_entity_id ON template_poster_results(entity_id);
CREATE INDEX IF NOT EXISTS idx_template_results_status ON template_poster_results(status);
CREATE INDEX IF NOT EXISTS idx_template_results_template_id ON template_poster_results(template_id);

-- Create triggers to update updated_at timestamp
CREATE TRIGGER update_template_jobs_updated_at
    BEFORE UPDATE ON template_generation_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_template_results_updated_at
    BEFORE UPDATE ON template_poster_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert initial log
INSERT INTO template_generation_logs (job_id, level, message, details)
VALUES ('system', 'INFO', 'Template generation schema initialized', ('{"version": "1.0.0", "timestamp": "' || CURRENT_TIMESTAMP || '"}')::jsonb);
