"""Configuration settings for the auth server"""

from typing import List, Optional, Dict, Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Server Configuration
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Google OAuth Configuration
    # 本番環境でSecret Manager有効時はOptional（Secret Managerから取得）
    google_client_id: Optional[str] = Field(None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/callback/{project_id}",
        alias="GOOGLE_REDIRECT_URI"
    )

    # JWT Configuration
    # 本番環境でSecret Manager有効時はOptional（Secret Managerから取得）
    jwt_secret_key: Optional[str] = Field(None, alias="JWT_SECRET_KEY")
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
    # API Proxy Server Authentication (Unified Auth Server's own credentials)
    api_proxy_client_id: str = Field(
        default="unified-auth-server",
        alias="API_PROXY_CLIENT_ID",
        description="Client ID for authenticating with API Proxy Server"
    )
    api_proxy_hmac_secret: Optional[str] = Field(
        None,
        alias="API_PROXY_HMAC_SECRET",
        description="HMAC secret for authenticating with API Proxy Server"
    )
    proxy_timeout_seconds: int = Field(
        default=300,
        alias="PROXY_TIMEOUT_SECONDS",
        description="HTTP timeout for API proxy requests (seconds)"
    )

    # Google Workspace Admin SDK Configuration (Service Account)
    workspace_service_account_file: Optional[str] = Field(
        default=None,
        alias="WORKSPACE_SERVICE_ACCOUNT_FILE",
        description="Path to service account JSON file for Admin SDK"
    )
    workspace_admin_email: Optional[str] = Field(
        default=None,
        alias="WORKSPACE_ADMIN_EMAIL",
        description="Admin email for domain-wide delegation impersonation"
    )

    # Allowed Domains
    allowed_domains: List[str] = Field(
        default_factory=lambda: ["i-seifu.jp", "i-seifu.ac.jp"],
        alias="ALLOWED_DOMAINS"
    )

    # Allowed Hosts for redirect URI validation (security)
    allowed_hosts: str | List[str] = Field(
        default="localhost:8000",
        alias="ALLOWED_HOSTS",
        description="Allowed host headers for redirect URI validation"
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

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse comma-separated hosts from environment variable"""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v

    @model_validator(mode='after')
    def validate_credentials(self):
        """
        Validate OAuth and JWT credentials based on Secret Manager configuration

        本番環境でSecret Manager無効時は環境変数必須
        開発環境でも環境変数が必要
        """
        if not self.secret_manager_enabled:
            # Secret Manager無効時は環境変数必須
            if not self.google_client_id or not self.google_client_secret:
                raise ValueError(
                    "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required "
                    "when SECRET_MANAGER_ENABLED=false"
                )
            if not self.jwt_secret_key:
                raise ValueError(
                    "JWT_SECRET_KEY is required when SECRET_MANAGER_ENABLED=false"
                )
        return self

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


# Local project configurations for development only
# これらの設定は開発環境（ENVIRONMENT=development）でのみ使用される
LOCAL_PROJECT_CONFIGS: Dict[str, Dict[str, Any]] = {}

# 開発環境専用のテスト設定を初期化
if settings.is_development:
    LOCAL_PROJECT_CONFIGS["test-project"] = {
        "name": "テストプロジェクト",
        "type": "streamlit_local",
        "description": "開発用テストプロジェクト（本番環境では無効）",
        "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp", "gmail.com"],  # 開発環境のみGmail許可
        "student_allowed": False,
        "admin_emails": [],
        "required_groups": [],
        "allowed_groups": [],
        "redirect_uris": ["http://localhost:8501/", "http://localhost:3000/callback"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": True,
        "product_id": "product-TestProject"
    }

# 以下のプロジェクト設定は開発・本番環境共通
if settings.is_development or settings.use_local_config:
    LOCAL_PROJECT_CONFIGS["slide-video"] = {
        "name": "スライド動画生成システム",
        "type": "streamlit_local",
        "description": "PowerPointから動画を生成するツール",
        "allowed_domains": settings.allowed_domains,  # 環境変数から取得
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
    }
    LOCAL_PROJECT_CONFIGS["group-ou-test"] = {
        "name": "グループ・OU認証テスト",
        "type": "streamlit_local",
        "description": "Google Workspaceグループと組織部門のテスト用プロジェクト",
        "allowed_domains": settings.allowed_domains,  # 環境変数から取得
        "student_allowed": False,
        "admin_emails": [],
        # グループベース認証のテスト（教職員グループに所属していればOK）
        "required_groups": [],
        "allowed_groups": [],  # 本番環境では環境変数で指定
        # 組織部門ベース認証
        "required_org_units": [],
        "allowed_org_units": [],
        "redirect_uris": ["http://localhost:8501/", "http://localhost:3000/callback"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": False
    }

    # 進路指導ポータル Shinro Compass
    LOCAL_PROJECT_CONFIGS["shinro-compass"] = {
        "name": "進路指導ポータル Shinro Compass",
        "type": "webapp",
        "description": "清風情報工科学院 日本語科の進路指導ポータル（学生400名・教職員50名）",
        "allowed_domains": ["i-seifu.jp"],
        "student_allowed": True,
        "admin_emails": ["h.hamada@i-seifu.jp"],
        "required_groups": [],
        "allowed_groups": [],
        "required_org_units": [],
        "allowed_org_units": [],
        "redirect_uris": [
            "http://localhost:3000/callback"
            # 本番URL確定後に追加: "https://shinro-compass-xxx.run.app/callback"
        ],
        "token_delivery": "cookie",
        "token_expiry_days": 30,
        "api_proxy_enabled": True,
        "product_id": "shinro-compass",
        # ロール判定ルール（priorityが小さいほど優先）
        # 判定順: 管理者 → 事務 → 教員 → 生徒
        "role_rules": [
            {
                "priority": 1,
                "role": "admin",
                "condition_type": "email_match",
                "emails": ["h.hamada@i-seifu.jp"]
            },
            {
                "priority": 2,
                "role": "office",
                "condition_type": "group_membership",
                "group_email": "office@i-seifu.jp"
            },
            {
                "priority": 3,
                "role": "teacher",
                "condition_type": "group_membership",
                "group_email": "staff@i-seifu.jp"
            },
            {
                "priority": 4,
                "role": "student",
                "condition_type": "default"
            }
        ]
    }