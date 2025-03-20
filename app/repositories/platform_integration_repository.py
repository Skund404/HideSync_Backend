# File: app/repositories/platform_integration_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime, timedelta

from app.db.models.platform_integration import PlatformIntegration, SyncEvent
from app.repositories.base_repository import BaseRepository


class PlatformIntegrationRepository(BaseRepository[PlatformIntegration]):
    """
    Repository for PlatformIntegration entity operations.

    Handles operations related to e-commerce platform integrations,
    including API credentials, settings, and connection status.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the PlatformIntegrationRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = PlatformIntegration

        # Define sensitive fields that need encryption
        if not hasattr(self.model, "SENSITIVE_FIELDS"):
            self.model.SENSITIVE_FIELDS = [
                "api_key",
                "api_secret",
                "access_token",
                "refresh_token",
            ]

    def get_integration_by_platform(
        self, platform: str
    ) -> Optional[PlatformIntegration]:
        """
        Get a platform integration by platform name.

        Args:
            platform (str): The platform name to find

        Returns:
            Optional[PlatformIntegration]: The platform integration if found, None otherwise
        """
        entity = (
            self.session.query(self.model)
            .filter(self.model.platform == platform)
            .first()
        )
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_integration_by_shop(self, shop_name: str) -> Optional[PlatformIntegration]:
        """
        Get a platform integration by shop name.

        Args:
            shop_name (str): The shop name to find

        Returns:
            Optional[PlatformIntegration]: The platform integration if found, None otherwise
        """
        entity = (
            self.session.query(self.model)
            .filter(self.model.shop_name == shop_name)
            .first()
        )
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_active_integrations(
        self, skip: int = 0, limit: int = 100
    ) -> List[PlatformIntegration]:
        """
        Get active platform integrations.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[PlatformIntegration]: List of active platform integrations
        """
        query = self.session.query(self.model).filter(self.model.active == True)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_integration_tokens(
        self,
        integration_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ) -> Optional[PlatformIntegration]:
        """
        Update a platform integration's authentication tokens.

        Args:
            integration_id (str): ID of the platform integration
            access_token (str): New access token
            refresh_token (Optional[str], optional): New refresh token
            token_expires_at (Optional[datetime], optional): Expiration timestamp for the token

        Returns:
            Optional[PlatformIntegration]: Updated platform integration if found, None otherwise
        """
        integration = self.get_by_id(integration_id)
        if not integration:
            return None

        integration.access_token = access_token

        if refresh_token:
            integration.refresh_token = refresh_token

        if token_expires_at:
            integration.token_expires_at = token_expires_at

        self.session.commit()
        self.session.refresh(integration)
        return self._decrypt_sensitive_fields(integration)

    def update_sync_timestamp(
        self, integration_id: str
    ) -> Optional[PlatformIntegration]:
        """
        Update a platform integration's last sync timestamp.

        Args:
            integration_id (str): ID of the platform integration

        Returns:
            Optional[PlatformIntegration]: Updated platform integration if found, None otherwise
        """
        integration = self.get_by_id(integration_id)
        if not integration:
            return None

        integration.lastSyncAt = datetime.now()

        self.session.commit()
        self.session.refresh(integration)
        return self._decrypt_sensitive_fields(integration)

    def toggle_active_status(
        self, integration_id: str
    ) -> Optional[PlatformIntegration]:
        """
        Toggle a platform integration's active status.

        Args:
            integration_id (str): ID of the platform integration

        Returns:
            Optional[PlatformIntegration]: Updated platform integration if found, None otherwise
        """
        integration = self.get_by_id(integration_id)
        if not integration:
            return None

        integration.active = not integration.active

        self.session.commit()
        self.session.refresh(integration)
        return self._decrypt_sensitive_fields(integration)

    def update_settings(
        self, integration_id: str, settings: Dict[str, Any]
    ) -> Optional[PlatformIntegration]:
        """
        Update a platform integration's settings.

        Args:
            integration_id (str): ID of the platform integration
            settings (Dict[str, Any]): New settings dictionary

        Returns:
            Optional[PlatformIntegration]: Updated platform integration if found, None otherwise
        """
        integration = self.get_by_id(integration_id)
        if not integration:
            return None

        integration.settings = settings

        self.session.commit()
        self.session.refresh(integration)
        return self._decrypt_sensitive_fields(integration)


class SyncEventRepository(BaseRepository[SyncEvent]):
    """
    Repository for SyncEvent entity operations.

    Handles operations related to platform synchronization events,
    including tracking successes, errors, and sync history.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the SyncEventRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = SyncEvent

    def get_events_by_integration(
        self, platform_integration_id: str, skip: int = 0, limit: int = 100
    ) -> List[SyncEvent]:
        """
        Get sync events for a specific platform integration.

        Args:
            platform_integration_id (str): ID of the platform integration
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[SyncEvent]: List of sync events for the integration
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.platform_integration_id == platform_integration_id)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_events_by_type(
        self, event_type: str, skip: int = 0, limit: int = 100
    ) -> List[SyncEvent]:
        """
        Get sync events by event type.

        Args:
            event_type (str): The event type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[SyncEvent]: List of sync events of the specified type
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.event_type == event_type)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_events_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[SyncEvent]:
        """
        Get sync events by status.

        Args:
            status (str): The status to filter by ('success' or 'error')
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[SyncEvent]: List of sync events with the specified status
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.status == status)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_events(
        self, days: int = 7, skip: int = 0, limit: int = 100
    ) -> List[SyncEvent]:
        """
        Get recent sync events.

        Args:
            days (int): Number of days to look back
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[SyncEvent]: List of recent sync events
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = (
            self.session.query(self.model)
            .filter(self.model.created_at >= cutoff_date)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create_sync_event(
        self,
        platform_integration_id: str,
        event_type: str,
        status: str,
        items_processed: int = 0,
        message: Optional[str] = None,
    ) -> SyncEvent:
        """
        Create a new sync event record.

        Args:
            platform_integration_id (str): ID of the platform integration
            event_type (str): Type of sync event
            status (str): Status of the sync ('success' or 'error')
            items_processed (int, optional): Number of items processed in the sync
            message (Optional[str], optional): Additional message or error details

        Returns:
            SyncEvent: The created sync event
        """
        event_data = {
            "platform_integration_id": platform_integration_id,
            "event_type": event_type,
            "status": status,
            "items_processed": items_processed,
            "message": message,
            "created_at": datetime.now(),
        }

        return self.create(event_data)

    def get_sync_statistics(self, platform_integration_id: str) -> Dict[str, Any]:
        """
        Get sync statistics for a platform integration.

        Args:
            platform_integration_id (str): ID of the platform integration

        Returns:
            Dict[str, Any]: Dictionary with sync statistics
        """
        from sqlalchemy import func

        # Total events count
        total_count = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.platform_integration_id == platform_integration_id)
            .scalar()
        )

        # Success count
        success_count = (
            self.session.query(func.count(self.model.id))
            .filter(
                and_(
                    self.model.platform_integration_id == platform_integration_id,
                    self.model.status == "success",
                )
            )
            .scalar()
        )

        # Error count
        error_count = (
            self.session.query(func.count(self.model.id))
            .filter(
                and_(
                    self.model.platform_integration_id == platform_integration_id,
                    self.model.status == "error",
                )
            )
            .scalar()
        )

        # Total items processed
        total_items = (
            self.session.query(func.sum(self.model.items_processed))
            .filter(self.model.platform_integration_id == platform_integration_id)
            .scalar()
            or 0
        )

        # Last sync event
        last_sync = (
            self.session.query(self.model)
            .filter(self.model.platform_integration_id == platform_integration_id)
            .order_by(desc(self.model.created_at))
            .first()
        )

        return {
            "total_events": total_count,
            "success_events": success_count,
            "error_events": error_count,
            "success_rate": (
                (success_count / total_count * 100) if total_count > 0 else 0
            ),
            "total_items_processed": total_items,
            "last_sync": {
                "event_type": last_sync.event_type if last_sync else None,
                "status": last_sync.status if last_sync else None,
                "created_at": last_sync.created_at if last_sync else None,
                "items_processed": last_sync.items_processed if last_sync else 0,
                "message": last_sync.message if last_sync else None,
            },
        }
