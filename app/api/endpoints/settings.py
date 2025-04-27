# app/api/endpoints/settings.py

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user, get_current_active_superuser
from app.schemas.settings import (
    SettingsDefinitionRead, SettingsDefinitionCreate, SettingsDefinitionUpdate,
    SettingsTemplateRead, SettingsTemplateCreate, SettingsTemplateUpdate,
    SettingValueUpdate
)
from app.services.settings_service import SettingsService
from app.core.exceptions import EntityNotFoundException, ValidationException

router = APIRouter()


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    """Provide SettingsService instance."""
    return SettingsService(db)


@router.get("/definitions", response_model=List[SettingsDefinitionRead])
def list_settings_definitions(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: SettingsService = Depends(get_settings_service),
        category: Optional[str] = Query(None, description="Filter by category"),
        subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
        applies_to: Optional[str] = Query(None, description="Filter by applies_to"),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
):
    """
    List settings definitions with filtering.
    """
    return service.list_definitions(
        category=category,
        subcategory=subcategory,
        applies_to=applies_to,
        skip=skip,
        limit=limit
    )


@router.get("/definitions/{key}", response_model=SettingsDefinitionRead)
def get_settings_definition(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: SettingsService = Depends(get_settings_service),
        key: str = Path(..., description="Key of the setting definition"),
):
    """
    Get a specific settings definition by key.
    """
    definition = service.get_definition(key)
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting definition with key '{key}' not found"
        )
    return definition


@router.post("/definitions", response_model=SettingsDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_settings_definition(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_superuser),  # Only superusers can create definitions
        service: SettingsService = Depends(get_settings_service),
        definition_in: SettingsDefinitionCreate,
):
    """
    Create a new settings definition.
    """
    try:
        return service.create_definition(definition_in.dict())
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/definitions/{key}", response_model=SettingsDefinitionRead)
def update_settings_definition(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_superuser),  # Only superusers can update definitions
        service: SettingsService = Depends(get_settings_service),
        key: str = Path(..., description="Key of the setting definition"),
        definition_in: SettingsDefinitionUpdate,
):
    """
    Update a settings definition.
    """
    try:
        definition = service.update_definition(key, definition_in.dict(exclude_unset=True))
        if not definition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting definition with key '{key}' not found"
            )
        return definition
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/definitions/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_settings_definition(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_superuser),  # Only superusers can delete definitions
        service: SettingsService = Depends(get_settings_service),
        key: str = Path(..., description="Key of the setting definition"),
):
    """
    Delete a settings definition.

    System settings cannot be deleted.
    """
    result = service.delete_definition(key)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to delete setting definition. It may be a system setting."
        )


@router.get("/values/{scope_type}/{scope_id}/{key}")
def get_setting_value(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: SettingsService = Depends(get_settings_service),
        scope_type: str = Path(..., description="Type of scope (system, organization, user)"),
        scope_id: str = Path(..., description="ID of the scope entity"),
        key: str = Path(..., description="Key of the setting"),
):
    """
    Get a setting value with fallback to default.
    """
    try:
        # Check user's permissions for this scope
        if scope_type == "system" and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superusers can access system settings"
            )

        if scope_type == "organization" and str(scope_id) != str(getattr(current_user, "organization_id", None)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access settings for your organization"
            )

        if scope_type == "user" and str(scope_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own user settings"
            )

        # Get the setting value
        value = service.get_setting(key, scope_type, scope_id)
        return {"key": key, "value": value}

    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/values/{scope_type}/{scope_id}")
def get_settings_by_category(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: SettingsService = Depends(get_settings_service),
        scope_type: str = Path(..., description="Type of scope (system, organization, user)"),
        scope_id: str = Path(..., description="ID of the scope entity"),
        category: Optional[str] = Query(..., description="Category of settings"),
):
    """
    Get all settings for a category and scope.
    """
    try:
        # Check user's permissions for this scope
        if scope_type == "system" and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superusers can access system settings"
            )

        if scope_type == "organization" and str(scope_id) != str(getattr(current_user, "organization_id", None)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access settings for your organization"
            )

        if scope_type == "user" and str(scope_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own user settings"
            )

        # Get the settings
        return service.get_settings_by_category(category, scope_type, scope_id)

    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/values/{scope_type}/{scope_id}/{key}")
def set_setting_value(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: SettingsService = Depends(get_settings_service),
        scope_type: str = Path(..., description="Type of scope (system, organization, user)"),
        scope_id: str = Path(..., description="ID of the scope entity"),
        key: str = Path(..., description="Key of the setting"),
        value_in: SettingValueUpdate,
):
    """
    Set a setting value.
    """
    try:
        # Check user's permissions for this scope
        if scope_type == "system" and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superusers can update system settings"
            )

        if scope_type == "organization" and str(scope_id) != str(getattr(current_user, "organization_id", None)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update settings for your organization"
            )

        if scope_type == "user" and str(scope_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own user settings"
            )

        # Set the setting value
        service.set_setting(key, value_in.value, scope_type, scope_id)
        return {"status": "success", "message": f"Setting '{key}' updated for {scope_type} {scope_id}"}

    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/templates", response_model=SettingsTemplateRead, status_code=status.HTTP_201_CREATED)
def create_settings_template(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_superuser),  # Only superusers can create templates
        service: SettingsService = Depends(get_settings_service),
        template_in: SettingsTemplateCreate,
):
    """
    Create a new settings template.
    """
    try:
        # Implementation depends on SettingsTemplateRepository and schema details
        # For simplicity, this endpoint is not fully implemented in this guide
        raise NotImplementedError("Template creation not implemented in this guide")
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/templates/{template_id}/apply/{scope_type}/{scope_id}")
def apply_settings_template(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: SettingsService = Depends(get_settings_service),
        template_id: int = Path(..., description="ID of the template"),
        scope_type: str = Path(..., description="Type of scope (system, organization, user)"),
        scope_id: str = Path(..., description="ID of the scope entity"),
):
    """
    Apply a settings template to a scope.
    """
    try:
        # Check user's permissions for this scope
        if scope_type == "system" and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superusers can apply templates to system settings"
            )

        if scope_type == "organization" and str(scope_id) != str(getattr(current_user, "organization_id", None)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only apply templates to your organization"
            )

        if scope_type == "user" and str(scope_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only apply templates to your own user settings"
            )

        # Apply the template
        applied_settings = service.apply_template(template_id, scope_type, scope_id)
        return {
            "status": "success",
            "message": f"Template {template_id} applied to {scope_type} {scope_id}",
            "settings": applied_settings
        }

    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/register")
def register_settings(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_superuser),  # Only superusers can register settings
        service: SettingsService = Depends(get_settings_service),
        definitions: List[Dict[str, Any]] = Body(..., description="List of setting definitions"),
):
    """
    Register multiple settings definitions, skipping existing ones.
    """
    try:
        result = service.register_settings(definitions)
        return {
            "status": "success",
            "message": f"Registered {len(result)} settings",
            "count": len(result)
        }
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )