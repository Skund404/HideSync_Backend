# File: app/schemas/entity_translation.py

"""
Pydantic schemas for Entity Translation system.

These schemas provide validation and serialization for the universal translation
system that handles all entity types in HideSync. They follow the same patterns
established by the enum schemas for consistency.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, root_validator
import re


class EntityTranslationBase(BaseModel):
    """
    Base schema for entity translations with comprehensive validation.

    This base class contains common fields and validation logic shared across
    all translation operations.
    """
    entity_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Entity type (e.g., 'workflow', 'product')",
        example="product"
    )

    entity_id: int = Field(
        ...,
        gt=0,
        description="ID of the entity being translated",
        example=123
    )

    locale: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Language code (e.g., 'en', 'de', 'fr-CA')",
        example="en"
    )

    field_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Field name being translated",
        example="name"
    )

    translated_value: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Translated text content",
        example="Produktname auf Deutsch"
    )

    @validator('entity_type')
    def validate_entity_type(cls, v):
        """Validate entity type format (lowercase, underscores only)."""
        if not re.match(r'^[a-z][a-z0-9_]*$', v):
            raise ValueError(
                'Entity type must start with lowercase letter and contain only '
                'lowercase letters, numbers, and underscores'
            )
        return v

    @validator('locale')
    def validate_locale(cls, v):
        """Validate locale format (ISO 639-1 with optional country code)."""
        if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
            raise ValueError(
                'Locale must be in format "xx" or "xx-XX" (e.g., "en", "fr-CA")'
            )
        return v

    @validator('field_name')
    def validate_field_name(cls, v):
        """Validate field name format (lowercase, underscores only)."""
        if not re.match(r'^[a-z][a-z0-9_]*$', v):
            raise ValueError(
                'Field name must start with lowercase letter and contain only '
                'lowercase letters, numbers, and underscores'
            )
        return v

    @validator('translated_value')
    def validate_translated_value(cls, v):
        """Validate translated content."""
        # Remove excessive whitespace
        v = re.sub(r'\s+', ' ', v.strip())

        if not v:
            raise ValueError('Translated value cannot be empty or only whitespace')

        # Check for potential security issues (basic XSS prevention)
        dangerous_patterns = ['<script', 'javascript:', 'onclick=', 'onerror=']
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError(f'Translated value contains potentially dangerous content: {pattern}')

        return v


class EntityTranslationCreate(BaseModel):
    """
    Schema for creating entity translations.

    Simplified version that only requires the essential fields for creation.
    The entity_type and entity_id will typically come from the URL path.
    """
    locale: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Language code",
        example="de"
    )

    field_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Field name to translate",
        example="description"
    )

    translated_value: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Translated text content",
        example="Deutsche Beschreibung des Produkts"
    )

    # Apply same validators as base class
    _validate_locale = validator('locale', allow_reuse=True)(EntityTranslationBase.validate_locale)
    _validate_field_name = validator('field_name', allow_reuse=True)(EntityTranslationBase.validate_field_name)
    _validate_translated_value = validator('translated_value', allow_reuse=True)(
        EntityTranslationBase.validate_translated_value)


class EntityTranslationUpdate(BaseModel):
    """
    Schema for updating entity translations.

    Only allows updating the translated value - other fields are immutable.
    """
    translated_value: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Updated translated text content",
        example="Aktualisierte deutsche Beschreibung"
    )

    _validate_translated_value = validator('translated_value', allow_reuse=True)(
        EntityTranslationBase.validate_translated_value)


class EntityTranslationResponse(EntityTranslationBase):
    """
    Schema for entity translation responses.

    Includes all fields plus metadata like timestamps and ID.
    """
    id: int = Field(..., description="Translation record ID", example=456)
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Convenience schemas for bulk operations and API responses
class BulkTranslationCreate(BaseModel):
    """Schema for creating multiple translations at once."""
    entity_type: str = Field(..., description="Entity type for all translations")
    entity_id: int = Field(..., description="Entity ID for all translations")
    translations: List[EntityTranslationCreate] = Field(
        ...,
        min_items=1,
        max_items=50,  # Reasonable limit for bulk operations
        description="List of translations to create"
    )

    @validator('translations')
    def validate_unique_locale_field_combinations(cls, v, values):
        """Ensure no duplicate locale/field combinations in bulk request."""
        seen_combinations = set()
        for translation in v:
            combination = (translation.locale, translation.field_name)
            if combination in seen_combinations:
                raise ValueError(
                    f'Duplicate translation for locale "{translation.locale}" '
                    f'and field "{translation.field_name}"'
                )
            seen_combinations.add(combination)
        return v


class TranslationSummary(BaseModel):
    """Summary of available translations for an entity."""
    entity_type: str = Field(..., description="Entity type", example="product")
    entity_id: int = Field(..., description="Entity ID", example=123)
    available_locales: List[str] = Field(
        ...,
        description="List of locales with translations",
        example=["en", "de", "fr"]
    )
    translatable_fields: List[str] = Field(
        ...,
        description="List of fields that can be translated",
        example=["name", "description", "summary"]
    )
    translated_fields: List[str] = Field(
        ...,
        description="List of fields that have translations",
        example=["name", "description"]
    )
    translation_count: int = Field(
        ...,
        ge=0,
        description="Total number of translation records",
        example=6
    )
    completeness_percentage: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Percentage of fields translated across all supported locales",
        example=75.5
    )


class EntityTranslationStats(BaseModel):
    """Statistics about the translation system."""
    total_entities: int = Field(..., ge=0, description="Total entities with translations")
    total_translations: int = Field(..., ge=0, description="Total translation records")
    supported_locales: List[str] = Field(..., description="All supported locales")
    entity_types: List[str] = Field(..., description="Entity types with translations")
    most_translated_locale: Optional[str] = Field(None, description="Locale with most translations")
    least_translated_locale: Optional[str] = Field(None, description="Locale with least translations")
    translation_coverage: Dict[str, int] = Field(
        default_factory=dict,
        description="Translation count per entity type"
    )


class ValidationErrorDetail(BaseModel):
    """Detailed validation error information."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    invalid_value: Any = Field(..., description="The invalid value that was provided")


class TranslationOperationResult(BaseModel):
    """Result of a translation operation (create/update/delete)."""
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    translation_id: Optional[int] = Field(None, description="ID of affected translation")
    entity_type: Optional[str] = Field(None, description="Entity type involved")
    entity_id: Optional[int] = Field(None, description="Entity ID involved")
    locale: Optional[str] = Field(None, description="Locale involved")
    field_name: Optional[str] = Field(None, description="Field name involved")
    errors: Optional[List[ValidationErrorDetail]] = Field(
        None,
        description="Validation errors if operation failed"
    )