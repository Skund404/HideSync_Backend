# app/schemas/preset.py

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


class PresetMetadata(BaseModel):
    """Metadata for a material preset."""
    version: str = Field("1.0.0", description="Version of the preset")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    created_by: Optional[str] = Field(None, description="Creator of the preset")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")


class PresetTheme(BaseModel):
    """Theme configuration for a preset."""
    system: Dict[str, Any] = Field(default_factory=dict, description="System-level theme settings")
    material_types: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Per material type theme settings")
    colors: Dict[str, Dict[str, str]] = Field(default_factory=dict, description="Color palettes")


class PresetSettings(BaseModel):
    """Settings configuration for a preset."""
    material_ui: Optional[Dict[str, Any]] = Field(None, description="UI settings for materials")
    material_system: Optional[Dict[str, Any]] = Field(None, description="System settings for materials")


class PresetSampleMaterial(BaseModel):
    """Sample material to be included in a preset."""
    material_type: str = Field(..., description="Type of material")
    name: str = Field(..., description="Name of the material")
    status: str = Field("in_stock", description="Inventory status")
    quantity: float = Field(0, description="Initial quantity")
    unit: str = Field(..., description="Unit of measurement")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Property values")


class PresetBase(BaseModel):
    """Base schema for material presets."""
    name: str = Field(..., description="Name of the preset")
    description: Optional[str] = Field(None, description="Description of the preset")
    author: Optional[str] = Field(None, description="Author of the preset")
    is_public: bool = Field(False, description="Whether the preset is publicly available")


class PresetConfigCreate(BaseModel):
    """Configuration for creating a preset."""
    metadata: PresetMetadata = Field(default_factory=PresetMetadata, description="Preset metadata")
    property_definitions: List[Dict[str, Any]] = Field(default_factory=list, description="Property definitions")
    material_types: List[Dict[str, Any]] = Field(default_factory=list, description="Material types")
    sample_materials: List[PresetSampleMaterial] = Field(default_factory=list, description="Sample materials")
    settings: Optional[PresetSettings] = Field(None, description="Settings configuration")
    theme: Optional[PresetTheme] = Field(None, description="Theme configuration")


class PresetCreate(PresetBase):
    """Schema for creating a new preset."""
    config: PresetConfigCreate = Field(..., description="Preset configuration")


class PresetUpdate(BaseModel):
    """Schema for updating a preset."""
    name: Optional[str] = Field(None, description="Name of the preset")
    description: Optional[str] = Field(None, description="Description of the preset")
    author: Optional[str] = Field(None, description="Author of the preset")
    is_public: Optional[bool] = Field(None, description="Whether the preset is publicly available")
    config: Optional[Dict[str, Any]] = Field(None, description="Preset configuration")


class PresetRead(PresetBase):
    """Schema for reading a preset."""
    id: int = Field(..., description="Unique identifier")
    config: Dict[str, Any] = Field(..., description="Preset configuration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: Optional[int] = Field(None, description="ID of the user who created the preset")

    class Config:
        orm_mode = True


class PresetList(BaseModel):
    """Schema for paginated preset list."""
    items: List[PresetRead] = Field(..., description="List of presets")
    total: int = Field(..., description="Total number of presets matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class PresetApplicationOptions(BaseModel):
    """Options for applying a preset."""
    material_types_to_include: List[str] = Field(default_factory=list, description="Material types to include")
    include_properties: bool = Field(True, description="Whether to include property definitions")
    include_sample_materials: bool = Field(True, description="Whether to create sample materials")
    include_settings: bool = Field(True, description="Whether to apply settings")
    theme_handling: str = Field("skip", description="How to handle theme conflicts: skip, overwrite, or rename")
    conflict_resolution: str = Field("skip", description="How to handle name conflicts: skip, overwrite, or rename")


class PresetApplicationResult(BaseModel):
    """Result of applying a preset."""
    preset_id: int = Field(..., description="ID of the applied preset")
    user_id: int = Field(..., description="ID of the user who applied the preset")
    applied_at: datetime = Field(..., description="Timestamp of application")
    options_used: PresetApplicationOptions = Field(..., description="Options used for application")
    created_property_definitions: int = Field(0, description="Number of property definitions created")
    updated_property_definitions: int = Field(0, description="Number of property definitions updated")
    created_material_types: int = Field(0, description="Number of material types created")
    updated_material_types: int = Field(0, description="Number of material types updated")
    created_materials: int = Field(0, description="Number of sample materials created")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during application")