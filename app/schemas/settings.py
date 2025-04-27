# app/schemas/settings.py

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime


# --- SettingsDefinition Schemas ---

class SettingsDefinitionTranslation(BaseModel):
    """Schema for settings definition translation."""
    display_name: str = Field(..., description="Localized display name")
    description: Optional[str] = Field(None, description="Localized description")


class SettingsDefinitionBase(BaseModel):
    """Base schema for settings definitions."""
    key: str = Field(..., description="Unique key for the setting", regex=r"^[a-zA-Z0-9_\.]+$")
    name: str = Field(..., description="Display name for the setting")
    description: Optional[str] = Field(None, description="Description of the setting")
    data_type: str = Field(..., description="Data type (string, number, boolean, json, enum, etc.)")
    default_value: Optional[Any] = Field(None, description="Default value")
    category: Optional[str] = Field(None, description="Category for organization")
    subcategory: Optional[str] = Field(None, description="Subcategory for organization")
    applies_to: str = Field(..., description="Scope type (system, organization, user, all)")
    tier_availability: Optional[str] = Field("all", description="Comma-separated tiers or 'all'")
    is_hidden: Optional[bool] = Field(False, description="Whether the setting is hidden in UI")
    ui_component: Optional[str] = Field(None, description="UI component for editing")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Validation rules")

    @validator('data_type')
    def validate_data_type(cls, v):
        valid_types = ['string', 'number', 'boolean', 'json', 'enum']
        if v not in valid_types:
            raise ValueError(f"data_type must be one of: {', '.join(valid_types)}")
        return v

    @validator('applies_to')
    def validate_applies_to(cls, v):
        valid_scopes = ['system', 'organization', 'user', 'all']
        if v not in valid_scopes:
            raise ValueError(f"applies_to must be one of: {', '.join(valid_scopes)}")
        return v


class SettingsDefinitionCreate(SettingsDefinitionBase):
    """Schema for creating a settings definition."""
    translations: Optional[Dict[str, SettingsDefinitionTranslation]] = Field(
        {}, description="Translations keyed by locale code"
    )
    is_system: Optional[bool] = Field(False, description="Whether this is a system setting")


class SettingsDefinitionUpdate(BaseModel):
    """Schema for updating a settings definition."""
    name: Optional[str] = Field(None, description="Display name for the setting")
    description: Optional[str] = Field(None, description="Description of the setting")
    default_value: Optional[Any] = Field(None, description="Default value")
    category: Optional[str] = Field(None, description="Category for organization")
    subcategory: Optional[str] = Field(None, description="Subcategory for organization")
    applies_to: Optional[str] = Field(None, description="Scope type (system, organization, user, all)")
    tier_availability: Optional[str] = Field(None, description="Comma-separated tiers or 'all'")
    is_hidden: Optional[bool] = Field(None, description="Whether the setting is hidden in UI")
    ui_component: Optional[str] = Field(None, description="UI component for editing")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Validation rules")
    translations: Optional[Dict[str, SettingsDefinitionTranslation]] = Field(
        None, description="Translations keyed by locale code"
    )

    @validator('applies_to')
    def validate_applies_to(cls, v):
        if v is None:
            return v
        valid_scopes = ['system', 'organization', 'user', 'all']
        if v not in valid_scopes:
            raise ValueError(f"applies_to must be one of: {', '.join(valid_scopes)}")
        return v


class SettingsDefinitionRead(SettingsDefinitionBase):
    """Schema for reading a settings definition."""
    id: int = Field(..., description="Unique identifier")
    translations: Dict[str, SettingsDefinitionTranslation] = Field(
        {}, description="Translations keyed by locale code"
    )
    is_system: bool = Field(False, description="Whether this is a system setting")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        orm_mode = True


# --- SettingsValue Schemas ---

class SettingValueUpdate(BaseModel):
    """Schema for updating a setting value."""
    value: Any = Field(..., description="Value to set")


# --- SettingsTemplate Schemas ---

class SettingsTemplateItemBase(BaseModel):
    """Base schema for settings template items."""
    setting_key: str = Field(..., description="Key of the setting")
    value: Any = Field(..., description="Value for the setting")


class SettingsTemplateItemCreate(SettingsTemplateItemBase):
    """Schema for creating a settings template item."""
    pass


class SettingsTemplateItemRead(SettingsTemplateItemBase):
    """Schema for reading a settings template item."""
    id: int = Field(..., description="Unique identifier")
    definition: Dict[str, Any] = Field(..., description="Setting definition")

    class Config:
        orm_mode = True


class SettingsTemplateBase(BaseModel):
    """Base schema for settings templates."""
    name: str = Field(..., description="Name of the template")
    description: Optional[str] = Field(None, description="Description of the template")
    category: Optional[str] = Field(None, description="Category of the template")
    applies_to: str = Field(..., description="Scope type (user, organization, all)")
    tier_availability: Optional[str] = Field("all", description="Comma-separated tiers or 'all'")


class SettingsTemplateCreate(SettingsTemplateBase):
    """Schema for creating a settings template."""
    items: List[SettingsTemplateItemCreate] = Field(
        ..., description="Settings to include in the template"
    )
    is_system: Optional[bool] = Field(False, description="Whether this is a system template")


class SettingsTemplateUpdate(BaseModel):
    """Schema for updating a settings template."""
    name: Optional[str] = Field(None, description="Name of the template")
    description: Optional[str] = Field(None, description="Description of the template")
    category: Optional[str] = Field(None, description="Category of the template")
    applies_to: Optional[str] = Field(None, description="Scope type (user, organization, all)")
    tier_availability: Optional[str] = Field(None, description="Comma-separated tiers or 'all'")
    items: Optional[List[SettingsTemplateItemCreate]] = Field(
        None, description="Settings to include in the template"
    )


class SettingsTemplateRead(SettingsTemplateBase):
    """Schema for reading a settings template."""
    id: int = Field(..., description="Unique identifier")
    items: List[SettingsTemplateItemRead] = Field(
        [], description="Settings included in the template"
    )
    is_system: bool = Field(False, description="Whether this is a system template")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        orm_mode = True