# app/settings/material_settings.py

"""
Settings for the Dynamic Material Management System.

This module defines the default settings for the Dynamic Material Management System,
including UI preferences, default units, and system behavior.
"""

from typing import Dict, Any, List
import json

# Default Material UI Settings
DEFAULT_MATERIAL_UI_SETTINGS = {
    # Card View Settings
    "card_view": {
        "enabled": True,
        "display_thumbnail": True,
        "max_properties": 4,
        "show_status_indicator": True,
        "columns_per_row": 3
    },

    # List View Settings
    "list_view": {
        "enabled": True,
        "default_page_size": 50,
        "default_columns": ["name", "quantity", "unit", "status", "supplier"],
        "allow_column_customization": True,
        "show_thumbnail": True
    },

    # Detail View Settings
    "detail_view": {
        "properties_section_title": "Properties",
        "inventory_section_title": "Inventory Information",
        "supplier_section_title": "Supplier Information",
        "media_section_title": "Media",
        "notes_section_title": "Notes",
        "show_edit_button": True
    },

    # Wizard Settings
    "wizard": {
        "use_templates": True,
        "show_help_text": True,
        "required_fields_first": True
    }
}

# Default Material System Settings
DEFAULT_MATERIAL_SYSTEM_SETTINGS = {
    # Units
    "default_units": {
        "weight": "g",
        "length": "mm",
        "area": "cm²",
        "volume": "ml",
        "thickness": "mm"
    },

    # Inventory Settings
    "inventory": {
        "allow_negative_quantities": False,
        "show_low_stock_warnings": True,
        "low_stock_threshold_percent": 20,
        "auto_update_status": True,
        "require_adjustment_notes": False
    },

    # Search Settings
    "search": {
        "index_custom_properties": True,
        "fuzzy_search": True,
        "tag_based_search": True
    },

    # Import/Export Settings
    "import_export": {
        "csv_format": "standard",
        "allow_material_type_import": True,
        "include_properties_in_export": True,
        "include_media_in_export": False
    }
}

# Template Material Types
TEMPLATE_MATERIAL_TYPES = [
    {
        "name": "fabric",
        "display_name": "Fabric",
        "icon": "fabric",
        "color_scheme": "purple",
        "properties": [
            {"name": "color", "required": False, "filterable": True, "in_list": True, "in_card": True},
            {"name": "material_composition", "required": True, "filterable": True, "in_list": True, "in_card": True},
            {"name": "width", "required": True, "filterable": True, "in_list": True, "in_card": True},
            {"name": "weight", "required": False, "filterable": True, "in_list": False, "in_card": True},
            {"name": "pattern", "required": False, "filterable": True, "in_list": True, "in_card": True},
            {"name": "status", "required": True, "filterable": True, "in_list": True, "in_card": True}
        ]
    },
    {
        "name": "thread",
        "display_name": "Thread",
        "icon": "thread",
        "color_scheme": "blue",
        "properties": [
            {"name": "color", "required": False, "filterable": True, "in_list": True, "in_card": True},
            {"name": "material_composition", "required": True, "filterable": True, "in_list": True, "in_card": True},
            {"name": "thread_thickness", "required": True, "filterable": True, "in_list": True, "in_card": True},
            {"name": "thread_length", "required": False, "filterable": True, "in_list": False, "in_card": True},
            {"name": "status", "required": True, "filterable": True, "in_list": True, "in_card": True}
        ]
    },
    {
        "name": "dye",
        "display_name": "Dye",
        "icon": "dye",
        "color_scheme": "teal",
        "properties": [
            {"name": "color", "required": True, "filterable": True, "in_list": True, "in_card": True},
            {"name": "dye_type", "required": True, "filterable": True, "in_list": True, "in_card": True},
            {"name": "volume", "required": True, "filterable": True, "in_list": True, "in_card": True},
            {"name": "application_method", "required": False, "filterable": True, "in_list": False, "in_card": True},
            {"name": "status", "required": True, "filterable": True, "in_list": True, "in_card": True}
        ]
    }
]

# Template Properties for Custom Material Types
TEMPLATE_PROPERTIES = [
    {
        "name": "color",
        "display_name": "Color",
        "data_type": "string",
        "group_name": "Appearance",
        "is_required": False
    },
    {
        "name": "material_composition",
        "display_name": "Material Composition",
        "data_type": "string",
        "group_name": "Physical Properties",
        "is_required": False
    },
    {
        "name": "width",
        "display_name": "Width",
        "data_type": "number",
        "group_name": "Dimensions",
        "unit": "mm",
        "is_required": False
    },
    {
        "name": "length",
        "display_name": "Length",
        "data_type": "number",
        "group_name": "Dimensions",
        "unit": "mm",
        "is_required": False
    },
    {
        "name": "height",
        "display_name": "Height",
        "data_type": "number",
        "group_name": "Dimensions",
        "unit": "mm",
        "is_required": False
    },
    {
        "name": "weight",
        "display_name": "Weight",
        "data_type": "number",
        "group_name": "Physical Properties",
        "unit": "g",
        "is_required": False
    },
    {
        "name": "pattern",
        "display_name": "Pattern",
        "data_type": "string",
        "group_name": "Appearance",
        "is_required": False
    },
    {
        "name": "thread_thickness",
        "display_name": "Thread Thickness",
        "data_type": "string",
        "group_name": "Physical Properties",
        "is_required": False
    },
    {
        "name": "thread_length",
        "display_name": "Thread Length",
        "data_type": "number",
        "group_name": "Physical Properties",
        "unit": "m",
        "is_required": False
    },
    {
        "name": "dye_type",
        "display_name": "Dye Type",
        "data_type": "string",
        "group_name": "Physical Properties",
        "is_required": False
    },
    {
        "name": "volume",
        "display_name": "Volume",
        "data_type": "number",
        "group_name": "Physical Properties",
        "unit": "ml",
        "is_required": False
    },
    {
        "name": "application_method",
        "display_name": "Application Method",
        "data_type": "string",
        "group_name": "Usage",
        "is_required": False
    },
    {
        "name": "status",
        "display_name": "Status",
        "data_type": "enum",
        "group_name": "Inventory",
        "is_required": True
    }
]


# Get settings for registration in the settings framework
def get_material_settings() -> List[Dict[str, Any]]:
    """
    Get the dynamic material settings definitions for registration.

    Returns:
        List of setting definitions
    """
    return [
        {
            "key": "material_ui",
            "name": "Material UI",
            "description": "UI settings for the material management system",
            "data_type": "json",
            "default_value": DEFAULT_MATERIAL_UI_SETTINGS,
            "category": "materials",
            "subcategory": "ui",
            "applies_to": "user",
            "tier_availability": "all",
            "is_hidden": False,
            "ui_component": "json-editor"
        },
        {
            "key": "material_system",
            "name": "Material System",
            "description": "System settings for the material management",
            "data_type": "json",
            "default_value": DEFAULT_MATERIAL_SYSTEM_SETTINGS,
            "category": "materials",
            "subcategory": "system",
            "applies_to": "system",
            "tier_availability": "all",
            "is_hidden": False,
            "ui_component": "json-editor"
        },
        {
            "key": "material_templates",
            "name": "Material Templates",
            "description": "Template material types for new users",
            "data_type": "json",
            "default_value": TEMPLATE_MATERIAL_TYPES,
            "category": "materials",
            "subcategory": "templates",
            "applies_to": "system",
            "tier_availability": "all",
            "is_hidden": True,
            "ui_component": "json-editor"
        },
        {
            "key": "material_property_templates",
            "name": "Material Property Templates",
            "description": "Template properties for custom material types",
            "data_type": "json",
            "default_value": TEMPLATE_PROPERTIES,
            "category": "materials",
            "subcategory": "templates",
            "applies_to": "system",
            "tier_availability": "all",
            "is_hidden": True,
            "ui_component": "json-editor"
        }
    ]