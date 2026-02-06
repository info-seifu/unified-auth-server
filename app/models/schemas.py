"""Pydantic schemas for API requests and responses"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
import re


class UserInfo(BaseModel):
    """User information from JWT token - matches OpenAPI schema"""

    email: EmailStr = Field(..., description="User's email address", example="yamada@i-seifu.jp")
    name: str = Field(..., description="User's full name", example="山田太郎")
    project_id: str = Field(..., description="Project identifier", example="slide-video")
    exp: int = Field(..., description="Token expiry (UNIX timestamp)", example=1738819200)
    valid: bool = Field(default=True, description="Token validity status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "yamada@i-seifu.jp",
                "name": "山田太郎",
                "project_id": "slide-video",
                "exp": 1738819200,
                "valid": True
            }
        }
    )


class ErrorResponse(BaseModel):
    """Error response - matches OpenAPI schema"""

    error: str = Field(..., description="Error code or message", example="AUTH_004")
    detail: Optional[str] = Field(None, description="Detailed error information", example="Token has expired")
    message: Optional[str] = Field(None, description="Human-readable error message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "AUTH_004",
                "detail": "Token has expired",
                "message": "Invalid token"
            }
        }
    )


class TokenResponse(BaseModel):
    """Token refresh response"""

    token: str = Field(..., description="New JWT token")
    expiry: str = Field(..., description="Token expiry time (ISO format)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expiry": "2025-02-06T12:00:00+00:00"
            }
        }
    )


class ProxyRequest(BaseModel):
    """API Proxy request - matches OpenAPI schema"""

    endpoint: str = Field(
        ...,
        description="API proxy server endpoint path",
        example="/api/openai/images/generate"
    )
    method: Literal["POST", "GET", "PUT", "DELETE", "PATCH"] = Field(
        default="POST",
        description="HTTP method (allowed: POST, GET, PUT, DELETE, PATCH)",
        example="POST"
    )
    data: Dict[str, Any] = Field(
        ...,
        description=(
            "Data to send to the API (varies by endpoint). "
            "将来的な改善: API別の専用スキーマ定義を検討"
        ),
        example={
            "prompt": "A beautiful landscape",
            "size": "1024x1024",
            "quality": "standard"
        }
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "Additional headers to include. "
            "システムヘッダー（Authorization, HMAC署名等）は自動的に追加されます"
        ),
        example={"X-Custom-Header": "value"}
    )

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """
        エンドポイントパスのバリデーション
        - 相対パス攻撃（..）を防ぐ
        - 基本的なパス形式を検証
        """
        # 相対パス攻撃を防ぐ
        if '..' in v:
            raise ValueError('Endpoint cannot contain ".." (path traversal attack prevention)')

        # 基本的なパス形式を検証
        # 許可: /api/openai/images, /v1/chat/{product_id}, api/endpoint 等
        if not re.match(r'^(/[\w\-/{}.]+|[\w\-]+)$', v):
            raise ValueError('Invalid endpoint format. Allowed characters: alphanumeric, -, _, /, {, }')

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "OpenAI Image Generation",
                    "value": {
                        "endpoint": "/api/openai/images/generate",
                        "data": {
                            "prompt": "A professional educational slide background",
                            "model": "dall-e-3",
                            "size": "1024x1024",
                            "quality": "standard",
                            "n": 1
                        }
                    }
                },
                {
                    "summary": "Claude API Request",
                    "value": {
                        "endpoint": "/api/anthropic/messages",
                        "data": {
                            "model": "claude-3-5-sonnet-20241022",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "スライドの内容を生成してください"
                                }
                            ],
                            "max_tokens": 4096,
                            "temperature": 1.0
                        }
                    }
                }
            ]
        }
    )


class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status", example="healthy")
    environment: str = Field(..., description="Environment name", example="development")
    debug: bool = Field(..., description="Debug mode status", example=False)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "environment": "development",
                "debug": False
            }
        }
    )


class ServiceInfoResponse(BaseModel):
    """Service information response"""

    service: str = Field(..., description="Service name", example="Unified Auth Server")
    version: str = Field(..., description="Service version", example="1.0.0")
    status: str = Field(..., description="Service status", example="running")
    environment: str = Field(..., description="Environment name", example="development")
    endpoints: Dict[str, str] = Field(..., description="Available endpoints")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "Unified Auth Server",
                "version": "1.0.0",
                "status": "running",
                "environment": "development",
                "endpoints": {
                    "login": "/login/{project_id}",
                    "callback": "/callback/{project_id}",
                    "verify": "/api/verify",
                    "refresh": "/api/refresh",
                    "logout": "/logout",
                    "health": "/health"
                }
            }
        }
    )


class AuditLogEntry(BaseModel):
    """Audit log entry model"""

    id: Optional[str] = Field(None, description="Log entry ID (Firestoreが自動生成)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp (UTC timezone-aware)"
    )
    event_type: str = Field(..., description="Type of event")
    project_id: str = Field(..., description="Project ID")
    user_email: EmailStr = Field(..., description="User's email")
    details: Dict[str, Any] = Field(default_factory=dict, description="Event details")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")


class AuditLogsResponse(BaseModel):
    """Response for audit logs query"""

    logs: List[AuditLogEntry] = Field(..., description="List of audit log entries")
    count: int = Field(..., description="Number of logs returned")


class LoginHistoryResponse(BaseModel):
    """Response for login history query"""

    history: List[AuditLogEntry] = Field(..., description="List of login events")
    count: int = Field(..., description="Number of events")
    user: EmailStr = Field(..., description="User's email")
    days: int = Field(..., description="Number of days queried")


class AuditStatistics(BaseModel):
    """Audit statistics model"""

    total_logins: int = Field(default=0, description="Total successful logins")
    failed_logins: int = Field(default=0, description="Total failed login attempts")
    unique_users: int = Field(default=0, description="Number of unique users")
    api_calls: int = Field(default=0, description="Total API proxy calls")
    by_event_type: Dict[str, int] = Field(default_factory=dict, description="Count by event type")


class AuditStatisticsResponse(BaseModel):
    """Response for audit statistics"""

    statistics: AuditStatistics = Field(..., description="Audit statistics")
    project_id: Optional[str] = Field(None, description="Project ID if filtered")
    period_days: int = Field(..., description="Analysis period in days")


class RoleRule(BaseModel):
    """ロール判定ルール

    プロジェクト設定内でユーザーのロールを決定するためのルール定義。
    priorityが小さいほど優先度が高く、最初にマッチしたルールが適用される。
    """

    priority: int = Field(..., description="優先順位（小さいほど優先）", ge=1)
    role: str = Field(..., description="割り当てるロール名", example="teacher")
    condition_type: Literal["group_membership", "email_pattern", "email_list", "default"] = Field(
        ...,
        description="判定条件の種類"
    )
    # group_membership用
    group_email: Optional[str] = Field(
        None,
        description="Google Groupのメールアドレス（condition_type=group_membershipの場合）",
        example="staff@i-seifu.jp"
    )
    # email_pattern用
    email_pattern: Optional[str] = Field(
        None,
        description="メールアドレスの正規表現パターン（condition_type=email_patternの場合）",
        example=r"^\d{8}@i-seifu\.jp$"
    )
    # email_list用
    email_list: Optional[List[str]] = Field(
        None,
        description="許可するメールアドレスのリスト（condition_type=email_listの場合）"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "グループメンバーシップによる判定",
                    "value": {
                        "priority": 1,
                        "role": "teacher",
                        "condition_type": "group_membership",
                        "group_email": "staff@i-seifu.jp"
                    }
                },
                {
                    "summary": "デフォルトロール",
                    "value": {
                        "priority": 99,
                        "role": "student",
                        "condition_type": "default"
                    }
                }
            ]
        }
    )


class RefreshTokenRequest(BaseModel):
    """リフレッシュトークンリクエスト"""

    refresh_token: str = Field(..., description="リフレッシュトークン")
    project_id: str = Field(..., description="プロジェクトID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "project_id": "shinro-compass"
            }
        }
    )


class TokenRefreshResponse(BaseModel):
    """トークンリフレッシュレスポンス"""

    access_token: str = Field(..., description="新しいアクセストークン")
    refresh_token: str = Field(..., description="新しいリフレッシュトークン")
    token_type: str = Field(default="Bearer", description="トークンタイプ")
    expires_in: int = Field(default=3600, description="アクセストークン有効期限（秒）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        }
    )


class ProjectConfig(BaseModel):
    """プロジェクト設定スキーマ"""

    name: str = Field(..., description="プロジェクト名")
    type: Literal["streamlit_local", "streamlit_cloud", "web_app", "webapp", "api_service"] = Field(
        ...,
        description="プロジェクトタイプ"
    )
    description: Optional[str] = Field(None, description="プロジェクトの説明")
    allowed_domains: List[str] = Field(..., description="許可するメールドメイン")
    student_allowed: bool = Field(default=False, description="学生アカウントを許可するか")
    admin_emails: List[str] = Field(default_factory=list, description="管理者メールアドレス")
    required_groups: List[str] = Field(default_factory=list, description="必須グループ")
    allowed_groups: List[str] = Field(default_factory=list, description="許可グループ")
    required_org_units: List[str] = Field(default_factory=list, description="必須組織部門")
    allowed_org_units: List[str] = Field(default_factory=list, description="許可組織部門")
    redirect_uris: List[str] = Field(..., description="許可するリダイレクトURI")
    token_delivery: Literal["query_param", "cookie"] = Field(..., description="トークン配信方法")
    token_expiry_days: int = Field(default=30, description="トークン有効期限（日数）")
    refresh_token_expiry_days: int = Field(default=30, description="リフレッシュトークン有効期限（日数）")
    api_proxy_enabled: bool = Field(default=False, description="APIプロキシを有効化")
    product_id: Optional[str] = Field(None, description="APIプロキシ用プロダクトID")
    role_rules: Optional[List[RoleRule]] = Field(
        None,
        description="ロール判定ルール（priorityが小さいほど優先）"
    )