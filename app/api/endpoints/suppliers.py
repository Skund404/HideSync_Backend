# File: app/api/endpoints/suppliers.py
"""
Supplier API endpoints for HideSync.

This module provides endpoints for managing suppliers, including
supplier information, ratings, purchasing history, and related operations.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.supplier import (
    Supplier,
    SupplierCreate,
    SupplierUpdate,
    SupplierWithDetails,
    SupplierSearchParams,
    SupplierRating,
    SupplierRatingCreate,
    SupplierHistory,
    SupplierHistoryCreate,
    PurchaseHistorySummary,
)
from app.services.supplier_service import SupplierService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()


@router.get("/", response_model=List[Supplier])
def list_suppliers(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    status: Optional[str] = Query(None, description="Filter by supplier status"),
    category: Optional[str] = Query(None, description="Filter by supplier category"),
    material_category: Optional[str] = Query(
        None, description="Filter by material category"
    ),
    search: Optional[str] = Query(None, description="Search term for name or contact"),
) -> List[Supplier]:
    """
    Retrieve suppliers with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        status: Optional filter by supplier status
        category: Optional filter by supplier category
        material_category: Optional filter by material category
        search: Optional search term for name or contact

    Returns:
        List of supplier records
    """
    search_params = SupplierSearchParams(
        status=status,
        category=category,
        material_category=material_category,
        search=search,
    )

    supplier_service = SupplierService(db)
    return supplier_service.get_suppliers(
        skip=skip, limit=limit, search_params=search_params
    )


@router.post("/", response_model=Supplier, status_code=status.HTTP_201_CREATED)
def create_supplier(
    *,
    db: Session = Depends(get_db),
    supplier_in: SupplierCreate,
    current_user: Any = Depends(get_current_active_user),
) -> Supplier:
    """
    Create a new supplier.

    Args:
        db: Database session
        supplier_in: Supplier data for creation
        current_user: Currently authenticated user

    Returns:
        Created supplier information

    Raises:
        HTTPException: If supplier creation fails due to business rules
    """
    supplier_service = SupplierService(db)
    try:
        return supplier_service.create_supplier(supplier_in, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{supplier_id}", response_model=SupplierWithDetails)
def get_supplier(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(
        ..., ge=1, description="The ID of the supplier to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> SupplierWithDetails:
    """
    Get detailed information about a specific supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier to retrieve
        current_user: Currently authenticated user

    Returns:
        Supplier information with details including materials and ratings

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_service = SupplierService(db)
    try:
        return supplier_service.get_supplier_with_details(supplier_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )


@router.put("/{supplier_id}", response_model=Supplier)
def update_supplier(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier to update"),
    supplier_in: SupplierUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Supplier:
    """
    Update a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier to update
        supplier_in: Updated supplier data
        current_user: Currently authenticated user

    Returns:
        Updated supplier information

    Raises:
        HTTPException: If the supplier doesn't exist or update violates business rules
    """
    supplier_service = SupplierService(db)
    try:
        return supplier_service.update_supplier(
            supplier_id, supplier_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier to delete"),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the supplier doesn't exist or can't be deleted
    """
    supplier_service = SupplierService(db)
    try:
        supplier_service.delete_supplier(supplier_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{supplier_id}/ratings", response_model=List[SupplierRating])
def get_supplier_ratings(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    current_user: Any = Depends(get_current_active_user),
) -> List[SupplierRating]:
    """
    Get ratings for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        current_user: Currently authenticated user

    Returns:
        List of supplier ratings

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_service = SupplierService(db)
    try:
        return supplier_service.get_supplier_ratings(supplier_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )


@router.post(
    "/{supplier_id}/ratings",
    response_model=SupplierRating,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_rating(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    rating_in: SupplierRatingCreate,
    current_user: Any = Depends(get_current_active_user),
) -> SupplierRating:
    """
    Create a rating for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        rating_in: Rating data
        current_user: Currently authenticated user

    Returns:
        Created supplier rating

    Raises:
        HTTPException: If the supplier doesn't exist or rating creation fails
    """
    supplier_service = SupplierService(db)
    try:
        return supplier_service.create_supplier_rating(
            supplier_id, rating_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{supplier_id}/history", response_model=List[SupplierHistory])
def get_supplier_history(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    current_user: Any = Depends(get_current_active_user),
) -> List[SupplierHistory]:
    """
    Get history entries for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        current_user: Currently authenticated user

    Returns:
        List of supplier history entries

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_service = SupplierService(db)
    try:
        return supplier_service.get_supplier_history(supplier_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )


@router.post(
    "/{supplier_id}/history",
    response_model=SupplierHistory,
    status_code=status.HTTP_201_CREATED,
)
def add_supplier_history(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    history_in: SupplierHistoryCreate,
    current_user: Any = Depends(get_current_active_user),
) -> SupplierHistory:
    """
    Add a history entry for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        history_in: History entry data
        current_user: Currently authenticated user

    Returns:
        Created supplier history entry

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_service = SupplierService(db)
    try:
        return supplier_service.add_supplier_history(
            supplier_id, history_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )


@router.get("/{supplier_id}/purchases", response_model=PurchaseHistorySummary)
def get_supplier_purchase_history(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: Any = Depends(get_current_active_user),
) -> PurchaseHistorySummary:
    """
    Get purchase history summary for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        current_user: Currently authenticated user

    Returns:
        Purchase history summary

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_service = SupplierService(db)
    try:
        return supplier_service.get_purchase_history(supplier_id, start_date, end_date)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )
