"""Configuration settings for the auth server"""

from typing import List, Optional, Dict, Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("allowed_domains", mode="before")
    @classmethod
    def parse_allowed_domains(cls, v):
        """Parse comma-separated domains from environment variable"""
        if isinstance(v, str):
            return [domain.strip() for domain in v.split(",")]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated origins from environment variable"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

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
        "required_org_units": [],
        "allowed_org_units": [],
        "redirect_uris": ["http://localhost:8501/"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": True,
        "product_id": "product-SlideVideo",
        "api_proxy_credentials_path": "projects/xxx/secrets/slidevideo-users"
    },
    "group-ou-test": {
        "name": "グループ・OU認証テスト",
        "type": "streamlit_local",
        "description": "Google Workspaceグループと組織部門のテスト用プロジェクト",
        "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
        "student_allowed": False,
        "admin_emails": [],
        # グループベース認証のテスト（教職員グループに所属していればOK）
        "required_groups": [],
        "allowed_groups": [],  # ["staff@i-seifu.jp"] をコメントアウト
        # 組織部門ベース認証のテスト（法人部のみ許可）
        "required_org_units": [],
        "allowed_org_units": ["/法人部"],
        "redirect_uris": ["http://localhost:8501/", "http://localhost:3000/callback"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": False
    }
}