# File: app/schemas/translation_api.py

"""
API-specific schemas for translation endpoints.

These schemas are designed specifically for REST API request/response handling,
providing clean interfaces for external consumers while maintaining internal
validation and business logic.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from app.schemas.entity_translation import EntityTranslationResponse, ValidationErrorDetail


class CreateTranslationRequest(BaseModel):
    """
    Request schema for creating/updating translations via API.

    Simplified interface that focuses on the essential translation data
    without requiring clients to provide entity metadata.
    """
    locale: str = Field(
        ...,
        description="Language code (e.g., 'en', 'de', 'fr-CA')",
        example="de"
    )

    field_name: str = Field(
        ...,
        description="Field name to translate",
        example="description"
    )

    translated_value: str = Field(
        ...,
        description="Translated text content",
        example="Deutsche Produktbeschreibung"
    )

    @validator('locale')
    def validate_locale_format(cls, v):
        """Validate locale format."""
        import re
        if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
            raise ValueError('Invalid locale format. Use "xx" or "xx-XX" format.')
        return v


class EntityTranslationsResponse(BaseModel):
    """Response schema for entity translations by locale."""
    entity_type: str = Field(..., description="Entity type", example="product")
    entity_id: int = Field(..., description="Entity ID", example=123)
    locale: str = Field(..., description="Requested locale", example="de")
    translations: Dict[str, str] = Field(
        ...,
        description="Field name to translated value mapping",
        example={"name": "Produktname", "description": "Deutsche Beschreibung"}
    )
    available_fields: List[str] = Field(
        ...,
        description="All translatable fields for this entity type",
        example=["name", "description", "summary", "features"]
    )
    missing_translations: List[str] = Field(
        ...,
        description="Fields that don't have translations in this locale",
        example=["summary", "features"]
    )


class FieldTranslationsResponse(BaseModel):
    """Response schema for field translations across locales."""
    entity_type: str = Field(..., description="Entity type", example="product")
    entity_id: int = Field(..., description="Entity ID", example=123)
    field_name: str = Field(..., description="Field name", example="description")
    translations: Dict[str, str] = Field(
        ...,
        description="Locale to translated value mapping",
        example={"en": "English description", "de": "Deutsche Beschreibung", "fr": "Description française"}
    )
    supported_locales: List[str] = Field(
        ...,
        description="All supported locales in the system",
        example=["en", "de", "fr", "es"]
    )
    missing_locales: List[str] = Field(
        ...,
        description="Locales that don't have translations for this field",
        example=["es"]
    )


class TranslationStatsResponse(BaseModel):
    """Response schema for translation statistics."""
    total_entities: int = Field(..., ge=0, description="Total entities with translations")
    total_translations: int = Field(..., ge=0, description="Total translation records")
    supported_locales: List[str] = Field(..., description="All supported locales")
    entity_types: List[str] = Field(..., description="Entity types with translations")
    coverage_by_locale: Dict[str, int] = Field(
        default_factory=dict,
        description="Translation count per locale"
    )
    coverage_by_entity_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Translation count per entity type"
    )
    last_updated: Optional[str] = Field(
        None,
        description="ISO timestamp of last translation update"
    )


class BulkTranslationRequest(BaseModel):
    """Request schema for bulk translation operations."""
    translations: List[CreateTranslationRequest] = Field(
        ...,
        min_items=1,
        max_items=100,  # Reasonable limit for API
        description="List of translations to create/update"
    )

    overwrite_existing: bool = Field(
        default=True,
        description="Whether to overwrite existing translations"
    )

    @validator('translations')
    def validate_no_duplicates(cls, v):
        """Ensure no duplicate locale/field combinations."""
        seen = set()
        for trans in v:
            key = (trans.locale, trans.field_name)
            if key in seen:
                raise ValueError(
                    f'Duplicate translation for locale "{trans.locale}" '
                    f'and field "{trans.field_name}"'
                )
            seen.add(key)
        return v


class BulkTranslationResponse(BaseModel):
    """Response schema for bulk translation operations."""
    success: bool = Field(..., description="Whether all operations succeeded")
    created_count: int = Field(..., ge=0, description="Number of translations created")
    updated_count: int = Field(..., ge=0, description="Number of translations updated")
    error_count: int = Field(..., ge=0, description="Number of operations that failed")
    errors: List[ValidationErrorDetail] = Field(
        default_factory=list,
        description="Details of any errors that occurred"
    )
    successful_translations: List[int] = Field(
        default_factory=list,
        description="IDs of successfully created/updated translations"
    )


class TranslationValidationResponse(BaseModel):
    """Response schema for translation validation."""
    entity_type: str = Field(..., description="Entity type being validated")
    entity_id: int = Field(..., description="Entity ID being validated")
    entity_exists: bool = Field(..., description="Whether the entity exists")
    translatable_fields: List[str] = Field(..., description="Fields that can be translated")
    translated_fields: List[str] = Field(..., description="Fields that have translations")
    available_locales: List[str] = Field(..., description="Locales with translations")
    translation_count: int = Field(..., ge=0, description="Total translation records")
    completeness: Dict[str, float] = Field(
        default_factory=dict,
        description="Translation completeness percentage per locale"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improving translation coverage"
    )