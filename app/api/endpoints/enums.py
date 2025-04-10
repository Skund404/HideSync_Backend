# app/api/endpoints/enums.py
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from sqlalchemy.orm import Session

# --- Project Imports ---
from app.api.deps import ( # Updated imports
    get_db,
    get_current_active_user,
    get_enum_service # <-- Import the service injector
)
from app.services.enum_service import EnumService # For type hinting
from app.db.models.user import User
from app.db.models.dynamic_enum import EnumType # For direct check

# --- Import Schemas ---
from app.schemas.enum import (
    EnumTypeRead,
    EnumValueCreate,
    EnumValueUpdate,
    EnumValueRead,
    EnumTranslationCreate,
    EnumTranslationUpdate,
    EnumTranslationRead,
)

# --- Router Setup ---
router = APIRouter()
logger = logging.getLogger(__name__)
# --- End Router Setup ---


# === Enum Type Endpoints ===

@router.get(
    "/types",
    response_model=List[EnumTypeRead],
    summary="Get All Enum Types",
    description="Retrieves a list of all registered enumeration types defined in the system."
)
def get_enum_types_endpoint(
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to get all registered enum types."""
    logger.info(f"User '{current_user.email}' requested all enum types.")
    types = enum_service.get_enum_types()
    logger.info(f"Returning {len(types)} enum types.")
    return types

# === Enum Value & Translation Endpoints ===

@router.get(
    "/",
    response_model=Dict[str, List[EnumValueRead]],
    summary="Get All Enum Values (All Types)",
    description="Retrieves all values for all enum types, keyed by system_name, with translations for the specified locale."
)
def get_all_enums(
    locale: str = Query("en", description="Locale code for translations (e.g., 'en', 'de')"),
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to get all enum values for a specific locale."""
    logger.info(f"User '{current_user.email}' requested all enum values for locale '{locale}'.")
    all_enums = enum_service.get_all_enums(locale)
    logger.info(f"Returning values for {len(all_enums)} enum types for locale '{locale}'.")
    return all_enums

@router.get(
    "/{enum_system_name}",
    response_model=List[EnumValueRead],
    summary="Get Values for a Specific Enum Type",
    description="Retrieves all active values for a specific enum type identified by its system name, with translations for the specified locale."
)
def get_enum_values_endpoint(
    enum_system_name: str,
    locale: str = Query("en", description="Locale code for translations"),
    db: Session = Depends(get_db), # Keep db session specifically for the direct EnumType check
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to get values for a specific enum type."""
    logger.info(f"User '{current_user.email}' requested values for enum '{enum_system_name}' with locale '{locale}'.")

    # Check if EnumType exists first using the db session directly
    # Alternatively, add a 'check_type_exists' method to EnumService
    enum_type_exists = db.query(EnumType).filter(EnumType.system_name == enum_system_name).first()
    if enum_type_exists is None:
        logger.warning(f"Enum type '{enum_system_name}' not found when requested by user '{current_user.email}'.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Enum type '{enum_system_name}' not found")

    # Fetch values using the injected service
    values = enum_service.get_enum_values(enum_system_name, locale)
    logger.info(f"Returning {len(values)} values for enum '{enum_system_name}' with locale '{locale}'.")
    return values

@router.post(
    "/{enum_system_name}",
    response_model=EnumValueRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a New Enum Value",
    description="Adds a new value to a specific enum type. Requires appropriate permissions."
)
def create_enum_value_endpoint(
    enum_system_name: str,
    enum_value_in: EnumValueCreate,
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to create a new enum value."""
    logger.info(f"User '{current_user.email}' attempting to create value for enum '{enum_system_name}' with code '{enum_value_in.code}'.")
    try:
        created_value_dict = enum_service.create_enum_value(enum_system_name, enum_value_in.model_dump())
        logger.info(f"Successfully created enum value ID {created_value_dict.get('id')} for '{enum_system_name}'.")
        return created_value_dict
    except ValueError as e:
        logger.error(f"ValueError creating enum value for '{enum_system_name}': {e}")
        if "Enum type not found" in str(e):
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        if "Value code already exists" in str(e) or "likely already exists" in str(e):
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotImplementedError:
         logger.error("create_enum_value service method not implemented.")
         raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Feature not implemented.")
    except Exception as e:
        logger.exception(f"Unexpected error creating enum value for '{enum_system_name}'.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")

@router.put(
    "/{enum_system_name}/{value_id}",
    response_model=EnumValueRead,
    summary="Update an Enum Value",
    description="Updates specific fields of an existing enum value. Cannot change 'code' or 'is_system' via this endpoint."
)
def update_enum_value_endpoint(
    enum_system_name: str,
    value_id: int,
    enum_value_update: EnumValueUpdate,
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to update an enum value."""
    logger.info(f"User '{current_user.email}' attempting to update enum value ID {value_id} for '{enum_system_name}'.")
    update_data = enum_value_update.model_dump(exclude_unset=True)
    if not update_data:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided.")

    try:
        updated_value_dict = enum_service.update_enum_value(enum_system_name, value_id, update_data)
        logger.info(f"Successfully updated enum value ID {value_id} for '{enum_system_name}'.")
        return updated_value_dict
    except ValueError as e:
        logger.error(f"ValueError updating enum value ID {value_id} for '{enum_system_name}': {e}")
        if "not found" in str(e).lower():
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        if "cannot modify" in str(e).lower():
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotImplementedError:
         logger.error("update_enum_value service method not implemented.")
         raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Feature not implemented.")
    except Exception as e:
        logger.exception(f"Unexpected error updating enum value ID {value_id} for '{enum_system_name}'.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.delete(
    "/{enum_system_name}/{value_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Enum Value",
    description="Deletes a specific, non-system enum value. Requires appropriate permissions."
)
def delete_enum_value_endpoint(
    enum_system_name: str,
    value_id: int,
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to delete an enum value."""
    logger.info(f"User '{current_user.email}' attempting to delete enum value ID {value_id} for '{enum_system_name}'.")
    try:
        enum_service.delete_enum_value(enum_system_name, value_id)
        logger.info(f"Successfully deleted enum value ID {value_id} for '{enum_system_name}'.")
        return None
    except ValueError as e:
        logger.error(f"ValueError deleting enum value ID {value_id} for '{enum_system_name}': {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        elif "cannot delete system value" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotImplementedError:
         logger.error("delete_enum_value service method not implemented.")
         raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Feature not implemented.")
    except Exception as e:
        logger.exception(f"Unexpected error deleting enum value ID {value_id} for '{enum_system_name}'.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


# === Translation Specific Endpoints ===

@router.post(
    "/{enum_system_name}/{value_code}/translations",
    response_model=EnumTranslationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add or Update a Translation for an Enum Value",
    description="Adds a new translation or updates an existing one for a specific enum value code and locale."
)
def create_or_update_enum_translation_endpoint(
    enum_system_name: str,
    value_code: str,
    translation_in: EnumTranslationCreate,
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to add or update a translation."""
    logger.info(f"User '{current_user.email}' adding/updating translation for enum '{enum_system_name}', value '{value_code}', locale '{translation_in.locale}'.")
    try:
        result_translation_dict = enum_service.create_or_update_translation(
            enum_system_name, value_code, translation_in.model_dump()
        )
        logger.info(f"Successfully added/updated translation ID {result_translation_dict.get('id')} for '{enum_system_name}/{value_code}', locale '{translation_in.locale}'.")
        return result_translation_dict
    except ValueError as e:
        logger.error(f"ValueError creating/updating translation for '{enum_system_name}/{value_code}': {e}")
        if "not found" in str(e).lower():
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotImplementedError:
         logger.error("create_or_update_translation service method not implemented.")
         raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Feature not implemented.")
    except Exception as e:
        logger.exception(f"Unexpected error creating/updating translation for '{enum_system_name}/{value_code}'.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.put(
    "/translations/{translation_id}",
    response_model=EnumTranslationRead,
    summary="Update an Existing Translation by ID",
    description="Updates the display text or description of a specific translation entry identified by its unique ID."
)
def update_enum_translation_endpoint(
    translation_id: int,
    translation_update: EnumTranslationUpdate,
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to update an existing translation by its ID."""
    logger.info(f"User '{current_user.email}' attempting to update translation ID {translation_id}.")
    update_data = translation_update.model_dump(exclude_unset=True)
    if not update_data:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided.")

    try:
        updated_translation_dict = enum_service.update_translation(translation_id, update_data)
        logger.info(f"Successfully updated translation ID {translation_id}.")
        return updated_translation_dict
    except ValueError as e:
        logger.error(f"ValueError updating translation ID {translation_id}: {e}")
        if "not found" in str(e).lower():
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotImplementedError:
         logger.error("update_translation service method not implemented.")
         raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Feature not implemented.")
    except Exception as e:
        logger.exception(f"Unexpected error updating translation ID {translation_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.delete(
    "/translations/{translation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Existing Translation by ID",
    description="Deletes a specific translation entry by its unique ID."
)
def delete_enum_translation_endpoint(
    translation_id: int,
    enum_service: EnumService = Depends(get_enum_service), # Inject Service
    current_user: User = Depends(get_current_active_user),
):
    """API endpoint to delete an existing translation by its ID."""
    logger.info(f"User '{current_user.email}' attempting to delete translation ID {translation_id}.")
    try:
        enum_service.delete_translation(translation_id)
        logger.info(f"Successfully deleted translation ID {translation_id}.")
        return None
    except ValueError as e:
        logger.error(f"ValueError deleting translation ID {translation_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotImplementedError:
        logger.error("delete_translation service method not implemented.")
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Feature not implemented.")
    except Exception as e:
        logger.exception(f"Unexpected error deleting translation ID {translation_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")