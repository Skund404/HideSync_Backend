"""
Tools API endpoints for HideSync.
... (rest of docstring) ...
"""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
# from fastapi import status # Import directly or use integer codes
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.tool import (
    Tool, ToolCreate, ToolUpdate, ToolSearchParams, ToolCheckout,
    ToolCheckoutCreate, ToolMaintenance, ToolMaintenanceCreate,
    ToolMaintenanceUpdate, MaintenanceSchedule
)
from app.services.tool_service import ToolService
from app.core.exceptions import (
    EntityNotFoundException, BusinessRuleException, ToolNotAvailableException,
    ValidationException, ToolNotFoundException, CheckoutNotFoundException,
    MaintenanceNotFoundException, InvalidStatusTransitionException
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Define HTTP status codes as integers
HTTP_400_BAD_REQUEST = 400
HTTP_404_NOT_FOUND = 404
HTTP_500_INTERNAL_SERVER_ERROR = 500
HTTP_201_CREATED = 201
HTTP_204_NO_CONTENT = 204


# --- Endpoints ---

@router.get("/", response_model=List[Tool])
def list_tools(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None), status: Optional[str] = Query(None),
    location: Optional[str] = Query(None), search: Optional[str] = Query(None)
) -> List[Tool]:
    """ Retrieve tools with optional filtering and pagination. """
    # ... (logging and search_params setup) ...
    logger.info(f"User {current_user.id} listing tools...")
    search_params = ToolSearchParams(category=category, status=status, location=location, search=search)
    tool_service = ToolService(db)
    try:
        tools = tool_service.get_tools(skip=skip, limit=limit, search_params=search_params)
        logger.info(f"Found {len(tools)} tools for user {current_user.id}")
        return tools
    except ValidationException as e:
        logger.warning(f"Validation error listing tools: {e}")
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing tools: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving tools.")


@router.post("/", response_model=Tool, status_code=HTTP_201_CREATED)
def create_tool(
    *,
    db: Session = Depends(get_db),
    tool_in: ToolCreate,
    current_user: Any = Depends(get_current_active_user)
) -> Tool:
    """ Create a new tool. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} creating tool: {tool_in.name}")
    tool_service = ToolService(db)
    create_data = tool_in.model_dump(exclude_unset=True)
    try:
        created_tool_obj = tool_service.create_tool(create_data, current_user.id)
        logger.info(f"Tool {created_tool_obj.id} created by user {current_user.id}")
        return created_tool_obj
    except (BusinessRuleException, ValidationException) as e:
        logger.warning(f"Failed to create tool '{tool_in.name}': {e}")
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating tool '{tool_in.name}': {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating tool.")


@router.get("/checkouts", response_model=List[ToolCheckout])
def list_checkouts(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    status: Optional[str] = Query(None), tool_id: Optional[int] = Query(None, ge=1),
    project_id: Optional[int] = Query(None, ge=1), user_id: Optional[int] = Query(None, ge=1)
) -> List[ToolCheckout]:
    """ Retrieve tool checkouts with optional filtering. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} listing checkouts...")
    tool_service = ToolService(db)
    try:
        checkouts = tool_service.get_checkouts(status=status, tool_id=tool_id, project_id=project_id, user_id=user_id)
        logger.info(f"Found {len(checkouts)} checkouts")
        return checkouts
    except Exception as e:
        logger.error(f"Unexpected error listing checkouts: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving checkouts.")


@router.post("/checkouts", response_model=ToolCheckout, status_code=HTTP_201_CREATED)
def checkout_tool(
    *,
    db: Session = Depends(get_db),
    checkout_in: ToolCheckoutCreate,
    current_user: Any = Depends(get_current_active_user)
) -> ToolCheckout:
    """ Check out a tool. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} checking out tool ID {checkout_in.tool_id}")
    tool_service = ToolService(db)
    checkout_data = checkout_in.model_dump(exclude_unset=True)
    try:
        created_checkout_obj = tool_service.checkout_tool(checkout_data, current_user.id)
        logger.info(f"Tool {checkout_in.tool_id} checked out (ID: {created_checkout_obj.id})")
        return created_checkout_obj
    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except ToolNotAvailableException as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except (BusinessRuleException, ValidationException) as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error checking out tool {checkout_in.tool_id}: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error during checkout.")


@router.put("/checkouts/{checkout_id}/return", response_model=ToolCheckout)
def return_tool(
    *,
    db: Session = Depends(get_db),
    checkout_id: int = Path(..., ge=1),
    condition: Optional[str] = Body(None, embed=True),
    notes: Optional[str] = Body(None, embed=True),
    current_user: Any = Depends(get_current_active_user)
) -> ToolCheckout:
    """ Return a checked out tool. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} returning checkout ID {checkout_id}")
    tool_service = ToolService(db)
    return_data = {"condition_after": condition, "issue_description": notes}
    return_data = {k: v for k, v in return_data.items() if v is not None}
    try:
        updated_checkout_obj = tool_service.return_tool(checkout_id, return_data, current_user.id)
        logger.info(f"Checkout ID {checkout_id} returned successfully")
        return updated_checkout_obj
    except (CheckoutNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except (BusinessRuleException, ValidationException) as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error returning checkout {checkout_id}: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error during tool return.")


@router.get("/maintenance", response_model=List[ToolMaintenance])
def list_maintenance(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    status: Optional[str] = Query(None), tool_id: Optional[int] = Query(None, ge=1),
    upcoming_only: bool = Query(False)
) -> List[ToolMaintenance]:
    """ Retrieve tool maintenance records with optional filtering. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} listing maintenance records...")
    tool_service = ToolService(db)
    try:
        maintenance_records = tool_service.get_maintenance_records(status=status, tool_id=tool_id, upcoming_only=upcoming_only)
        logger.info(f"Found {len(maintenance_records)} maintenance records")
        return maintenance_records
    except Exception as e:
        logger.error(f"Unexpected error listing maintenance: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving maintenance.")


@router.get("/maintenance/schedule", response_model=MaintenanceSchedule)
def get_maintenance_schedule(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)
) -> MaintenanceSchedule:
    """ Get tool maintenance schedule. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} getting maintenance schedule...")
    tool_service = ToolService(db)
    try:
        schedule = tool_service.get_maintenance_schedule(start_date, end_date)
        logger.info("Retrieved maintenance schedule")
        return schedule
    except ValidationException as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting maintenance schedule: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving schedule.")


@router.post("/maintenance", response_model=ToolMaintenance, status_code=HTTP_201_CREATED)
def create_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_in: ToolMaintenanceCreate,
    current_user: Any = Depends(get_current_active_user)
) -> ToolMaintenance:
    """ Create a tool maintenance record. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} creating maintenance for tool ID {maintenance_in.tool_id}")
    tool_service = ToolService(db)
    maintenance_data = maintenance_in.model_dump(exclude_unset=True)
    try:
        created_maint_obj = tool_service.create_maintenance(maintenance_data, current_user.id)
        logger.info(f"Maintenance record {created_maint_obj.id} created")
        return created_maint_obj
    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except (BusinessRuleException, ValidationException) as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating maintenance for tool {maintenance_in.tool_id}: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating maintenance record.")


@router.put("/maintenance/{maintenance_id}", response_model=ToolMaintenance)
def update_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_id: int = Path(..., ge=1),
    maintenance_in: ToolMaintenanceUpdate,
    current_user: Any = Depends(get_current_active_user)
) -> ToolMaintenance:
    """ Update a tool maintenance record. """
    # ... (logging and input validation) ...
    logger.info(f"User {current_user.id} updating maintenance ID {maintenance_id}")
    tool_service = ToolService(db)
    update_data = maintenance_in.model_dump(exclude_unset=True)
    if not update_data: raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="No update data.")
    try:
        updated_maint_obj = tool_service.update_maintenance(maintenance_id, update_data, current_user.id)
        logger.info(f"Maintenance record {maintenance_id} updated")
        return updated_maint_obj
    except (MaintenanceNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except (BusinessRuleException, ValidationException) as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating maintenance {maintenance_id}: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating maintenance.")


@router.post("/maintenance/{maintenance_id}/complete", response_model=ToolMaintenance)
def complete_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_id: int = Path(..., ge=1),
    notes: str = Body(..., embed=True),
    cost: Optional[float] = Body(None, embed=True, ge=0),
    current_user: Any = Depends(get_current_active_user)
) -> ToolMaintenance:
    """ Mark a maintenance record as completed. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} completing maintenance ID {maintenance_id}")
    tool_service = ToolService(db)
    completion_data = {"details": notes, "cost": cost}
    completion_data = {k: v for k, v in completion_data.items() if v is not None}
    try:
        completed_maint_obj = tool_service.complete_maintenance(maintenance_id, completion_data, current_user.id)
        logger.info(f"Maintenance record {maintenance_id} completed")
        return completed_maint_obj
    except (MaintenanceNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except (BusinessRuleException, ValidationException) as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error completing maintenance {maintenance_id}: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error completing maintenance.")


@router.get("/{tool_id}", response_model=Tool)
def get_tool(
    *,
    db: Session = Depends(get_db),
    tool_id: int = Path(..., ge=1),
    current_user: Any = Depends(get_current_active_user)
) -> Tool:
    """ Get detailed information about a specific tool. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} getting tool ID {tool_id}")
    tool_service = ToolService(db)
    try:
        tool = tool_service.get_tool(tool_id)
        logger.info(f"Retrieved tool {tool_id}")
        return tool
    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting tool {tool_id}: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving tool.")


@router.put("/{tool_id}", response_model=Tool)
def update_tool(
    *,
    db: Session = Depends(get_db),
    tool_id: int = Path(..., ge=1),
    tool_in: ToolUpdate,
    current_user: Any = Depends(get_current_active_user)
) -> Tool:
    """ Update a tool. """
    # ... (logging and input validation) ...
    logger.info(f"User {current_user.id} updating tool ID {tool_id}")
    tool_service = ToolService(db)
    update_data = tool_in.model_dump(exclude_unset=True)
    if not update_data: raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="No update data.")
    try:
        updated_tool_obj = tool_service.update_tool(tool_id, update_data, current_user.id)
        logger.info(f"Tool {tool_id} updated")
        return updated_tool_obj
    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except (BusinessRuleException, ValidationException, InvalidStatusTransitionException) as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating tool {tool_id}: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating tool.")

@router.delete("/maintenance/{maintenance_id}", status_code=HTTP_204_NO_CONTENT)
def delete_maintenance(
    *,
    db: Session = Depends(get_db),
    maintenance_id: int = Path(..., ge=1),
    current_user: Any = Depends(get_current_active_user)
) -> None:
    logger.info(f"User {current_user.id} deleting maintenance ID {maintenance_id}")
    tool_service = ToolService(db)
    try:
        tool_service.delete_maintenance_record(maintenance_id, current_user.id)
        logger.info(f"Maintenance {maintenance_id} deleted")
        # No return content needed
    except (MaintenanceNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting maintenance {maintenance_id}: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error deleting maintenance.")


@router.delete("/{tool_id}", status_code=HTTP_204_NO_CONTENT)
def delete_tool(
    *,
    db: Session = Depends(get_db),
    tool_id: int = Path(..., ge=1),
    current_user: Any = Depends(get_current_active_user)
) -> None:
    """ Delete a tool. """
    # ... (logging) ...
    logger.info(f"User {current_user.id} deleting tool ID {tool_id}")
    tool_service = ToolService(db)
    try:
        tool_service.delete_tool(tool_id, current_user.id)
        logger.info(f"Tool {tool_id} deleted")
        # No return content needed
    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting tool {tool_id}: {e}", exc_info=True)
        # FIX: Use integer status code
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error deleting tool.")