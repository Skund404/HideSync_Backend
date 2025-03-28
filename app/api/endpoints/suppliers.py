# File: app/api/endpoints/suppliers.py
"""
Supplier API endpoints for HideSync.

This module provides endpoints for managing suppliers, including
supplier information, ratings, purchasing history, and related operations.
"""

from typing import Any, List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.supplier import (
    SupplierResponse as Supplier,
    SupplierCreate,
    SupplierUpdate,
    SupplierDetailResponse,
)
from app.schemas.supplier_rating import (
    SupplierRatingCreate,
    SupplierRatingResponse,
    SupplierRatingSummary,
)
from app.schemas.supplier_history import (
    SupplierHistoryCreate,
    SupplierHistoryResponse,
    SupplierEventCreate,
    SupplierEventInDB,
)
from app.schemas.compatibility import (
    SupplierSearchParams,
    PurchaseHistorySummary,
)
from app.services.supplier_service import SupplierService
from app.services.supplier_history_service import SupplierHistoryService
from app.services.supplier_rating_service import SupplierRatingService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()


def list(self, **filters) -> List[Supplier]:
    """
    List suppliers with optional filtering.
    """
    query = self.session.query(self.model)

    # Apply specific filters if present
    if "name" in filters and filters["name"]:
        query = query.filter(self.model.name == filters["name"])

    if "status" in filters and filters["status"]:
        query = query.filter(self.model.status == filters["status"])

    if "category" in filters and filters["category"]:
        query = query.filter(self.model.category == filters["category"])

    # Apply pagination
    skip = filters.get("skip", 0)
    limit = filters.get("limit", 100)

    # Execute query - NO order_by since it's not supported
    # Apply pagination through list slicing if needed
    entities = query.all()

    # Apply pagination after fetch (not ideal but works)
    if skip or limit:
        entities = entities[skip:skip + limit]

    # Decrypt sensitive fields
    return [self._decrypt_sensitive_fields(entity) for entity in entities]


@router.get("/", response_model=List[Supplier])
def list_suppliers(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        page: int = Query(1, ge=1, description="Page number"),
        pageSize: int = Query(10, ge=1, le=100, description="Items per page")
) -> List[Supplier]:
    """
    Retrieve suppliers with pagination.
    """
    # Convert page/pageSize to skip/limit
    skip = (page - 1) * pageSize
    limit = pageSize

    supplier_service = SupplierService(db)
    return supplier_service.get_suppliers(skip=skip, limit=limit)

@router.post("/", response_model=Supplier, status_code=status.HTTP_201_CREATED)
def create_supplier(
        *,
        db: Session = Depends(get_db),
        supplier_in: SupplierCreate,
        current_user: Any = Depends(get_current_active_user),
) -> Supplier:
    """
    Create a new supplier.
    """
    supplier_service = SupplierService(db)
    try:
        # Convert Pydantic model to dict
        supplier_data = supplier_in.dict(exclude_unset=True)

        # Call service with user_id separately
        return supplier_service.create_supplier(supplier_data, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/", response_model=Supplier, status_code=status.HTTP_201_CREATED)
def create_supplier(
        *,
        db: Session = Depends(get_db),
        supplier_in: SupplierCreate,
        current_user: Any = Depends(get_current_active_user),
) -> Supplier:
    """
    Create a new supplier.
    """
    supplier_service = SupplierService(db)
    try:
        supplier_data = supplier_in.dict(exclude_unset=True)
        # Do NOT add created_by if the Supplier model doesn't have this field
        # supplier_data["created_by"] = current_user.id

        return supplier_service.create_supplier(supplier_data)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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


@router.get("/{supplier_id}/ratings", response_model=List[SupplierRatingResponse])
def get_supplier_ratings(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    current_user: Any = Depends(get_current_active_user),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of ratings to return"
    ),
) -> List[SupplierRatingResponse]:
    """
    Get ratings for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        current_user: Currently authenticated user
        limit: Maximum number of ratings to return

    Returns:
        List of supplier ratings

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_rating_service = SupplierRatingService(db)
    try:
        return supplier_rating_service.get_ratings_by_supplier(supplier_id, limit=limit)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )


@router.get("/{supplier_id}/rating-summary", response_model=SupplierRatingSummary)
def get_supplier_rating_summary(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    current_user: Any = Depends(get_current_active_user),
) -> SupplierRatingSummary:
    """
    Get detailed rating statistics for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        current_user: Currently authenticated user

    Returns:
        Supplier rating summary with statistics

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_rating_service = SupplierRatingService(db)
    try:
        metrics = supplier_rating_service.get_supplier_rating_metrics(supplier_id)

        # Get the supplier to get the current rating
        supplier_service = SupplierService(db)
        supplier = supplier_service.get_by_id(supplier_id)

        return SupplierRatingSummary(
            supplier_id=supplier_id,
            current_rating=supplier.rating or 0,
            statistics=metrics,
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )


@router.post(
    "/{supplier_id}/ratings",
    response_model=SupplierRatingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_rating(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    rating_in: SupplierRatingCreate,
    current_user: Any = Depends(get_current_active_user),
) -> SupplierRatingResponse:
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
    supplier_rating_service = SupplierRatingService(db)
    try:
        return supplier_rating_service.record_rating(
            supplier_id=supplier_id,
            rating=rating_in.rating,
            comments=rating_in.comments,
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{supplier_id}/history", response_model=List[SupplierHistoryResponse])
def get_supplier_history(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    current_user: Any = Depends(get_current_active_user),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of history entries to return"
    ),
) -> List[SupplierHistoryResponse]:
    """
    Get history entries for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        current_user: Currently authenticated user
        limit: Maximum number of history entries to return

    Returns:
        List of supplier history entries

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_history_service = SupplierHistoryService(db)
    try:
        return supplier_history_service.get_history_by_supplier(
            supplier_id, limit=limit
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )


@router.post(
    "/{supplier_id}/history",
    response_model=SupplierHistoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_supplier_history(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    history_in: SupplierHistoryCreate,
    current_user: Any = Depends(get_current_active_user),
) -> SupplierHistoryResponse:
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
    supplier_history_service = SupplierHistoryService(db)
    supplier_service = SupplierService(db)

    try:
        # Check if supplier exists
        supplier = supplier_service.get_by_id(supplier_id)
        if not supplier:
            raise EntityNotFoundException(f"Supplier with ID {supplier_id} not found")

        # Record the status change
        return supplier_history_service.record_status_change(
            supplier_id=supplier_id,
            previous_status=history_in.previous_status,
            new_status=history_in.new_status,
            reason=history_in.reason,
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with ID {supplier_id} not found",
        )


@router.get("/{supplier_id}/status-timeline", response_model=List[dict])
def get_supplier_status_timeline(
    *,
    db: Session = Depends(get_db),
    supplier_id: int = Path(..., ge=1, description="The ID of the supplier"),
    current_user: Any = Depends(get_current_active_user),
) -> List[dict]:
    """
    Get status timeline for a supplier.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        current_user: Currently authenticated user

    Returns:
        List of status changes with dates and details

    Raises:
        HTTPException: If the supplier doesn't exist
    """
    supplier_history_service = SupplierHistoryService(db)
    try:
        return supplier_history_service.get_supplier_status_timeline(supplier_id)
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


@router.get("/analytics/status-trends", response_model=Dict[str, Any])
def get_supplier_status_trends(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get trends in supplier status changes.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Status change trends by month and status
    """
    supplier_history_service = SupplierHistoryService(db)
    return supplier_history_service.get_status_change_trends()


@router.get("/analytics/top-rated", response_model=List[dict])
def get_top_rated_suppliers(
    *,
    db: Session = Depends(get_db),
    min_ratings: int = Query(3, ge=1, description="Minimum number of ratings required"),
    limit: int = Query(
        5, ge=1, le=20, description="Maximum number of suppliers to return"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> List[dict]:
    """
    Get top-rated suppliers.

    Args:
        db: Database session
        min_ratings: Minimum number of ratings required
        limit: Maximum number of suppliers to return
        current_user: Currently authenticated user

    Returns:
        List of top-rated suppliers with their average ratings
    """
    supplier_rating_service = SupplierRatingService(db)
    supplier_service = SupplierService(db)

    top_rated = supplier_rating_service.get_top_rated_suppliers(
        min_ratings=min_ratings, limit=limit
    )

    result = []
    for supplier_id, average_rating in top_rated:
        supplier = supplier_service.get_by_id(supplier_id)
        if supplier:
            result.append(
                {
                    "id": supplier.id,
                    "name": supplier.name,
                    "category": supplier.category,
                    "average_rating": average_rating,
                }
            )

    return result
