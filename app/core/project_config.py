"""Project configuration management"""

from typing import Dict, Any, Optional
from app.config import settings, LOCAL_PROJECT_CONFIGS
from app.core.errors import ProjectNotFoundError
import logging

logger = logging.getLogger(__name__)


class ProjectConfigManager:
    """Manage project configurations from Firestore or local settings"""

    def __init__(self):
        self.use_local_config = settings.use_local_config or settings.is_development
        self._firestore_client = None

    @property
    def firestore_client(self):
        """Lazy load Firestore client"""
        if not self._firestore_client and not self.use_local_config:
            from app.core.firestore_client import get_firestore_client
            self._firestore_client = get_firestore_client()
        return self._firestore_client

    async def get_project_config(self, project_id: str) -> Dict[str, Any]:
        """
        Get project configuration

        Args:
            project_id: Project identifier

        Returns:
            Project configuration dictionary

        Raises:
            ProjectNotFoundError: If project not found
        """
        if self.use_local_config:
            # Use local configuration for development
            config = LOCAL_PROJECT_CONFIGS.get(project_id)
            if not config:
                logger.warning(f"Project {project_id} not found in local config")
                raise ProjectNotFoundError(project_id)

            logger.info(f"Using local config for project: {project_id}")
            return config

        # Fetch from Firestore in production
        try:
            doc_ref = self.firestore_client.collection('projects').document(project_id)
            doc = doc_ref.get()

            if not doc.exists:
                logger.warning(f"Project {project_id} not found in Firestore")
                raise ProjectNotFoundError(project_id)

            config = doc.to_dict()
            logger.info(f"Fetched config from Firestore for project: {project_id}")
            return config

        except Exception as e:
            logger.error(f"Error fetching project config from Firestore: {str(e)}")
            # Fall back to local config if available
            if project_id in LOCAL_PROJECT_CONFIGS:
                logger.info(f"Falling back to local config for project: {project_id}")
                return LOCAL_PROJECT_CONFIGS[project_id]
            raise ProjectNotFoundError(project_id)

    async def list_projects(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available projects

        Returns:
            Dictionary of project_id -> project_config
        """
        if self.use_local_config:
            return LOCAL_PROJECT_CONFIGS

        try:
            projects = {}
            docs = self.firestore_client.collection('projects').stream()
            for doc in docs:
                projects[doc.id] = doc.to_dict()
            return projects
        except Exception as e:
            logger.error(f"Error listing projects from Firestore: {str(e)}")
            return LOCAL_PROJECT_CONFIGS

    async def create_project(
        self,
        project_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new project configuration

        Args:
            project_id: Project identifier
            config: Project configuration

        Returns:
            Created project configuration
        """
        if self.use_local_config:
            LOCAL_PROJECT_CONFIGS[project_id] = config
            logger.info(f"Created local project config: {project_id}")
            return config

        try:
            doc_ref = self.firestore_client.collection('projects').document(project_id)
            doc_ref.set(config)
            logger.info(f"Created project in Firestore: {project_id}")
            return config
        except Exception as e:
            logger.error(f"Error creating project in Firestore: {str(e)}")
            raise

    async def update_project(
        self,
        project_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update project configuration

        Args:
            project_id: Project identifier
            updates: Fields to update

        Returns:
            Updated project configuration
        """
        # Get existing config
        config = await self.get_project_config(project_id)
        config.update(updates)

        if self.use_local_config:
            LOCAL_PROJECT_CONFIGS[project_id] = config
            logger.info(f"Updated local project config: {project_id}")
            return config

        try:
            doc_ref = self.firestore_client.collection('projects').document(project_id)
            doc_ref.update(updates)
            logger.info(f"Updated project in Firestore: {project_id}")
            return config
        except Exception as e:
            logger.error(f"Error updating project in Firestore: {str(e)}")
            raise

    async def delete_project(self, project_id: str) -> bool:
        """
        Delete project configuration

        Args:
            project_id: Project identifier

        Returns:
            True if deleted successfully
        """
        if self.use_local_config:
            if project_id in LOCAL_PROJECT_CONFIGS:
                del LOCAL_PROJECT_CONFIGS[project_id]
                logger.info(f"Deleted local project config: {project_id}")
                return True
            return False

        try:
            doc_ref = self.firestore_client.collection('projects').document(project_id)
            doc_ref.delete()
            logger.info(f"Deleted project from Firestore: {project_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting project from Firestore: {str(e)}")
            raise

    def validate_project_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate project configuration

        Args:
            config: Project configuration to validate

        Returns:
            True if valid
        """
        required_fields = [
            'name',
            'type',
            'allowed_domains',
            'redirect_uris',
            'token_delivery'
        ]

        for field in required_fields:
            if field not in config:
                logger.warning(f"Missing required field in project config: {field}")
                return False

        # Validate type
        valid_types = ['streamlit_local', 'streamlit_cloud', 'web_app', 'api_service']
        if config['type'] not in valid_types:
            logger.warning(f"Invalid project type: {config['type']}")
            return False

        # Validate token_delivery
        valid_deliveries = ['query_param', 'cookie']
        if config['token_delivery'] not in valid_deliveries:
            logger.warning(f"Invalid token delivery method: {config['token_delivery']}")
            return False

        return True


# Create singleton instance
project_config_manager = ProjectConfigManager()