"""
Tools API endpoints for HideSync.

Provides comprehensive tool management functionality including CRUD operations,
checkout/return workflows, maintenance scheduling, and localization support.
Enhanced with translation capabilities for multilingual tool management.
"""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_tool_service, get_localization_service
from app.schemas.tool import (
    Tool, ToolCreate, ToolUpdate, ToolSearchParams, ToolCheckout,
    ToolCheckoutCreate, ToolMaintenance, ToolMaintenanceCreate,
    ToolMaintenanceUpdate, MaintenanceSchedule
)
from app.services.tool_service import ToolService
from app.services.localization_service import LocalizationService
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


# --- Tool CRUD Endpoints ---

@router.get("/", response_model=List[Tool])
def list_tools(
    *,
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None, description="Filter by tool category"),
    status: Optional[str] = Query(None, description="Filter by tool status"),
    location: Optional[str] = Query(None, description="Filter by storage location"),
    search: Optional[str] = Query(None, description="Search term for name or description"),
    locale: Optional[str] = Query(None, description="Locale code for translations (e.g., 'en', 'de')"),
    tool_service: ToolService = Depends(get_tool_service)
) -> List[Tool]:
    """
    Retrieve tools with optional filtering, pagination, and localization.

    The locale parameter enables translation of tool fields to the specified language.
    If no locale is provided, original field values are returned.
    """
    logger.info(f"User {current_user.id} listing tools with locale: {locale}")
    search_params = ToolSearchParams(category=category, status=status, location=location, search=search)

    try:
        if locale:
            tools = tool_service.get_tools_with_locale(
                skip=skip, limit=limit, search_params=search_params, locale=locale
            )
        else:
            tools = tool_service.get_tools(skip=skip, limit=limit, search_params=search_params)

        logger.info(f"Found {len(tools)} tools for user {current_user.id}")
        return tools
    except ValidationException as e:
        logger.warning(f"Validation error listing tools: {e}")
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing tools: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving tools.")


@router.post("/", response_model=Tool, status_code=HTTP_201_CREATED)
def create_tool(
    *,
    tool_in: ToolCreate,
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> Tool:
    """Create a new tool."""
    logger.info(f"User {current_user.id} creating tool: {tool_in.name}")
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
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating tool.")


@router.get("/{tool_id}", response_model=Tool)
def get_tool(
    *,
    tool_id: int = Path(..., ge=1, description="Tool ID"),
    locale: Optional[str] = Query(None, description="Locale code for translations (e.g., 'en', 'de')"),
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> Tool:
    """
    Get detailed information about a specific tool with optional localization.

    The locale parameter enables translation of tool fields to the specified language.
    If no locale is provided, original field values are returned.
    """
    logger.info(f"User {current_user.id} getting tool ID {tool_id} with locale: {locale}")

    try:
        if locale:
            tool = tool_service.get_tool_with_locale(tool_id, locale=locale)
        else:
            tool = tool_service.get_tool(tool_id)

        logger.info(f"Retrieved tool {tool_id}")
        return tool
    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting tool {tool_id}: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving tool.")


@router.put("/{tool_id}", response_model=Tool)
def update_tool(
    *,
    tool_id: int = Path(..., ge=1, description="Tool ID"),
    tool_in: ToolUpdate,
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> Tool:
    """Update a tool."""
    logger.info(f"User {current_user.id} updating tool ID {tool_id}")
    update_data = tool_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="No update data.")

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
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating tool.")


@router.delete("/{tool_id}", status_code=HTTP_204_NO_CONTENT)
def delete_tool(
    *,
    tool_id: int = Path(..., ge=1, description="Tool ID"),
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> None:
    """Delete a tool."""
    logger.info(f"User {current_user.id} deleting tool ID {tool_id}")

    try:
        tool_service.delete_tool(tool_id, current_user.id)
        logger.info(f"Tool {tool_id} deleted")
    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting tool {tool_id}: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error deleting tool.")


# --- Checkout Endpoints ---

@router.get("/checkouts", response_model=List[ToolCheckout])
def list_checkouts(
    *,
    current_user: Any = Depends(get_current_active_user),
    status: Optional[str] = Query(None, description="Filter by checkout status"),
    tool_id: Optional[int] = Query(None, ge=1, description="Filter by tool ID"),
    project_id: Optional[int] = Query(None, ge=1, description="Filter by project ID"),
    user_id: Optional[int] = Query(None, ge=1, description="Filter by user ID"),
    locale: Optional[str] = Query(None, description="Locale code for translations"),
    tool_service: ToolService = Depends(get_tool_service)
) -> List[ToolCheckout]:
    """Retrieve tool checkouts with optional filtering and localization."""
    logger.info(f"User {current_user.id} listing checkouts with locale: {locale}")

    try:
        if locale:
            checkouts = tool_service.get_checkouts_with_locale(
                status=status, tool_id=tool_id, project_id=project_id,
                user_id=user_id, locale=locale
            )
        else:
            checkouts = tool_service.get_checkouts(
                status=status, tool_id=tool_id, project_id=project_id, user_id=user_id
            )

        logger.info(f"Found {len(checkouts)} checkouts")
        return checkouts
    except Exception as e:
        logger.error(f"Unexpected error listing checkouts: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving checkouts.")


@router.post("/checkouts", response_model=ToolCheckout, status_code=HTTP_201_CREATED)
def checkout_tool(
    *,
    checkout_in: ToolCheckoutCreate,
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> ToolCheckout:
    """Check out a tool."""
    logger.info(f"User {current_user.id} checking out tool ID {checkout_in.tool_id}")
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
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error during checkout.")


@router.put("/checkouts/{checkout_id}/return", response_model=ToolCheckout)
def return_tool(
    *,
    checkout_id: int = Path(..., ge=1, description="Checkout ID"),
    condition: Optional[str] = Body(None, embed=True, description="Tool condition after return"),
    notes: Optional[str] = Body(None, embed=True, description="Return notes or issues"),
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> ToolCheckout:
    """Return a checked out tool."""
    logger.info(f"User {current_user.id} returning checkout ID {checkout_id}")
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
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error during tool return.")


# --- Maintenance Endpoints ---

@router.get("/maintenance", response_model=List[ToolMaintenance])
def list_maintenance(
    *,
    current_user: Any = Depends(get_current_active_user),
    status: Optional[str] = Query(None, description="Filter by maintenance status"),
    tool_id: Optional[int] = Query(None, ge=1, description="Filter by tool ID"),
    upcoming_only: bool = Query(False, description="Show only upcoming maintenance"),
    locale: Optional[str] = Query(None, description="Locale code for translations"),
    tool_service: ToolService = Depends(get_tool_service)
) -> List[ToolMaintenance]:
    """Retrieve tool maintenance records with optional filtering and localization."""
    logger.info(f"User {current_user.id} listing maintenance records with locale: {locale}")

    try:
        if locale:
            maintenance_records = tool_service.get_maintenance_records_with_locale(
                status=status, tool_id=tool_id, upcoming_only=upcoming_only, locale=locale
            )
        else:
            maintenance_records = tool_service.get_maintenance_records(
                status=status, tool_id=tool_id, upcoming_only=upcoming_only
            )

        logger.info(f"Found {len(maintenance_records)} maintenance records")
        return maintenance_records
    except Exception as e:
        logger.error(f"Unexpected error listing maintenance: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving maintenance.")


@router.get("/maintenance/schedule", response_model=MaintenanceSchedule)
def get_maintenance_schedule(
    *,
    current_user: Any = Depends(get_current_active_user),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    tool_service: ToolService = Depends(get_tool_service)
) -> MaintenanceSchedule:
    """Get tool maintenance schedule."""
    logger.info(f"User {current_user.id} getting maintenance schedule...")

    try:
        schedule = tool_service.get_maintenance_schedule(start_date, end_date)
        logger.info("Retrieved maintenance schedule")
        return schedule
    except ValidationException as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting maintenance schedule: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving schedule.")


@router.post("/maintenance", response_model=ToolMaintenance, status_code=HTTP_201_CREATED)
def create_maintenance(
    *,
    maintenance_in: ToolMaintenanceCreate,
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> ToolMaintenance:
    """Create a tool maintenance record."""
    logger.info(f"User {current_user.id} creating maintenance for tool ID {maintenance_in.tool_id}")
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
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating maintenance record.")


@router.put("/maintenance/{maintenance_id}", response_model=ToolMaintenance)
def update_maintenance(
    *,
    maintenance_id: int = Path(..., ge=1, description="Maintenance ID"),
    maintenance_in: ToolMaintenanceUpdate,
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> ToolMaintenance:
    """Update a tool maintenance record."""
    logger.info(f"User {current_user.id} updating maintenance ID {maintenance_id}")
    update_data = maintenance_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="No update data.")

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
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating maintenance.")


@router.post("/maintenance/{maintenance_id}/complete", response_model=ToolMaintenance)
def complete_maintenance(
    *,
    maintenance_id: int = Path(..., ge=1, description="Maintenance ID"),
    notes: str = Body(..., embed=True, description="Completion notes"),
    cost: Optional[float] = Body(None, embed=True, ge=0, description="Maintenance cost"),
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> ToolMaintenance:
    """Mark a maintenance record as completed."""
    logger.info(f"User {current_user.id} completing maintenance ID {maintenance_id}")
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
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error completing maintenance.")


@router.delete("/maintenance/{maintenance_id}", status_code=HTTP_204_NO_CONTENT)
def delete_maintenance(
    *,
    maintenance_id: int = Path(..., ge=1, description="Maintenance ID"),
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
) -> None:
    """Delete a maintenance record."""
    logger.info(f"User {current_user.id} deleting maintenance ID {maintenance_id}")

    try:
        tool_service.delete_maintenance_record(maintenance_id, current_user.id)
        logger.info(f"Maintenance {maintenance_id} deleted")
    except (MaintenanceNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting maintenance {maintenance_id}: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error deleting maintenance.")


# --- Translation Endpoints ---

@router.get("/{tool_id}/translations/{locale}")
def get_tool_translations(
    tool_id: int = Path(..., ge=1, description="Tool ID"),
    locale: str = Path(..., description="Locale code (e.g., 'en', 'de')"),
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
):
    """Get all translations for a tool in specific locale."""
    logger.info(f"User {current_user.id} getting translations for tool {tool_id} in locale {locale}")

    try:
        translations = tool_service.get_tool_localized_fields(tool_id, locale)
        return {
            "tool_id": tool_id,
            "locale": locale,
            "translations": translations
        }
    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting tool translations: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving translations.")


@router.post("/{tool_id}/translations")
def create_tool_translation(
    tool_id: int = Path(..., ge=1, description="Tool ID"),
    translation_request: dict = Body(..., example={
        "locale": "de",
        "field_name": "name",
        "translated_value": "Deutscher Werkzeugname"
    }),
    current_user: Any = Depends(get_current_active_user),
    tool_service: ToolService = Depends(get_tool_service)
):
    """Create or update translation for a tool field."""
    logger.info(f"User {current_user.id} creating translation for tool {tool_id}")

    try:
        # Validate required fields
        required_fields = ["locale", "field_name", "translated_value"]
        if not all(k in translation_request for k in required_fields):
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(required_fields)}"
            )

        success = tool_service.create_tool_translation(
            tool_id=tool_id,
            locale=translation_request["locale"],
            field_name=translation_request["field_name"],
            translated_value=translation_request["translated_value"],
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Failed to create translation")

        logger.info(f"Translation created for tool {tool_id}")
        return {"message": "Translation created successfully"}

    except (ToolNotFoundException, EntityNotFoundException) as e:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error creating tool translation: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating translation.")


@router.get("/{tool_id}/translations")
def get_all_tool_translations(
    tool_id: int = Path(..., ge=1, description="Tool ID"),
    current_user: Any = Depends(get_current_active_user),
    localization_service: LocalizationService = Depends(get_localization_service)
):
    """Get all available translations for a tool across all locales."""
    logger.info(f"User {current_user.id} getting all translations for tool {tool_id}")

    try:
        all_translations = localization_service.get_all_translations_for_entity(
            entity_type="tool",
            entity_id=tool_id
        )
        return {
            "tool_id": tool_id,
            "translations": all_translations
        }
    except Exception as e:
        logger.error(f"Error getting all tool translations: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving translations.")


# --- Maintenance Translation Endpoints ---

@router.get("/maintenance/{maintenance_id}/translations/{locale}")
def get_maintenance_translations(
    maintenance_id: int = Path(..., ge=1, description="Maintenance ID"),
    locale: str = Path(..., description="Locale code"),
    current_user: Any = Depends(get_current_active_user),
    localization_service: LocalizationService = Depends(get_localization_service)
):
    """Get all translations for a maintenance record in specific locale."""
    try:
        translations = localization_service.get_translations_for_entity_by_locale(
            entity_type="tool_maintenance",
            entity_id=maintenance_id,
            locale=locale
        )
        return {
            "maintenance_id": maintenance_id,
            "locale": locale,
            "translations": translations
        }
    except Exception as e:
        logger.error(f"Error getting maintenance translations: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving translations.")


@router.post("/maintenance/{maintenance_id}/translations")
def create_maintenance_translation(
    maintenance_id: int = Path(..., ge=1, description="Maintenance ID"),
    translation_request: dict = Body(..., example={
        "locale": "de",
        "field_name": "details",
        "translated_value": "Deutsche Wartungsdetails"
    }),
    current_user: Any = Depends(get_current_active_user),
    localization_service: LocalizationService = Depends(get_localization_service)
):
    """Create or update translation for a maintenance field."""
    try:
        # Validate required fields
        required_fields = ["locale", "field_name", "translated_value"]
        if not all(k in translation_request for k in required_fields):
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(required_fields)}"
            )

        localization_service.create_or_update_translation(
            entity_type="tool_maintenance",
            entity_id=maintenance_id,
            locale=translation_request["locale"],
            field_name=translation_request["field_name"],
            translated_value=translation_request["translated_value"],
            user_id=current_user.id
        )

        return {"message": "Translation created successfully"}

    except Exception as e:
        logger.error(f"Error creating maintenance translation: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating translation.")


# --- Checkout Translation Endpoints ---

@router.get("/checkouts/{checkout_id}/translations/{locale}")
def get_checkout_translations(
    checkout_id: int = Path(..., ge=1, description="Checkout ID"),
    locale: str = Path(..., description="Locale code"),
    current_user: Any = Depends(get_current_active_user),
    localization_service: LocalizationService = Depends(get_localization_service)
):
    """Get all translations for a checkout record in specific locale."""
    try:
        translations = localization_service.get_translations_for_entity_by_locale(
            entity_type="tool_checkout",
            entity_id=checkout_id,
            locale=locale
        )
        return {
            "checkout_id": checkout_id,
            "locale": locale,
            "translations": translations
        }
    except Exception as e:
        logger.error(f"Error getting checkout translations: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving translations.")


@router.post("/checkouts/{checkout_id}/translations")
def create_checkout_translation(
    checkout_id: int = Path(..., ge=1, description="Checkout ID"),
    translation_request: dict = Body(..., example={
        "locale": "de",
        "field_name": "notes",
        "translated_value": "Deutsche Checkout-Notizen"
    }),
    current_user: Any = Depends(get_current_active_user),
    localization_service: LocalizationService = Depends(get_localization_service)
):
    """Create or update translation for a checkout field."""
    try:
        # Validate required fields
        required_fields = ["locale", "field_name", "translated_value"]
        if not all(k in translation_request for k in required_fields):
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(required_fields)}"
            )

        localization_service.create_or_update_translation(
            entity_type="tool_checkout",
            entity_id=checkout_id,
            locale=translation_request["locale"],
            field_name=translation_request["field_name"],
            translated_value=translation_request["translated_value"],
            user_id=current_user.id
        )

        return {"message": "Translation created successfully"}

    except Exception as e:
        logger.error(f"Error creating checkout translation: {e}", exc_info=True)
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating translation.")