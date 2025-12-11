"""Secret Manager client for managing secrets"""

from typing import Optional, Dict, Any
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class SecretManagerClient:
    """Handle Secret Manager operations"""

    def __init__(self):
        self.enabled = settings.secret_manager_enabled
        self.gcp_project_id = settings.gcp_project_id
        self._client = None

    @property
    def client(self):
        """Lazy load Secret Manager client"""
        if not self._client and self.enabled:
            try:
                from google.cloud import secretmanager
                self._client = secretmanager.SecretManagerServiceClient()
                logger.info("Secret Manager client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize Secret Manager client: {str(e)}")
        return self._client

    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """
        Get secret value from Secret Manager

        Args:
            secret_name: Name of the secret
            version: Secret version (default: latest)

        Returns:
            Secret value as string or None if not found
        """
        if not self.enabled or not self.client:
            logger.debug(f"Secret Manager disabled, cannot get secret: {secret_name}")
            return None

        try:
            # Build the resource name
            name = f"projects/{self.gcp_project_id}/secrets/{secret_name}/versions/{version}"

            # Access the secret version
            response = self.client.access_secret_version(request={"name": name})

            # Decode the secret payload
            payload = response.payload.data.decode("UTF-8")
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return payload

        except Exception as e:
            logger.error(f"Failed to get secret {secret_name}: {str(e)}")
            return None

    def get_secret_json(self, secret_name: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """
        Get secret value as JSON from Secret Manager

        Args:
            secret_name: Name of the secret
            version: Secret version (default: latest)

        Returns:
            Secret value as dictionary or None if not found
        """
        secret_value = self.get_secret(secret_name, version)
        if not secret_value:
            return None

        try:
            return json.loads(secret_value)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secret {secret_name} as JSON: {str(e)}")
            return None

    def get_oauth_credentials(self) -> Optional[Dict[str, str]]:
        """
        Get Google OAuth credentials from Secret Manager

        Returns:
            Dictionary with client_id and client_secret
        """
        if not self.enabled:
            # Use environment variables in development
            return {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret
            }

        secret_name = settings.oauth_credentials_secret_name
        credentials = self.get_secret_json(secret_name)

        if not credentials:
            logger.warning("OAuth credentials not found in Secret Manager, using env vars")
            return {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret
            }

        return credentials

    def get_jwt_secret_key(self) -> str:
        """
        Get JWT secret key from Secret Manager

        Returns:
            JWT secret key
        """
        if not self.enabled:
            # Use environment variable in development
            return settings.jwt_secret_key

        secret_name = settings.jwt_key_secret_name
        secret_key = self.get_secret(secret_name)

        if not secret_key:
            logger.warning("JWT secret key not found in Secret Manager, using env var")
            return settings.jwt_secret_key

        return secret_key

    def get_api_proxy_credentials(self, email: str, project_id: str) -> Optional[Dict[str, str]]:
        """
        Get API proxy credentials for a user

        Args:
            email: User's email address
            project_id: Project ID

        Returns:
            Dictionary with client_id and client_secret for API proxy
        """
        if not self.enabled:
            # Return mock credentials in development
            logger.debug(f"Secret Manager disabled, returning mock credentials for {email}")
            return {
                "client_id": f"{project_id}-{email.split('@')[0]}",
                "client_secret": f"mock-secret-{email.split('@')[0]}"
            }

        # Get the secret path from project config
        from app.core.project_config import project_config_manager
        import asyncio

        # Get project config synchronously (or use cached version)
        try:
            # Try to get from local config first
            from app.config import LOCAL_PROJECT_CONFIGS
            project_config = LOCAL_PROJECT_CONFIGS.get(project_id)

            if not project_config:
                # Fall back to async call (not ideal but necessary here)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                project_config = loop.run_until_complete(
                    project_config_manager.get_project_config(project_id)
                )
                loop.close()

            secret_path = project_config.get("api_proxy_credentials_path")
            if not secret_path:
                logger.error(f"No api_proxy_credentials_path for project {project_id}")
                return None

            # Get all user credentials from the secret
            secret_name = secret_path.split("/")[-1]
            all_credentials = self.get_secret_json(secret_name)

            if not all_credentials:
                logger.error(f"Failed to get credentials from {secret_name}")
                return None

            # Get credentials for specific user
            user_creds = all_credentials.get(email)
            if not user_creds:
                logger.warning(f"No credentials found for user {email} in {secret_name}")
                return None

            return user_creds

        except Exception as e:
            logger.error(f"Error getting API proxy credentials: {str(e)}")
            return None


# Create singleton instance
secret_manager_client = SecretManagerClient()