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


# Global settings instance
settings = Settings()
