# app/schemas/enum.py
from pydantic import BaseModel, Field, ConfigDict # Use ConfigDict for Pydantic v2
from typing import Optional, List, Dict

# Pydantic v1 compatibility - remove if using only v2
# from pydantic import BaseModel, Field
# try:
#     from pydantic import ConfigDict # Pydantic v2
# except ImportError:
#     ConfigDict = None # Placeholder for v1


# --- EnumType Schemas ---

class EnumTypeBase(BaseModel):
    name: str = Field(..., description="User-friendly display name (e.g., 'Material Type')")
    system_name: str = Field(..., description="Internal system name/key (e.g., 'material_type')")
    description: Optional[str] = Field(None, description="Optional description of the enum type")
    # table_name is usually an internal detail, might not need in API schema unless admin manages it
    # table_name: str = Field(..., description="Name of the database table holding values")

class EnumTypeRead(EnumTypeBase):
    id: int

    # For Pydantic v2
    model_config = ConfigDict(from_attributes=True)
    # For Pydantic v1
    # class Config:
    #     orm_mode = True


# --- EnumValue Schemas ---
# Represents data from the dynamic 'enum_value_...' tables

class EnumValueBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=100, description="Technical code for the enum value (e.g., 'vegetable_tanned')")
    display_text: str = Field(..., min_length=1, description="Default display text (usually English)")
    description: Optional[str] = Field(None, description="Optional description of the value")
    display_order: int = Field(0, ge=0, description="Order for displaying the value in lists")
    is_system: bool = Field(False, description="Indicates if this is a core system value (non-deletable, potentially restricted edits)")
    parent_id: Optional[int] = Field(None, description="Optional parent value ID for hierarchical enums")
    is_active: bool = Field(True, description="Indicates if the enum value is currently active and usable")

class EnumValueCreate(EnumValueBase):
    # Inherits all fields from Base, all are required on creation by default
    pass

class EnumValueUpdate(BaseModel):
    # Only allow updating specific fields, all optional
    display_text: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None # Allow setting to null/empty
    display_order: Optional[int] = Field(None, ge=0)
    parent_id: Optional[int] = None # Allow setting/unsetting parent
    is_active: Optional[bool] = None

    # Ensure at least one field is provided for update
    # You might add a root validator for this if using Pydantic v1, or check in endpoint/service

class EnumValueRead(EnumValueBase):
    id: int

    # For Pydantic v2
    model_config = ConfigDict(from_attributes=True)
    # For Pydantic v1
    # class Config:
    #     orm_mode = True


# --- EnumTranslation Schemas ---

class EnumTranslationBase(BaseModel):
    locale: str = Field(..., min_length=2, max_length=10, description="Locale code (e.g., 'de', 'fr-CA')")
    display_text: str = Field(..., min_length=1, description="Translated display text for this locale")
    description: Optional[str] = Field(None, description="Optional translated description for this locale")

class EnumTranslationCreate(EnumTranslationBase):
    # Inherits all required fields from Base
    pass

class EnumTranslationUpdate(BaseModel):
    # Only allow updating text fields, both optional
    display_text: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None # Allow setting to null/empty

class EnumTranslationRead(EnumTranslationBase):
    id: int
    # Include context from the database record
    enum_type: str = Field(..., description="The 'name' of the EnumType this translation belongs to")
    enum_value: str = Field(..., description="The 'code' of the EnumValue this translation belongs to")

    # For Pydantic v2
    model_config = ConfigDict(from_attributes=True)
    # For Pydantic v1
    # class Config:
    #     orm_mode = True