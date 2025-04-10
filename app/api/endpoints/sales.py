# File: app/api/endpoints/sales.py
"""
Sales API endpoints for HideSync.

This module provides endpoints for managing sales, orders, and related
operations like payments, shipments, and order fulfillment.
"""

from typing import Any, List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.compatibility import (
    Sale,
    SaleCreate,
    SaleUpdate,
    SaleItem,
    SaleItemCreate,
    SaleSearchParams,
    SaleWithDetails,
    SaleStatusUpdate,
    PaymentUpdate,
)
from app.schemas.refund import RefundCreate, RefundResponse
from app.schemas.shipment import ShipmentCreate, ShipmentResponse
from app.services.sale_service import SaleService
from app.services.refund_service import RefundService
from app.services.shipment_service import ShipmentService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    InvalidStatusTransitionException,
)
from app.core.exceptions import (
    InsufficientInventoryException as InsufficientQuantityException,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[Sale])
def list_sales(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    status: Optional[str] = Query(None, description="Filter by sale status"),
    customer_id: Optional[int] = Query(None, ge=1, description="Filter by customer ID"),
    start_date: Optional[str] = Query(
        None, description="Filter by start date (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter by end date (YYYY-MM-DD)"
    ),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    search: Optional[str] = Query(None, description="Search term"),
) -> List[Sale]:
    """
    Retrieve sales with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        status: Optional filter by sale status
        customer_id: Optional filter by customer ID
        start_date: Optional filter by start date
        end_date: Optional filter by end date
        payment_status: Optional filter by payment status
        search: Optional search term

    Returns:
        List of sale records
    """
    search_params = SaleSearchParams(
        status=status,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
        payment_status=payment_status,
        search=search,
    )

    sale_service = SaleService(db)
    return sale_service.get_sales(skip=skip, limit=limit, search_params=search_params)


@router.post("/", response_model=Sale, status_code=status.HTTP_201_CREATED)
def create_sale(
    *,
    db: Session = Depends(get_db),
    sale_in: SaleCreate,
    current_user: Any = Depends(get_current_active_user),
) -> Sale:
    """
    Create a new sale.

    Args:
        db: Database session
        sale_in: Sale data for creation
        current_user: Currently authenticated user

    Returns:
        Created sale information

    Raises:
        HTTPException: If sale creation fails due to business rules
    """
    sale_service = SaleService(db)
    try:
        return sale_service.create_sale(sale_in, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{sale_id}", response_model=SaleWithDetails)
def get_sale(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale to retrieve"),
    current_user: Any = Depends(get_current_active_user),
) -> SaleWithDetails:
    """
    Get detailed information about a specific sale.

    Args:
        db: Database session
        sale_id: ID of the sale to retrieve
        current_user: Currently authenticated user

    Returns:
        Sale information with details including items and customer

    Raises:
        HTTPException: If the sale doesn't exist
    """
    sale_service = SaleService(db)
    try:
        return sale_service.get_sale_with_details(sale_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )


@router.put("/{sale_id}", response_model=Sale)
def update_sale(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale to update"),
    sale_in: SaleUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Sale:
    """
    Update a sale.

    Args:
        db: Database session
        sale_id: ID of the sale to update
        sale_in: Updated sale data
        current_user: Currently authenticated user

    Returns:
        Updated sale information

    Raises:
        HTTPException: If the sale doesn't exist or update violates business rules
    """
    sale_service = SaleService(db)
    try:
        return sale_service.update_sale(sale_id, sale_in, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale to delete"),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a sale.

    Args:
        db: Database session
        sale_id: ID of the sale to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the sale doesn't exist or can't be deleted
    """
    sale_service = SaleService(db)
    try:
        sale_service.delete_sale(sale_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{sale_id}/status", response_model=Sale)
def update_sale_status(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    status_update: SaleStatusUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Sale:
    """
    Update a sale's status.

    Args:
        db: Database session
        sale_id: ID of the sale
        status_update: New status data
        current_user: Currently authenticated user

    Returns:
        Updated sale information

    Raises:
        HTTPException: If the sale doesn't exist or status transition is invalid
    """
    sale_service = SaleService(db)
    try:
        return sale_service.update_sale_status(sale_id, status_update, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )
    except InvalidStatusTransitionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{sale_id}/payment", response_model=Sale)
def update_payment_status(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    payment_update: PaymentUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Sale:
    """
    Update a sale's payment status.

    Args:
        db: Database session
        sale_id: ID of the sale
        payment_update: Payment update data
        current_user: Currently authenticated user

    Returns:
        Updated sale information

    Raises:
        HTTPException: If the sale doesn't exist or update fails
    """
    sale_service = SaleService(db)
    try:
        return sale_service.update_payment_status(
            sale_id, payment_update, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{sale_id}/items", response_model=SaleItem, status_code=status.HTTP_201_CREATED
)
def add_sale_item(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    item_in: SaleItemCreate,
    current_user: Any = Depends(get_current_active_user),
) -> SaleItem:
    """
    Add an item to a sale.

    Args:
        db: Database session
        sale_id: ID of the sale
        item_in: Sale item data
        current_user: Currently authenticated user

    Returns:
        Added sale item

    Raises:
        HTTPException: If the sale doesn't exist or item can't be added
    """
    sale_service = SaleService(db)
    try:
        return sale_service.add_sale_item(sale_id, item_in, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{sale_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_sale_item(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    item_id: int = Path(..., ge=1, description="The ID of the item"),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Remove an item from a sale.

    Args:
        db: Database session
        sale_id: ID of the sale
        item_id: ID of the item to remove
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the sale or item doesn't exist
    """
    sale_service = SaleService(db)
    try:
        sale_service.remove_sale_item(sale_id, item_id, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{sale_id}/refund",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
)
def process_sale_refund(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    refund_in: RefundCreate,
    current_user: Any = Depends(get_current_active_user),
) -> RefundResponse:
    """
    Process a refund for a sale.

    Args:
        db: Database session
        sale_id: ID of the sale
        refund_in: Refund data for creation
        current_user: Currently authenticated user

    Returns:
        Created refund information

    Raises:
        HTTPException: If the sale doesn't exist or refund fails
    """
    # Validate that the sale exists
    sale_service = SaleService(db)
    try:
        sale = sale_service.get_by_id(sale_id)
        if not sale:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sale with ID {sale_id} not found",
            )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )

    # Create refund for the sale
    refund_service = RefundService(db)
    try:
        # Ensure the sale_id in the refund data matches the path parameter
        refund_data = refund_in.dict()
        refund_data["sale_id"] = sale_id

        return refund_service.create_refund(refund_data)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{sale_id}/refunds", response_model=List[RefundResponse])
def get_sale_refunds(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    current_user: Any = Depends(get_current_active_user),
) -> List[RefundResponse]:
    """
    Get refund history for a sale.

    Args:
        db: Database session
        sale_id: ID of the sale
        current_user: Currently authenticated user

    Returns:
        List of refunds for the sale

    Raises:
        HTTPException: If the sale doesn't exist
    """
    # Validate that the sale exists
    sale_service = SaleService(db)
    try:
        sale = sale_service.get_by_id(sale_id)
        if not sale:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sale with ID {sale_id} not found",
            )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )

    # Get refunds for the sale
    refund_service = RefundService(db)
    return refund_service.get_refunds_by_sale(sale_id)


@router.post(
    "/{sale_id}/ship",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sale_shipment(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    shipment_in: ShipmentCreate,
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Create a shipment for a sale.

    Args:
        db: Database session
        sale_id: ID of the sale
        shipment_in: Shipment data for creation
        current_user: Currently authenticated user

    Returns:
        Created shipment information

    Raises:
        HTTPException: If the sale doesn't exist or shipment creation fails
    """
    # Validate that the sale exists
    sale_service = SaleService(db)
    try:
        sale = sale_service.get_by_id(sale_id)
        if not sale:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sale with ID {sale_id} not found",
            )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )

    # Create shipment for the sale
    shipment_service = ShipmentService(db)
    try:
        # Ensure the sale_id in the shipment data matches the path parameter
        shipment_data = shipment_in.dict()
        shipment_data["sale_id"] = sale_id

        return shipment_service.create_shipment(shipment_data)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{sale_id}/shipments", response_model=ShipmentResponse)
def get_sale_shipment(
    *,
    db: Session = Depends(get_db),
    sale_id: int = Path(..., ge=1, description="The ID of the sale"),
    current_user: Any = Depends(get_current_active_user),
) -> ShipmentResponse:
    """
    Get shipment history for a sale.

    Args:
        db: Database session
        sale_id: ID of the sale
        current_user: Currently authenticated user

    Returns:
        Shipment for the sale

    Raises:
        HTTPException: If the sale doesn't exist or has no shipment
    """
    # Validate that the sale exists
    sale_service = SaleService(db)
    try:
        sale = sale_service.get_by_id(sale_id)
        if not sale:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sale with ID {sale_id} not found",
            )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale with ID {sale_id} not found",
        )

    # Get shipment for the sale
    shipment_service = ShipmentService(db)
    shipment = shipment_service.get_shipment_by_sale(sale_id)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No shipment found for sale with ID {sale_id}",
        )
    return shipment


@router.post("/import", response_model=List[Sale], status_code=status.HTTP_201_CREATED)
def batch_import_sales(
    *,
    db: Session = Depends(get_db),
    sales_data: List[SaleCreate] = Body(...),
    current_user: Any = Depends(get_current_active_user),
) -> List[Sale]:
    """
    Batch import sales data.

    Args:
        db: Database session
        sales_data: List of sale data for creation
        current_user: Currently authenticated user

    Returns:
        List of created sales

    Raises:
        HTTPException: If batch import fails
    """
    sale_service = SaleService(db)
    created_sales = []
    failed_sales = []

    try:
        # Process each sale in a separate transaction
        for sale_data in sales_data:
            try:
                created_sale = sale_service.create_sale(sale_data.dict())
                created_sales.append(created_sale)
            except Exception as e:
                # Log the error and continue with the next sale
                logger.error(f"Error importing sale: {str(e)}", exc_info=True)
                failed_sales.append({"data": sale_data.dict(), "error": str(e)})

        # If all sales failed, raise an exception
        if len(failed_sales) == len(sales_data):
            raise BusinessRuleException(f"All {len(sales_data)} sales failed to import")

        # If some sales failed, log the failures
        if failed_sales:
            logger.warning(
                f"{len(failed_sales)} out of {len(sales_data)} sales failed to import"
            )

        return created_sales
    except Exception as e:
        # Log the error and raise a generic exception
        logger.error(f"Error in batch import: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch import failed: {str(e)}",
        )
