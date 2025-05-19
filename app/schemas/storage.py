# File: app/schemas/storage.py
"""
Storage Schemas for the Dynamic Material Management System.

This module defines Pydantic schemas for storage entities following the same
patterns as the dynamic material schemas. Updated to support:
- Dynamic storage location types with custom properties
- Settings-aware response models
- Theme integration
- Enhanced validation
- Internationalization support
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
import re


# --- Storage Property Definition Schemas ---

class StoragePropertyEnumOptionBase(BaseModel):
    """Base schema for storage property enum options."""
    value: str = Field(..., description="Unique value code for the option")
    display_value: str = Field(..., description="Display text for the option")
    color: Optional[str] = Field(None, description="Optional color code for the option")
    display_order: Optional[int] = Field(None, description="Order for displaying options")


class StoragePropertyEnumOptionCreate(StoragePropertyEnumOptionBase):
    """Schema for creating a new storage property enum option."""
    pass


class StoragePropertyEnumOptionRead(StoragePropertyEnumOptionBase):
    """Schema for reading a storage property enum option."""
    id: int = Field(..., description="Unique identifier")

    class Config:
        orm_mode = True


class StoragePropertyDefinitionTranslation(BaseModel):
    """Schema for storage property definition translation."""
    display_name: str = Field(..., description="Localized display name")
    description: Optional[str] = Field(None, description="Localized description")


class StoragePropertyDefinitionBase(BaseModel):
    """Base schema for storage property definitions."""
    name: str = Field(..., description="Unique name for the property", regex=r"^[a-zA-Z0-9_]+$")
    data_type: str = Field(..., description="Data type (string, number, boolean, enum, date, reference, file)")
    group_name: Optional[str] = Field(None, description="Optional group name for organizing properties")
    unit: Optional[str] = Field(None, description="Optional unit of measurement")
    is_required: Optional[bool] = Field(False, description="Whether this property is required")
    has_multiple_values: Optional[bool] = Field(False, description="Whether this property can have multiple values")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Optional validation rules")

    @validator('data_type')
    def validate_data_type(cls, v):
        valid_types = ['string', 'number', 'boolean', 'enum', 'date', 'reference', 'file']
        if v not in valid_types:
            raise ValueError(f"data_type must be one of: {', '.join(valid_types)}")
        return v


class StoragePropertyDefinitionCreate(StoragePropertyDefinitionBase):
    """Schema for creating a new storage property definition."""
    translations: Optional[Dict[str, StoragePropertyDefinitionTranslation]] = Field(
        {}, description="Translations keyed by locale code"
    )
    enum_type_id: Optional[int] = Field(None, description="ID of the enum type for enum properties")
    enum_options: Optional[List[StoragePropertyEnumOptionCreate]] = Field(None, description="Custom enum options")

    @validator('enum_options', 'enum_type_id')
    def validate_enum_config(cls, v, values):
        data_type = values.get('data_type')
        if data_type == 'enum':
            if v is None and values.get('enum_type_id') is None and values.get('enum_options') is None:
                raise ValueError("Either enum_type_id or enum_options must be provided for enum properties")
        elif v is not None:
            raise ValueError(f"enum_options or enum_type_id can only be used with enum data_type")
        return v


class StoragePropertyDefinitionUpdate(BaseModel):
    """Schema for updating a storage property definition."""
    group_name: Optional[str] = Field(None, description="Optional group name for organizing properties")
    unit: Optional[str] = Field(None, description="Optional unit of measurement")
    is_required: Optional[bool] = Field(None, description="Whether this property is required")
    has_multiple_values: Optional[bool] = Field(None, description="Whether this property can have multiple values")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Optional validation rules")
    translations: Optional[Dict[str, StoragePropertyDefinitionTranslation]] = Field(
        None, description="Translations keyed by locale code"
    )
    enum_options: Optional[List[StoragePropertyEnumOptionCreate]] = Field(None, description="Custom enum options")


class StoragePropertyDefinitionRead(StoragePropertyDefinitionBase):
    """Schema for reading a storage property definition."""
    id: int = Field(..., description="Unique identifier")
    translations: Dict[str, StoragePropertyDefinitionTranslation] = Field(
        {}, description="Translations keyed by locale code"
    )
    enum_type_id: Optional[int] = Field(None, description="ID of the enum type for enum properties")
    enum_options: List[StoragePropertyEnumOptionRead] = Field([], description="Custom enum options")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    is_system: bool = Field(False, description="Whether this is a system property")

    class Config:
        orm_mode = True


# --- Storage Location Type Schemas ---

class StorageLocationTypePropertyBase(BaseModel):
    """Schema for storage location type property assignments."""
    property_id: int = Field(..., description="ID of the property")
    display_order: Optional[int] = Field(None, description="Order for displaying the property")
    is_required: Optional[bool] = Field(False,
                                        description="Whether the property is required for this storage location type")
    is_filterable: Optional[bool] = Field(True, description="Whether the property can be used for filtering")
    is_displayed_in_list: Optional[bool] = Field(True, description="Whether to display the property in list views")
    is_displayed_in_card: Optional[bool] = Field(True, description="Whether to display the property in card views")
    default_value: Optional[Any] = Field(None, description="Default value for the property")
    enum_options: Optional[List[StoragePropertyEnumOptionCreate]] = Field(None,
                                                                          description="Custom enum options for this property")
    enum_type_id: Optional[int] = Field(None, description="ID of the enum type for this property")


class StorageLocationTypeTranslation(BaseModel):
    """Schema for storage location type translation."""
    display_name: str = Field(..., description="Localized display name")
    description: Optional[str] = Field(None, description="Localized description")


class StorageLocationTypeBase(BaseModel):
    """Base schema for storage location types."""
    name: str = Field(..., description="Unique name for the storage location type", regex=r"^[a-zA-Z0-9_]+$")
    icon: Optional[str] = Field(None, description="Icon identifier or path")
    color_scheme: Optional[str] = Field(None, description="Color scheme for UI")
    ui_config: Optional[Dict[str, Any]] = Field(None, description="UI configuration as JSON")
    storage_config: Optional[Dict[str, Any]] = Field(None, description="Storage configuration as JSON")
    visibility_level: Optional[str] = Field("all", description="Visibility level (all, admin, specific tier)")


class StorageLocationTypeCreate(StorageLocationTypeBase):
    """Schema for creating a new storage location type."""
    translations: Dict[str, StorageLocationTypeTranslation] = Field(
        {}, description="Translations keyed by locale code"
    )
    properties: List[StorageLocationTypePropertyBase] = Field(
        [], description="Properties assigned to this storage location type"
    )


class StorageLocationTypeUpdate(BaseModel):
    """Schema for updating a storage location type."""
    icon: Optional[str] = Field(None, description="Icon identifier or path")
    color_scheme: Optional[str] = Field(None, description="Color scheme for UI")
    ui_config: Optional[Dict[str, Any]] = Field(None, description="UI configuration as JSON")
    storage_config: Optional[Dict[str, Any]] = Field(None, description="Storage configuration as JSON")
    visibility_level: Optional[str] = Field(None, description="Visibility level (all, admin, specific tier)")
    translations: Optional[Dict[str, StorageLocationTypeTranslation]] = Field(
        None, description="Translations keyed by locale code"
    )
    properties: Optional[List[StorageLocationTypePropertyBase]] = Field(
        None, description="Properties assigned to this storage location type"
    )


class StorageLocationTypeRead(StorageLocationTypeBase):
    """Schema for reading a storage location type."""
    id: int = Field(..., description="Unique identifier")
    translations: Dict[str, StorageLocationTypeTranslation] = Field(
        {}, description="Translations keyed by locale code"
    )
    properties: List[Dict[str, Any]] = Field(
        [], description="Properties assigned to this storage location type"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    is_system: bool = Field(False, description="Whether this is a system storage location type")

    class Config:
        orm_mode = True


class StorageLocationTypeList(BaseModel):
    """Schema for paginated storage location type list."""
    items: List[StorageLocationTypeRead] = Field(..., description="List of storage location types")
    total: int = Field(..., description="Total number of storage location types matching the query")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    page_size: int = Field(..., description="Number of items per page")


# --- Storage Location Property Value Schemas ---

class StorageLocationPropertyValueBase(BaseModel):
    """Base schema for storage location property values."""
    property_id: int = Field(..., description="ID of the property")
    value: Any = Field(None, description="Value of the property")


class StorageLocationPropertyValueCreate(StorageLocationPropertyValueBase):
    """Schema for creating a storage location property value."""
    pass


class StorageLocationPropertyValueRead(StorageLocationPropertyValueBase):
    """Schema for reading a storage location property value."""
    property: Dict[str, Any] = Field(..., description="Property definition")

    class Config:
        orm_mode = True


# --- Storage Location Schemas ---

class StorageLocationBase(BaseModel):
    """Base schema for storage locations."""
    storage_location_type_id: int = Field(..., description="ID of the storage location type")
    name: str = Field(..., description="Name of the storage location")
    section: Optional[str] = Field(None, description="Organizational section")
    description: Optional[str] = Field(None, description="Description of the storage location")
    dimensions: Optional[Dict[str, Any]] = Field(None, description="Physical dimensions")
    capacity: Optional[int] = Field(None, description="Storage capacity", ge=0)
    status: Optional[str] = Field("ACTIVE", description="Status of the storage location")
    notes: Optional[str] = Field(None, description="Additional notes")
    parent_storage_id: Optional[str] = Field(None, description="ID of parent storage location")
    ui_config: Optional[Dict[str, Any]] = Field(None, description="UI configuration")
    storage_config: Optional[Dict[str, Any]] = Field(None, description="Storage-specific configuration")


class StorageLocationCreate(StorageLocationBase):
    """Schema for creating a storage location."""
    property_values: List[StorageLocationPropertyValueCreate] = Field(
        [], description="Property values for this storage location"
    )
    translations: Optional[Dict[str, str]] = Field(None, description="Translations for display names")


class StorageLocationUpdate(BaseModel):
    """Schema for updating a storage location."""
    name: Optional[str] = Field(None, description="Name of the storage location")
    section: Optional[str] = Field(None, description="Organizational section")
    description: Optional[str] = Field(None, description="Description of the storage location")
    dimensions: Optional[Dict[str, Any]] = Field(None, description="Physical dimensions")
    capacity: Optional[int] = Field(None, description="Storage capacity", ge=0)
    status: Optional[str] = Field(None, description="Status of the storage location")
    notes: Optional[str] = Field(None, description="Additional notes")
    parent_storage_id: Optional[str] = Field(None, description="ID of parent storage location")
    ui_config: Optional[Dict[str, Any]] = Field(None, description="UI configuration")
    storage_config: Optional[Dict[str, Any]] = Field(None, description="Storage-specific configuration")
    property_values: Optional[List[StorageLocationPropertyValueCreate]] = Field(
        None, description="Property values for this storage location"
    )
    translations: Optional[Dict[str, str]] = Field(None, description="Translations for display names")


class StorageLocationRead(StorageLocationBase):
    """Schema for reading a storage location."""
    id: str = Field(..., description="Unique identifier")
    utilized: int = Field(0, description="Currently utilized capacity")
    available_capacity: Optional[int] = Field(None, description="Available capacity")
    utilization_percentage: Optional[float] = Field(None, description="Utilization percentage")
    storage_location_type: Dict[str, Any] = Field(..., description="Storage location type information")
    property_values: List[Dict[str, Any]] = Field([], description="Property values")
    translations: List[Dict[str, Any]] = Field([], description="Translations")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    last_modified: Optional[str] = Field(None, description="Last modification date")

    # Settings-aware fields (added by service when apply_settings=True)
    ui_settings: Optional[Dict[str, Any]] = Field(None, description="Applied UI settings")

    class Config:
        orm_mode = True


class StorageLocationList(BaseModel):
    """Schema for paginated storage location list."""
    items: List[StorageLocationRead] = Field(..., description="List of storage locations")
    total: int = Field(..., description="Total number of storage locations matching the query")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    page_size: int = Field(..., description="Number of items per page")


# --- Storage Cell Schemas ---

class StorageCellBase(BaseModel):
    """Base schema for storage cells."""
    position: Optional[Dict[str, Any]] = Field(None, description="Position within storage location")
    material_id: Optional[int] = Field(None, description="ID of assigned material")
    occupied: bool = Field(False, description="Whether the cell is occupied")
    notes: Optional[str] = Field(None, description="Additional notes")


class StorageCellCreate(StorageCellBase):
    """Schema for creating a storage cell."""
    pass


class StorageCellRead(StorageCellBase):
    """Schema for reading a storage cell."""
    id: str = Field(..., description="Unique identifier")
    storage_id: str = Field(..., description="ID of parent storage location")
    label: str = Field(..., description="Human-readable cell label")
    material: Optional[Dict[str, Any]] = Field(None, description="Assigned material information")

    class Config:
        orm_mode = True


class StorageCellList(BaseModel):
    """Schema for paginated storage cell list."""
    items: List[StorageCellRead] = Field(..., description="List of storage cells")
    total: int = Field(..., description="Total number of storage cells matching the query")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    page_size: int = Field(..., description="Number of items per page")


# --- Storage Assignment Schemas ---

class StorageAssignmentBase(BaseModel):
    """Base schema for storage assignments."""
    material_id: int = Field(..., description="ID of the assigned material")
    storage_id: str = Field(..., description="ID of the storage location")
    position: Optional[Dict[str, Any]] = Field(None, description="Position within storage location")
    quantity: float = Field(..., description="Assigned quantity", gt=0)
    notes: Optional[str] = Field(None, description="Additional notes")


class StorageAssignmentCreate(StorageAssignmentBase):
    """Schema for creating a storage assignment."""

    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v


class StorageAssignmentRead(StorageAssignmentBase):
    """Schema for reading a storage assignment."""
    id: str = Field(..., description="Unique identifier")
    assigned_date: Optional[str] = Field(None, description="Date of assignment")
    assigned_by: Optional[str] = Field(None, description="Person who made the assignment")
    material: Optional[Dict[str, Any]] = Field(None, description="Material information")
    location: Optional[Dict[str, Any]] = Field(None, description="Storage location information")
    material_type_name: Optional[str] = Field(None, description="Material type name")
    material_name: Optional[str] = Field(None, description="Material name")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        orm_mode = True


class StorageAssignmentUpdate(BaseModel):
    """Schema for updating a storage assignment."""
    quantity: Optional[float] = Field(None, description="Updated quantity", gt=0)
    position: Optional[Dict[str, Any]] = Field(None, description="Updated position")
    notes: Optional[str] = Field(None, description="Updated notes")

    @validator('quantity')
    def validate_quantity(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Quantity must be positive")
        return v


class StorageAssignmentList(BaseModel):
    """Schema for paginated storage assignment list."""
    items: List[StorageAssignmentRead] = Field(..., description="List of storage assignments")
    total: int = Field(..., description="Total number of storage assignments matching the query")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    page_size: int = Field(..., description="Number of items per page")


# --- Storage Move Schemas ---

class StorageMoveBase(BaseModel):
    """Base schema for storage moves."""
    material_id: int = Field(..., description="ID of the moved material")
    from_storage_id: str = Field(..., description="Source storage location ID")
    to_storage_id: str = Field(..., description="Destination storage location ID")
    quantity: float = Field(..., description="Moved quantity", gt=0)
    reason: Optional[str] = Field(None, description="Reason for the move")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('to_storage_id')
    def validate_different_locations(cls, v, values):
        if 'from_storage_id' in values and v == values['from_storage_id']:
            raise ValueError("Source and destination storage locations must be different")
        return v


class StorageMoveCreate(StorageMoveBase):
    """Schema for creating a storage move."""

    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v


class StorageMoveRead(StorageMoveBase):
    """Schema for reading a storage move."""
    id: str = Field(..., description="Unique identifier")
    move_date: Optional[str] = Field(None, description="Date of movement")
    moved_by: Optional[str] = Field(None, description="Person who made the move")
    material: Optional[Dict[str, Any]] = Field(None, description="Material information")
    from_location: Optional[Dict[str, Any]] = Field(None, description="Source location information")
    to_location: Optional[Dict[str, Any]] = Field(None, description="Destination location information")
    from_location_name: Optional[str] = Field(None, description="Source location name")
    to_location_name: Optional[str] = Field(None, description="Destination location name")
    material_type_name: Optional[str] = Field(None, description="Material type name")
    material_name: Optional[str] = Field(None, description="Material name")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        orm_mode = True


class StorageMoveList(BaseModel):
    """Schema for paginated storage move list."""
    items: List[StorageMoveRead] = Field(..., description="List of storage moves")
    total: int = Field(..., description="Total number of storage moves matching the query")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    page_size: int = Field(..., description="Number of items per page")


# --- Analytics and Report Schemas ---

class StorageLocationUtilization(BaseModel):
    """Schema for storage location utilization data."""
    id: str = Field(..., description="Storage location ID")
    name: str = Field(..., description="Storage location name")
    capacity: int = Field(..., description="Total capacity")
    utilized: int = Field(..., description="Currently utilized")
    utilization_percentage: float = Field(..., description="Utilization percentage")
    storage_location_type: Optional[str] = Field(None, description="Storage location type name")


class StorageTypeUtilization(BaseModel):
    """Schema for storage type utilization summary."""
    capacity: float = Field(..., description="Total capacity for this type")
    utilized: float = Field(..., description="Total utilized for this type")
    locations: int = Field(..., description="Number of locations of this type")
    utilization_percentage: float = Field(..., description="Utilization percentage for this type")


class StorageSectionUtilization(BaseModel):
    """Schema for storage section utilization summary."""
    capacity: float = Field(..., description="Total capacity for this section")
    utilized: float = Field(..., description="Total utilized for this section")
    locations: int = Field(..., description="Number of locations in this section")
    utilization_percentage: float = Field(..., description="Utilization percentage for this section")


class MaterialTypeStorageInfo(BaseModel):
    """Schema for material type storage information."""
    material_type_id: int = Field(..., description="Material type ID")
    material_type_name: str = Field(..., description="Material type name")
    unique_materials: int = Field(..., description="Number of unique materials of this type in storage")
    total_quantity: float = Field(..., description="Total quantity of this material type in storage")


class StorageOccupancyReport(BaseModel):
    """Schema for comprehensive storage occupancy report."""
    total_locations: int = Field(..., description="Total number of storage locations")
    total_capacity: float = Field(..., description="Total storage capacity")
    total_utilized: float = Field(..., description="Total utilized capacity")
    total_items: int = Field(..., description="Total number of items in storage")
    utilization_percentage: float = Field(..., description="Overall utilization percentage")
    overall_usage_percentage: float = Field(..., description="Overall usage percentage")
    items_by_type: Dict[str, MaterialTypeStorageInfo] = Field(..., description="Items breakdown by material type")
    by_type: Dict[str, StorageTypeUtilization] = Field(..., description="Utilization by storage location type")
    by_section: Dict[str, StorageSectionUtilization] = Field(..., description="Utilization by section")
    locations_by_type: Dict[str, int] = Field(..., description="Location count by type")
    locations_by_section: Dict[str, int] = Field(..., description="Location count by section")
    locations_at_capacity: int = Field(..., description="Number of locations at or near capacity")
    locations_nearly_empty: int = Field(..., description="Number of nearly empty locations")
    most_utilized_locations: List[StorageLocationUtilization] = Field(..., description="Most utilized locations")
    least_utilized_locations: List[StorageLocationUtilization] = Field(..., description="Least utilized locations")
    recommendations: List[str] = Field(..., description="Optimization recommendations")


class MaterialTypeStorageSummary(BaseModel):
    """Schema for material type storage summary."""
    success: bool = Field(..., description="Whether the operation was successful")
    material_types: Dict[str, MaterialTypeStorageInfo] = Field(..., description="Material type summary")
    total_types: int = Field(..., description="Total number of material types in storage")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class StorageUtilizationSyncResult(BaseModel):
    """Schema for storage utilization synchronization result."""
    success: bool = Field(..., description="Whether the sync was successful")
    message: str = Field(..., description="Result message")
    updated_count: int = Field(..., description="Number of locations updated")
    updated_locations: List[Dict[str, Any]] = Field(..., description="Details of updated locations")


class StorageOperationResult(BaseModel):
    """Schema for general storage operation results."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Result message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional result data")


# --- Storage Search and Filter Schemas ---

class StorageSearchParams(BaseModel):
    """Schema for storage search parameters."""
    search: Optional[str] = Field(None, description="General search term")
    storage_location_type_id: Optional[int] = Field(None, description="Filter by storage location type")
    section: Optional[str] = Field(None, description="Filter by section")
    status: Optional[str] = Field(None, description="Filter by status")
    has_capacity: Optional[bool] = Field(None, description="Filter locations with available capacity")
    parent_storage_id: Optional[str] = Field(None, description="Filter by parent storage location")
    capacity_range: Optional[Dict[str, int]] = Field(None, description="Filter by capacity range")
    utilization_range: Optional[Dict[str, float]] = Field(None, description="Filter by utilization percentage range")


class StorageAssignmentSearchParams(BaseModel):
    """Schema for storage assignment search parameters."""
    material_id: Optional[int] = Field(None, description="Filter by material ID")
    material_type_id: Optional[int] = Field(None, description="Filter by material type ID")
    storage_id: Optional[str] = Field(None, description="Filter by storage location ID")
    assigned_by: Optional[str] = Field(None, description="Filter by who assigned")
    date_range: Optional[Dict[str, str]] = Field(None, description="Filter by assignment date range")


class StorageMoveSearchParams(BaseModel):
    """Schema for storage move search parameters."""
    material_id: Optional[int] = Field(None, description="Filter by material ID")
    material_type_id: Optional[int] = Field(None, description="Filter by material type ID")
    from_storage_id: Optional[str] = Field(None, description="Filter by source storage location")
    to_storage_id: Optional[str] = Field(None, description="Filter by destination storage location")
    moved_by: Optional[str] = Field(None, description="Filter by who moved")
    date_range: Optional[Dict[str, str]] = Field(None, description="Filter by move date range")
    reason: Optional[str] = Field(None, description="Filter by move reason")


# --- Storage Settings Schemas ---

class StorageUICardViewSettings(BaseModel):
    """Schema for storage UI card view settings."""
    display_thumbnail: bool = Field(True, description="Whether to display thumbnails in card view")
    max_properties: int = Field(4, description="Maximum number of properties to show in card view", ge=1, le=10)
    show_utilization: bool = Field(True, description="Whether to show utilization bars")


class StorageUIListViewSettings(BaseModel):
    """Schema for storage UI list view settings."""
    default_columns: List[str] = Field(
        ["name", "type", "capacity", "utilized", "section", "status"],
        description="Default columns to display in list view"
    )
    show_thumbnail: bool = Field(True, description="Whether to show thumbnails in list view")


class StorageUIGridViewSettings(BaseModel):
    """Schema for storage UI grid view settings."""
    show_utilization: bool = Field(True, description="Whether to show utilization indicators")
    show_capacity: bool = Field(True, description="Whether to show capacity indicators")
    compact_mode: bool = Field(False, description="Whether to use compact grid mode")


class StorageUISettings(BaseModel):
    """Schema for storage UI settings."""
    card_view: StorageUICardViewSettings = Field(default_factory=StorageUICardViewSettings)
    list_view: StorageUIListViewSettings = Field(default_factory=StorageUIListViewSettings)
    grid_view: StorageUIGridViewSettings = Field(default_factory=StorageUIGridViewSettings)


# --- Import/Export Schemas ---

class StorageLocationExport(BaseModel):
    """Schema for exporting storage location data."""
    storage_location_type: StorageLocationTypeRead
    storage_locations: List[StorageLocationRead]
    property_definitions: List[StoragePropertyDefinitionRead]
    settings: Optional[StorageUISettings] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StorageLocationImport(BaseModel):
    """Schema for importing storage location data."""
    storage_location_types: List[StorageLocationTypeCreate]
    storage_locations: List[StorageLocationCreate]
    property_definitions: List[StoragePropertyDefinitionCreate]
    settings: Optional[StorageUISettings] = None
    conflict_resolution: Optional[str] = Field("skip", description="How to handle conflicts (skip, overwrite, rename)")
    apply_settings: bool = Field(True, description="Whether to apply included settings")


class StorageImportResult(BaseModel):
    """Schema for storage import operation result."""
    success: bool = Field(..., description="Whether the import was successful")
    message: str = Field(..., description="Result message")
    created_storage_location_types: int = Field(0, description="Number of storage location types created")
    created_storage_locations: int = Field(0, description="Number of storage locations created")
    created_property_definitions: int = Field(0, description="Number of property definitions created")
    skipped_items: int = Field(0, description="Number of items skipped due to conflicts")
    errors: List[str] = Field([], description="List of error messages")
    warnings: List[str] = Field([], description="List of warning messages")


# --- Bulk Operation Schemas ---

class BulkStorageLocationUpdate(BaseModel):
    """Schema for bulk updating storage locations."""
    location_ids: List[str] = Field(..., description="List of storage location IDs to update")
    updates: StorageLocationUpdate = Field(..., description="Updates to apply to all selected locations")
    apply_to_children: bool = Field(False, description="Whether to apply updates to child locations as well")


class BulkStorageLocationResult(BaseModel):
    """Schema for bulk storage location operation result."""
    success: bool = Field(..., description="Whether the bulk operation was successful")
    message: str = Field(..., description="Result message")
    updated_count: int = Field(0, description="Number of locations successfully updated")
    failed_count: int = Field(0, description="Number of locations that failed to update")
    failed_locations: List[Dict[str, Any]] = Field([], description="Details of failed location updates")


class BulkStorageAssignmentCreate(BaseModel):
    """Schema for bulk creating storage assignments."""
    assignments: List[StorageAssignmentCreate] = Field(..., description="List of assignments to create")
    validate_capacity: bool = Field(True, description="Whether to validate storage capacity constraints")
    skip_on_error: bool = Field(True, description="Whether to skip items that cause errors")


class BulkStorageAssignmentResult(BaseModel):
    """Schema for bulk storage assignment operation result."""
    success: bool = Field(..., description="Whether the bulk operation was successful")
    message: str = Field(..., description="Result message")
    created_count: int = Field(0, description="Number of assignments successfully created")
    failed_count: int = Field(0, description="Number of assignments that failed to create")
    failed_assignments: List[Dict[str, Any]] = Field([], description="Details of failed assignment creations")


# --- Validation Helpers ---

class StorageLocationValidation(BaseModel):
    """Schema for storage location validation results."""
    is_valid: bool = Field(..., description="Whether the storage location configuration is valid")
    errors: List[str] = Field([], description="List of validation errors")
    warnings: List[str] = Field([], description="List of validation warnings")
    suggestions: List[str] = Field([], description="List of optimization suggestions")


class StorageCapacityCheck(BaseModel):
    """Schema for storage capacity check results."""
    has_capacity: bool = Field(..., description="Whether the storage location has available capacity")
    available_capacity: int = Field(..., description="Available capacity")
    required_capacity: int = Field(..., description="Required capacity for the operation")
    can_accommodate: bool = Field(..., description="Whether the location can accommodate the request")
    alternatives: List[Dict[str, Any]] = Field([],
                                               description="Alternative storage locations if this one cannot accommodate")


# --- Advanced Analytics Schemas ---

class StorageEfficiencyMetrics(BaseModel):
    """Schema for storage efficiency metrics."""
    space_utilization_score: float = Field(..., description="Overall space utilization score (0-100)")
    capacity_efficiency: float = Field(..., description="Capacity efficiency percentage")
    location_distribution_score: float = Field(..., description="How well materials are distributed across locations")
    accessibility_score: float = Field(..., description="How accessible stored materials are")
    recommendations: List[str] = Field([], description="Efficiency improvement recommendations")


class StorageTrendAnalysis(BaseModel):
    """Schema for storage trend analysis."""
    period: str = Field(..., description="Analysis period (daily, weekly, monthly)")
    utilization_trend: List[Dict[str, Any]] = Field(..., description="Utilization trend data points")
    assignment_trend: List[Dict[str, Any]] = Field(..., description="Assignment trend data points")
    move_trend: List[Dict[str, Any]] = Field(..., description="Movement trend data points")
    growth_rate: float = Field(..., description="Storage utilization growth rate")
    projected_full_date: Optional[str] = Field(None, description="Projected date when storage will be full")
    insights: List[str] = Field([], description="Trend insights and observations")


class StorageOptimizationSuggestion(BaseModel):
    """Schema for storage optimization suggestions."""
    type: str = Field(..., description="Type of optimization (consolidation, expansion, reorganization)")
    priority: str = Field(..., description="Priority level (high, medium, low)")
    description: str = Field(..., description="Description of the optimization")
    affected_locations: List[str] = Field([], description="Storage locations that would be affected")
    estimated_benefit: str = Field(..., description="Estimated benefit description")
    implementation_effort: str = Field(..., description="Implementation effort level")
    cost_impact: Optional[str] = Field(None, description="Estimated cost impact")


class StorageOptimizationReport(BaseModel):
    """Schema for comprehensive storage optimization report."""
    efficiency_metrics: StorageEfficiencyMetrics = Field(..., description="Current efficiency metrics")
    trend_analysis: StorageTrendAnalysis = Field(..., description="Trend analysis")
    optimization_suggestions: List[StorageOptimizationSuggestion] = Field(..., description="Optimization suggestions")
    quick_wins: List[str] = Field([], description="Quick optimization wins")
    long_term_recommendations: List[str] = Field([], description="Long-term strategic recommendations")
    generated_at: datetime = Field(default_factory=datetime.now, description="Report generation timestamp")