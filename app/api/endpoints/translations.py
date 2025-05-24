# File: app/api/endpoints/translations.py

"""
Translation Management API Endpoints

This module provides RESTful API endpoints for managing entity translations.
It follows the exact same pattern as the enum endpoints to maintain consistency
throughout the HideSync API architecture.
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body

from app.api import deps
from app.services.localization_service import LocalizationService
from app.db.models.user import User
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.schemas.entity_translation import EntityTranslationResponse
from app.schemas.translation_api import (
    CreateTranslationRequest,
    EntityTranslationsResponse,
    FieldTranslationsResponse,
    TranslationStatsResponse,
    TranslationValidationResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


# System Configuration Endpoints
@router.get("/locales", response_model=List[str])
def get_supported_locales(
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Get list of supported locales for translations.

    Returns all locale codes that are configured and supported by the system.
    """
    try:
        return localization_service.get_supported_locales()
    except Exception as e:
        logger.error(f"Error getting supported locales: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve supported locales"
        )


@router.get("/entity-types", response_model=List[str])
def get_supported_entity_types(
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Get list of supported entity types for translation.

    Returns all entity types that are configured for translation support.
    """
    try:
        return localization_service.get_supported_entity_types()
    except Exception as e:
        logger.error(f"Error getting supported entity types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve supported entity types"
        )


@router.get("/entity-types/{entity_type}/fields", response_model=List[str])
def get_translatable_fields(
        entity_type: str = Path(..., description="Entity type (e.g., 'product', 'workflow')"),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Get list of translatable fields for a specific entity type.

    Returns all field names that can be translated for the given entity type.
    """
    try:
        return localization_service.get_translatable_fields(entity_type)
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting translatable fields for {entity_type}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translatable fields"
        )


@router.get("/stats", response_model=TranslationStatsResponse)
def get_translation_statistics(
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Get comprehensive translation system statistics.

    Returns statistics about translation coverage, supported locales,
    entity types, and other system metrics.
    """
    try:
        stats = localization_service.get_translation_statistics()
        return TranslationStatsResponse(
            total_entities=stats.get("unique_entities", 0),
            total_translations=stats.get("total_translations", 0),
            supported_locales=stats.get("supported_locales", []),
            entity_types=stats.get("entity_types", []),
            coverage_by_locale=stats.get("distribution", {}).get("by_locale", {}),
            coverage_by_entity_type=stats.get("distribution", {}).get("by_entity_type", {}),
            last_updated=stats.get("latest_update")
        )
    except Exception as e:
        logger.error(f"Error getting translation stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translation statistics"
        )


# Translation Management Endpoints
@router.post("/{entity_type}/{entity_id}/translations", status_code=status.HTTP_201_CREATED)
def create_or_update_translation(
        entity_type: str = Path(..., description="Entity type (e.g., 'workflow', 'product')"),
        entity_id: int = Path(..., description="Entity ID", gt=0),
        request: CreateTranslationRequest = Body(...),
        current_user: User = Depends(deps.get_current_active_user),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Create or update a translation for an entity field.

    If a translation already exists for the specified entity, locale, and field,
    it will be updated. Otherwise, a new translation will be created.
    """
    try:
        translation = localization_service.create_or_update_translation(
            entity_type=entity_type,
            entity_id=entity_id,
            locale=request.locale,
            field_name=request.field_name,
            translated_value=request.translated_value,
            user_id=current_user.id
        )

        return {
            "message": "Translation saved successfully",
            "translation_id": translation.id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "locale": request.locale,
            "field_name": request.field_name,
            "created_at": translation.created_at.isoformat(),
            "updated_at": translation.updated_at.isoformat()
        }

    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating/updating translation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process translation"
        )


@router.get("/{entity_type}/{entity_id}/translations/{locale}", response_model=Dict[str, str])
def get_entity_translations_for_locale(
        entity_type: str = Path(..., description="Entity type"),
        entity_id: int = Path(..., description="Entity ID", gt=0),
        locale: str = Path(..., description="Locale code (e.g., 'en', 'de')"),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Get all translated fields for an entity in a specific locale.

    Returns a dictionary mapping field names to their translated values
    for the specified entity and locale.
    """
    try:
        translations = localization_service.get_translations_for_entity_by_locale(
            entity_type, entity_id, locale
        )
        return translations
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving translations for {entity_type}#{entity_id} in {locale}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translations"
        )


@router.get("/{entity_type}/{entity_id}/translations/{field_name}/all", response_model=Dict[str, str])
def get_all_translations_for_field(
        entity_type: str = Path(..., description="Entity type"),
        entity_id: int = Path(..., description="Entity ID", gt=0),
        field_name: str = Path(..., description="Field name"),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Get all translations for a specific field across all locales.

    Returns a dictionary mapping locale codes to translated values
    for the specified entity field.
    """
    try:
        translations = localization_service.get_all_translations_for_field(
            entity_type, entity_id, field_name
        )
        return translations
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving field translations for {entity_type}#{entity_id}.{field_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve field translations"
        )


@router.get("/{entity_type}/{entity_id}/translations")
def get_all_entity_translations(
        entity_type: str = Path(..., description="Entity type"),
        entity_id: int = Path(..., description="Entity ID", gt=0),
        locale: Optional[str] = Query(None, description="Optional locale filter"),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Get all translations for an entity, optionally filtered by locale.

    Returns comprehensive translation data organized by locale and field.
    """
    try:
        if locale:
            # Get translations for specific locale
            translations = localization_service.get_translations_for_entity_by_locale(
                entity_type, entity_id, locale
            )
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "locale": locale,
                "translations": translations
            }
        else:
            # Get all translations organized by locale
            # This requires a more complex query - we'll build it from individual locale queries
            supported_locales = localization_service.get_supported_locales()
            all_translations = {}

            for loc in supported_locales:
                locale_translations = localization_service.get_translations_for_entity_by_locale(
                    entity_type, entity_id, loc
                )
                if locale_translations:
                    all_translations[loc] = locale_translations

            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "translations_by_locale": all_translations,
                "available_locales": list(all_translations.keys())
            }

    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving all translations for {entity_type}#{entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translations"
        )


# Validation and Administrative Endpoints
@router.get("/{entity_type}/{entity_id}/validation")
def validate_entity_translation_setup(
        entity_type: str = Path(..., description="Entity type"),
        entity_id: int = Path(..., description="Entity ID", gt=0),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Validate translation setup for a specific entity.

    Returns detailed information about the entity's translation status,
    including completeness metrics and recommendations for improvement.
    """
    try:
        validation_result = localization_service.validate_entity_translation_setup(entity_type, entity_id)
        return validation_result
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error validating translation setup for {entity_type}#{entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate translation setup"
        )


@router.delete("/translations/{translation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_translation(
        translation_id: int = Path(..., description="Translation ID", gt=0),
        current_user: User = Depends(deps.get_current_active_user),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Delete a specific translation by its ID.

    This permanently removes the translation record from the system.
    """
    try:
        success = localization_service.delete_translation(
            translation_id, user_id=current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete translation"
            )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting translation {translation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete translation"
        )


@router.delete("/{entity_type}/{entity_id}/translations", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_entity_translations(
        entity_type: str = Path(..., description="Entity type"),
        entity_id: int = Path(..., description="Entity ID", gt=0),
        current_user: User = Depends(deps.get_current_active_user),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Delete all translations for a specific entity.

    WARNING: This permanently removes all translation records for the entity.
    """
    try:
        # This would require adding a method to the service
        # For now, we'll return a not implemented response
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Bulk deletion endpoint not yet implemented"
        )
    except Exception as e:
        logger.error(f"Error deleting all translations for {entity_type}#{entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete entity translations"
        )


# Administrative Endpoints
@router.post("/admin/cleanup/{entity_type}")
def cleanup_orphaned_translations(
        entity_type: str = Path(..., description="Entity type to clean up"),
        dry_run: bool = Query(True, description="If true, only report what would be cleaned up"),
        current_user: User = Depends(deps.get_current_active_user),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Clean up orphaned translations for entities that no longer exist.

    This administrative endpoint helps maintain data integrity by removing
    translation records for entities that have been deleted.
    """
    try:
        # Add role-based access control here if needed
        # if not current_user.is_admin:
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

        cleanup_result = localization_service.cleanup_orphaned_translations(entity_type, dry_run)
        return cleanup_result
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error cleaning up orphaned translations for {entity_type}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup orphaned translations"
        )


# Utility Endpoints
@router.get("/{entity_type}/{entity_id}/field/{field_name}/translation/{locale}")
def get_single_translation(
        entity_type: str = Path(..., description="Entity type"),
        entity_id: int = Path(..., description="Entity ID", gt=0),
        field_name: str = Path(..., description="Field name"),
        locale: str = Path(..., description="Locale code"),
        use_fallback: bool = Query(True, description="Whether to use fallback strategy"),
        localization_service: LocalizationService = Depends(deps.get_localization_service)
):
    """
    Get a single translation with optional fallback strategy.

    Returns the translated value for a specific entity field and locale,
    with intelligent fallback to default locale or original value if enabled.
    """
    try:
        translation = localization_service.get_translation(
            entity_type, entity_id, field_name, locale, use_fallback
        )

        if translation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Translation not found for {entity_type}#{entity_id}.{field_name} in {locale}"
            )

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "field_name": field_name,
            "locale": locale,
            "translated_value": translation,
            "fallback_used": use_fallback
        }

    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error getting single translation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translation"
        )