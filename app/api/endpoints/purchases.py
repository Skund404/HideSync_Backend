# File: app/api/endpoints/purchases.py
"""
Purchase management API endpoints for the HideSync system.

This module defines the API endpoints for managing purchases within the HideSync system,
including order creation, status management, receiving, and purchase planning.
Purchases represent orders placed with suppliers for materials, tools, and other supplies.
"""

from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body, status
from sqlalchemy.orm import Session
from datetime import datetime, date

from app.api.deps import get_current_active_user
from app.core.exceptions import (
    BusinessRuleException,
    ValidationException,
    EntityNotFoundException,
)
from app.db.session import get_db
from app.db.models.enums import PurchaseStatus, PaymentStatus
from app.schemas.purchase import (
    PurchaseCreate,
    PurchaseUpdate,
    PurchaseResponse,
    PurchaseListResponse,
    PurchaseItemCreate,
    PurchaseItemUpdate,
    PurchaseItemResponse,
    PurchaseItemListResponse,
    PurchaseReceiveData,
)
from app.services.purchase_service import PurchaseService
from app.services.purchase_timeline_service import PurchaseTimelineService
from app.schemas.purchase_timeline import (
    PurchaseTimeline,
    PurchaseTimelineItem,
    PurchasePlan,
)

router = APIRouter()


@router.get("/", response_model=PurchaseListResponse)
def list_purchases(
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    status: Optional[str] = Query(None, description="Filter by purchase status"),
    date_from: Optional[str] = Query(None, description="Filter by date (from)"),
    date_to: Optional[str] = Query(None, description="Filter by date (to)"),
    sort_by: Optional[str] = Query("date", description="Field to sort by"),
    sort_dir: Optional[str] = Query("desc", description="Sort direction (asc/desc)"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get a list of purchases with optional filtering.

    This endpoint retrieves purchases with various filter options
    like supplier, status, and date range.
    """
    purchase_service = PurchaseService(db)

    # Build filter parameters
    filters = {}
    if supplier_id:
        filters["supplier_id"] = supplier_id
    if status:
        filters["status"] = status
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    # Get purchases
    purchases = purchase_service.list(
        skip=skip, limit=limit, sort_by=sort_by, sort_dir=sort_dir, **filters
    )
    total = purchase_service.count(**filters)

    return {"items": purchases, "total": total, "skip": skip, "limit": limit}


@router.post("/", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
def create_purchase(
    purchase_data: PurchaseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Create a new purchase order.

    Creates a new purchase order with the supplier, items, and related details.
    """
    purchase_service = PurchaseService(db)

    try:
        purchase = purchase_service.create_purchase(purchase_data.dict())
        return purchase
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{purchase_id}", response_model=PurchaseResponse)
def get_purchase(
    purchase_id: str = Path(..., description="The ID of the purchase to retrieve"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get a purchase by ID.

    Retrieves detailed information about a specific purchase order,
    including all line items, status, and supplier details.
    """
    purchase_service = PurchaseService(db)
    purchase = purchase_service.get_by_id(purchase_id)

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase with ID {purchase_id} not found",
        )

    return purchase


@router.put("/{purchase_id}", response_model=PurchaseResponse)
def update_purchase(
    purchase_id: str = Path(..., description="The ID of the purchase to update"),
    purchase_data: PurchaseUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Update a purchase.

    Updates a purchase order with new information such as delivery date,
    payment status, or notes.
    """
    purchase_service = PurchaseService(db)

    try:
        purchase = purchase_service.update_purchase(
            purchase_id, purchase_data.dict(exclude_unset=True)
        )

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase with ID {purchase_id} not found",
            )

        return purchase
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{purchase_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase(
    purchase_id: str = Path(..., description="The ID of the purchase to delete"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> None:
    """
    Delete a purchase.

    Deletes a purchase order that is in a draft or planning status.
    Orders that have been placed or received cannot be deleted.
    """
    purchase_service = PurchaseService(db)

    try:
        result = purchase_service.delete_purchase(purchase_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase with ID {purchase_id} not found",
            )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{purchase_id}/items", response_model=PurchaseItemListResponse)
def get_purchase_items(
    purchase_id: str = Path(..., description="The ID of the purchase"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get items for a purchase.

    Retrieves all line items associated with a specific purchase order.
    """
    purchase_service = PurchaseService(db)

    # Check if purchase exists
    purchase = purchase_service.get_by_id(purchase_id)
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase with ID {purchase_id} not found",
        )

    # Get items
    items = purchase_service.get_purchase_items(purchase_id)

    return {"items": items, "total": len(items)}


@router.post("/{purchase_id}/items", response_model=PurchaseItemResponse)
def add_purchase_item(
    purchase_id: str = Path(..., description="The ID of the purchase"),
    item_data: PurchaseItemCreate = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Add an item to a purchase.

    Adds a new line item to an existing purchase order.
    """
    purchase_service = PurchaseService(db)

    try:
        item = purchase_service.add_purchase_item(purchase_id, item_data.dict())
        return item
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )


@router.put("/{purchase_id}/items/{item_id}", response_model=PurchaseItemResponse)
def update_purchase_item(
    purchase_id: str = Path(..., description="The ID of the purchase"),
    item_id: int = Path(..., description="The ID of the item to update"),
    item_data: PurchaseItemUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Update a purchase order item.

    Updates an existing line item within a purchase order, allowing for changes
    to quantity, price, or other item details.
    """
    purchase_service = PurchaseService(db)

    # Check if purchase exists
    purchase = purchase_service.get_by_id(purchase_id)
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase with ID {purchase_id} not found",
        )

    try:
        # Check if item belongs to this purchase
        items = purchase_service.get_purchase_items(purchase_id)
        if not any(item.id == item_id for item in items):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found in purchase {purchase_id}",
            )

        # Check if purchase is in a valid state for updates
        if purchase.status not in [
            PurchaseStatus.PLANNING,
            PurchaseStatus.DRAFT,
            PurchaseStatus.PENDING_APPROVAL,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update items in a purchase with status {purchase.status}",
            )

        # Update the item
        item = purchase_service.update_purchase_item(
            item_id, item_data.dict(exclude_unset=True)
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found in purchase {purchase_id}",
            )

        return item
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{purchase_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_item(
    purchase_id: str = Path(..., description="The ID of the purchase"),
    item_id: int = Path(..., description="The ID of the item to delete"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> None:
    """
    Delete a purchase order item.

    Removes a line item from a purchase order. This is only allowed
    for purchase orders in certain statuses (e.g., DRAFT, PLANNING).
    """
    purchase_service = PurchaseService(db)

    # Check if purchase exists
    purchase = purchase_service.get_by_id(purchase_id)
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase with ID {purchase_id} not found",
        )

    # Check if purchase is in a valid state for item deletion
    if purchase.status not in [
        PurchaseStatus.PLANNING,
        PurchaseStatus.DRAFT,
        PurchaseStatus.PENDING_APPROVAL,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete items from a purchase in status {purchase.status}",
        )

    try:
        # Get the item to verify it belongs to this purchase
        items = purchase_service.get_purchase_items(purchase_id)
        if not any(item.id == item_id for item in items):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found in purchase {purchase_id}",
            )

        # Delete the item
        result = purchase_service.delete_purchase_item(item_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found",
            )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# New endpoints for purchase management


@router.patch("/{purchase_id}/status", response_model=PurchaseResponse)
def update_purchase_status(
    purchase_id: str = Path(..., description="The ID of the purchase"),
    new_status: str = Body(..., embed=True),
    notes: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Update a purchase's status.

    Updates the status of a purchase order (e.g., from ORDERED to SHIPPED),
    with optional notes about the status change.
    """
    purchase_service = PurchaseService(db)

    try:
        purchase = purchase_service.update_purchase_status(purchase_id, new_status)

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase with ID {purchase_id} not found",
            )

        # Add notes if provided
        if notes:
            purchase_service.update_purchase(purchase_id, {"notes": notes})

        return purchase
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase with ID {purchase_id} not found",
        )


@router.get("/by-supplier/{supplier_id}", response_model=PurchaseListResponse)
def get_purchases_by_supplier(
    supplier_id: int = Path(..., description="The ID of the supplier"),
    status: Optional[str] = Query(None, description="Filter by purchase status"),
    date_from: Optional[str] = Query(None, description="Filter by date (from)"),
    date_to: Optional[str] = Query(None, description="Filter by date (to)"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get purchases by supplier.

    Retrieves all purchase orders for a specific supplier,
    with optional filtering by status and date range.
    """
    purchase_service = PurchaseService(db)

    # Build filter parameters
    filters = {"supplier_id": supplier_id}
    if status:
        filters["status"] = status
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    # Get purchases
    purchases = purchase_service.list(skip=skip, limit=limit, **filters)
    total = purchase_service.count(**filters)

    return {"items": purchases, "total": total, "skip": skip, "limit": limit}


@router.get("/by-status/{status}", response_model=PurchaseListResponse)
def get_purchases_by_status(
    status: str = Path(..., description="The purchase status"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    date_from: Optional[str] = Query(None, description="Filter by date (from)"),
    date_to: Optional[str] = Query(None, description="Filter by date (to)"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get purchases by status.

    Retrieves all purchase orders with a specific status,
    with optional filtering by supplier and date range.
    """
    purchase_service = PurchaseService(db)

    # Validate status
    try:
        # Check if status is valid
        if status not in [s.value for s in PurchaseStatus]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid purchase status: {status}",
            )
    except AttributeError:
        # If PurchaseStatus doesn't have values, ignore validation
        pass

    # Build filter parameters
    filters = {"status": status}
    if supplier_id:
        filters["supplier_id"] = supplier_id
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    # Get purchases
    purchases = purchase_service.list(skip=skip, limit=limit, **filters)
    total = purchase_service.count(**filters)

    return {"items": purchases, "total": total, "skip": skip, "limit": limit}


@router.get("/timeline", response_model=PurchaseTimeline)
def get_purchase_timeline(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    period: str = Query("month", description="Time period (day, week, month, quarter)"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get purchase timeline.

    Retrieves a timeline view of purchases, grouped by time periods (day, week, month, quarter).
    Useful for visualizing purchase patterns and upcoming deliveries.
    """
    timeline_service = PurchaseTimelineService(db)

    # Parse dates if provided
    start_date_obj = None
    end_date_obj = None

    if start_date:
        try:
            start_date_obj = datetime.fromisoformat(start_date).date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start date format. Use YYYY-MM-DD.",
            )

    if end_date:
        try:
            end_date_obj = datetime.fromisoformat(end_date).date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end date format. Use YYYY-MM-DD.",
            )

    try:
        # Get timeline
        timeline = timeline_service.get_purchase_timeline(
            start_date=start_date_obj,
            end_date=end_date_obj,
            period=period,
            supplier_id=supplier_id,
        )

        return timeline
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{purchase_id}/receive", response_model=PurchaseResponse)
def receive_purchase(
    purchase_id: str = Path(..., description="The ID of the purchase"),
    receive_data: PurchaseReceiveData = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Receive a purchase.

    Records the receipt of items for a purchase order,
    updating inventory levels and order status.
    """
    purchase_service = PurchaseService(db)

    try:
        purchase = purchase_service.receive_items(purchase_id, receive_data.dict())

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase with ID {purchase_id} not found",
            )

        return purchase
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/planner", response_model=PurchasePlan)
def create_purchase_plan(
    min_stock_days: int = Query(30, description="Minimum days of stock to maintain"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    material_type: Optional[str] = Query(None, description="Filter by material type"),
    include_pending: bool = Query(
        True, description="Include pending purchases in calculations"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Create purchase plan based on inventory.

    Analyzes current inventory levels and usage rates to recommend
    purchases needed to maintain minimum stock levels.
    """
    timeline_service = PurchaseTimelineService(db)

    try:
        # Create purchase plan
        plan = timeline_service.create_purchase_plan(
            min_stock_days=min_stock_days,
            supplier_id=supplier_id,
            material_type=material_type,
            include_pending=include_pending,
        )

        return plan
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating purchase plan: {str(e)}",
        )
