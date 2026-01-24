"""
Configuration management using pydantic-settings
"""
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # OpenRouter API
    openrouter_api_key: str

    # Django API
    django_api_url: str = "https://gcp.gravitron.run"

    # AWS S3 (optional - only required for S3 uploads)
    aws_s3_bucket: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_base_url: Optional[str] = None

    # Application
    base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # RedPanda / Kafka Configuration
    redpanda_broker: str = "localhost:19092"
    redpanda_schema_registry: str = "http://localhost:18081"
    
    # PostgreSQL Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "poster_generation"
    postgres_user: str = "poster_user"
    postgres_password: str = "poster_secure_pwd_2024"

    # Redis Configuration (for TaskIQ)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # Batch Processing Configuration
    batch_size: int = 10  # Increased to 10 parallel jobs
    max_concurrent_jobs: int = 5
    taskiq_workers: int = 4  # Number of TaskIQ worker processes

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def is_s3_configured(self) -> bool:
        """Check if S3 is properly configured"""
        return all([
            self.aws_s3_bucket,
            self.aws_access_key_id,
            self.aws_secret_access_key,
            self.s3_base_url
        ])
    
    @property
    def postgres_dsn(self) -> str:
        """Get PostgreSQL connection DSN"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


# Global settings instance
settings = Settings()

