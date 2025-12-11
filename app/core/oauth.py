"""Google OAuth handling"""

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import Request
from typing import Dict, Any, Optional, Tuple
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class GoogleOAuthHandler:
    """Handle Google OAuth authentication flow"""

    def __init__(self):
        self.oauth = OAuth()
        self.google_client = None
        self._setup_google_client()

    def _setup_google_client(self):
        """Setup Google OAuth client"""
        self.oauth.register(
            name='google',
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile',
                'prompt': 'select_account',  # Always show account selector
            }
        )
        self.google_client = self.oauth.google

    async def create_authorization_url(
        self,
        request: Request,
        project_id: str,
        redirect_uri: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Create Google OAuth authorization URL

        Args:
            request: FastAPI request object
            project_id: Project ID for the authentication
            redirect_uri: Custom redirect URI (defaults to settings)

        Returns:
            Tuple of (authorization_url, state)
        """
        # Store project_id in session for callback
        request.session['project_id'] = project_id

        # Build redirect URI
        if not redirect_uri:
            # Use default redirect URI from settings
            redirect_uri = settings.google_redirect_uri.format(project_id=project_id)
            # Make it absolute URL in production
            if settings.is_production:
                host = request.headers.get('host', 'auth.yourcompany.com')
                redirect_uri = f"https://{host}/callback/{project_id}"
            else:
                host = request.headers.get('host', 'localhost:8000')
                redirect_uri = f"http://{host}/callback/{project_id}"

        # Create authorization URL - Authlib will automatically handle state
        # IMPORTANT: Pass request as first argument so Authlib can save state in session
        authorization_result = await self.google_client.authorize_redirect(
            request,
            redirect_uri
        )

        # authorize_redirect returns a RedirectResponse, extract the URL
        authorization_url = str(authorization_result.headers.get('location', ''))
        # State is now stored in session by Authlib
        state = request.session.get('_state_google_' + self.google_client.name, None)

        logger.info(f"Created authorization URL for project: {project_id}")
        return authorization_url, state

    async def handle_callback(
        self,
        request: Request,
        code: str,
        state: str,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Handle OAuth callback and exchange code for user info

        Args:
            request: Starlette request object
            code: Authorization code from Google
            state: State token for CSRF verification
            project_id: Project ID

        Returns:
            User information dictionary

        Raises:
            OAuthError: If OAuth flow fails
            ValueError: If state doesn't match
        """
        try:
            # Exchange code for token - Authlib will automatically verify state from session
            token = await self.google_client.authorize_access_token(request)

            # Get user info from Google
            user_info = token.get('userinfo')
            if not user_info:
                # If userinfo not in token, fetch it separately
                user_info = await self.google_client.get(
                    'https://www.googleapis.com/oauth2/v2/userinfo',
                    token=token
                ).json()

            # Extract relevant information
            result = {
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'given_name': user_info.get('given_name'),
                'family_name': user_info.get('family_name'),
                'picture': user_info.get('picture'),
                'email_verified': user_info.get('email_verified', False),
                'locale': user_info.get('locale', 'ja'),
                'hd': user_info.get('hd'),  # Hosted domain (for Google Workspace)
            }

            logger.info(f"OAuth successful for user: {result['email']}")
            return result

        except OAuthError as e:
            logger.error(f"OAuth error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during OAuth: {str(e)}")
            raise OAuthError(f"OAuth flow failed: {str(e)}")

    def get_logout_url(self, return_url: Optional[str] = None) -> str:
        """
        Get Google logout URL

        Args:
            return_url: URL to return to after logout

        Returns:
            Google logout URL
        """
        base_url = "https://accounts.google.com/logout"
        if return_url:
            return f"{base_url}?continue={return_url}"
        return base_url


# Create singleton instance
google_oauth_handler = GoogleOAuthHandler()