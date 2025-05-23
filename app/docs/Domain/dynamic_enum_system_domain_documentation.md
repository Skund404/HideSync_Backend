# Dynamic Enum System Documentation

## Overview

The Dynamic Enum System is a flexible, multi-language enumeration management solution built with FastAPI, SQLAlchemy, and Pydantic. It allows for runtime management of enumeration types and values with full internationalization support.

## Key Features

- **Dynamic Enum Management**: Create, update, and delete enum types and values at runtime
- **Multi-language Support**: Full internationalization with locale-specific translations
- **Hierarchical Values**: Support for parent-child relationships between enum values
- **System Protection**: Differentiate between system-managed and user-defined values
- **RESTful API**: Complete CRUD operations via HTTP endpoints
- **Type Safety**: Pydantic schemas ensure data validation and type safety

## Architecture

### Core Components

1. **Database Models** (`dynamic_enum.py`)
2. **API Schemas** (`enum.py`)
3. **Service Layer** (`enum_service.py`)
4. **API Endpoints** (`enums.py`)
5. **Seeding Scripts** (`seed_enum_types.py`)

## Database Schema

### EnumType Table
Stores metadata about each enum type in the system.

```sql
CREATE TABLE enum_types (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,           -- Display name (e.g., "Material Type")
    description VARCHAR(255),                    -- Optional description
    table_name VARCHAR(100) UNIQUE NOT NULL,     -- Dynamic table name (e.g., "enum_value_material_type")
    system_name VARCHAR(100) UNIQUE NOT NULL,    -- API identifier (e.g., "material_type")
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

### EnumTranslation Table
Stores localized translations for enum values.

```sql
CREATE TABLE enum_translations (
    id INTEGER PRIMARY KEY,
    enum_type VARCHAR(100) NOT NULL,             -- References EnumType.name
    enum_value VARCHAR(100) NOT NULL,            -- References dynamic table code
    locale VARCHAR(10) NOT NULL,                 -- Language code (e.g., "en", "de", "fr-CA")
    display_text VARCHAR(255) NOT NULL,          -- Localized display text
    description TEXT,                            -- Localized description
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE(enum_type, enum_value, locale)
);
```

### Dynamic Enum Value Tables
Each enum type gets its own table named `enum_value_{system_name}`.

```sql
CREATE TABLE enum_value_material_type (
    id INTEGER PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,           -- Technical identifier
    display_order INTEGER DEFAULT 0,            -- Sort order
    is_system BOOLEAN DEFAULT FALSE,             -- System-managed flag
    parent_id INTEGER,                           -- Hierarchical parent reference
    is_active BOOLEAN DEFAULT TRUE,              -- Active status
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

## API Reference

### Base URL
All enum endpoints are prefixed with `/api/enums`

### Authentication
All endpoints require authentication via the `get_current_active_user` dependency.

### Endpoints

#### Get All Enum Types
```http
GET /api/enums/types
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Material Type",
    "system_name": "material_type"
  }
]
```

#### Get All Enum Values (All Types)
```http
GET /api/enums/?locale=en
```

**Parameters:**
- `locale` (query, optional): Language code (default: "en")

**Response:**
```json
{
  "material_type": [
    {
      "id": 1,
      "code": "leather",
      "display_text": "Leather",
      "description": "Natural leather material",
      "display_order": 1,
      "is_system": true,
      "parent_id": null,
      "is_active": true
    }
  ]
}
```

#### Get Values for Specific Enum Type
```http
GET /api/enums/{enum_system_name}?locale=en
```

**Parameters:**
- `enum_system_name` (path): System name of the enum type
- `locale` (query, optional): Language code (default: "en")

**Response:**
```json
[
  {
    "id": 1,
    "code": "leather",
    "display_text": "Leather", 
    "description": "Natural leather material",
    "display_order": 1,
    "is_system": true,
    "parent_id": null,
    "is_active": true
  }
]
```

#### Create New Enum Value
```http
POST /api/enums/{enum_system_name}
```

**Request Body:**
```json
{
  "code": "synthetic_leather",
  "display_text": "Synthetic Leather",
  "description": "Artificial leather material",
  "display_order": 2,
  "is_system": false,
  "parent_id": null,
  "is_active": true
}
```

**Response:** `201 Created` with the created enum value

#### Update Enum Value
```http
PUT /api/enums/{enum_system_name}/{value_id}
```

**Request Body:**
```json
{
  "display_text": "Updated Display Text",
  "description": "Updated description",
  "display_order": 5,
  "is_active": false
}
```

**Response:** Updated enum value object

**Note:** Cannot modify `code` or `is_system` fields. System values have limited updatable fields.

#### Delete Enum Value
```http
DELETE /api/enums/{enum_system_name}/{value_id}
```

**Response:** `204 No Content`

**Note:** Cannot delete system values (`is_system: true`)

#### Create/Update Translation
```http
POST /api/enums/{enum_system_name}/{value_code}/translations
```

**Request Body:**
```json
{
  "locale": "de",
  "display_text": "Leder",
  "description": "Natürliches Ledermaterial"
}
```

**Response:** `201 Created` with translation object

#### Update Translation by ID
```http
PUT /api/enums/translations/{translation_id}
```

**Request Body:**
```json
{
  "display_text": "Updated German Text",
  "description": "Updated German description"
}
```

#### Delete Translation
```http
DELETE /api/enums/translations/{translation_id}
```

**Response:** `204 No Content`

## Usage Examples

### Python Client Usage

```python
import httpx

class EnumClient:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {auth_token}"}
    
    async def get_enum_values(self, enum_type: str, locale: str = "en"):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/enums/{enum_type}",
                params={"locale": locale},
                headers=self.headers
            )
            return response.json()
    
    async def create_enum_value(self, enum_type: str, value_data: dict):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/enums/{enum_type}",
                json=value_data,
                headers=self.headers
            )
            return response.json()

# Usage
client = EnumClient("https://api.example.com", "your-token")
materials = await client.get_enum_values("material_type", "de")
```

### Frontend Integration

```javascript
// React/TypeScript example
interface EnumValue {
  id: number;
  code: string;
  display_text: string;
  description?: string;
  display_order: number;
  is_system: boolean;
  parent_id?: number;
  is_active: boolean;
}

const useEnumValues = (enumType: string, locale: string = 'en') => {
  const [values, setValues] = useState<EnumValue[]>([]);
  
  useEffect(() => {
    fetch(`/api/enums/${enumType}?locale=${locale}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(setValues);
  }, [enumType, locale]);
  
  return values;
};

// Usage in component
const MaterialSelect = () => {
  const materials = useEnumValues('material_type', 'en');
  
  return (
    <select>
      {materials.map(material => (
        <option key={material.id} value={material.code}>
          {material.display_text}
        </option>
      ))}
    </select>
  );
};
```

## Service Layer Usage

```python
from app.services.enum_service import EnumService
from app.db.session import get_db

def example_service_usage():
    db = next(get_db())
    enum_service = EnumService(db)
    
    # Get all enum types
    types = enum_service.get_enum_types()
    
    # Get values for specific type with German translations
    values = enum_service.get_enum_values("material_type", "de")
    
    # Create new enum value
    new_value_data = {
        "code": "canvas",
        "display_text": "Canvas",
        "description": "Heavy-duty fabric material",
        "display_order": 10,
        "is_system": False,
        "is_active": True
    }
    created = enum_service.create_enum_value("material_type", new_value_data)
    
    # Add German translation
    translation_data = {
        "locale": "de",
        "display_text": "Segeltuch", 
        "description": "Schweres Stoffmaterial"
    }
    enum_service.create_or_update_translation("material_type", "canvas", translation_data)
```

## Setup and Configuration

### 1. Database Migration
Ensure the `enum_types` and `enum_translations` tables are created:

```python
# In your Alembic migration or database setup
from app.db.models.dynamic_enum import EnumType, EnumTranslation
```

### 2. Seed Enum Types
Run the seeding script to populate initial enum types:

```bash
python scripts/seed_enum_types.py
```

### 3. Create Dynamic Tables
For each enum type, create its corresponding `enum_value_*` table:

```sql
-- Example for material_type enum
CREATE TABLE enum_value_material_type (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(100) UNIQUE NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_system BOOLEAN DEFAULT 0,
    parent_id INTEGER,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4. Dependency Injection Setup
Ensure the `get_enum_service` dependency is configured:

```python
# In app/api/deps.py
from app.services.enum_service import EnumService

def get_enum_service(db: Session = Depends(get_db)) -> EnumService:
    return EnumService(db)
```

## Best Practices

### Naming Conventions
- **EnumType.name**: User-friendly display name (e.g., "Material Type")
- **EnumType.system_name**: Snake_case API identifier (e.g., "material_type")  
- **EnumType.table_name**: Database table name (e.g., "enum_value_material_type")
- **EnumValue.code**: Technical identifier (e.g., "vegetable_tanned_leather")

### Translation Management
- Always provide English (`en`) translations as the fallback
- Use descriptive locale codes (`en-US`, `fr-CA`, `de-AT`)
- Consider RTL languages when implementing frontend components

### System Values
- Mark core business values as `is_system: true`
- System values should not be deleted through the API
- Allow limited updates to system values (display_text, display_order)

### Performance Considerations
- Use `display_order` for consistent sorting
- Consider caching frequently accessed enum values
- Use `is_active` for soft deletion instead of hard deletion

### Error Handling
- The service layer raises `ValueError` for business logic errors
- API endpoints translate these to appropriate HTTP status codes
- All database operations are wrapped in transactions

## Troubleshooting

### Common Issues

**1. EnumType not found (404)**
```
Enum type 'invalid_type' not found
```
- Verify the enum type exists in the `enum_types` table
- Check the `system_name` spelling

**2. Duplicate code conflict (409)**
```
Value code 'existing_code' already exists for enum type 'material_type'
```
- Enum value codes must be unique within each enum type
- Use different codes or update the existing value

**3. Cannot modify system value (400)**
```
Cannot delete system value ID 1 ('leather') for type 'material_type'
```
- System values are protected from deletion
- Only certain fields can be updated on system values

**4. Translation locale validation**
- Ensure locale codes follow standard format (ISO 639-1)
- Minimum 2 characters, maximum 10 characters

### Logging
The system provides comprehensive logging at various levels:
- `INFO`: Normal operations and successful transactions
- `WARNING`: Potential issues or missing translations
- `ERROR`: Failed operations and validation errors
- `DEBUG`: Detailed SQL queries and internal operations

## Future Enhancements

Potential areas for expansion:
- **Audit Trail**: Track changes to enum values and translations
- **Bulk Operations**: Import/export enum data via CSV/JSON
- **Validation Rules**: Custom validation for enum value codes
- **Caching Layer**: Redis integration for high-performance lookups
- **Admin UI**: Web interface for non-technical enum management
- **API Versioning**: Support for schema evolution
- **Webhooks**: Notifications when enum values change