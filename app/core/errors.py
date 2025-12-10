"""Error handling and custom exceptions"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class AuthError(HTTPException):
    """Base authentication error"""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}

        super().__init__(
            status_code=status_code,
            detail={
                "error": error_code,
                "message": message,
                **self.details
            }
        )


class InvalidDomainError(AuthError):
    """Raised when user's email domain is not allowed"""

    def __init__(self, domain: str, allowed_domains: list):
        super().__init__(
            error_code="AUTH_001",
            message=f"Domain '{domain}' is not allowed",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"allowed_domains": allowed_domains}
        )


class StudentNotAllowedError(AuthError):
    """Raised when student account tries to access non-student project"""

    def __init__(self, email: str):
        super().__init__(
            error_code="AUTH_002",
            message="Student accounts are not allowed for this project",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"email": email}
        )


class AdminOnlyError(AuthError):
    """Raised when non-admin tries to access admin-only project"""

    def __init__(self, email: str):
        super().__init__(
            error_code="AUTH_003",
            message="This project is restricted to administrators only",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"email": email}
        )


class InvalidTokenError(AuthError):
    """Raised when JWT token is invalid"""

    def __init__(self, reason: str = "Invalid token"):
        super().__init__(
            error_code="AUTH_004",
            message=reason,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class TokenExpiredError(AuthError):
    """Raised when JWT token has expired"""

    def __init__(self):
        super().__init__(
            error_code="AUTH_005",
            message="Token has expired",
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class ProjectNotFoundError(AuthError):
    """Raised when project ID is not found"""

    def __init__(self, project_id: str):
        super().__init__(
            error_code="AUTH_006",
            message=f"Project '{project_id}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"project_id": project_id}
        )


class GroupMembershipRequiredError(AuthError):
    """Raised when user is not a member of required groups"""

    def __init__(self, required_groups: list):
        super().__init__(
            error_code="AUTH_007",
            message="User is not a member of required groups",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"required_groups": required_groups}
        )


class NoMatchingGroupError(AuthError):
    """Raised when user is not a member of any allowed groups"""

    def __init__(self, allowed_groups: list):
        super().__init__(
            error_code="AUTH_008",
            message="User is not a member of any allowed groups",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"allowed_groups": allowed_groups}
        )


class ProxyError(HTTPException):
    """Base proxy error"""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}

        super().__init__(
            status_code=status_code,
            detail={
                "error": error_code,
                "message": message,
                **self.details
            }
        )


class ClientSecretNotFoundError(ProxyError):
    """Raised when client secret is not found for user"""

    def __init__(self, email: str):
        super().__init__(
            error_code="PROXY_001",
            message=f"Client secret not found for user: {email}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"email": email}
        )


class APIProxyFailedError(ProxyError):
    """Raised when API proxy request fails"""

    def __init__(self, reason: str):
        super().__init__(
            error_code="PROXY_002",
            message=f"API proxy request failed: {reason}",
            status_code=status.HTTP_502_BAD_GATEWAY
        )