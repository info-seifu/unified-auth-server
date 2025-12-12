"""Google Workspace Admin SDK client for groups and organizational units"""

from typing import List, Optional
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class WorkspaceAdminClient:
    """
    Google Workspace Admin SDK client

    Note: This client works in Cloud Run environment using OAuth tokens
    obtained from user authentication flow.
    """

    def __init__(self):
        """Initialize Workspace Admin client"""
        self.service = None

    def _build_service(self, access_token: str):
        """
        Build Admin SDK service with OAuth access token

        Args:
            access_token: OAuth2 access token from user authentication

        Returns:
            Admin SDK service instance
        """
        credentials = Credentials(token=access_token)
        return build('admin', 'directory_v1', credentials=credentials, cache_discovery=False)

    async def get_user_groups(self, access_token: str, user_email: str) -> List[str]:
        """
        Get list of groups that a user belongs to (including nested groups)

        This method retrieves all groups that a user is a member of, including
        groups that are nested within other groups (transitive membership).

        Args:
            access_token: OAuth2 access token
            user_email: User's email address

        Returns:
            List of group email addresses (e.g., ['group1@domain.com', 'group2@domain.com'])
            Includes both direct membership and nested group membership

        Raises:
            HttpError: If API call fails
        """
        try:
            service = self._build_service(access_token)

            # Get direct groups for user
            direct_groups = set()
            page_token = None

            while True:
                try:
                    result = service.groups().list(
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
                        logger.warning(
                            f"Insufficient permissions to list groups for {user_email}. "
                            "User may not have admin privileges."
                        )
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
                    parent_result = service.groups().list(
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
            raise

    async def get_user_org_unit(self, access_token: str, user_email: str) -> Optional[str]:
        """
        Get the organizational unit path of a user

        Args:
            access_token: OAuth2 access token
            user_email: User's email address

        Returns:
            Organizational unit path (e.g., '/教職員/専任教員') or None if not found

        Raises:
            HttpError: If API call fails
        """
        try:
            service = self._build_service(access_token)

            try:
                # Get user information
                user = service.users().get(userKey=user_email).execute()
                org_unit_path = user.get('orgUnitPath', '/')

                logger.info(f"User {user_email} belongs to org unit: {org_unit_path}")
                return org_unit_path

            except HttpError as e:
                if e.resp.status == 403:
                    logger.warning(
                        f"Insufficient permissions to get org unit for {user_email}. "
                        "User may not have admin privileges."
                    )
                    return None
                raise

        except Exception as e:
            logger.error(f"Failed to get org unit for {user_email}: {str(e)}")
            raise

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
