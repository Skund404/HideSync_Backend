# File: services/platform_integration_service.py

"""
Platform integration service for the HideSync system.

This module provides functionality for integrating with external e-commerce and marketplace
platforms such as Etsy, Shopify, WooCommerce, etc. It handles platform authentication,
data synchronization, webhook management, and integration status tracking.

The service enables bidirectional data flow between HideSync and external platforms,
allowing for automatic import of orders, customers, and product data as well as
export of inventory levels, order status updates, and other critical information.

Key features:
- Platform connection management with secure credential storage
- Scheduled and on-demand data synchronization
- Detailed synchronization event logging and error tracking
- Support for various entity types (orders, products, customers, inventory)
- Extensible adapter-based architecture for new platform support

Credentials are stored securely using encryption provided by the key service, and
all operations are tracked for audit and troubleshooting purposes.
"""

from typing import List, Optional, Dict, Any, Union, Tuple, Type
from datetime import datetime, timedelta
import logging
import json
import uuid
from enum import Enum, auto
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    ConcurrentOperationException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.platform_integration import PlatformIntegration, SyncEvent
from app.repositories.platform_integration_repository import (
    PlatformIntegrationRepository,
    SyncEventRepository,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Direction of synchronization between HideSync and external platforms."""

    IMPORT = auto()  # From external platform to HideSync
    EXPORT = auto()  # From HideSync to external platform
    BIDIRECTIONAL = auto()  # Both ways


class SyncEntityType(Enum):
    """Types of entities that can be synchronized with external platforms."""

    PRODUCT = auto()
    ORDER = auto()
    CUSTOMER = auto()
    INVENTORY = auto()
    ALL = auto()


class PlatformConnected(DomainEvent):
    """Event emitted when a platform integration is created or reconnected."""

    def __init__(
        self,
        integration_id: str,
        platform: str,
        shop_name: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize platform connected event.

        Args:
            integration_id: ID of the platform integration
            platform: Platform type (etsy, shopify, etc.)
            shop_name: Name of the shop
            user_id: Optional ID of the user who created the connection
        """
        super().__init__()
        self.integration_id = integration_id
        self.platform = platform
        self.shop_name = shop_name
        self.user_id = user_id


class PlatformDisconnected(DomainEvent):
    """Event emitted when a platform integration is disconnected."""

    def __init__(
        self,
        integration_id: str,
        platform: str,
        shop_name: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize platform disconnected event.

        Args:
            integration_id: ID of the platform integration
            platform: Platform type (etsy, shopify, etc.)
            shop_name: Name of the shop
            user_id: Optional ID of the user who disconnected the platform
        """
        super().__init__()
        self.integration_id = integration_id
        self.platform = platform
        self.shop_name = shop_name
        self.user_id = user_id


class PlatformSyncStarted(DomainEvent):
    """Event emitted when a platform synchronization process starts."""

    def __init__(
        self,
        integration_id: str,
        direction: SyncDirection,
        entity_types: List[SyncEntityType],
        user_id: Optional[int] = None,
    ):
        """
        Initialize platform sync started event.

        Args:
            integration_id: ID of the platform integration
            direction: Direction of synchronization
            entity_types: Types of entities being synchronized
            user_id: Optional ID of the user who initiated the sync
        """
        super().__init__()
        self.integration_id = integration_id
        self.direction = direction
        self.entity_types = entity_types
        self.user_id = user_id


class PlatformSyncCompleted(DomainEvent):
    """Event emitted when a platform synchronization process completes successfully."""

    def __init__(
        self,
        integration_id: str,
        direction: SyncDirection,
        entity_types: List[SyncEntityType],
        stats: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        """
        Initialize platform sync completed event.

        Args:
            integration_id: ID of the platform integration
            direction: Direction of synchronization
            entity_types: Types of entities that were synchronized
            stats: Statistics about the synchronization process
            user_id: Optional ID of the user who initiated the sync
        """
        super().__init__()
        self.integration_id = integration_id
        self.direction = direction
        self.entity_types = entity_types
        self.stats = stats
        self.user_id = user_id


class PlatformSyncFailed(DomainEvent):
    """Event emitted when a platform synchronization process fails."""

    def __init__(
        self,
        integration_id: str,
        direction: SyncDirection,
        entity_types: List[SyncEntityType],
        error: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize platform sync failed event.

        Args:
            integration_id: ID of the platform integration
            direction: Direction of synchronization
            entity_types: Types of entities that were being synchronized
            error: Error message describing the failure
            user_id: Optional ID of the user who initiated the sync
        """
        super().__init__()
        self.integration_id = integration_id
        self.direction = direction
        self.entity_types = entity_types
        self.error = error
        self.user_id = user_id


# Validation functions
validate_integration = validate_entity(PlatformIntegration)
validate_sync_event = validate_entity(SyncEvent)


class PlatformIntegrationService(BaseService[PlatformIntegration]):
    """
    Service for managing platform integrations in the HideSync system.

    Provides functionality for:
    - Managing connections to external e-commerce platforms
    - Synchronizing data between HideSync and external platforms
    - Tracking synchronization events and history
    - Configuring platform-specific settings
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        sync_event_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        key_service=None,
        sale_service=None,
        customer_service=None,
        product_service=None,
        inventory_service=None,
        platform_adapters=None,
    ):
        """
        Initialize PlatformIntegrationService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for platform integrations
            sync_event_repository: Optional repository for sync events
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            key_service: Optional key service for encryption/decryption
            sale_service: Optional sale service for order operations
            customer_service: Optional customer service for customer operations
            product_service: Optional product service for product operations
            inventory_service: Optional inventory service for inventory operations
            platform_adapters: Optional dictionary of platform adapters
        """
        self.session = session
        self.repository = repository or PlatformIntegrationRepository(
            session, key_service
        )
        self.sync_event_repository = sync_event_repository or SyncEventRepository(
            session
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.key_service = key_service
        self.sale_service = sale_service
        self.customer_service = customer_service
        self.product_service = product_service
        self.inventory_service = inventory_service

        # Initialize platform adapters (actual implementations would be injected)
        self.platform_adapters = platform_adapters or {}

    @validate_input(validate_integration)
    def create_integration(self, data: Dict[str, Any]) -> PlatformIntegration:
        """
        Create a new platform integration.

        Args:
            data: Integration data including platform, shop name, and credentials
                Required fields:
                - platform: Platform type (etsy, shopify, etc.)
                - shop_name: Name of the shop
                - credentials: Dictionary containing required credentials

        Returns:
            Created platform integration entity

        Raises:
            ValidationException: If validation fails
            IntegrationException: If platform is not supported or connection fails
        """
        with self.transaction():
            # Validate platform type
            platform = data.get("platform")
            if platform not in self.get_supported_platforms():
                from app.core.exceptions import IntegrationException

                raise IntegrationException(
                    f"Unsupported platform: {platform}",
                    "INTEGRATION_001",
                    {"supported_platforms": self.get_supported_platforms()},
                )

            # Generate unique ID if not provided
            if "id" not in data:
                data["id"] = str(uuid.uuid4())

            # Set active by default if not specified
            if "active" not in data:
                data["active"] = True

            # Extract credentials
            credentials = data.pop("credentials", {})

            # Flatten credential fields into integration data
            # The repository will handle encryption of sensitive fields
            for key, value in credentials.items():
                data[key] = value

            # Convert settings to JSON string if it's a dictionary
            if "settings" in data and isinstance(data["settings"], dict):
                data["settings"] = json.dumps(data["settings"])

            # Create integration
            integration = self.repository.create(data)

            # Verify connection
            try:
                self._verify_connection(integration)
            except Exception as e:
                # Rollback creation on connection failure
                self.repository.delete(integration.id)
                from app.core.exceptions import IntegrationException

                raise IntegrationException(
                    f"Failed to verify platform connection: {str(e)}",
                    "INTEGRATION_002",
                    {"platform": platform, "shop_name": data.get("shop_name")},
                ) from e

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PlatformConnected(
                        integration_id=integration.id,
                        platform=integration.platform,
                        shop_name=integration.shop_name,
                        user_id=user_id,
                    )
                )

            return integration

    def update_integration(
        self, integration_id: str, data: Dict[str, Any]
    ) -> PlatformIntegration:
        """
        Update an existing platform integration.

        Args:
            integration_id: ID of the integration to update
            data: Updated integration data

        Returns:
            Updated platform integration entity

        Raises:
            EntityNotFoundException: If integration not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if integration exists
            integration = self.get_by_id(integration_id)
            if not integration:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PlatformIntegration", integration_id)

            # Extract credentials
            credentials = data.pop("credentials", {})

            # Flatten credential fields into integration data
            # The repository will handle encryption of sensitive fields
            for key, value in credentials.items():
                data[key] = value

            # Convert settings to JSON string if it's a dictionary
            if "settings" in data and isinstance(data["settings"], dict):
                data["settings"] = json.dumps(data["settings"])

            # Update integration
            updated_integration = self.repository.update(integration_id, data)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"PlatformIntegration:{integration_id}")

            # If the integration was reactivated, publish connection event
            if (
                "active" in data
                and data["active"]
                and not integration.active
                and self.event_bus
            ):
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PlatformConnected(
                        integration_id=integration.id,
                        platform=integration.platform,
                        shop_name=integration.shop_name,
                        user_id=user_id,
                    )
                )

            # If the integration was deactivated, publish disconnection event
            if (
                "active" in data
                and not data["active"]
                and integration.active
                and self.event_bus
            ):
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PlatformDisconnected(
                        integration_id=integration.id,
                        platform=integration.platform,
                        shop_name=integration.shop_name,
                        user_id=user_id,
                    )
                )

            return updated_integration

    def delete_integration(self, integration_id: str) -> bool:
        """
        Delete a platform integration.

        Args:
            integration_id: ID of the integration to delete

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If integration not found
        """
        with self.transaction():
            # Check if integration exists
            integration = self.get_by_id(integration_id)
            if not integration:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PlatformIntegration", integration_id)

            # Store platform info for event
            platform = integration.platform
            shop_name = integration.shop_name

            # Delete integration
            result = self.repository.delete(integration_id)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"PlatformIntegration:{integration_id}")

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PlatformDisconnected(
                        integration_id=integration_id,
                        platform=platform,
                        shop_name=shop_name,
                        user_id=user_id,
                    )
                )

            return result

    def get_integration_with_details(self, integration_id: str) -> Dict[str, Any]:
        """
        Get a platform integration with additional details.

        Args:
            integration_id: ID of the integration

        Returns:
            Integration with details including recent sync events

        Raises:
            EntityNotFoundException: If integration not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"PlatformIntegration:detail:{integration_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get integration
        integration = self.get_by_id(integration_id)
        if not integration:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PlatformIntegration", integration_id)

        # Convert to dict and parse settings
        result = integration.to_dict()

        if "settings" in result and result["settings"]:
            try:
                result["settings"] = json.loads(result["settings"])
            except json.JSONDecodeError:
                # Keep as string if not valid JSON
                pass

        # Get recent sync events
        recent_events = self.sync_event_repository.list(
            platform_integration_id=integration_id,
            limit=5,
            order_by="created_at",
            order_dir="desc",
        )

        result["recent_events"] = [
            {
                "id": event.id,
                "event_type": event.event_type,
                "status": event.status,
                "created_at": (
                    event.created_at.isoformat() if event.created_at else None
                ),
                "items_processed": event.items_processed,
                "message": event.message,
            }
            for event in recent_events
        ]

        # Get sync statistics
        result["sync_stats"] = self._calculate_sync_statistics(integration_id)

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def get_supported_platforms(self) -> List[str]:
        """
        Get a list of supported platform types.

        Returns:
            List of supported platform identifiers
        """
        # This would return keys from the platform adapters dictionary
        # For now, return a hardcoded list
        return ["etsy", "shopify", "woocommerce", "amazon", "ebay"]

    def sync_platform(
        self,
        integration_id: str,
        direction: Union[SyncDirection, str] = SyncDirection.IMPORT,
        entity_types: Optional[List[Union[SyncEntityType, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronize data with a platform.

        Args:
            integration_id: Platform integration ID
            direction: Sync direction (IMPORT, EXPORT, or BIDIRECTIONAL)
            entity_types: Entity types to sync (defaults to ALL)

        Returns:
            Sync results with statistics

        Raises:
            EntityNotFoundException: If integration not found
            IntegrationException: If sync fails or integration is inactive
        """
        # Convert string direction to enum if needed
        if isinstance(direction, str):
            try:
                direction = SyncDirection[direction.upper()]
            except KeyError:
                raise ValidationException(
                    f"Invalid sync direction: {direction}",
                    {
                        "direction": [
                            f"Must be one of: {', '.join([d.name for d in SyncDirection])}"
                        ]
                    },
                )

        # Default to ALL entity type if not specified
        if not entity_types:
            entity_types = [SyncEntityType.ALL]

        # Convert string entity types to enum if needed
        parsed_entity_types = []
        for entity_type in entity_types:
            if isinstance(entity_type, str):
                try:
                    parsed_entity_type = SyncEntityType[entity_type.upper()]
                    parsed_entity_types.append(parsed_entity_type)
                except KeyError:
                    raise ValidationException(
                        f"Invalid entity type: {entity_type}",
                        {
                            "entity_type": [
                                f"Must be one of: {', '.join([t.name for t in SyncEntityType])}"
                            ]
                        },
                    )
            else:
                parsed_entity_types.append(entity_type)

        entity_types = parsed_entity_types

        # Get integration
        integration = self.get_by_id(integration_id)
        if not integration:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PlatformIntegration", integration_id)

        # Check if integration is active
        if not integration.active:
            from app.core.exceptions import IntegrationException

            raise IntegrationException(
                f"Platform integration is inactive: {integration_id}",
                "INTEGRATION_004",
                {"platform": integration.platform, "shop_name": integration.shop_name},
            )

        # Get platform adapter
        adapter = self._get_platform_adapter(integration)

        # Start sync event
        sync_event = self._create_sync_event(
            integration_id=integration_id,
            event_type=f"{direction.name.lower()}_started",
            status="in_progress",
            message=f"Starting {direction.name.lower()} sync for {', '.join([e.name.lower() for e in entity_types])}",
        )

        # Publish event if available
        if self.event_bus:
            user_id = (
                self.security_context.current_user.id if self.security_context else None
            )
            self.event_bus.publish(
                PlatformSyncStarted(
                    integration_id=integration_id,
                    direction=direction,
                    entity_types=entity_types,
                    user_id=user_id,
                )
            )

        try:
            # Perform sync based on direction
            if direction == SyncDirection.IMPORT:
                result = self._import_from_platform(adapter, integration, entity_types)
            elif direction == SyncDirection.EXPORT:
                result = self._export_to_platform(adapter, integration, entity_types)
            elif direction == SyncDirection.BIDIRECTIONAL:
                import_result = self._import_from_platform(
                    adapter, integration, entity_types
                )
                export_result = self._export_to_platform(
                    adapter, integration, entity_types
                )
                result = {
                    "import": import_result,
                    "export": export_result,
                    "total_processed": import_result["total_processed"]
                    + export_result["total_processed"],
                    "total_errors": import_result["total_errors"]
                    + export_result["total_errors"],
                }

            # Update sync event
            self._update_sync_event(
                sync_event["id"],
                status="success",
                items_processed=result["total_processed"],
                message=f"Completed {direction.name.lower()} sync: {result['total_processed']} items processed, {result['total_errors']} errors",
            )

            # Update integration last sync time
            self.repository.update(integration_id, {"last_sync_at": datetime.now()})

            # Publish completion event
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PlatformSyncCompleted(
                        integration_id=integration_id,
                        direction=direction,
                        entity_types=entity_types,
                        stats=result,
                        user_id=user_id,
                    )
                )

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(
                    f"PlatformIntegration:detail:{integration_id}"
                )

            return result

        except Exception as e:
            logger.exception(f"Platform sync failed: {str(e)}")

            # Update sync event
            self._update_sync_event(
                sync_event["id"], status="error", message=f"Sync failed: {str(e)}"
            )

            # Publish failure event
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PlatformSyncFailed(
                        integration_id=integration_id,
                        direction=direction,
                        entity_types=entity_types,
                        error=str(e),
                        user_id=user_id,
                    )
                )

            from app.core.exceptions import IntegrationException

            raise IntegrationException(
                f"Platform sync failed: {str(e)}",
                "INTEGRATION_005",
                {"platform": integration.platform, "shop_name": integration.shop_name},
            ) from e

    def verify_connection(self, integration_id: str) -> bool:
        """
        Verify connection to platform.

        Args:
            integration_id: ID of the integration

        Returns:
            True if connection is successful

        Raises:
            EntityNotFoundException: If integration not found
            IntegrationException: If connection fails
        """
        # Get integration
        integration = self.get_by_id(integration_id)
        if not integration:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PlatformIntegration", integration_id)

        # Get platform adapter
        adapter = self._get_platform_adapter(integration)

        # Verify connection
        try:
            connection_result = adapter.verify_connection()

            # Update last verified timestamp if connection succeeded
            if connection_result:
                self.repository.update(
                    integration_id, {"last_verified_at": datetime.now()}
                )

            return connection_result

        except Exception as e:
            from app.core.exceptions import IntegrationException

            raise IntegrationException(
                f"Failed to verify platform connection: {str(e)}",
                "INTEGRATION_006",
                {"platform": integration.platform, "shop_name": integration.shop_name},
            ) from e

    def refresh_access_token(self, integration_id: str) -> bool:
        """
        Refresh the access token for an integration if it supports token refresh.

        Args:
            integration_id: ID of the integration

        Returns:
            True if token was refreshed successfully

        Raises:
            EntityNotFoundException: If integration not found
            IntegrationException: If token refresh fails
        """
        # Get integration
        integration = self.get_by_id(integration_id)
        if not integration:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PlatformIntegration", integration_id)

        # Check if token is expired or will expire soon
        token_expires_at = integration.token_expires_at
        if token_expires_at and token_expires_at > datetime.now() + timedelta(hours=1):
            # Token is still valid for more than an hour
            return True

        # Get platform adapter
        adapter = self._get_platform_adapter(integration)

        # Check if adapter supports token refresh
        if not hasattr(adapter, "refresh_access_token"):
            logger.warning(
                f"Platform adapter for {integration.platform} does not support token refresh"
            )
            return False

        try:
            # Refresh token using adapter
            refresh_result = adapter.refresh_access_token()

            if refresh_result and "access_token" in refresh_result:
                # Update integration with new token
                update_data = {
                    "access_token": refresh_result["access_token"],
                    "token_expires_at": refresh_result.get("expires_at"),
                }

                # Update refresh token if provided
                if "refresh_token" in refresh_result:
                    update_data["refresh_token"] = refresh_result["refresh_token"]

                self.repository.update(integration_id, update_data)
                return True

            return False

        except Exception as e:
            from app.core.exceptions import IntegrationException

            raise IntegrationException(
                f"Failed to refresh access token: {str(e)}",
                "INTEGRATION_007",
                {"platform": integration.platform, "shop_name": integration.shop_name},
            ) from e

    def get_sync_history(
        self,
        integration_id: str,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get synchronization history for an integration.

        Args:
            integration_id: ID of the integration
            event_type: Optional event type filter
            status: Optional status filter
            from_date: Optional start date filter
            to_date: Optional end date filter
            limit: Maximum number of events to return

        Returns:
            List of sync events

        Raises:
            EntityNotFoundException: If integration not found
        """
        # Check if integration exists
        if not self.repository.exists(integration_id):
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PlatformIntegration", integration_id)

        # Prepare filters
        filters = {"platform_integration_id": integration_id}

        if event_type:
            filters["event_type"] = event_type

        if status:
            filters["status"] = status

        if from_date:
            filters["created_at_gte"] = from_date

        if to_date:
            filters["created_at_lte"] = to_date

        # Get sync events
        events = self.sync_event_repository.list(
            limit=limit, order_by="created_at", order_dir="desc", **filters
        )

        # Format results
        return [
            {
                "id": event.id,
                "event_type": event.event_type,
                "status": event.status,
                "created_at": (
                    event.created_at.isoformat() if event.created_at else None
                ),
                "items_processed": event.items_processed,
                "message": event.message,
            }
            for event in events
        ]

    def process_webhook(
        self, platform: str, shop_identifier: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a webhook notification from a platform.

        Args:
            platform: Platform identifier (etsy, shopify, etc.)
            shop_identifier: Shop identifier or name
            data: Webhook payload data

        Returns:
            Processing result

        Raises:
            IntegrationException: If webhook processing fails
        """
        # Find matching integration
        integrations = self.repository.list(platform=platform, active=True)

        # Filter by shop identifier
        matching_integrations = [
            i
            for i in integrations
            if i.shop_name == shop_identifier
            or self._match_shop_identifier(i, shop_identifier)
        ]

        if not matching_integrations:
            from app.core.exceptions import IntegrationException

            raise IntegrationException(
                f"No active integration found for {platform} shop {shop_identifier}",
                "INTEGRATION_008",
            )

        integration = matching_integrations[0]

        # Get webhook type from data
        webhook_type = data.get("type", "unknown")

        # Create sync event for webhook
        sync_event = self._create_sync_event(
            integration_id=integration.id,
            event_type=f"webhook_{webhook_type}",
            status="in_progress",
            message=f"Processing {webhook_type} webhook from {platform}",
        )

        try:
            # Get platform adapter
            adapter = self._get_platform_adapter(integration)

            # Process webhook using adapter
            if not hasattr(adapter, "process_webhook"):
                logger.warning(
                    f"Platform adapter for {integration.platform} does not support webhook processing"
                )

                self._update_sync_event(
                    sync_event["id"],
                    status="error",
                    message=f"Webhook processing not supported for {platform}",
                )

                return {
                    "success": False,
                    "message": f"Webhook processing not supported for {platform}",
                }

            # Process webhook
            result = adapter.process_webhook(webhook_type, data)

            # Handle order creation/update if needed
            if webhook_type in ["order_created", "order_updated"] and self.sale_service:
                self._handle_order_webhook(integration, data, webhook_type)

            # Handle product creation/update if needed
            if (
                webhook_type in ["product_created", "product_updated"]
                and self.product_service
            ):
                self._handle_product_webhook(integration, data, webhook_type)

            # Handle inventory update if needed
            if webhook_type == "inventory_updated" and self.inventory_service:
                self._handle_inventory_webhook(integration, data)

            # Update sync event
            self._update_sync_event(
                sync_event["id"],
                status="success",
                items_processed=1,
                message=f"Successfully processed {webhook_type} webhook from {platform}",
            )

            return {
                "success": True,
                "message": f"Successfully processed {webhook_type} webhook",
                "details": result,
            }

        except Exception as e:
            logger.exception(f"Webhook processing failed: {str(e)}")

            # Update sync event
            self._update_sync_event(
                sync_event["id"],
                status="error",
                message=f"Webhook processing failed: {str(e)}",
            )

            from app.core.exceptions import IntegrationException

            raise IntegrationException(
                f"Webhook processing failed: {str(e)}",
                "INTEGRATION_009",
                {"platform": platform, "shop_identifier": shop_identifier},
            ) from e

    def generate_webhook_endpoints(self, integration_id: str) -> Dict[str, str]:
        """
        Generate webhook endpoint URLs for a platform integration.

        Args:
            integration_id: ID of the integration

        Returns:
            Dictionary of webhook endpoints by type

        Raises:
            EntityNotFoundException: If integration not found
        """
        # Get integration
        integration = self.get_by_id(integration_id)
        if not integration:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PlatformIntegration", integration_id)

        # Generate base webhook URL
        # In a real implementation, this would come from a configuration
        base_url = "https://hidesync.example.com/api/webhooks"

        # Generate endpoints for common webhook types
        return {
            "order_created": f"{base_url}/{integration.platform}/{integration.id}/order_created",
            "order_updated": f"{base_url}/{integration.platform}/{integration.id}/order_updated",
            "order_cancelled": f"{base_url}/{integration.platform}/{integration.id}/order_cancelled",
            "product_created": f"{base_url}/{integration.platform}/{integration.id}/product_created",
            "product_updated": f"{base_url}/{integration.platform}/{integration.id}/product_updated",
            "inventory_updated": f"{base_url}/{integration.platform}/{integration.id}/inventory_updated",
            "customer_created": f"{base_url}/{integration.platform}/{integration.id}/customer_created",
            "customer_updated": f"{base_url}/{integration.platform}/{integration.id}/customer_updated",
        }

    def find_integrations_by_platform(
        self, platform: str, active_only: bool = True
    ) -> List[PlatformIntegration]:
        """
        Find platform integrations by platform type.

        Args:
            platform: Platform identifier (etsy, shopify, etc.)
            active_only: Whether to include only active integrations

        Returns:
            List of matching platform integrations
        """
        filters = {"platform": platform}

        if active_only:
            filters["active"] = True

        return self.repository.list(**filters)

    def get_integration_by_shop(
        self, platform: str, shop_name: str
    ) -> Optional[PlatformIntegration]:
        """
        Find a platform integration by platform and shop name.

        Args:
            platform: Platform identifier (etsy, shopify, etc.)
            shop_name: Shop name or identifier

        Returns:
            Matching platform integration or None if not found
        """
        integrations = self.repository.list(
            platform=platform, shop_name=shop_name, limit=1
        )

        return integrations[0] if integrations else None

    def _get_platform_adapter(self, integration: PlatformIntegration) -> Any:
        """
        Get appropriate adapter for a platform integration.

        Args:
            integration: Platform integration entity

        Returns:
            Platform adapter instance

        Raises:
            IntegrationException: If adapter not found
        """
        adapter_class = self.platform_adapters.get(integration.platform)
        if not adapter_class:
            from app.core.exceptions import IntegrationException

            raise IntegrationException(
                f"No adapter available for platform: {integration.platform}",
                "INTEGRATION_006",
            )

        # Create adapter instance with credentials
        credentials = {
            "api_key": integration.api_key,
            "api_secret": integration.api_secret,
            "access_token": integration.access_token,
            "refresh_token": integration.refresh_token,
            "token_expires_at": integration.token_expires_at,
        }

        # Parse settings
        settings = {}
        if integration.settings:
            try:
                settings = json.loads(integration.settings)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse settings for integration {integration.id}"
                )

        return adapter_class(
            shop_name=integration.shop_name, credentials=credentials, settings=settings
        )

    def _verify_connection(self, integration: PlatformIntegration) -> bool:
        """
        Verify connection to platform.

        Args:
            integration: Platform integration entity

        Returns:
            True if connection successful

        Raises:
            IntegrationException: If connection fails
        """
        adapter = self._get_platform_adapter(integration)
        return adapter.verify_connection()

    def _import_from_platform(
        self,
        adapter: Any,
        integration: PlatformIntegration,
        entity_types: List[SyncEntityType],
    ) -> Dict[str, Any]:
        """
        Import data from external platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity
            entity_types: Entity types to import

        Returns:
            Import statistics
        """
        results = {"total_processed": 0, "total_errors": 0, "by_entity_type": {}}

        # Process each entity type
        all_types = SyncEntityType.ALL in entity_types

        if all_types or SyncEntityType.ORDER in entity_types:
            order_results = self._import_orders(adapter, integration)
            results["by_entity_type"]["orders"] = order_results
            results["total_processed"] += order_results["processed"]
            results["total_errors"] += order_results["errors"]

        if all_types or SyncEntityType.PRODUCT in entity_types:
            product_results = self._import_products(adapter, integration)
            results["by_entity_type"]["products"] = product_results
            results["total_processed"] += product_results["processed"]
            results["total_errors"] += product_results["errors"]

        if all_types or SyncEntityType.CUSTOMER in entity_types:
            customer_results = self._import_customers(adapter, integration)
            results["by_entity_type"]["customers"] = customer_results
            results["total_processed"] += customer_results["processed"]
            results["total_errors"] += customer_results["errors"]

        if all_types or SyncEntityType.INVENTORY in entity_types:
            inventory_results = self._import_inventory(adapter, integration)
            results["by_entity_type"]["inventory"] = inventory_results
            results["total_processed"] += inventory_results["processed"]
            results["total_errors"] += inventory_results["errors"]

        return results

    def _export_to_platform(
        self,
        adapter: Any,
        integration: PlatformIntegration,
        entity_types: List[SyncEntityType],
    ) -> Dict[str, Any]:
        """
        Export data to external platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity
            entity_types: Entity types to export

        Returns:
            Export statistics
        """
        results = {"total_processed": 0, "total_errors": 0, "by_entity_type": {}}

        # Process each entity type
        all_types = SyncEntityType.ALL in entity_types

        if all_types or SyncEntityType.PRODUCT in entity_types:
            product_results = self._export_products(adapter, integration)
            results["by_entity_type"]["products"] = product_results
            results["total_processed"] += product_results["processed"]
            results["total_errors"] += product_results["errors"]

        if all_types or SyncEntityType.INVENTORY in entity_types:
            inventory_results = self._export_inventory(adapter, integration)
            results["by_entity_type"]["inventory"] = inventory_results
            results["total_processed"] += inventory_results["processed"]
            results["total_errors"] += inventory_results["errors"]

        # Order export may not be needed, but included for completeness
        if all_types or SyncEntityType.ORDER in entity_types:
            order_results = self._export_order_updates(adapter, integration)
            results["by_entity_type"]["orders"] = order_results
            results["total_processed"] += order_results["processed"]
            results["total_errors"] += order_results["errors"]

        return results

    def _import_orders(
        self, adapter: Any, integration: PlatformIntegration
    ) -> Dict[str, Any]:
        """
        Import orders from platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity

        Returns:
            Import statistics
        """
        logger.info(
            f"Importing orders from {integration.platform} for {integration.shop_name}"
        )

        # Default results for fallback
        results = {"processed": 0, "errors": 0, "created": 0, "updated": 0}

        # Get orders from platform using adapter
        if not hasattr(adapter, "get_orders"):
            logger.warning(
                f"Platform adapter for {integration.platform} does not support order import"
            )
            return results

        try:
            # Get last sync time to determine which orders to fetch
            last_sync = integration.last_sync_at or datetime.now() - timedelta(days=30)

            # Fetch orders
            orders = adapter.get_orders(since=last_sync)

            if not orders:
                logger.info(f"No new orders to import from {integration.platform}")
                return results

            # Process each order
            created_count = 0
            updated_count = 0
            error_count = 0

            for order in orders:
                try:
                    # Check if order already exists by platform order ID
                    # This would normally use the sale service
                    if self.sale_service:
                        existing_sale = self.sale_service.find_by_platform_order_id(
                            platform=integration.platform,
                            platform_order_id=order.get("id"),
                        )

                        if existing_sale:
                            # Update existing order
                            self.sale_service.update_from_platform(
                                existing_sale.id, order
                            )
                            updated_count += 1
                        else:
                            # Create new order
                            self.sale_service.create_from_platform(
                                platform=integration.platform,
                                platform_integration_id=integration.id,
                                order_data=order,
                            )
                            created_count += 1
                    else:
                        # Just count orders for simulation
                        created_count += 1

                except Exception as e:
                    logger.error(f"Error processing order {order.get('id')}: {str(e)}")
                    error_count += 1

            results = {
                "processed": created_count + updated_count,
                "errors": error_count,
                "created": created_count,
                "updated": updated_count,
            }

            return results

        except Exception as e:
            logger.exception(f"Order import failed: {str(e)}")
            return {"processed": 0, "errors": 1, "created": 0, "updated": 0}

    def _import_products(
        self, adapter: Any, integration: PlatformIntegration
    ) -> Dict[str, Any]:
        """
        Import products from platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity

        Returns:
            Import statistics
        """
        logger.info(
            f"Importing products from {integration.platform} for {integration.shop_name}"
        )

        # Default results for fallback
        results = {"processed": 0, "errors": 0, "created": 0, "updated": 0}

        # Implementation would follow similar pattern to _import_orders
        # For now, return a placeholder
        return results

    def _import_customers(
        self, adapter: Any, integration: PlatformIntegration
    ) -> Dict[str, Any]:
        """
        Import customers from platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity

        Returns:
            Import statistics
        """
        logger.info(
            f"Importing customers from {integration.platform} for {integration.shop_name}"
        )

        # Default results for fallback
        results = {"processed": 0, "errors": 0, "created": 0, "updated": 0}

        # Implementation would follow similar pattern to _import_orders
        # For now, return a placeholder
        return results

    def _import_inventory(
        self, adapter: Any, integration: PlatformIntegration
    ) -> Dict[str, Any]:
        """
        Import inventory from platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity

        Returns:
            Import statistics
        """
        logger.info(
            f"Importing inventory from {integration.platform} for {integration.shop_name}"
        )

        # Default results for fallback
        results = {"processed": 0, "errors": 0, "created": 0, "updated": 0}

        # Implementation would follow similar pattern to _import_orders
        # For now, return a placeholder
        return results

    def _export_products(
        self, adapter: Any, integration: PlatformIntegration
    ) -> Dict[str, Any]:
        """
        Export products to platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity

        Returns:
            Export statistics
        """
        logger.info(
            f"Exporting products to {integration.platform} for {integration.shop_name}"
        )

        # Default results for fallback
        results = {"processed": 0, "errors": 0, "created": 0, "updated": 0}

        # Implementation would use product service to get products for export
        # For now, return a placeholder
        return results

    def _export_inventory(
        self, adapter: Any, integration: PlatformIntegration
    ) -> Dict[str, Any]:
        """
        Export inventory to platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity

        Returns:
            Export statistics
        """
        logger.info(
            f"Exporting inventory to {integration.platform} for {integration.shop_name}"
        )

        # Default results for fallback
        results = {"processed": 0, "errors": 0, "created": 0, "updated": 0}

        # Implementation would use inventory service to get inventory for export
        # For now, return a placeholder
        return results

    def _export_order_updates(
        self, adapter: Any, integration: PlatformIntegration
    ) -> Dict[str, Any]:
        """
        Export order updates to platform.

        Args:
            adapter: Platform adapter
            integration: Platform integration entity

        Returns:
            Export statistics
        """
        logger.info(
            f"Exporting order updates to {integration.platform} for {integration.shop_name}"
        )

        # Default results for fallback
        results = {"processed": 0, "errors": 0, "created": 0, "updated": 0}

        # Implementation would use sale service to get orders for status updates
        # For now, return a placeholder
        return results

    def _create_sync_event(
        self,
        integration_id: str,
        event_type: str,
        status: str,
        message: str,
        items_processed: int = 0,
    ) -> Dict[str, Any]:
        """
        Create a sync event record.

        Args:
            integration_id: Platform integration ID
            event_type: Type of event
            status: Event status
            message: Event message
            items_processed: Number of items processed

        Returns:
            Created sync event
        """
        event_data = {
            "id": str(uuid.uuid4()),
            "platform_integration_id": integration_id,
            "event_type": event_type,
            "status": status,
            "message": message,
            "items_processed": items_processed,
            "created_at": datetime.now(),
        }

        event = self.sync_event_repository.create(event_data)

        return {
            "id": event.id,
            "event_type": event.event_type,
            "status": event.status,
            "message": event.message,
            "items_processed": event.items_processed,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }

    def _update_sync_event(
        self,
        event_id: str,
        status: str,
        message: str,
        items_processed: Optional[int] = None,
    ) -> None:
        """
        Update a sync event record.

        Args:
            event_id: ID of the event to update
            status: New status
            message: New message
            items_processed: Optional number of items processed
        """
        update_data = {"status": status, "message": message}

        if items_processed is not None:
            update_data["items_processed"] = items_processed

        self.sync_event_repository.update(event_id, update_data)

    def _calculate_sync_statistics(self, integration_id: str) -> Dict[str, Any]:
        """
        Calculate synchronization statistics for an integration.

        Args:
            integration_id: Platform integration ID

        Returns:
            Dictionary with sync statistics
        """
        # Get all sync events
        events = self.sync_event_repository.list(platform_integration_id=integration_id)

        # Calculate statistics
        total_events = len(events)
        success_count = len([e for e in events if e.status == "success"])
        error_count = len([e for e in events if e.status == "error"])
        in_progress_count = len([e for e in events if e.status == "in_progress"])

        # Calculate by event type
        event_types = {}
        for event in events:
            event_type = event.event_type
            if event_type not in event_types:
                event_types[event_type] = {
                    "total": 0,
                    "success": 0,
                    "error": 0,
                    "in_progress": 0,
                }

            event_types[event_type]["total"] += 1
            event_types[event_type][event.status] += 1

        # Calculate items processed
        total_items_processed = sum(e.items_processed or 0 for e in events)

        # Calculate recent success rate (last 7 days)
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_events = [
            e for e in events if e.created_at and e.created_at >= seven_days_ago
        ]
        recent_success_count = len([e for e in recent_events if e.status == "success"])
        recent_error_count = len([e for e in recent_events if e.status == "error"])

        recent_success_rate = 0
        if recent_success_count + recent_error_count > 0:
            recent_success_rate = round(
                recent_success_count
                / (recent_success_count + recent_error_count)
                * 100,
                1,
            )

        return {
            "total_events": total_events,
            "success_count": success_count,
            "error_count": error_count,
            "in_progress_count": in_progress_count,
            "success_rate": (
                round(success_count / total_events * 100, 1) if total_events > 0 else 0
            ),
            "total_items_processed": total_items_processed,
            "by_event_type": event_types,
            "recent_success_rate": recent_success_rate,
        }

    def _match_shop_identifier(
        self, integration: PlatformIntegration, shop_identifier: str
    ) -> bool:
        """
        Check if the shop identifier matches the integration.

        This handles cases where the shop identifier might be different from the shop name
        but still refers to the same shop (e.g., shop ID vs. shop handle).

        Args:
            integration: Platform integration entity
            shop_identifier: Shop identifier from webhook

        Returns:
            True if shop identifier matches the integration
        """
        # Default implementation just checks exact match
        if integration.shop_name == shop_identifier:
            return True

        # Check settings for alternative identifiers
        if integration.settings:
            try:
                settings = json.loads(integration.settings)
                alternative_identifiers = settings.get(
                    "alternative_shop_identifiers", []
                )
                if shop_identifier in alternative_identifiers:
                    return True
            except json.JSONDecodeError:
                pass

        return False

    def _handle_order_webhook(
        self, integration: PlatformIntegration, data: Dict[str, Any], webhook_type: str
    ) -> None:
        """
        Handle order webhook data.

        Args:
            integration: Platform integration entity
            data: Webhook data
            webhook_type: Type of webhook
        """
        if not self.sale_service:
            logger.warning("Sale service not available for handling order webhook")
            return

        order_data = data.get("order", {})
        if not order_data:
            order_data = data  # Some platforms send the order directly

        # Get platform order ID
        platform_order_id = order_data.get("id")
        if not platform_order_id:
            logger.warning("No order ID found in webhook data")
            return

        try:
            # Check if order already exists
            existing_sale = self.sale_service.find_by_platform_order_id(
                platform=integration.platform, platform_order_id=platform_order_id
            )

            if existing_sale and webhook_type == "order_updated":
                # Update existing order
                self.sale_service.update_from_platform(existing_sale.id, order_data)
                logger.info(
                    f"Updated sale {existing_sale.id} from {integration.platform} webhook"
                )

            elif not existing_sale and webhook_type == "order_created":
                # Create new order
                new_sale = self.sale_service.create_from_platform(
                    platform=integration.platform,
                    platform_integration_id=integration.id,
                    order_data=order_data,
                )
                logger.info(
                    f"Created new sale {new_sale.id} from {integration.platform} webhook"
                )

        except Exception as e:
            logger.error(f"Error handling order webhook: {str(e)}")

    def _handle_product_webhook(
        self, integration: PlatformIntegration, data: Dict[str, Any], webhook_type: str
    ) -> None:
        """
        Handle product webhook data.

        Args:
            integration: Platform integration entity
            data: Webhook data
            webhook_type: Type of webhook
        """
        # Similar implementation to _handle_order_webhook
        # This would update products in the product service
        pass

    def _handle_inventory_webhook(
        self, integration: PlatformIntegration, data: Dict[str, Any]
    ) -> None:
        """
        Handle inventory webhook data.

        Args:
            integration: Platform integration entity
            data: Webhook data
        """
        # Similar implementation to _handle_order_webhook
        # This would update inventory in the inventory service
        pass
