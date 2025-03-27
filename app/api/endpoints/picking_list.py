# File: app/api/routes/picking_list.py
"""
API endpoints for picking list management in the HideSync system.

This module provides endpoints for creating, retrieving, updating, and managing
picking lists and their items. It supports material collection workflows and
integrates with the project management system.

Endpoints include:
- Create/retrieve/update picking lists
- Add/update/delete picking list items
- Mark items as picked
- Track picking list progress
- Generate picking list reports
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.picking_list import (
    PickingListCreate,
    PickingListUpdate,
    PickingListResponse,
    PickingListDetailResponse,
    PickingListItemCreate,
    PickingListItemUpdate,
    PickingListItemResponse,
    PickingListStatusUpdate,
    PickItemRequest,
    CancelPickingListRequest,
    PickingListReportResponse,
    PickingListStatus,
)
from app.services.picking_list_service import PickingListService
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    BusinessRuleException,
)

router = APIRouter()


# Helper function to create service
def get_picking_list_service(
    session: Session = Depends(deps.get_db),
    current_user: dict = Depends(deps.get_current_user),
) -> PickingListService:
    """
    Create and return a PickingListService instance with dependencies.

    Args:
        session: Database session
        current_user: Current authenticated user

    Returns:
        PickingListService instance
    """
    # Access service registry to get other required services
    # In a real implementation, these would be retrieved from a service registry
    # or dependency injection container
    return PickingListService(
        session=session,
        security_context={"current_user": current_user} if current_user else None,
    )


# Picking List Endpoints


@router.post(
    "/",
    response_model=PickingListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new picking list",
)
def create_picking_list(
    picking_list: PickingListCreate,
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Create a new picking list for a project.

    Creates a picking list to track materials needed for a specific project.
    Optionally includes initial items in the list.

    Args:
        picking_list: Picking list data including project ID and optional items
        service: PickingListService instance

    Returns:
        Created picking list

    Raises:
        HTTPException: If validation fails or referenced entities don't exist
    """
    try:
        result = service.create_picking_list(picking_list.dict())
        return result
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.errors},
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/from-project/{project_id}",
    response_model=PickingListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a picking list from project",
)
def create_picking_list_from_project(
    project_id: int = Path(..., description="ID of the project"),
    assigned_to: Optional[str] = Query(None, description="Person assigned to the list"),
    notes: Optional[str] = Query(None, description="Additional notes"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Automatically create a picking list from a project.

    Generates a picking list with items based on the project's materials requirements.

    Args:
        project_id: ID of the project
        assigned_to: Person assigned to pick the list
        notes: Additional notes
        service: PickingListService instance

    Returns:
        Created picking list

    Raises:
        HTTPException: If project doesn't exist or creation fails
    """
    try:
        result = service.create_picking_list_from_project(
            project_id=str(project_id), assigned_to=assigned_to, notes=notes
        )
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/", response_model=List[PickingListResponse], summary="Get all picking lists"
)
def get_picking_lists(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    status: Optional[PickingListStatus] = Query(None, description="Filter by status"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Get picking lists with optional filtering.

    Retrieves picking lists with pagination and filtering options.

    Args:
        project_id: Optional filter by project ID
        status: Optional filter by status
        assigned_to: Optional filter by assignee
        skip: Number of records to skip (for pagination)
        limit: Maximum records to return
        service: PickingListService instance

    Returns:
        List of picking lists matching the criteria
    """
    try:
        # Determine which repository method to call based on filters
        if project_id:
            return service.get_picking_lists_by_project(str(project_id))
        elif status:
            return service.repository.get_picking_lists_by_status(status, skip, limit)
        elif assigned_to:
            return service.repository.get_picking_lists_by_assignee(
                assigned_to, skip, limit
            )
        else:
            return service.list(skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/active",
    response_model=List[PickingListResponse],
    summary="Get active picking lists",
)
def get_active_picking_lists(
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Get all active (pending or in-progress) picking lists.

    Retrieves picking lists that are not completed or cancelled.

    Args:
        service: PickingListService instance

    Returns:
        List of active picking lists
    """
    try:
        return service.get_active_picking_lists()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{picking_list_id}",
    response_model=PickingListDetailResponse,
    summary="Get picking list details",
)
def get_picking_list(
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Get detailed information about a picking list.

    Retrieves a picking list with its items, project information, and completion statistics.

    Args:
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        Detailed picking list information

    Raises:
        HTTPException: If picking list doesn't exist
    """
    try:
        result = service.get_picking_list_with_details(picking_list_id)
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch(
    "/{picking_list_id}",
    response_model=PickingListResponse,
    summary="Update picking list",
)
def update_picking_list(
    update_data: PickingListUpdate,
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Update a picking list's properties.

    Updates status, assignee, or notes for a picking list.

    Args:
        update_data: Data to update
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        Updated picking list

    Raises:
        HTTPException: If picking list doesn't exist or validation fails
    """
    try:
        result = service.update_picking_list(
            picking_list_id, update_data.dict(exclude_unset=True)
        )
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.errors},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch(
    "/{picking_list_id}/status",
    response_model=PickingListResponse,
    summary="Update picking list status",
)
def update_picking_list_status(
    status_update: PickingListStatusUpdate,
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Update a picking list's status.

    Changes the status of a picking list and optionally adds notes.

    Args:
        status_update: New status and optional notes
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        Updated picking list

    Raises:
        HTTPException: If picking list doesn't exist or status transition is invalid
    """
    try:
        # First update the status
        result = service.update_status(picking_list_id, status_update.status)

        # If completed_by is provided and the status is COMPLETED
        if (
            status_update.status == PickingListStatus.COMPLETED
            and status_update.completed_by
        ):
            update_data = {"assignedTo": status_update.completed_by}
            result = service.update_picking_list(picking_list_id, update_data)

        # If notes are provided
        if status_update.notes:
            # Get existing notes
            existing_notes = (
                result.notes if hasattr(result, "notes") and result.notes else ""
            )
            if existing_notes:
                new_notes = f"{existing_notes}\nStatus update: {status_update.notes}"
            else:
                new_notes = f"Status update: {status_update.notes}"

            update_data = {"notes": new_notes}
            result = service.update_picking_list(picking_list_id, update_data)

        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.errors},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch(
    "/{picking_list_id}/assign",
    response_model=PickingListResponse,
    summary="Assign picking list",
)
def assign_picking_list(
    assigned_to: str = Query(..., description="Person to assign the list to"),
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Assign a picking list to a person.

    Updates the assignee for a picking list.

    Args:
        assigned_to: Person to assign the list to
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        Updated picking list

    Raises:
        HTTPException: If picking list doesn't exist
    """
    try:
        result = service.repository.assign_picking_list(picking_list_id, assigned_to)
        if not result:
            raise EntityNotFoundException("PickingList", picking_list_id)
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/{picking_list_id}/complete",
    response_model=PickingListResponse,
    summary="Mark picking list as complete",
)
def mark_picking_list_complete(
    picking_list_id: str = Path(..., description="ID of the picking list"),
    completed_by: Optional[str] = Query(None, description="Person completing the list"),
    notes: Optional[str] = Query(None, description="Completion notes"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Mark a picking list as completed.

    Changes the status to completed and records who completed it.

    Args:
        picking_list_id: ID of the picking list
        completed_by: Person who completed the list
        notes: Completion notes
        service: PickingListService instance

    Returns:
        Updated picking list

    Raises:
        HTTPException: If picking list doesn't exist
    """
    try:
        result = service.mark_list_completed(picking_list_id, completed_by, notes)
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/{picking_list_id}/cancel",
    response_model=PickingListResponse,
    summary="Cancel picking list",
)
def cancel_picking_list(
    cancel_data: CancelPickingListRequest,
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Cancel a picking list.

    Changes the status to cancelled and records the reason.

    Args:
        cancel_data: Cancellation reason
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        Updated picking list

    Raises:
        HTTPException: If picking list doesn't exist or is completed
    """
    try:
        result = service.cancel_picking_list(picking_list_id, cancel_data.reason)
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{picking_list_id}/report",
    response_model=PickingListReportResponse,
    summary="Generate picking list report",
)
def generate_picking_list_report(
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Generate a comprehensive report for a picking list.

    Creates a report with detailed statistics about the picking list.

    Args:
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        Detailed picking list report

    Raises:
        HTTPException: If picking list doesn't exist
    """
    try:
        result = service.generate_picking_list_report(picking_list_id)
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Picking List Item Endpoints


@router.post(
    "/{picking_list_id}/items",
    response_model=PickingListItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to picking list",
)
def add_picking_list_item(
    item: PickingListItemCreate,
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Add an item to a picking list.

    Adds a material or component to be picked for a project.

    Args:
        item: Item data to add
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        Created picking list item

    Raises:
        HTTPException: If picking list doesn't exist or validation fails
    """
    try:
        result = service.add_item(picking_list_id, item.dict())
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.errors},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{picking_list_id}/items",
    response_model=List[PickingListItemResponse],
    summary="Get picking list items",
)
def get_picking_list_items(
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Get all items in a picking list.

    Retrieves the items with their details.

    Args:
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        List of picking list items

    Raises:
        HTTPException: If picking list doesn't exist
    """
    try:
        result = service.get_items(picking_list_id)
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/{picking_list_id}/items/incomplete",
    response_model=List[PickingListItemResponse],
    summary="Get incomplete items",
)
def get_incomplete_items(
    picking_list_id: str = Path(..., description="ID of the picking list"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Get items that haven't been fully picked yet.

    Retrieves items with pending or partial status.

    Args:
        picking_list_id: ID of the picking list
        service: PickingListService instance

    Returns:
        List of incomplete items

    Raises:
        HTTPException: If picking list doesn't exist
    """
    try:
        result = service.get_incomplete_items(picking_list_id)
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch(
    "/items/{item_id}",
    response_model=PickingListItemResponse,
    summary="Update picking list item",
)
def update_picking_list_item(
    update_data: PickingListItemUpdate,
    item_id: str = Path(..., description="ID of the item"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Update a picking list item.

    Updates quantity picked, status, or notes for an item.

    Args:
        update_data: Data to update
        item_id: ID of the item
        service: PickingListService instance

    Returns:
        Updated picking list item

    Raises:
        HTTPException: If item doesn't exist or validation fails
    """
    try:
        result = service.update_item(item_id, update_data.dict(exclude_unset=True))
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.errors},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/items/{item_id}/pick",
    response_model=PickingListItemResponse,
    summary="Record picked item",
)
def pick_item(
    pick_data: PickItemRequest,
    item_id: str = Path(..., description="ID of the item"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Record a quantity of an item as picked.

    Updates the picked quantity and status for an item.

    Args:
        pick_data: Quantity and optional location/notes
        item_id: ID of the item
        service: PickingListService instance

    Returns:
        Updated picking list item

    Raises:
        HTTPException: If item doesn't exist or validation fails
    """
    try:
        result = service.pick_item(
            item_id=item_id,
            quantity_picked=pick_data.quantity_picked,
            location=pick_data.location,
            notes=pick_data.notes,
        )
        return result
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.errors},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from picking list",
)
def delete_picking_list_item(
    item_id: str = Path(..., description="ID of the item"),
    service: PickingListService = Depends(get_picking_list_service),
):
    """
    Remove an item from a picking list.

    Deletes an item if it hasn't been picked yet.

    Args:
        item_id: ID of the item
        service: PickingListService instance

    Raises:
        HTTPException: If item doesn't exist, has been picked, or deletion fails
    """
    try:
        success = service.delete_item(item_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete item",
            )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
