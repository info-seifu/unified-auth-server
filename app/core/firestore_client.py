"""Firestore client setup and management"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

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

    async def get_audit_logs(
        self,
        project_id: Optional[str] = None,
        user_email: Optional[str] = None,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs with filtering options

        Args:
            project_id: Filter by project ID
            user_email: Filter by user email
            event_type: Filter by event type
            start_date: Filter logs after this date
            end_date: Filter logs before this date
            limit: Maximum number of logs to return

        Returns:
            List of audit log entries
        """
        if not self.client:
            return []

        try:
            query = self.client.collection('audit_logs')

            # Apply filters
            if project_id:
                query = query.where('project_id', '==', project_id)
            if user_email:
                query = query.where('user_email', '==', user_email)
            if event_type:
                query = query.where('event_type', '==', event_type)
            if start_date:
                query = query.where('timestamp', '>=', start_date)
            if end_date:
                query = query.where('timestamp', '<=', end_date)

            # Order by timestamp descending and limit
            query = query.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)

            logs = []
            for doc in query.stream():
                log_entry = doc.to_dict()
                log_entry['id'] = doc.id
                logs.append(log_entry)

            return logs

        except Exception as e:
            logger.error(f"Failed to get audit logs: {str(e)}")
            return []

    async def get_login_history(
        self,
        user_email: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get login history for a specific user

        Args:
            user_email: User's email
            days: Number of days to look back (default: 30)

        Returns:
            List of login events
        """
        if not self.client:
            return []

        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = self.client.collection('audit_logs') \
                .where('user_email', '==', user_email) \
                .where('event_type', 'in', ['login_success', 'login_failed']) \
                .where('timestamp', '>=', start_date) \
                .order_by('timestamp', direction=firestore.Query.DESCENDING) \
                .limit(100)

            history = []
            for doc in query.stream():
                entry = doc.to_dict()
                entry['id'] = doc.id
                history.append(entry)

            return history

        except Exception as e:
            logger.error(f"Failed to get login history: {str(e)}")
            return []

    async def get_audit_statistics(
        self,
        project_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get audit statistics for monitoring

        Args:
            project_id: Project ID (optional, for project-specific stats)
            days: Number of days to analyze (default: 7)

        Returns:
            Dictionary containing statistics
        """
        if not self.client:
            return {
                'total_logins': 0,
                'failed_logins': 0,
                'unique_users': 0,
                'api_calls': 0
            }

        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            base_query = self.client.collection('audit_logs').where('timestamp', '>=', start_date)

            if project_id:
                base_query = base_query.where('project_id', '==', project_id)

            # Count different event types
            stats = {
                'total_logins': 0,
                'failed_logins': 0,
                'unique_users': set(),
                'api_calls': 0,
                'by_event_type': {}
            }

            for doc in base_query.stream():
                data = doc.to_dict()
                event_type = data.get('event_type', '')

                # Count by event type
                stats['by_event_type'][event_type] = stats['by_event_type'].get(event_type, 0) + 1

                # Specific counters
                if event_type == 'login_success':
                    stats['total_logins'] += 1
                elif event_type == 'login_failed':
                    stats['failed_logins'] += 1
                elif event_type == 'api_proxy_call':
                    stats['api_calls'] += 1

                # Track unique users
                if 'user_email' in data:
                    stats['unique_users'].add(data['user_email'])

            # Convert set to count
            stats['unique_users'] = len(stats['unique_users'])

            return stats

        except Exception as e:
            logger.error(f"Failed to get audit statistics: {str(e)}")
            return {
                'total_logins': 0,
                'failed_logins': 0,
                'unique_users': 0,
                'api_calls': 0
            }

    async def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """
        Delete audit logs older than retention period

        Args:
            retention_days: Number of days to retain logs (default: 90)

        Returns:
            Number of deleted documents
        """
        if not self.client:
            return 0

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            old_logs = self.client.collection('audit_logs').where('timestamp', '<', cutoff_date)

            deleted_count = 0
            batch = self.client.batch()
            batch_size = 0

            for doc in old_logs.stream():
                batch.delete(doc.reference)
                batch_size += 1
                deleted_count += 1

                # Commit batch every 500 documents
                if batch_size >= 500:
                    batch.commit()
                    batch = self.client.batch()
                    batch_size = 0

            # Commit remaining documents
            if batch_size > 0:
                batch.commit()

            logger.info(f"Cleaned up {deleted_count} old audit logs")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {str(e)}")
            return 0


# Create singleton instance
firestore_manager = FirestoreManager()