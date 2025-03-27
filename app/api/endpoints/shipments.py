# File: app/api/endpoints/shipments.py
"""
Shipments API endpoints for HideSync.

This module provides endpoints for managing shipments, including
creating, tracking, and updating shipping information.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentUpdate,
    ShipmentShip,
    ShipmentResponse,
    TrackingUpdate,
)
from app.services.shipment_service import ShipmentService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
)

router = APIRouter()


@router.post("/", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_shipment(
    *,
    db: Session = Depends(get_db),
    shipment_in: ShipmentCreate,
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Create a new shipment.

    Args:
        db: Database session
        shipment_in: Shipment data for creation
        current_user: Currently authenticated user

    Returns:
        Created shipment information

    Raises:
        HTTPException: If shipment creation fails due to business rules
    """
    shipment_service = ShipmentService(db)
    try:
        return shipment_service.create_shipment(shipment_in.dict())
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(
    *,
    db: Session = Depends(get_db),
    shipment_id: int = Path(
        ..., ge=1, description="The ID of the shipment to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Get detailed information about a specific shipment.

    Args:
        db: Database session
        shipment_id: ID of the shipment to retrieve
        current_user: Currently authenticated user

    Returns:
        Shipment information

    Raises:
        HTTPException: If the shipment doesn't exist
    """
    shipment_service = ShipmentService(db)
    try:
        shipment = shipment_service.get_by_id(shipment_id)
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shipment with ID {shipment_id} not found",
            )
        return shipment
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found",
        )


@router.put("/{shipment_id}", response_model=ShipmentResponse)
def update_shipment(
    *,
    db: Session = Depends(get_db),
    shipment_id: int = Path(..., ge=1, description="The ID of the shipment to update"),
    shipment_in: ShipmentUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Update a shipment.

    Args:
        db: Database session
        shipment_id: ID of the shipment to update
        shipment_in: Updated shipment data
        current_user: Currently authenticated user

    Returns:
        Updated shipment information

    Raises:
        HTTPException: If the shipment doesn't exist or update violates business rules
    """
    shipment_service = ShipmentService(db)
    try:
        return shipment_service.update(
            shipment_id, shipment_in.dict(exclude_unset=True)
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{shipment_id}/ship", response_model=ShipmentResponse)
def mark_as_shipped(
    *,
    db: Session = Depends(get_db),
    shipment_id: int = Path(..., ge=1, description="The ID of the shipment"),
    ship_data: ShipmentShip,
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Mark a shipment as shipped with tracking information.

    Args:
        db: Database session
        shipment_id: ID of the shipment
        ship_data: Shipping data including tracking number and carrier
        current_user: Currently authenticated user

    Returns:
        Updated shipment information

    Raises:
        HTTPException: If the shipment doesn't exist or can't be marked as shipped
    """
    shipment_service = ShipmentService(db)
    try:
        return shipment_service.mark_as_shipped(
            shipment_id=shipment_id,
            tracking_number=ship_data.tracking_number,
            shipping_method=ship_data.shipping_method,
            shipping_cost=ship_data.shipping_cost,
            ship_date=ship_data.ship_date,
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{shipment_id}/status", response_model=ShipmentResponse)
def update_shipment_status(
    *,
    db: Session = Depends(get_db),
    shipment_id: int = Path(..., ge=1, description="The ID of the shipment"),
    status: str = Body(..., embed=True),
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Update a shipment's status.

    Args:
        db: Database session
        shipment_id: ID of the shipment
        status: New status value
        current_user: Currently authenticated user

    Returns:
        Updated shipment information

    Raises:
        HTTPException: If the shipment doesn't exist
    """
    shipment_service = ShipmentService(db)
    try:
        return shipment_service.update_shipment_status(shipment_id, status)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found",
        )


@router.put("/{shipment_id}/tracking", response_model=ShipmentResponse)
def update_tracking_info(
    *,
    db: Session = Depends(get_db),
    shipment_id: int = Path(..., ge=1, description="The ID of the shipment"),
    tracking_data: TrackingUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Update tracking information for a shipment.

    Args:
        db: Database session
        shipment_id: ID of the shipment
        tracking_data: New tracking information
        current_user: Currently authenticated user

    Returns:
        Updated shipment information

    Raises:
        HTTPException: If the shipment doesn't exist
    """
    shipment_service = ShipmentService(db)
    try:
        return shipment_service.update_tracking_info(
            shipment_id=shipment_id,
            tracking_number=tracking_data.tracking_number,
            shipping_provider=tracking_data.shipping_provider,
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found",
        )


@router.get("/by-sale/{sale_id}", response_model=ShipmentResponse)
def get_shipment_by_sale(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Get shipment information for a specific sale.

    Args:
        db: Database session
        sale_id: ID of the sale
        current_user: Currently authenticated user

    Returns:
        Shipment information

    Raises:
        HTTPException: If no shipment exists for the sale
    """
    shipment_service = ShipmentService(db)
    shipment = shipment_service.get_shipment_by_sale(sale_id)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No shipment found for sale with ID {sale_id}",
        )
    return shipment


@router.get("/pending", response_model=List[ShipmentResponse])
def get_pending_shipments(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
) -> List[ShipmentResponse]:
    """
    Get all pending shipments.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return

    Returns:
        List of pending shipments
    """
    shipment_service = ShipmentService(db)
    return shipment_service.get_pending_shipments()[:limit]
