# File: app/api/endpoints/inventory.py
"""
Inventory API endpoints for HideSync.

This module provides endpoints for managing inventory, including
inventory tracking, transactions, and stock adjustments.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_inventory_service
from app.db.session import get_db
from app.schemas.inventory import (
    Inventory,
    InventoryTransaction,
    InventoryTransactionCreate,
    InventorySearchParams,
    InventoryAdjustment,
    StockLevelReport,
)
from app.services.inventory_service import InventoryService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    StorageLocationNotFoundException,
)
from app.core.exceptions import (
    InsufficientInventoryException as InsufficientQuantityException,
)
from app.schemas.inventory import InventorySummaryResponse
import logging
logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[Inventory])
def list_inventory(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    # RENAMED PARAMETER with ALIAS
    inventory_status: Optional[str] = Query(None, alias="status", description="Filter by inventory status"),
    location: Optional[str] = Query(None, description="Filter by storage location"),
    item_type: Optional[str] = Query(
        None, description="Filter by item type (material/product/tool)"
    ),
    search: Optional[str] = Query(None, description="Search term for item name"),
) -> List[Inventory]:
    """
    Retrieve inventory items with optional filtering and pagination.
    """
    search_params = InventorySearchParams(
        status=inventory_status, # Use renamed parameter
        location=location,
        item_type=item_type,
        search=search
    )

    inventory_service = InventoryService(db)

    try:
        # Ensure the service method calls the NEW repository method (e.g., list_with_filters)
        items = inventory_service.list_inventory_items(
            skip=skip, limit=limit, search_params=search_params
        )
        return items
    except AttributeError as e:
         # This exception should ideally not be hit if the repo method exists
         # But if it does, the status code lookup should now work
         raise HTTPException(
             status_code=status.HTTP_501_NOT_IMPLEMENTED, # status now correctly refers to the imported module
             detail=f"Inventory listing functionality is not fully implemented: {e}"
         )
    except Exception as e:
        # logger.error(f"Error listing inventory: {e}", exc_info=True) # Optional logging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving inventory items."
        )

@router.get(
    "/summary",
    response_model=InventorySummaryResponse,
    summary="Get Inventory Summary",
    description="Retrieves overall inventory statistics.",
    # dependencies=[Depends(PermissionsChecker(["inventory:read", "product:read"]))], # Optional permissions
)
def get_inventory_summary(
    *,
    inventory_service: InventoryService = Depends(get_inventory_service), # Use dependency getter
    current_user: Any = Depends(get_current_active_user),
) -> InventorySummaryResponse:
    """
    Endpoint to retrieve inventory summary statistics.
    """
    try:
        summary_data = inventory_service.get_summary_data()
        return summary_data
    except NotImplementedError as e:
         logger.error(f"Summary endpoint failed: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting inventory summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while calculating the inventory summary.",
        )

@router.get("/transactions", response_model=List[InventoryTransaction])
def list_inventory_transactions(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    item_id: Optional[int] = Query(None, ge=1, description="Filter by item ID"),
    transaction_type: Optional[str] = Query(
        None, description="Filter by transaction type"
    ),
    start_date: Optional[str] = Query(
        None, description="Filter by start date (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter by end date (YYYY-MM-DD)"
    ),
) -> List[InventoryTransaction]:
    """
    Retrieve inventory transactions with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        item_id: Optional filter by item ID
        transaction_type: Optional filter by transaction type
        start_date: Optional filter by start date (YYYY-MM-DD)
        end_date: Optional filter by end date (YYYY-MM-DD)

    Returns:
        List of inventory transaction records
    """
    inventory_service = InventoryService(db)
    return inventory_service.get_inventory_transactions(
        skip=skip,
        limit=limit,
        item_id=item_id,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
    )


@router.post(
    "/transactions",
    response_model=InventoryTransaction,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_transaction(
    *,
    db: Session = Depends(get_db),
    transaction_in: InventoryTransactionCreate,
    current_user: Any = Depends(get_current_active_user),
) -> InventoryTransaction:
    """
    Create a new inventory transaction.

    Args:
        db: Database session
        transaction_in: Transaction data for creation
        current_user: Currently authenticated user

    Returns:
        Created inventory transaction

    Raises:
        HTTPException: If transaction creation fails
    """
    inventory_service = InventoryService(db)
    try:
        return inventory_service.create_transaction(transaction_in, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InsufficientQuantityException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient quantity available for this transaction",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/adjust", response_model=Inventory)
def adjust_inventory(
    *,
    db: Session = Depends(get_db),
    adjustment: InventoryAdjustment,
    current_user: Any = Depends(get_current_active_user),
) -> Inventory:
    """
    Adjust inventory quantity.

    Args:
        db: Database session
        adjustment: Inventory adjustment data
        current_user: Currently authenticated user

    Returns:
        Updated inventory record

    Raises:
        HTTPException: If adjustment fails
    """
    inventory_service = InventoryService(db)
    try:
        return inventory_service.adjust_inventory(adjustment, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Inventory item not found"
        )
    except InsufficientQuantityException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient quantity available for this adjustment",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/transfer", response_model=Inventory)
def transfer_inventory(
    *,
    db: Session = Depends(get_db),
    item_id: int = Body(..., ge=1, embed=True, description="ID of the inventory item"),
    quantity: float = Body(..., gt=0, embed=True, description="Quantity to transfer"),
    source_location: str = Body(..., embed=True, description="Source storage location"),
    target_location: str = Body(..., embed=True, description="Target storage location"),
    notes: Optional[str] = Body(
        None, embed=True, description="Notes for this transfer"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> Inventory:
    """
    Transfer inventory between storage locations.

    Args:
        db: Database session
        item_id: ID of the inventory item
        quantity: Quantity to transfer
        source_location: Source storage location
        target_location: Target storage location
        notes: Optional notes for this transfer
        current_user: Currently authenticated user

    Returns:
        Updated inventory record

    Raises:
        HTTPException: If transfer fails
    """
    inventory_service = InventoryService(db)
    try:
        return inventory_service.transfer_inventory(
            item_id, quantity, source_location, target_location, notes, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item with ID {item_id} not found",
        )
    except StorageLocationNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InsufficientQuantityException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient quantity at source location",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/low-stock", response_model=List[Inventory])
def get_low_stock_items(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    threshold_percentage: Optional[float] = Query(
        20.0, ge=0, le=100, description="Low stock threshold percentage"
    ),
    item_type: Optional[str] = Query(
        None, description="Filter by item type (material/product/tool)"
    ),
) -> List[Inventory]:
    """
    Get items with low stock levels.

    Args:
        db: Database session
        current_user: Currently authenticated user
        threshold_percentage: Low stock threshold percentage
        item_type: Optional filter by item type

    Returns:
        List of low stock inventory records
    """
    inventory_service = InventoryService(db)
    return inventory_service.get_low_stock_items(threshold_percentage, item_type)


@router.get("/report", response_model=StockLevelReport)
def get_stock_level_report(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    item_type: Optional[str] = Query(
        None, description="Filter by item type (material/product/tool)"
    ),
    group_by: Optional[str] = Query(
        "type", description="Group by field (type, location, status)"
    ),
) -> StockLevelReport:
    """
    Get stock level report.

    Args:
        db: Database session
        current_user: Currently authenticated user
        item_type: Optional filter by item type
        group_by: Field to group results by

    Returns:
        Stock level report
    """
    inventory_service = InventoryService(db)
    return inventory_service.get_stock_level_report(item_type, group_by)
