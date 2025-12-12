"""Google Workspace Admin SDK client for groups and organizational units

This module uses a service account with domain-wide delegation to access
Admin SDK APIs, allowing any user's group and org unit information to be
retrieved regardless of the user's admin privileges.

Supports two authentication methods:
1. Service account JSON file (local development)
2. Application Default Credentials (Cloud Run with attached service account)
"""

from typing import List, Optional
import logging
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
import google.auth

logger = logging.getLogger(__name__)

# Required scopes for Admin SDK
SCOPES = [
    'https://www.googleapis.com/auth/admin.directory.group.readonly',
    'https://www.googleapis.com/auth/admin.directory.user.readonly',
]


class WorkspaceAdminClient:
    """
    Google Workspace Admin SDK client using service account

    This client uses a service account with domain-wide delegation to access
    user group memberships and organizational unit information. This allows
    the auth server to retrieve this information for any user, regardless of
    their admin privileges.

    Authentication methods:
    1. Service account JSON file (for local development)
    2. Application Default Credentials (for Cloud Run)

    Requirements:
    - Service account with domain-wide delegation enabled
    - Admin email for impersonation
    """

    def __init__(self):
        """Initialize Workspace Admin client"""
        self._service = None
        self._credentials = None
        self._initialized = False

    def initialize(self, service_account_file: Optional[str], admin_email: str, service_account_json: Optional[str] = None) -> bool:
        """
        Initialize the client with service account credentials

        Args:
            service_account_file: Path to service account JSON key file (None for Secret Manager)
            admin_email: Admin email for domain-wide delegation impersonation
            service_account_json: JSON string of service account credentials (from Secret Manager)

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if service_account_file:
                # Method 1: Use service account JSON file (local development)
                self._credentials = service_account.Credentials.from_service_account_file(
                    service_account_file,
                    scopes=SCOPES
                )
                logger.info("Using service account JSON file for authentication")
            elif service_account_json:
                # Method 2: Use service account JSON from Secret Manager (Cloud Run)
                service_account_info = json.loads(service_account_json)
                self._credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=SCOPES
                )
                logger.info("Using service account from Secret Manager")
            else:
                # Method 3: Use Application Default Credentials (fallback)
                credentials, project = google.auth.default(scopes=SCOPES)
                self._credentials = credentials
                logger.info(f"Using Application Default Credentials (project: {project})")

            # Delegate credentials to impersonate admin user
            self._credentials = self._credentials.with_subject(admin_email)

            # Build the Admin SDK service
            self._service = build(
                'admin',
                'directory_v1',
                credentials=self._credentials,
                cache_discovery=False
            )

            self._initialized = True
            logger.info(f"Workspace Admin client initialized, impersonating {admin_email}")
            return True

        except FileNotFoundError:
            logger.error(f"Service account file not found: {service_account_file}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Workspace Admin client: {str(e)}")
            return False

    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized"""
        return self._initialized

    def _ensure_initialized(self) -> bool:
        """Ensure client is initialized before making API calls"""
        if not self._initialized:
            logger.warning("Workspace Admin client not initialized. Group/OU validation will be skipped.")
            return False
        return True

    async def get_user_groups(self, user_email: str) -> List[str]:
        """
        Get list of groups that a user belongs to (including nested groups)

        This method retrieves all groups that a user is a member of, including
        groups that are nested within other groups (transitive membership).

        Args:
            user_email: User's email address

        Returns:
            List of group email addresses (e.g., ['group1@domain.com', 'group2@domain.com'])
            Includes both direct membership and nested group membership
            Returns empty list if client not initialized or on error
        """
        if not self._ensure_initialized():
            return []

        try:
            # Get direct groups for user
            direct_groups = set()
            page_token = None

            while True:
                try:
                    result = self._service.groups().list(
                        userKey=user_email,
                        pageToken=page_token
                    ).execute()

                    if 'groups' in result:
                        for group in result['groups']:
                            direct_groups.add(group['email'])

                    page_token = result.get('nextPageToken')
                    if not page_token:
                        break

                except HttpError as e:
                    if e.resp.status == 403:
                        logger.error(
                            f"Permission denied when listing groups for {user_email}. "
                            f"Check service account domain-wide delegation settings. "
                            f"Error details: {e.error_details if hasattr(e, 'error_details') else 'N/A'}"
                        )
                        return []
                    elif e.resp.status == 404:
                        logger.warning(f"User {user_email} not found in directory")
                        return []
                    raise

            # Now expand nested groups (get parent groups of direct groups)
            all_groups = set(direct_groups)
            groups_to_check = list(direct_groups)
            checked_groups = set()

            while groups_to_check:
                current_group = groups_to_check.pop(0)

                if current_group in checked_groups:
                    continue

                checked_groups.add(current_group)

                # Get groups that contain this group as a member
                try:
                    parent_result = self._service.groups().list(
                        userKey=current_group,
                        pageToken=None
                    ).execute()

                    if 'groups' in parent_result:
                        for parent_group in parent_result['groups']:
                            parent_email = parent_group['email']
                            if parent_email not in all_groups:
                                all_groups.add(parent_email)
                                groups_to_check.append(parent_email)

                except HttpError as e:
                    if e.resp.status in [403, 404]:
                        # Group might not exist or no permission, skip
                        continue
                    logger.warning(f"Could not check parent groups for {current_group}: {str(e)}")
                    continue

            groups_list = list(all_groups)
            logger.info(f"Retrieved {len(groups_list)} groups for {user_email} (including nested groups)")
            return groups_list

        except Exception as e:
            logger.error(f"Failed to get groups for {user_email}: {str(e)}")
            return []

    async def get_user_org_unit(self, user_email: str) -> Optional[str]:
        """
        Get the organizational unit path of a user

        Args:
            user_email: User's email address

        Returns:
            Organizational unit path (e.g., '/教職員/専任教員') or None if not found
        """
        if not self._ensure_initialized():
            return None

        try:
            # Get user information
            user = self._service.users().get(userKey=user_email).execute()
            org_unit_path = user.get('orgUnitPath', '/')

            logger.info(f"User {user_email} belongs to org unit: {org_unit_path}")
            return org_unit_path

        except HttpError as e:
            if e.resp.status == 403:
                logger.error(
                    f"Permission denied when getting org unit for {user_email}. "
                    "Check service account domain-wide delegation settings."
                )
                return None
            elif e.resp.status == 404:
                logger.warning(f"User {user_email} not found in directory")
                return None
            logger.error(f"HTTP error getting org unit for {user_email}: {str(e)}")
            return None

        except Exception as e:
            logger.error(f"Failed to get org unit for {user_email}: {str(e)}")
            return None

    def check_org_unit_hierarchy(self, user_org_unit: str, allowed_org_unit: str) -> bool:
        """
        Check if user's org unit matches or is a child of allowed org unit

        Hierarchical matching:
        - User in '/教職員/専任教員' matches allowed '/教職員' (parent)
        - User in '/教職員' matches allowed '/教職員' (exact)
        - User in '/学生' does NOT match allowed '/教職員'

        Args:
            user_org_unit: User's organizational unit path
            allowed_org_unit: Allowed organizational unit path

        Returns:
            True if user's org unit matches or is a descendant of allowed org unit
        """
        # Normalize paths (remove trailing slashes)
        user_path = user_org_unit.rstrip('/')
        allowed_path = allowed_org_unit.rstrip('/')

        # Exact match
        if user_path == allowed_path:
            return True

        # Check if user's org unit is a child of allowed org unit
        # e.g., user='/教職員/専任教員', allowed='/教職員' -> True
        if user_path.startswith(allowed_path + '/'):
            return True

        return False


# Singleton instance
workspace_admin_client = WorkspaceAdminClient()


def initialize_workspace_admin_client() -> bool:
    """
    Initialize the workspace admin client with settings from config

    This should be called during application startup.

    Authentication priority:
    1. If WORKSPACE_SERVICE_ACCOUNT_FILE is set, use JSON file (local dev)
    2. If SECRET_MANAGER_ENABLED, try to get from Secret Manager (Cloud Run)
    3. Otherwise, use Application Default Credentials (fallback)

    Returns:
        True if initialization successful, False otherwise
    """
    from app.config import settings

    if not settings.workspace_admin_email:
        logger.info("Workspace admin email not configured. Group/OU validation will be disabled.")
        return False

    service_account_json = None
    service_account_file = settings.workspace_service_account_file

    # Try to get from Secret Manager if enabled
    if not service_account_file and settings.secret_manager_enabled:
        try:
            from app.core.secret_manager import secret_manager_client
            service_account_json = secret_manager_client.get_secret("workspace-service-account")
            if service_account_json:
                logger.info("Retrieved service account from Secret Manager")
        except Exception as e:
            logger.warning(f"Failed to retrieve service account from Secret Manager: {str(e)}")

    if service_account_file:
        logger.info(f"Using service account file: {service_account_file}")
    elif service_account_json:
        logger.info("Using service account from Secret Manager")
    else:
        logger.info("No service account file or Secret Manager configured, will use Application Default Credentials")

    return workspace_admin_client.initialize(
        service_account_file,
        settings.workspace_admin_email,
        service_account_json
    )
