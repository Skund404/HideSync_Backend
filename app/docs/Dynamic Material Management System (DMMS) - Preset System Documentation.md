# Dynamic Material Management System (DMMS) - Preset System Documentation

https://claude.ai/chat/a9b94a0c-9ee2-41aa-a3f6-67060c3e393d

## Table of Contents
- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Data Models](#data-models)
- [API Endpoints](#api-endpoints)
- [Common Use Cases](#common-use-cases)
- [Troubleshooting](#troubleshooting)
- [Extension Points](#extension-points)

## Overview

The Preset System extends the Dynamic Material Management System (DMMS) to support sharing, reusing, and standardizing material configurations across users and organizations.

### Key Features

- **Preset Storage**: Save configuration blueprints for material types, properties, and sample materials
- **Selective Application**: Apply presets wholly or partially to a workshop environment
- **Conflict Resolution**: Handle naming conflicts with skip/overwrite/rename strategies
- **Community Sharing**: Import/export presets via JSON files
- **Settings Integration**: Apply user settings alongside material configuration

### Concepts

- **Preset**: A complete configuration blueprint that exists in the system but has no effect until applied
- **Preset Application**: The process of activating a preset, creating actual entities in the DMMS
- **Material Type**: A category of materials with defined properties (e.g., leather, wood)
- **Property Definition**: A reusable attribute that can be assigned to material types
- **Sample Material**: Example materials included in presets to demonstrate proper usage

## System Architecture

The Preset System follows the same layered architecture as the core DMMS:

1. **Database Layer**: Models for presets, applications, and errors
2. **Repository Layer**: Data access and persistence
3. **Service Layer**: Business logic and orchestration
4. **API Layer**: REST endpoints for client interaction

### Integration Points

The system integrates with these DMMS components:

- **PropertyDefinitionService**: For creating and updating property definitions
- **MaterialTypeService**: For creating and updating material types
- **DynamicMaterialService**: For creating sample materials
- **SettingsService**: For applying user settings

## Data Models

### MaterialPreset

Stores preset metadata and configuration.

```python
class MaterialPreset(Base, TimestampMixin):
    __tablename__ = "material_presets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    author = Column(String(255))
    is_public = Column(Boolean, default=False)
    _config = Column("config", Text, nullable=False)  # JSON configuration
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    applications = relationship("PresetApplication", back_populates="preset")
```

### PresetApplication

Records the application of a preset by a user.

```python
class PresetApplication(Base):
    __tablename__ = "preset_applications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    preset_id = Column(Integer, ForeignKey("material_presets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    _options_used = Column("options_used", Text)  # JSON options
    created_property_definitions = Column(Integer, default=0)
    updated_property_definitions = Column(Integer, default=0)
    created_material_types = Column(Integer, default=0)
    updated_material_types = Column(Integer, default=0)
    created_materials = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    
    # Relationships
    preset = relationship("MaterialPreset", back_populates="applications")
```

### PresetApplicationError

Records errors that occurred during preset application.

```python
class PresetApplicationError(Base):
    __tablename__ = "preset_application_errors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("preset_applications.id", ondelete="CASCADE"), nullable=False)
    error_type = Column(String(50), nullable=False)
    entity_type = Column(String(50))
    entity_name = Column(String(255))
    error_message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
```

### Config JSON Structure

The configuration is stored as JSON with this structure:

```json
{
  "metadata": {
    "version": "1.0.0",
    "created_at": "2025-04-01T00:00:00Z",
    "created_by": "username",
    "tags": ["leather", "craft"]
  },
  "property_definitions": [
    {
      "name": "leather_type",
      "data_type": "enum",
      "group_name": "Leather Properties",
      "validation_rules": {},
      "is_required": true,
      "has_multiple_values": false,
      "enum_options": [
        {"value": "veg_tan", "display_value": "Vegetable Tanned"},
        {"value": "chrome_tan", "display_value": "Chrome Tanned"}
      ]
    }
  ],
  "material_types": [
    {
      "name": "leather",
      "icon": "leather",
      "color_scheme": "amber",
      "ui_config": {},
      "storage_config": {},
      "properties": [
        {
          "property_name": "leather_type",
          "display_order": 1,
          "is_required": true,
          "is_filterable": true,
          "is_displayed_in_list": true,
          "is_displayed_in_card": true
        }
      ]
    }
  ],
  "sample_materials": [
    {
      "material_type": "leather",
      "name": "Natural Veg Tan",
      "status": "in_stock",
      "quantity": 1,
      "unit": "hide",
      "properties": {
        "leather_type": "veg_tan",
        "thickness": 2.0,
        "color": "#D4A76A"
      }
    }
  ],
  "settings": {
    "material_ui": {},
    "material_system": {}
  },
  "theme": {
    "system": {},
    "material_types": {}
  }
}
```

## API Endpoints

### List Presets

```
GET /api/presets
```

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: 100)
- `search`: Search term for name and description
- `is_public`: Filter by public status (true/false)
- `tags`: Filter by tag names (comma-separated)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "Leatherworking Standard",
      "description": "Standard preset for leatherworking",
      "author": "John Doe",
      "is_public": true,
      "config": { /* preset configuration */ },
      "created_at": "2025-05-20T10:00:00Z",
      "updated_at": "2025-05-20T10:00:00Z",
      "created_by": 1
    }
  ],
  "total": 10,
  "page": 1,
  "size": 100,
  "pages": 1
}
```

### Create Preset

```
POST /api/presets
```

**Request Body:**
```json
{
  "name": "Leatherworking Standard",
  "description": "Standard preset for leatherworking",
  "author": "John Doe",
  "is_public": true,
  "config": { /* preset configuration */ }
}
```

**Response:**
Created preset object.

### Get Preset

```
GET /api/presets/{preset_id}
```

**Response:**
Preset object.

### Update Preset

```
PUT /api/presets/{preset_id}
```

**Request Body:**
```json
{
  "name": "Updated Preset Name",
  "description": "Updated description",
  "is_public": true
}
```

**Response:**
Updated preset object.

### Delete Preset

```
DELETE /api/presets/{preset_id}
```

**Response:**
HTTP 204 No Content

### Import Preset

```
POST /api/presets/import
```

**Request:**
`multipart/form-data` with file upload.

**Response:**
Imported preset object.

### Export Preset

```
GET /api/presets/{preset_id}/export
```

**Response:**
JSON file download.

### Apply Preset

```
POST /api/presets/{preset_id}/apply
```

**Request Body:**
```json
{
  "material_types_to_include": ["leather", "thread"],
  "include_properties": true,
  "include_sample_materials": true,
  "include_settings": true,
  "theme_handling": "skip",
  "conflict_resolution": "skip"
}
```

**Response:**
```json
{
  "preset_id": 1,
  "user_id": 1,
  "applied_at": "2025-05-20T10:30:00Z",
  "options_used": { /* application options */ },
  "created_property_definitions": 5,
  "updated_property_definitions": 2,
  "created_material_types": 3,
  "updated_material_types": 0,
  "created_materials": 8,
  "errors": []
}
```

### Generate Preset

```
POST /api/presets/generate
```

**Query Parameters:**
- `material_type_ids`: List of material type IDs to include
- `name`: Name for the generated preset
- `description`: Description for the preset
- `include_samples`: Whether to include sample materials (default: true)
- `include_settings`: Whether to include settings (default: true)

**Response:**
Generated preset object.

## Common Use Cases

### Creating a Specialized Craft Preset

1. Set up your material types and properties for a specific craft
2. Create sample materials that demonstrate typical usage
3. Configure settings for optimal display
4. Use the Generate Preset endpoint to create a preset from your configuration
5. Make the preset public to share with the community

### Applying a Preset to a New Workshop

1. List available presets to find an appropriate one
2. Review the preset details to understand its configuration
3. Apply the preset with selective options:
   - Include only relevant material types
   - Choose whether to create sample materials
   - Set conflict resolution strategy

### Sharing Presets Across Organizations

1. Export the preset from the source organization
2. Share the JSON file securely
3. Import the preset in the target organization
4. Apply the preset with appropriate options

### Customizing Borrowed Presets

1. Import a preset from the community
2. Make a copy of the preset with a new name
3. Modify the configuration as needed
4. Apply the customized preset to your workshop

## Troubleshooting

### Common Issues

#### Preset Application Conflicts

**Issue**: Conflicts when applying a preset with existing material types or properties.

**Solution**: Use the appropriate conflict resolution strategy:
- `skip`: Leave existing items unchanged (safest option)
- `overwrite`: Replace existing items with imported ones
- `rename`: Rename imported items to avoid conflicts (e.g., "leather_1")

#### Missing Dependencies

**Issue**: Property references in material types that don't exist.

**Solution**: 
- Always include dependencies when generating presets
- Ensure `include_properties` is set to `true` when applying presets

#### Permission Issues

**Issue**: Unable to access or apply presets.

**Solution**:
- Ensure users have appropriate permissions
- Only the creator can modify non-public presets
- Public presets can be accessed by all users but only modified by the creator

### Error Handling

The `PresetApplicationError` model records detailed information about errors during preset application. If an application fails, check the error records for specific reasons.

**Common error types:**
- `property_error`: Issues with property definitions
- `material_type_error`: Issues with material types
- `sample_material_error`: Issues with sample materials
- `setting_error`: Issues with settings application
- `theme_error`: Issues with theme application
- `application_error`: General application issues

## Extension Points

The preset system was designed for extensibility. Here are key points where future enhancements can be made:

### Versioning Support

Future versions could add:
- Version tracking for presets
- Compatibility checking 
- Upgrade paths for older presets

### Advanced Sharing

The sharing mechanism could be extended with:
- Rating and review system
- Categorization and tagging
- Featured preset collections
- Premium paid presets

### Visual Builder

A UI layer could be added for:
- Visual preset creation
- Drag-and-drop property configuration
- Live preview of material cards
- Theme customization

### Dependency Management

Dependency handling could be enhanced with:
- Automatic dependency resolution
- Cross-preset dependencies
- Partial property inheritance

To extend the preset system, follow the existing architecture patterns and ensure proper integration with the DMMS core components.