"""Configuration settings for the auth server"""

from typing import List, Optional, Dict, Any
import os

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Server Configuration
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Google OAuth Configuration
    google_client_id: str = Field(..., alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(..., alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/callback/{project_id}",
        alias="GOOGLE_REDIRECT_URI"
    )

    # JWT Configuration
    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiry_days: int = Field(default=30, alias="JWT_EXPIRY_DAYS")

    # Google Cloud Configuration
    gcp_project_id: Optional[str] = Field(None, alias="GCP_PROJECT_ID")
    use_firebase_emulator: bool = Field(default=False, alias="USE_FIREBASE_EMULATOR")
    firebase_emulator_host: str = Field(default="localhost:8080", alias="FIREBASE_EMULATOR_HOST")

    # Secret Manager Configuration
    secret_manager_enabled: bool = Field(default=False, alias="SECRET_MANAGER_ENABLED")
    oauth_credentials_secret_name: str = Field(
        default="google-oauth-credentials",
        alias="OAUTH_CREDENTIALS_SECRET_NAME"
    )
    jwt_key_secret_name: str = Field(
        default="jwt-secret-key",
        alias="JWT_KEY_SECRET_NAME"
    )

    # API Proxy Server Configuration
    api_proxy_server_url: str = Field(
        default="https://api-key-server.run.app",
        alias="API_PROXY_SERVER_URL"
    )

    # Allowed Domains
    allowed_domains: List[str] = Field(
        default_factory=lambda: ["i-seifu.jp", "i-seifu.ac.jp"],
        alias="ALLOWED_DOMAINS"
    )

    # CORS Settings
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8501",
            "http://localhost:8000"
        ],
        alias="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    # Development Mode
    use_local_config: bool = Field(default=False, alias="USE_LOCAL_CONFIG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            # Handle comma-separated lists for domains and CORS origins
            if field_name in ["allowed_domains", "cors_origins"]:
                if "," in raw_val:
                    return [domain.strip() for domain in raw_val.split(",")]
            return raw_val

    def __init__(self, **values):
        # Parse comma-separated environment variables
        if "ALLOWED_DOMAINS" in os.environ:
            domains = os.environ["ALLOWED_DOMAINS"]
            if "," in domains:
                values["allowed_domains"] = [d.strip() for d in domains.split(",")]

        if "CORS_ORIGINS" in os.environ:
            origins = os.environ["CORS_ORIGINS"]
            if "," in origins:
                values["cors_origins"] = [o.strip() for o in origins.split(",")]

        super().__init__(**values)

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment.lower() in ["development", "dev", "local"]

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment.lower() in ["production", "prod"]


# Create settings instance
settings = Settings()


# Local project configurations for development
LOCAL_PROJECT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "test-project": {
        "name": "テストプロジェクト",
        "type": "streamlit_local",
        "description": "開発用テストプロジェクト",
        "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp", "gmail.com"],  # Allow Gmail for testing
        "student_allowed": False,
        "admin_emails": [],
        "required_groups": [],
        "allowed_groups": [],
        "redirect_uris": ["http://localhost:8501/", "http://localhost:3000/callback"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": True,
        "product_id": "product-TestProject"
    },
    "slide-video": {
        "name": "スライド動画生成システム",
        "type": "streamlit_local",
        "description": "PowerPointから動画を生成するツール",
        "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
        "student_allowed": False,
        "admin_emails": [],
        "required_groups": [],
        "allowed_groups": [],
        "redirect_uris": ["http://localhost:8501/"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": True,
        "product_id": "product-SlideVideo",
        "api_proxy_credentials_path": "projects/xxx/secrets/slidevideo-users"
    }
}