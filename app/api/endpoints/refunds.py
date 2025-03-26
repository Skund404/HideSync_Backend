# File: app/api/endpoints/refunds.py
"""
Refunds API endpoints for HideSync.

This module provides endpoints for managing refunds, including
creating, processing, and tracking customer refunds.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.refund import (
    RefundCreate,
    RefundUpdate,
    RefundProcess,
    RefundCancel,
    RefundResponse
)
from app.services.refund_service import RefundService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
)

router = APIRouter()


@router.post("/", response_model=RefundResponse, status_code=status.HTTP_201_CREATED)
def create_refund(
    *,
    db: Session = Depends(get_db),
    refund_in: RefundCreate,
    current_user: Any = Depends(get_current_active_user),
) -> RefundResponse:
    """
    Create a new refund.

    Args:
        db: Database session
        refund_in: Refund data for creation
        current_user: Currently authenticated user

    Returns:
        Created refund information

    Raises:
        HTTPException: If refund creation fails due to business rules
    """
    refund_service = RefundService(db)
    try:
        return refund_service.create_refund(refund_in.dict())
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{refund_id}", response_model=RefundResponse)
def get_refund(
    *,
    db: Session = Depends(get_db),
    refund_id: int = Path(..., ge=1, description="The ID of the refund to retrieve"),
    current_user: Any = Depends(get_current_active_user),
) -> RefundResponse:
    """
    Get detailed information about a specific refund.

    Args:
        db: Database session
        refund_id: ID of the refund to retrieve
        current_user: Currently authenticated user

    Returns:
        Refund information

    Raises:
        HTTPException: If the refund doesn't exist
    """
    refund_service = RefundService(db)
    try:
        refund = refund_service.get_by_id(refund_id)
        if not refund:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Refund with ID {refund_id} not found",
            )
        return refund
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Refund with ID {refund_id} not found",
        )


@router.put("/{refund_id}", response_model=RefundResponse)
def update_refund(
    *,
    db: Session = Depends(get_db),
    refund_id: int = Path(..., ge=1, description="The ID of the refund to update"),
    refund_in: RefundUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> RefundResponse:
    """
    Update a refund.

    Args:
        db: Database session
        refund_id: ID of the refund to update
        refund_in: Updated refund data
        current_user: Currently authenticated user

    Returns:
        Updated refund information

    Raises:
        HTTPException: If the refund doesn't exist or update violates business rules
    """
    refund_service = RefundService(db)
    try:
        return refund_service.update(refund_id, refund_in.dict(exclude_unset=True))
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Refund with ID {refund_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{refund_id}/process", response_model=RefundResponse)
def process_refund(
    *,
    db: Session = Depends(get_db),
    refund_id: int = Path(..., ge=1, description="The ID of the refund"),
    process_data: RefundProcess,
    current_user: Any = Depends(get_current_active_user),
) -> RefundResponse:
    """
    Process a refund with transaction details.

    Args:
        db: Database session
        refund_id: ID of the refund
        process_data: Processing data including transaction ID and payment method
        current_user: Currently authenticated user

    Returns:
        Updated refund information

    Raises:
        HTTPException: If the refund doesn't exist or can't be processed
    """
    refund_service = RefundService(db)
    try:
        return refund_service.process_refund(
            refund_id=refund_id,
            transaction_id=process_data.transaction_id,
            payment_method=process_data.payment_method,
            notes=process_data.notes,
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Refund with ID {refund_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{refund_id}/cancel", response_model=RefundResponse)
def cancel_refund(
    *,
    db: Session = Depends(get_db),
    refund_id: int = Path(..., ge=1, description="The ID of the refund"),
    cancel_data: RefundCancel,
    current_user: Any = Depends(get_current_active_user),
) -> RefundResponse:
    """
    Cancel a pending refund.

    Args:
        db: Database session
        refund_id: ID of the refund
        cancel_data: Cancellation data including reason
        current_user: Currently authenticated user

    Returns:
        Updated refund information

    Raises:
        HTTPException: If the refund doesn't exist or can't be cancelled
    """
    refund_service = RefundService(db)
    try:
        return refund_service.cancel_refund(
            refund_id=refund_id,
            reason=cancel_data.reason,
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Refund with ID {refund_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/by-sale/{sale_id}", response_model=List[RefundResponse])
def get_refunds_by_sale(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    current_user: Any = Depends(get_current_active_user),
) -> List[RefundResponse]:
    """
    Get all refunds for a specific sale.

    Args:
        db: Database session
        sale_id: ID of the sale
        current_user: Currently authenticated user

    Returns:
        List of refunds for the sale
    """
    refund_service = RefundService(db)
    return refund_service.get_refunds_by_sale(sale_id)


@router.get("/pending", response_model=List[RefundResponse])
def get_pending_refunds(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
) -> List[RefundResponse]:
    """
    Get all pending refunds.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return

    Returns:
        List of pending refunds
    """
    refund_service = RefundService(db)
    return refund_service.get_pending_refunds()[:limit]