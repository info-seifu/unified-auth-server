"""Pydantic schemas for API requests and responses"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr


class UserInfo(BaseModel):
    """User information from JWT token - matches OpenAPI schema"""

    email: EmailStr = Field(..., description="User's email address", example="yamada@i-seifu.jp")
    name: str = Field(..., description="User's full name", example="山田太郎")
    project_id: str = Field(..., description="Project identifier", example="slide-video")
    exp: int = Field(..., description="Token expiry (UNIX timestamp)", example=1738819200)
    valid: bool = Field(default=True, description="Token validity status")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "yamada@i-seifu.jp",
                "name": "山田太郎",
                "project_id": "slide-video",
                "exp": 1738819200,
                "valid": True
            }
        }


class ErrorResponse(BaseModel):
    """Error response - matches OpenAPI schema"""

    error: str = Field(..., description="Error code or message", example="AUTH_004")
    detail: Optional[str] = Field(None, description="Detailed error information", example="Token has expired")
    message: Optional[str] = Field(None, description="Human-readable error message")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "AUTH_004",
                "detail": "Token has expired",
                "message": "Invalid token"
            }
        }


class TokenResponse(BaseModel):
    """Token refresh response"""

    token: str = Field(..., description="New JWT token")
    expiry: str = Field(..., description="Token expiry time (ISO format)")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expiry": "2025-02-06T12:00:00+00:00"
            }
        }


class ProxyRequest(BaseModel):
    """API Proxy request - matches OpenAPI schema"""

    endpoint: str = Field(
        ...,
        description="API proxy server endpoint path",
        example="/api/openai/images/generate"
    )
    method: str = Field(
        default="POST",
        description="HTTP method",
        example="POST"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Data to send to the API (varies by endpoint)",
        example={
            "prompt": "A beautiful landscape",
            "size": "1024x1024",
            "quality": "standard"
        }
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Additional headers to include",
        example={"Content-Type": "application/json"}
    )

    class Config:
        json_schema_extra = {
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


class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status", example="healthy")
    environment: str = Field(..., description="Environment name", example="development")
    debug: bool = Field(..., description="Debug mode status", example=False)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "environment": "development",
                "debug": False
            }
        }


class ServiceInfoResponse(BaseModel):
    """Service information response"""

    service: str = Field(..., description="Service name", example="Unified Auth Server")
    version: str = Field(..., description="Service version", example="1.0.0")
    status: str = Field(..., description="Service status", example="running")
    environment: str = Field(..., description="Environment name", example="development")
    endpoints: Dict[str, str] = Field(..., description="Available endpoints")

    class Config:
        json_schema_extra = {
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


class AuditLogEntry(BaseModel):
    """Audit log entry model"""

    id: Optional[str] = Field(None, description="Log entry ID")
    timestamp: Optional[datetime] = Field(None, description="Event timestamp")
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

    total_logins: int = Field(0, description="Total successful logins")
    failed_logins: int = Field(0, description="Total failed login attempts")
    unique_users: int = Field(0, description="Number of unique users")
    api_calls: int = Field(0, description="Total API proxy calls")
    by_event_type: Dict[str, int] = Field(default_factory=dict, description="Count by event type")


class AuditStatisticsResponse(BaseModel):
    """Response for audit statistics"""

    statistics: AuditStatistics = Field(..., description="Audit statistics")
    project_id: Optional[str] = Field(None, description="Project ID if filtered")
    period_days: int = Field(..., description="Analysis period in days")