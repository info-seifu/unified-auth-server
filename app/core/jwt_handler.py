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
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.default_expiry_days = settings.jwt_expiry_days

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

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

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
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True}
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

        Args:
            token: JWT token string

        Returns:
            Decoded token payload without verification
        """
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
        expiry_days: Optional[int] = None
    ) -> str:
        """
        Refresh an existing token with a new expiry time

        Args:
            token: Existing JWT token
            expiry_days: New token expiry in days

        Returns:
            New JWT token with updated expiry

        Raises:
            InvalidTokenError: If token is invalid
        """
        # Verify the current token (allow expired tokens for refresh)
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Allow expired tokens
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