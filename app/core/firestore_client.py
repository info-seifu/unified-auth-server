"""Firestore client setup and management"""

import os
import logging
from typing import Optional, Dict, Any

from google.cloud import firestore
from google.cloud.firestore import Client
from app.config import settings

logger = logging.getLogger(__name__)


def get_firestore_client() -> Optional[Client]:
    """
    Get Firestore client instance

    Returns:
        Firestore client or None if not available
    """
    try:
        if settings.use_firebase_emulator:
            # Use Firebase emulator for local development
            os.environ['FIRESTORE_EMULATOR_HOST'] = settings.firebase_emulator_host
            logger.info(f"Using Firebase emulator at {settings.firebase_emulator_host}")
            return firestore.Client(project=settings.gcp_project_id or 'demo-project')

        if settings.gcp_project_id:
            # Use real Firestore with project ID
            return firestore.Client(project=settings.gcp_project_id)

        # Try to use default credentials
        return firestore.Client()

    except Exception as e:
        logger.warning(f"Could not initialize Firestore client: {str(e)}")
        logger.info("Falling back to local configuration")
        return None


class FirestoreManager:
    """Manager for Firestore operations"""

    def __init__(self):
        self.client = get_firestore_client()

    def is_available(self) -> bool:
        """Check if Firestore is available"""
        return self.client is not None

    async def log_audit_event(
        self,
        event_type: str,
        project_id: str,
        user_email: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log an audit event to Firestore

        Args:
            event_type: Type of event (login_success, login_failed, etc.)
            project_id: Project ID
            user_email: User's email
            details: Additional event details
            ip_address: Client IP address
            user_agent: Client user agent
        """
        if not self.client:
            logger.debug("Firestore not available, skipping audit log")
            return

        try:
            audit_data = {
                'timestamp': firestore.SERVER_TIMESTAMP,
                'event_type': event_type,
                'project_id': project_id,
                'user_email': user_email,
                'details': details
            }

            if ip_address:
                audit_data['ip_address'] = ip_address
            if user_agent:
                audit_data['user_agent'] = user_agent

            self.client.collection('audit_logs').add(audit_data)
            logger.debug(f"Logged audit event: {event_type} for {user_email}")

        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}")

    async def get_user_settings(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user-specific settings from Firestore

        Args:
            email: User's email

        Returns:
            User settings dictionary or None
        """
        if not self.client:
            return None

        try:
            doc_ref = self.client.collection('user_settings').document(email)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to get user settings: {str(e)}")
            return None

    async def save_user_settings(self, email: str, user_settings: Dict[str, Any]) -> None:
        """
        Save user-specific settings to Firestore

        Args:
            email: User's email
            user_settings: Settings to save
        """
        if not self.client:
            return

        try:
            doc_ref = self.client.collection('user_settings').document(email)
            doc_ref.set(user_settings, merge=True)
            logger.debug(f"Saved user settings for {email}")
        except Exception as e:
            logger.error(f"Failed to save user settings: {str(e)}")


# Create singleton instance
firestore_manager = FirestoreManager()