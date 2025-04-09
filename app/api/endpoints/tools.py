"""
Tools API endpoints for HideSync.

This module provides endpoints for managing tools, including
tool information, maintenance, checkouts, and related operations.
"""

import logging  # Import logging
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
    ValidationException,  # Import ValidationException
)

router = APIRouter()
logger = logging.getLogger(__name__)  # Add logger


# Root routes first
@router.get("/", response_model=List[Tool])
def list_tools(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),  # Required for authentication
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
    logger.info(
        f"User {current_user.id} listing tools with params: skip={skip}, limit={limit}, category={category}, status={status}, location={location}, search={search}"
    )
    search_params = ToolSearchParams(
        category=category, status=status, location=location, search=search
    )

    tool_service = ToolService(db)
    try:
        tools = tool_service.get_tools(
            skip=skip, limit=limit, search_params=search_params
        )
        logger.info(f"Found {len(tools)} tools for user {current_user.id}")
        return tools
    except ValidationException as e:
        logger.warning(
            f"Validation error during tool listing for user {current_user.id}: {e}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error listing tools for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving tools.",
        )


@router.post("/", response_model=Tool, status_code=status.HTTP_201_CREATED)
def create_tool(
    *,
    db: Session = Depends(get_db),
    tool_in: ToolCreate,  # Receive Pydantic model
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
        HTTPException: If tool creation fails due to business rules or validation
    """
    logger.info(f"User {current_user.id} attempting to create tool: {tool_in.name}")
    tool_service = ToolService(db)
    # Convert Pydantic model to dict for the service layer
    create_data = tool_in.model_dump()
    try:
        # Pass the dictionary and the user's ID to the service method
        created_tool_obj = tool_service.create_tool(create_data, current_user.id)
        logger.info(
            f"Tool {created_tool_obj.id} created successfully by user {current_user.id}"
        )
        # FastAPI handles converting the SQLAlchemy object back to the response_model
        return created_tool_obj
    except (BusinessRuleException, ValidationException) as e:
        logger.warning(
            f"Failed to create tool '{tool_in.name}' by user {current_user.id}: {e}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error creating tool '{tool_in.name}' by user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the tool.",
        )


# Tool checkouts routes
@router.get("/checkouts", response_model=List[ToolCheckout])
def list_checkouts(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    status: Optional[str] = Query(None, description="Filter by checkout status"),
    tool_id: Optional[int] = Query(None, ge=1, description="Filter by tool ID"),
    project_id: Optional[int] = Query(None, ge=1, description="Filter by project ID"),
    user_id: Optional[int] = Query(
        None, ge=1, description="Filter by user ID (who checked out)"
    ),  # Clarified user_id meaning
) -> List[ToolCheckout]:
    """
    Retrieve tool checkouts with optional filtering.

    Args:
        db: Database session
        current_user: Currently authenticated user
        status: Optional filter by checkout status
        tool_id: Optional filter by tool ID
        project_id: Optional filter by project ID
        user_id: Optional filter by user ID (who checked out)

    Returns:
        List of tool checkout records
    """
    logger.info(
        f"User {current_user.id} listing checkouts with params: status={status}, tool_id={tool_id}, project_id={project_id}, user_id={user_id}"
    )
    tool_service = ToolService(db)
    try:
        checkouts = tool_service.get_checkouts(
            status=status, tool_id=tool_id, project_id=project_id, user_id=user_id
        )
        logger.info(f"Found {len(checkouts)} checkouts for user {current_user.id}")
        return checkouts
    except Exception as e:
        logger.error(
            f"Unexpected error listing checkouts for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving checkouts.",
        )


@router.post(
    "/checkouts", response_model=ToolCheckout, status_code=status.HTTP_201_CREATED
)
def checkout_tool(
    *,
    db: Session = Depends(get_db),
    checkout_in: ToolCheckoutCreate,  # Pydantic model
    current_user: Any = Depends(get_current_active_user),
) -> ToolCheckout:
    """
    Check out a tool.

    Args:
        db: Database session
        checkout_in: Checkout data
        current_user: Currently authenticated user (performing the action)

    Returns:
        Tool checkout record

    Raises:
        HTTPException: If checkout fails
    """
    logger.info(
        f"User {current_user.id} attempting to checkout tool ID {checkout_in.tool_id}"
    )
    tool_service = ToolService(db)
    checkout_data = checkout_in.model_dump()  # Convert to dict
    try:
        # Pass dict and user_id (of the person performing the checkout)
        # Note: checkout_data already contains 'checked_out_by'
        created_checkout_obj = tool_service.checkout_tool(
            checkout_data, current_user.id
        )
        logger.info(
            f"Tool {checkout_in.tool_id} checked out successfully (checkout ID: {created_checkout_obj.id}) by user {current_user.id}"
        )
        return created_checkout_obj
    except EntityNotFoundException as e:
        logger.warning(f"Checkout failed by user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ToolNotAvailableException as e:
        logger.warning(f"Checkout failed by user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (BusinessRuleException, ValidationException) as e:
        logger.warning(f"Checkout failed by user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error checking out tool {checkout_in.tool_id} by user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during checkout.",
        )


@router.put("/checkouts/{checkout_id}/return", response_model=ToolCheckout)
def return_tool(
    *,
    db: Session = Depends(get_db),
    checkout_id: int = Path(..., ge=1, description="The ID of the checkout"),
    # Using Body now for condition/notes for potentially longer text
    condition: Optional[str] = Body(
        None, embed=True, description="Condition of the tool upon return"
    ),
    notes: Optional[str] = Body(
        None, embed=True, description="Notes about the return (e.g., issues)"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> ToolCheckout:
    """
    Return a checked out tool.

    Args:
        db: Database session
        checkout_id: ID of the checkout
        condition: Optional condition of the tool upon return (e.g., GOOD, DAMAGED)
        notes: Optional notes about the return, describing issues if any
        current_user: Currently authenticated user

    Returns:
        Updated tool checkout record

    Raises:
        HTTPException: If return fails
    """
    logger.info(
        f"User {current_user.id} attempting to return checkout ID {checkout_id}"
    )
    tool_service = ToolService(db)
    # Package data for the service layer
    return_data = {
        "condition_after": condition,
        "issue_description": notes,  # Assuming notes describe issues
    }
    # Filter out None values if the service layer prefers only provided fields
    return_data = {k: v for k, v in return_data.items() if v is not None}

    try:
        # Pass checkout_id, data dict, and user_id
        updated_checkout_obj = tool_service.return_tool(
            checkout_id, return_data, current_user.id
        )
        logger.info(
            f"Checkout ID {checkout_id} returned successfully by user {current_user.id}"
        )
        return updated_checkout_obj
    except EntityNotFoundException as e:  # More specific exception
        logger.warning(
            f"Return failed for checkout {checkout_id} by user {current_user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),  # Pass exception message
        )
    except (BusinessRuleException, ValidationException) as e:
        logger.warning(
            f"Return failed for checkout {checkout_id} by user {current_user.id}: {e}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error returning checkout {checkout_id} by user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during tool return.",
        )


# Tool maintenance routes
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
    logger.info(
        f"User {current_user.id} listing maintenance records with params: status={status}, tool_id={tool_id}, upcoming_only={upcoming_only}"
    )
    tool_service = ToolService(db)
    try:
        maintenance_records = tool_service.get_maintenance_records(
            status=status, tool_id=tool_id, upcoming_only=upcoming_only
        )
        logger.info(
            f"Found {len(maintenance_records)} maintenance records for user {current_user.id}"
        )
        return maintenance_records
    except Exception as e:
        logger.error(
            f"Unexpected error listing maintenance for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving maintenance records.",
        )


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
    logger.info(
        f"User {current_user.id} requesting maintenance schedule: start={start_date}, end={end_date}"
    )
    tool_service = ToolService(db)
    try:
        schedule = tool_service.get_maintenance_schedule(start_date, end_date)
        logger.info(f"Retrieved maintenance schedule for user {current_user.id}")
        return schedule  # Assuming service returns the correct Pydantic model
    except ValidationException as e:
        logger.warning(
            f"Validation error getting maintenance schedule for user {current_user.id}: {e}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error getting maintenance schedule for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving maintenance schedule.",
        )


@router.post(
    "/maintenance", response_model=ToolMaintenance, status_code=status.HTTP_201_CREATED
)
def create_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_in: ToolMaintenanceCreate,  # Pydantic model
    current_user: Any = Depends(get_current_active_user),
) -> ToolMaintenance:
    """
    Create a tool maintenance record. Often used to schedule maintenance.

    Args:
        db: Database session
        maintenance_in: Maintenance data
        current_user: Currently authenticated user

    Returns:
        Created maintenance record

    Raises:
        HTTPException: If maintenance creation fails
    """
    logger.info(
        f"User {current_user.id} attempting to create maintenance for tool ID {maintenance_in.tool_id}"
    )
    tool_service = ToolService(db)
    maintenance_data = maintenance_in.model_dump()  # Convert to dict
    try:
        # Pass dict and user_id
        created_maint_obj = tool_service.create_maintenance(
            maintenance_data, current_user.id
        )
        logger.info(
            f"Maintenance record {created_maint_obj.id} created successfully for tool {maintenance_in.tool_id} by user {current_user.id}"
        )
        return created_maint_obj
    except EntityNotFoundException as e:  # e.g., Tool ID doesn't exist
        logger.warning(f"Maintenance creation failed by user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),  # Pass specific error message
        )
    except (BusinessRuleException, ValidationException) as e:
        logger.warning(f"Maintenance creation failed by user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error creating maintenance for tool {maintenance_in.tool_id} by user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the maintenance record.",
        )


@router.put("/maintenance/{maintenance_id}", response_model=ToolMaintenance)
def update_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_id: int = Path(
        ..., ge=1, description="The ID of the maintenance record"
    ),
    maintenance_in: ToolMaintenanceUpdate,  # Pydantic model
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
    logger.info(
        f"User {current_user.id} attempting to update maintenance ID {maintenance_id}"
    )
    tool_service = ToolService(db)
    update_data = maintenance_in.model_dump(
        exclude_unset=True
    )  # Convert to dict, exclude unset fields

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided for maintenance record.",
        )

    try:
        # Pass ID, dict, and user_id
        updated_maint_obj = tool_service.update_maintenance(
            maintenance_id, update_data, current_user.id
        )
        logger.info(
            f"Maintenance record {maintenance_id} updated successfully by user {current_user.id}"
        )
        return updated_maint_obj
    except EntityNotFoundException as e:
        logger.warning(f"Maintenance update failed by user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),  # Pass specific error message
        )
    except (BusinessRuleException, ValidationException) as e:
        logger.warning(f"Maintenance update failed by user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error updating maintenance {maintenance_id} by user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating the maintenance record.",
        )


@router.post("/maintenance/{maintenance_id}/complete", response_model=ToolMaintenance)
def complete_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_id: int = Path(
        ..., ge=1, description="The ID of the maintenance record"
    ),
    # Using Body for potentially longer notes and optional cost
    notes: str = Body(
        ..., embed=True, description="Notes about the completed maintenance"
    ),
    cost: Optional[float] = Body(
        None, embed=True, description="Cost of the maintenance", ge=0  # Add validation
    ),
    # Add condition_after? Assuming 'COMPLETED' implies good condition unless noted otherwise?
    # condition_after: Optional[str] = Body(None, embed=True, description="Condition after completion")
    current_user: Any = Depends(get_current_active_user),
) -> ToolMaintenance:
    """
    Mark a maintenance record as completed.

    Args:
        db: Database session
        maintenance_id: ID of the maintenance record
        notes: Notes about the completed maintenance
        cost: Optional cost of the maintenance
        # condition_after: Optional final condition
        current_user: Currently authenticated user

    Returns:
        Updated maintenance record

    Raises:
        HTTPException: If completion fails
    """
    logger.info(
        f"User {current_user.id} attempting to complete maintenance ID {maintenance_id}"
    )
    tool_service = ToolService(db)
    completion_data = {
        "details": notes,  # Map notes to details field in service? Or add a completion_notes field? Check service method.
        "cost": cost,
        # "condition_after": condition_after # Pass if needed
    }
    # Filter out None values
    completion_data = {k: v for k, v in completion_data.items() if v is not None}

    try:
        # Pass ID, dict, and user_id
        completed_maint_obj = tool_service.complete_maintenance(
            maintenance_id, completion_data, current_user.id
        )
        logger.info(
            f"Maintenance record {maintenance_id} completed successfully by user {current_user.id}"
        )
        return completed_maint_obj
    except EntityNotFoundException as e:
        logger.warning(f"Maintenance completion failed by user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),  # Pass specific error message
        )
    except (BusinessRuleException, ValidationException) as e:
        logger.warning(f"Maintenance completion failed by user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error completing maintenance {maintenance_id} by user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while completing the maintenance record.",
        )


# Tool-specific routes (with ID parameter) come last
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
    logger.info(f"User {current_user.id} requesting details for tool ID {tool_id}")
    tool_service = ToolService(db)
    try:
        tool = tool_service.get_tool(tool_id)  # Use the specific get_tool method
        logger.info(f"Retrieved details for tool {tool_id} for user {current_user.id}")
        return tool
    except EntityNotFoundException as e:
        logger.warning(f"Tool {tool_id} not found for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),  # Use exception message
        )
    except Exception as e:
        logger.error(
            f"Unexpected error getting tool {tool_id} for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving tool details.",
        )


@router.put("/{tool_id}", response_model=Tool)
def update_tool(
    *,
    db: Session = Depends(get_db),
    tool_id: int = Path(..., ge=1, description="The ID of the tool to update"),
    tool_in: ToolUpdate,  # Input is Pydantic model
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
    logger.info(f"User {current_user.id} attempting to update tool ID {tool_id}")
    tool_service = ToolService(db)
    # Convert Pydantic model to dict for the service layer
    update_data = tool_in.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided.",
        )

    try:
        # Pass the dictionary and the user's ID to the service method
        updated_tool_obj = tool_service.update_tool(
            tool_id, update_data, current_user.id
        )
        logger.info(f"Tool {tool_id} updated successfully by user {current_user.id}")
        return updated_tool_obj
    except EntityNotFoundException as e:
        logger.warning(
            f"Update failed for tool {tool_id} by user {current_user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),  # Use exception message
        )
    except (BusinessRuleException, ValidationException) as e:
        logger.warning(
            f"Update failed for tool {tool_id} by user {current_user.id}: {e}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error updating tool {tool_id} by user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating the tool.",
        )


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
    logger.info(f"User {current_user.id} attempting to delete tool ID {tool_id}")
    tool_service = ToolService(db)
    try:
        # Pass user_id to service method for logging/auditing
        tool_service.delete_tool(tool_id, current_user.id)
        logger.info(f"Tool {tool_id} deleted successfully by user {current_user.id}")
        # No return content needed for 204
    except EntityNotFoundException as e:
        logger.warning(
            f"Delete failed for tool {tool_id} by user {current_user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),  # Use exception message
        )
    except (
        BusinessRuleException
    ) as e:  # Catch specific business rule violation (e.g., tool checked out)
        logger.warning(
            f"Delete failed for tool {tool_id} by user {current_user.id}: {e}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error deleting tool {tool_id} by user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while deleting the tool.",
        )
