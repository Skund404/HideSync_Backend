# File: app/api/endpoints/tools.py
"""
Tools API endpoints for HideSync.

This module provides endpoints for managing tools, including
tool information, maintenance, checkouts, and related operations.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.tool import (
    Tool,
    ToolCreate,
    ToolUpdate,
    ToolSearchParams,
    ToolCheckout,
    ToolCheckoutCreate,
    ToolMaintenance,
    ToolMaintenanceCreate,
    ToolMaintenanceUpdate,
    MaintenanceSchedule,
)
from app.services.tool_service import ToolService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    ToolNotAvailableException,
)

router = APIRouter()


@router.get("/", response_model=List[Tool])
def list_tools(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    category: Optional[str] = Query(None, description="Filter by tool category"),
    status: Optional[str] = Query(None, description="Filter by tool status"),
    location: Optional[str] = Query(None, description="Filter by storage location"),
    search: Optional[str] = Query(
        None, description="Search term for name or description"
    ),
) -> List[Tool]:
    """
    Retrieve tools with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        category: Optional filter by tool category
        status: Optional filter by tool status
        location: Optional filter by storage location
        search: Optional search term for name or description

    Returns:
        List of tool records
    """
    search_params = ToolSearchParams(
        category=category, status=status, location=location, search=search
    )

    tool_service = ToolService(db)
    return tool_service.get_tools(skip=skip, limit=limit, search_params=search_params)


@router.post("/", response_model=Tool, status_code=status.HTTP_201_CREATED)
def create_tool(
    *,
    db: Session = Depends(get_db),
    tool_in: ToolCreate,
    current_user: Any = Depends(get_current_active_user),
) -> Tool:
    """
    Create a new tool.

    Args:
        db: Database session
        tool_in: Tool data for creation
        current_user: Currently authenticated user

    Returns:
        Created tool information

    Raises:
        HTTPException: If tool creation fails due to business rules
    """
    tool_service = ToolService(db)
    try:
        return tool_service.create_tool(tool_in, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{tool_id}", response_model=Tool)
def get_tool(
    *,
    db: Session = Depends(get_db),
    tool_id: int = Path(..., ge=1, description="The ID of the tool to retrieve"),
    current_user: Any = Depends(get_current_active_user),
) -> Tool:
    """
    Get detailed information about a specific tool.

    Args:
        db: Database session
        tool_id: ID of the tool to retrieve
        current_user: Currently authenticated user

    Returns:
        Tool information

    Raises:
        HTTPException: If the tool doesn't exist
    """
    tool_service = ToolService(db)
    try:
        return tool_service.get_tool(tool_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )


@router.put("/{tool_id}", response_model=Tool)
def update_tool(
    *,
    db: Session = Depends(get_db),
    tool_id: int = Path(..., ge=1, description="The ID of the tool to update"),
    tool_in: ToolUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Tool:
    """
    Update a tool.

    Args:
        db: Database session
        tool_id: ID of the tool to update
        tool_in: Updated tool data
        current_user: Currently authenticated user

    Returns:
        Updated tool information

    Raises:
        HTTPException: If the tool doesn't exist or update violates business rules
    """
    tool_service = ToolService(db)
    try:
        return tool_service.update_tool(tool_id, tool_in, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(
    *,
    db: Session = Depends(get_db),
    tool_id: int = Path(..., ge=1, description="The ID of the tool to delete"),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a tool.

    Args:
        db: Database session
        tool_id: ID of the tool to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the tool doesn't exist or can't be deleted
    """
    tool_service = ToolService(db)
    try:
        tool_service.delete_tool(tool_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Tool checkouts
@router.get("/checkouts", response_model=List[ToolCheckout])
def list_checkouts(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    status: Optional[str] = Query(None, description="Filter by checkout status"),
    tool_id: Optional[int] = Query(None, ge=1, description="Filter by tool ID"),
    project_id: Optional[int] = Query(None, ge=1, description="Filter by project ID"),
    user_id: Optional[int] = Query(None, ge=1, description="Filter by user ID"),
) -> List[ToolCheckout]:
    """
    Retrieve tool checkouts with optional filtering.

    Args:
        db: Database session
        current_user: Currently authenticated user
        status: Optional filter by checkout status
        tool_id: Optional filter by tool ID
        project_id: Optional filter by project ID
        user_id: Optional filter by user ID

    Returns:
        List of tool checkout records
    """
    tool_service = ToolService(db)
    return tool_service.get_checkouts(
        status=status, tool_id=tool_id, project_id=project_id, user_id=user_id
    )


@router.post(
    "/checkouts", response_model=ToolCheckout, status_code=status.HTTP_201_CREATED
)
def checkout_tool(
    *,
    db: Session = Depends(get_db),
    checkout_in: ToolCheckoutCreate,
    current_user: Any = Depends(get_current_active_user),
) -> ToolCheckout:
    """
    Check out a tool.

    Args:
        db: Database session
        checkout_in: Checkout data
        current_user: Currently authenticated user

    Returns:
        Tool checkout record

    Raises:
        HTTPException: If checkout fails
    """
    tool_service = ToolService(db)
    try:
        return tool_service.checkout_tool(checkout_in, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ToolNotAvailableException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/checkouts/{checkout_id}/return", response_model=ToolCheckout)
def return_tool(
    *,
    db: Session = Depends(get_db),
    checkout_id: int = Path(..., ge=1, description="The ID of the checkout"),
    condition: Optional[str] = Query(
        None, description="Condition of the tool upon return"
    ),
    notes: Optional[str] = Query(None, description="Notes about the return"),
    current_user: Any = Depends(get_current_active_user),
) -> ToolCheckout:
    """
    Return a checked out tool.

    Args:
        db: Database session
        checkout_id: ID of the checkout
        condition: Optional condition of the tool upon return
        notes: Optional notes about the return
        current_user: Currently authenticated user

    Returns:
        Updated tool checkout record

    Raises:
        HTTPException: If return fails
    """
    tool_service = ToolService(db)
    try:
        return tool_service.return_tool(checkout_id, condition, notes, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkout with ID {checkout_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Tool maintenance
@router.get("/maintenance", response_model=List[ToolMaintenance])
def list_maintenance(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    status: Optional[str] = Query(None, description="Filter by maintenance status"),
    tool_id: Optional[int] = Query(None, ge=1, description="Filter by tool ID"),
    upcoming_only: bool = Query(False, description="Show only upcoming maintenance"),
) -> List[ToolMaintenance]:
    """
    Retrieve tool maintenance records with optional filtering.

    Args:
        db: Database session
        current_user: Currently authenticated user
        status: Optional filter by maintenance status
        tool_id: Optional filter by tool ID
        upcoming_only: Filter to show only upcoming maintenance

    Returns:
        List of tool maintenance records
    """
    tool_service = ToolService(db)
    return tool_service.get_maintenance_records(
        status=status, tool_id=tool_id, upcoming_only=upcoming_only
    )


@router.post(
    "/maintenance", response_model=ToolMaintenance, status_code=status.HTTP_201_CREATED
)
def create_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_in: ToolMaintenanceCreate,
    current_user: Any = Depends(get_current_active_user),
) -> ToolMaintenance:
    """
    Create a tool maintenance record.

    Args:
        db: Database session
        maintenance_in: Maintenance data
        current_user: Currently authenticated user

    Returns:
        Created maintenance record

    Raises:
        HTTPException: If maintenance creation fails
    """
    tool_service = ToolService(db)
    try:
        return tool_service.create_maintenance(maintenance_in, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {maintenance_in.tool_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/maintenance/{maintenance_id}", response_model=ToolMaintenance)
def update_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_id: int = Path(
        ..., ge=1, description="The ID of the maintenance record"
    ),
    maintenance_in: ToolMaintenanceUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> ToolMaintenance:
    """
    Update a tool maintenance record.

    Args:
        db: Database session
        maintenance_id: ID of the maintenance record
        maintenance_in: Updated maintenance data
        current_user: Currently authenticated user

    Returns:
        Updated maintenance record

    Raises:
        HTTPException: If maintenance update fails
    """
    tool_service = ToolService(db)
    try:
        return tool_service.update_maintenance(
            maintenance_id, maintenance_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance record with ID {maintenance_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/maintenance/schedule", response_model=MaintenanceSchedule)
def get_maintenance_schedule(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> MaintenanceSchedule:
    """
    Get tool maintenance schedule.

    Args:
        db: Database session
        current_user: Currently authenticated user
        start_date: Optional start date
        end_date: Optional end date

    Returns:
        Maintenance schedule
    """
    tool_service = ToolService(db)
    return tool_service.get_maintenance_schedule(start_date, end_date)


@router.post("/maintenance/{maintenance_id}/complete", response_model=ToolMaintenance)
def complete_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_id: int = Path(
        ..., ge=1, description="The ID of the maintenance record"
    ),
    notes: str = Body(
        ..., embed=True, description="Notes about the completed maintenance"
    ),
    cost: Optional[float] = Body(
        None, embed=True, description="Cost of the maintenance"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> ToolMaintenance:
    """
    Mark a maintenance record as completed.

    Args:
        db: Database session
        maintenance_id: ID of the maintenance record
        notes: Notes about the completed maintenance
        cost: Optional cost of the maintenance
        current_user: Currently authenticated user

    Returns:
        Updated maintenance record

    Raises:
        HTTPException: If completion fails
    """
    tool_service = ToolService(db)
    try:
        return tool_service.complete_maintenance(
            maintenance_id, notes, cost, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance record with ID {maintenance_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
