"""JWT token handling"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from app.config import settings
from app.core.errors import InvalidTokenError, TokenExpiredError
import logging

logger = logging.getLogger(__name__)


class JWTHandler:
    """Handle JWT token creation and verification"""

    def __init__(self):
        self.algorithm = settings.jwt_algorithm
        self.default_expiry_days = settings.jwt_expiry_days
        self._secret_key_cache = None

    def _get_secret_key(self) -> str:
        """
        Get JWT secret key from Secret Manager if enabled, otherwise from settings

        Returns:
            JWT secret key
        """
        # Return cached key if available
        if self._secret_key_cache:
            return self._secret_key_cache

        # Get from environment if Secret Manager is disabled
        if not settings.secret_manager_enabled:
            if not settings.jwt_secret_key:
                raise ValueError("JWT_SECRET_KEY not configured")
            self._secret_key_cache = settings.jwt_secret_key
            return self._secret_key_cache

        # Load from Secret Manager if enabled
        from app.core.secret_manager import secret_manager_client
        secret_key = secret_manager_client.get_jwt_secret_key()

        if not secret_key:
            raise ValueError("JWT secret key not found in Secret Manager")

        logger.info("Loaded JWT secret key from Secret Manager")
        self._secret_key_cache = secret_key
        return self._secret_key_cache

    def create_token(
        self,
        email: str,
        name: str,
        project_id: str,
        expiry_days: Optional[int] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a JWT token with user information

        Args:
            email: User's email address
            name: User's full name
            project_id: Project ID for which the token is issued
            expiry_days: Token expiry in days (defaults to settings)
            additional_claims: Additional claims to include in the token

        Returns:
            JWT token string
        """
        now = datetime.now(timezone.utc)
        expiry_days = expiry_days or self.default_expiry_days
        expiry = now + timedelta(days=expiry_days)

        payload = {
            "email": email,
            "name": name,
            "project_id": project_id,
            "iat": now,
            "exp": expiry,
            "iss": "unified-auth-server",
            "sub": email  # Subject is the user's email
        }

        # Add any additional claims
        if additional_claims:
            payload.update(additional_claims)

        secret_key = self._get_secret_key()
        token = jwt.encode(payload, secret_key, algorithm=self.algorithm)

        logger.info(f"Token created for user: {email}, project: {project_id}")
        return token

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded token payload

        Raises:
            InvalidTokenError: If token is invalid
            TokenExpiredError: If token has expired
        """
        try:
            secret_key = self._get_secret_key()
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True},
                issuer="unified-auth-server"  # Issuer検証を追加
            )

            logger.debug(f"Token verified for user: {payload.get('email')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: Token expired")
            raise TokenExpiredError()

        except jwt.InvalidTokenError as e:
            logger.warning(f"Token verification failed: {str(e)}")
            raise InvalidTokenError(f"Token verification failed: {str(e)}")

    def decode_without_verification(self, token: str) -> Dict[str, Any]:
        """
        Decode a JWT token without verification (for debugging only)

        WARNING: This method is only available in development mode for security reasons.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload without verification

        Raises:
            RuntimeError: If called in production environment
        """
        from app.config import settings

        if not settings.is_development:
            logger.error("Attempted to use decode_without_verification in production")
            raise RuntimeError(
                "decode_without_verification is only available in development mode"
            )

        try:
            return jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
        except Exception as e:
            logger.error(f"Failed to decode token: {str(e)}")
            return {}

    def refresh_token(
        self,
        token: str,
        expiry_days: Optional[int] = None,
        max_refresh_days: int = 7
    ) -> str:
        """
        Refresh an existing token with a new expiry time

        セキュリティ: 期限切れから一定期間(デフォルト7日)以内のトークンのみリフレッシュ可能

        Args:
            token: Existing JWT token
            expiry_days: New token expiry in days
            max_refresh_days: Maximum days after expiry to allow refresh (default: 7)

        Returns:
            New JWT token with updated expiry

        Raises:
            InvalidTokenError: If token is invalid or too old to refresh
            TokenExpiredError: If token expired too long ago
        """
        # Verify the current token (allow expired tokens for refresh)
        try:
            secret_key = self._get_secret_key()
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Allow expired tokens
            )

            # Check if token is too old to refresh
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                days_since_expiry = (now - exp_datetime).days

                if days_since_expiry > max_refresh_days:
                    logger.warning(
                        f"Token refresh denied: expired {days_since_expiry} days ago "
                        f"(max: {max_refresh_days}), user: {payload.get('email')}"
                    )
                    raise TokenExpiredError(
                        f"Token expired too long ago ({days_since_expiry} days). "
                        f"Please log in again."
                    )

        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Cannot refresh invalid token: {str(e)}")

        # Create a new token with the same claims but new expiry
        return self.create_token(
            email=payload["email"],
            name=payload["name"],
            project_id=payload["project_id"],
            expiry_days=expiry_days,
            additional_claims={
                k: v for k, v in payload.items()
                if k not in ["email", "name", "project_id", "iat", "exp", "iss", "sub"]
            }
        )

    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """
        Get the expiry time of a token

        Args:
            token: JWT token string

        Returns:
            Expiry datetime or None if invalid
        """
        try:
            payload = self.decode_without_verification(token)
            exp = payload.get("exp")
            if exp:
                return datetime.fromtimestamp(exp, tz=timezone.utc)
        except Exception:
            pass
        return None


# Create a singleton instance
jwt_handler = JWTHandler()