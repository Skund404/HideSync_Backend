# File: app/api/endpoints/platform_integrations.py
"""
Platform Integration API endpoints for HideSync.

This module provides endpoints for managing integrations with external platforms
like Shopify, Etsy, and other e-commerce systems.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.platform_integration import (
    PlatformIntegration,
    PlatformIntegrationCreate,
    PlatformIntegrationUpdate,
    SyncEvent,
    SyncEventCreate,
    SyncSettings,
    PlatformIntegrationWithEvents,
    SyncResult,
)
from app.services.platform_integration_service import PlatformIntegrationService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    IntegrationException,
)

router = APIRouter()


@router.get("/", response_model=List[PlatformIntegration])
def list_integrations(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        active: Optional[bool] = Query(None, description="Filter by active status"),
        platform: Optional[str] = Query(None, description="Filter by platform type"),
) -> List[PlatformIntegration]:
    """
    Retrieve platform integrations with optional filtering.

    Args:
        db: Database session
        current_user: Currently authenticated user
        active: Optional filter by active status
        platform: Optional filter by platform type

    Returns:
        List of platform integration records
    """
    integration_service = PlatformIntegrationService(db)
    return integration_service.get_integrations(active=active, platform=platform)


@router.post(
    "/", response_model=PlatformIntegration, status_code=status.HTTP_201_CREATED
)
def create_integration(
        *,
        db: Session = Depends(get_db),
        integration_in: PlatformIntegrationCreate,
        current_user: Any = Depends(get_current_active_user),
) -> PlatformIntegration:
    """
    Create a new platform integration.

    Args:
        db: Database session
        integration_in: Platform integration data for creation
        current_user: Currently authenticated user

    Returns:
        Created platform integration information

    Raises:
        HTTPException: If integration creation fails
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.create_integration(integration_in, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{integration_id}", response_model=PlatformIntegrationWithEvents)
def get_integration(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(
            ..., description="The ID of the integration to retrieve"
        ),
        current_user: Any = Depends(get_current_active_user),
) -> PlatformIntegrationWithEvents:
    """
    Get detailed information about a specific platform integration.

    Args:
        db: Database session
        integration_id: ID of the integration to retrieve
        current_user: Currently authenticated user

    Returns:
        Platform integration information with sync events

    Raises:
        HTTPException: If the integration doesn't exist
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.get_integration_with_events(integration_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )


@router.put("/{integration_id}", response_model=PlatformIntegration)
def update_integration(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(..., description="The ID of the integration to update"),
        integration_in: PlatformIntegrationUpdate,
        current_user: Any = Depends(get_current_active_user),
) -> PlatformIntegration:
    """
    Update a platform integration.

    Args:
        db: Database session
        integration_id: ID of the integration to update
        integration_in: Updated integration data
        current_user: Currently authenticated user

    Returns:
        Updated platform integration information

    Raises:
        HTTPException: If the integration doesn't exist or update fails
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.update_integration(
            integration_id, integration_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_integration(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(..., description="The ID of the integration to delete"),
        current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a platform integration.

    Args:
        db: Database session
        integration_id: ID of the integration to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the integration doesn't exist or can't be deleted
    """
    integration_service = PlatformIntegrationService(db)
    try:
        integration_service.delete_integration(integration_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{integration_id}/sync", response_model=SyncResult)
def trigger_sync(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(..., description="The ID of the integration"),
        sync_direction: str = Query(
            "import", description="Sync direction: import, export, or bidirectional"
        ),
        entity_type: Optional[str] = Query(
            None, description="Entity type to sync: product, order, inventory, or all"
        ),
        current_user: Any = Depends(get_current_active_user),
) -> SyncResult:
    """
    Trigger synchronization with external platform.

    Args:
        db: Database session
        integration_id: ID of the integration
        sync_direction: Direction of synchronization
        entity_type: Type of entity to synchronize
        current_user: Currently authenticated user

    Returns:
        Synchronization result

    Raises:
        HTTPException: If the integration doesn't exist or sync fails
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.trigger_sync(
            integration_id, sync_direction, entity_type, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )
    except IntegrationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Synchronization failed: {str(e)}",
        )


@router.put("/{integration_id}/settings", response_model=PlatformIntegration)
def update_sync_settings(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(..., description="The ID of the integration"),
        settings: SyncSettings = Body(..., description="Updated synchronization settings"),
        current_user: Any = Depends(get_current_active_user),
) -> PlatformIntegration:
    """
    Update synchronization settings for a platform integration.

    This endpoint allows updating configuration for automatic synchronization,
    including sync intervals, which entities to sync, and mappings between
    HideSync and platform-specific values.

    Args:
        db: Database session
        integration_id: ID of the integration
        settings: Synchronization settings object with updated values
        current_user: Currently authenticated user

    Returns:
        Updated platform integration with new settings

    Raises:
        HTTPException: If the integration doesn't exist or settings are invalid
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.update_sync_settings(
            integration_id, settings, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid settings: {str(e)}"
        )


@router.get("/{integration_id}/events", response_model=List[SyncEvent])
def get_sync_events(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(..., description="The ID of the integration"),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of records to return"
        ),
        current_user: Any = Depends(get_current_active_user),
) -> List[SyncEvent]:
    """
    Get synchronization events for a platform integration.

    Args:
        db: Database session
        integration_id: ID of the integration
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        current_user: Currently authenticated user

    Returns:
        List of synchronization events

    Raises:
        HTTPException: If the integration doesn't exist
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.get_sync_events(integration_id, skip, limit)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )


@router.post(
    "/{integration_id}/events",
    response_model=SyncEvent,
    status_code=status.HTTP_201_CREATED,
)
def create_sync_event(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(..., description="The ID of the integration"),
        event_in: SyncEventCreate = Body(..., description="Sync event data to create"),
        current_user: Any = Depends(get_current_active_user),
) -> SyncEvent:
    """
    Create a sync event manually.

    This endpoint allows manual creation of synchronization events for tracking
    integration activities that might have occurred outside the system or for
    recording custom synchronization operations.

    Args:
        db: Database session
        integration_id: ID of the integration
        event_in: Sync event data containing event type, status, and details
        current_user: Currently authenticated user

    Returns:
        Created sync event with generated ID and timestamps

    Raises:
        HTTPException: If the integration doesn't exist or event data is invalid
    """
    integration_service = PlatformIntegrationService(db)
    try:
        # Validate event type
        valid_event_types = [
            "order_import", "order_export", "product_import", "product_export",
            "inventory_update", "customer_import", "manual_sync", "webhook_received",
            "error_recovery"
        ]

        if event_in.event_type not in valid_event_types and not event_in.event_type.startswith("custom_"):
            raise BusinessRuleException(
                f"Invalid event type. Must be one of {valid_event_types} or start with 'custom_'"
            )

        return integration_service.create_sync_event(
            integration_id, event_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sync event: {str(e)}"
        )


@router.post("/{integration_id}/connect", response_model=Dict[str, Any])
def connect_platform(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(..., description="The ID of the integration"),
        auth_code: Optional[str] = Query(
            None, description="Authorization code (if using OAuth)"
        ),
        shop_url: Optional[str] = Query(
            None, description="Shop URL (for certain platforms)"
        ),
        current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Connect to a platform using OAuth or other authentication methods.

    Args:
        db: Database session
        integration_id: ID of the integration
        auth_code: Authorization code (if using OAuth)
        shop_url: Shop URL (for certain platforms)
        current_user: Currently authenticated user

    Returns:
        Connection result

    Raises:
        HTTPException: If connection fails
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.connect_platform(
            integration_id, auth_code, shop_url, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )
    except IntegrationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection failed: {str(e)}",
        )


@router.get("/{integration_id}/sync-events", response_model=List[SyncEvent])
def get_sync_events_alias(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(..., description="The ID of the integration"),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of records to return"
        ),
        current_user: Any = Depends(get_current_active_user),
) -> List[SyncEvent]:
    """
    Get synchronization events for a platform integration.

    This is an alias for the 'get_sync_events' endpoint to maintain
    naming consistency with the enhancement plan.

    Args:
        db: Database session
        integration_id: ID of the integration
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        current_user: Currently authenticated user

    Returns:
        List of synchronization events

    Raises:
        HTTPException: If the integration doesn't exist
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.get_sync_events(integration_id, skip, limit)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )


@router.get("/{integration_id}/with-details", response_model=Dict[str, Any])
def get_integration_with_details(
        *,
        db: Session = Depends(get_db),
        integration_id: str = Path(
            ..., description="The ID of the integration to retrieve with details"
        ),
        current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get detailed information about a platform integration, including sync statistics.

    This endpoint provides comprehensive details about an integration, including
    basic configuration, sync events history, statistics on sync success/failure rates,
    connection health, and platform-specific details.

    Args:
        db: Database session
        integration_id: ID of the integration to retrieve
        current_user: Currently authenticated user

    Returns:
        Platform integration information with detailed statistics and sync history

    Raises:
        HTTPException: If the integration doesn't exist
    """
    integration_service = PlatformIntegrationService(db)
    try:
        return integration_service.get_integration_with_details(integration_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform integration with ID {integration_id} not found",
        )