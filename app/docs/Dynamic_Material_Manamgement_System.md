# Dynamic Material Management System

## Overview

The Dynamic Material Management System (DMMS) provides a flexible, database-driven approach to managing materials inventory. Unlike the previous hardcoded material types, DMMS allows users to define, manage and extend custom material types with dynamic properties without requiring code changes or developer intervention.

## Key Features

- **Custom Material Types**: Create custom material types beyond the standard leather, hardware, and supplies
- **Dynamic Properties**: Define custom properties with various data types (string, number, boolean, enum, etc.)
- **Property Validation**: Set validation rules for property values to ensure data integrity
- **Multi-language Support**: Full localization support for material types and properties
- **Media Integration**: Attach images and other media to materials
- **Tag Support**: Categorize materials with tags for improved organization
- **Import/Export**: Export and import material types and configurations
- **Wizard Interface**: User-friendly wizards for easy material type creation
- **Templates**: Predefined templates for common maker categories
- **Dynamic UI**: Adaptive UI that changes based on material type
- **Powerful Search**: Search across all properties and material types

## Architecture

The DMMS follows a layered architecture:

1. **Database Layer**: Dynamic tables that store material types, properties, and values
2. **Repository Layer**: Data access objects for CRUD operations
3. **Service Layer**: Business logic and validation
4. **API Layer**: RESTful endpoints for frontend integration
5. **Frontend Layer**: Dynamic components that adapt to material types

## Database Schema

### Core Tables

- `material_types`: Defines available material types
- `material_type_translations`: Localized translations for material types
- `property_definitions`: Defines available properties and their data types
- `property_definition_translations`: Localized translations for properties
- `property_enum_options`: Custom enum options for properties
- `material_type_properties`: Junction table linking material types to properties
- `dynamic_materials`: Stores materials with their base attributes
- `material_property_values`: Stores the values of properties for each material
- `material_media`: Links media assets to materials
- `material_tags`: Links tags to materials

## Usage Guide

### Creating a New Material Type

1. Navigate to Material Types in the administration section
2. Click "Add Material Type"
3. Provide a name, icon, and color scheme for the material type
4. Add properties from the available property definitions
5. Configure display options for each property
6. Set required properties
7. Save the material type

### Adding a New Material

1. Navigate to the Materials section
2. Select "New Material"
3. Choose the material type
4. Fill out the base information (name, quantity, unit, etc.)
5. Enter values for the type-specific properties
6. Add tags if needed
7. Upload media
8. Save the material

### Managing Property Definitions

1. Navigate to Property Definitions in the administration section
2. View existing properties
3. Create new properties with appropriate data types
4. Add validation rules if needed
5. For enum properties, choose to use the dynamic enum system or custom options
6. Add translations for different languages

### Importing and Exporting

1. Navigate to Material Types
2. Select "Export" to export material type definitions
3. Use "Import" to import material type definitions from JSON files
4. This allows sharing material type configurations between systems

## API Reference

### Material Types API

- `GET /api/v1/material-types`: List all material types
- `POST /api/v1/material-types`: Create a new material type
- `GET /api/v1/material-types/{id}`: Get a specific material type
- `PUT /api/v1/material-types/{id}`: Update a material type
- `DELETE /api/v1/material-types/{id}`: Delete a material type
- `GET /api/v1/material-types/export`: Export material types
- `POST /api/v1/material-types/import`: Import material types

### Property Definitions API

- `GET /api/v1/property-definitions`: List all property definitions
- `POST /api/v1/property-definitions`: Create a new property definition
- `GET /api/v1/property-definitions/{id}`: Get a specific property definition
- `PUT /api/v1/property-definitions/{id}`: Update a property definition
- `DELETE /api/v1/property-definitions/{id}`: Delete a property definition
- `GET /api/v1/property-definitions/{id}/enum-values`: Get enum values for a property
- `POST /api/v1/property-definitions/{id}/enum-options`: Add an enum option to a property
- `DELETE /api/v1/property-definitions/{id}/enum-options/{option_id}`: Delete an enum option

### Dynamic Materials API

- `GET /api/v1/dynamic-materials`: List materials with filtering
- `POST /api/v1/dynamic-materials`: Create a new material
- `GET /api/v1/dynamic-materials/{id}`: Get a specific material
- `PUT /api/v1/dynamic-materials/{id}`: Update a material
- `DELETE /api/v1/dynamic-materials/{id}`: Delete a material
- `POST /api/v1/dynamic-materials/{id}/adjust-stock`: Adjust material stock
- `GET /api/v1/dynamic-materials/low-stock`: Get low stock materials
- `GET /api/v1/dynamic-materials/out-of-stock`: Get out of stock materials
- `POST /api/v1/dynamic-materials/{id}/media`: Attach media to a material
- `POST /api/v1/dynamic-materials/{id}/tags`: Add tags to a material
- `DELETE /api/v1/dynamic-materials/{id}/tags/{tag_name}`: Remove a tag from a material

## Settings

The DMMS provides several configurable settings:

### Material UI Settings

Controls the appearance and behavior of the material UI:
- Card view options
- List view options
- Detail view customization
- Wizard behavior

### Material System Settings

Controls system behavior:
- Default units for different measurements
- Inventory behavior (negative quantities, low stock warnings)
- Search configuration
- Import/export options

### Template Settings

Provides templates for:
- Common material types
- Standard properties

## Migration from Legacy System

The DMMS includes tools to migrate from the legacy material system:

1. All existing leather materials will be migrated to the "leather" material type
2. All existing hardware materials will be migrated to the "hardware" material type
3. All existing supplies materials will be migrated to the "supplies" material type
4. Appropriate properties will be created and populated based on existing fields

## Best Practices

1. **Property Naming**: Use clear, consistent naming for properties
2. **Group Related Properties**: Use the group_name field to organize properties
3. **Use Validation Rules**: Set appropriate validation rules for properties
4. **Provide Translations**: Add translations for material types and properties
5. **Use Templates**: Start with templates when creating new material types
6. **Use Tags**: Apply tags for easier searching and filtering
7. **Optimize Properties**: Only include properties that are genuinely needed
8. **Consider UI Display**: Configure which properties appear in lists and cards

## Limitations

1. Cannot change a material's type after creation
2. System material types cannot be deleted
3. Properties used by material types cannot be deleted