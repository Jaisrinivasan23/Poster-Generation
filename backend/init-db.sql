-- Initialize PostgreSQL Database for Poster Generation
-- This file is executed on first container startup

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
CREATE TYPE job_status AS ENUM ('pending', 'queued', 'processing', 'completed', 'failed', 'cancelled');
CREATE TYPE log_level AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');

-- Batch Jobs Table
CREATE TABLE IF NOT EXISTS batch_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(100) UNIQUE NOT NULL,
    campaign_name VARCHAR(255),
    status job_status DEFAULT 'pending',
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    template_html TEXT,
    template_url VARCHAR(500),
    poster_size VARCHAR(50),
    model VARCHAR(50),
    user_identifiers TEXT,
    metadata JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Job Logs Table
CREATE TABLE IF NOT EXISTS job_logs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL,
    level log_level DEFAULT 'INFO',
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Generated Posters Table
CREATE TABLE IF NOT EXISTS generated_posters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(100) NOT NULL,
    user_identifier VARCHAR(255),
    username VARCHAR(255),
    display_name VARCHAR(255),
    poster_url VARCHAR(500),
    s3_key VARCHAR(500),
    status job_status DEFAULT 'pending',
    processing_time_ms INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_created_at ON batch_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_job_id ON batch_jobs(job_id);

CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_logs_created_at ON job_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_logs_level ON job_logs(level);

CREATE INDEX IF NOT EXISTS idx_generated_posters_job_id ON generated_posters(job_id);
CREATE INDEX IF NOT EXISTS idx_generated_posters_username ON generated_posters(username);
CREATE INDEX IF NOT EXISTS idx_generated_posters_status ON generated_posters(status);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_batch_jobs_updated_at
    BEFORE UPDATE ON batch_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_generated_posters_updated_at
    BEFORE UPDATE ON generated_posters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Poster Failure Details Table
CREATE TABLE IF NOT EXISTS poster_failure_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(100) NOT NULL,
    poster_id UUID,
    user_identifier VARCHAR(255),
    username VARCHAR(255),
    failure_type VARCHAR(100),
    error_message TEXT,
    error_details JSONB DEFAULT '{}',
    retry_count INTEGER DEFAULT 0,
    html_template TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (poster_id) REFERENCES generated_posters(id) ON DELETE CASCADE
);

-- Create indexes for failure details
CREATE INDEX IF NOT EXISTS idx_failure_details_job_id ON poster_failure_details(job_id);
CREATE INDEX IF NOT EXISTS idx_failure_details_poster_id ON poster_failure_details(poster_id);
CREATE INDEX IF NOT EXISTS idx_failure_details_failure_type ON poster_failure_details(failure_type);
CREATE INDEX IF NOT EXISTS idx_failure_details_created_at ON poster_failure_details(created_at DESC);

-- Insert initial log
INSERT INTO job_logs (job_id, level, message, details)
VALUES ('system', 'INFO', 'Database initialized successfully', ('{"version": "1.0.0", "timestamp": "' || CURRENT_TIMESTAMP || '"}')::jsonb);
