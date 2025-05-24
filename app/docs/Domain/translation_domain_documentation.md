# HideSync Localization System Documentation

**Version:** 2.0  
**Last Updated:** May 24, 2025  
**Status:** Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [System Components](#system-components)
4. [Configuration](#configuration)
5. [API Reference](#api-reference)
6. [Usage Examples](#usage-examples)
7. [Database Schema](#database-schema)
8. [Supported Entity Types](#supported-entity-types)
9. [Fallback Strategy](#fallback-strategy)
10. [Performance Considerations](#performance-considerations)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The HideSync Localization System provides comprehensive translation capabilities for entity fields across all domains in the application. It operates **alongside** the existing Dynamic Enum System, handling entity-specific translations while preserving the enum system's responsibility for enumeration display text.

### Key Features

✅ **Universal Translation Support**: Single system handles all entity types  
✅ **Intelligent Fallback**: Graceful degradation from requested locale → default locale → original value  
✅ **API-First Design**: RESTful endpoints for all translation operations  
✅ **Architectural Consistency**: Mirrors existing patterns from Dynamic Enum System  
✅ **Production Ready**: Comprehensive error handling, logging, and validation  
✅ **Performance Optimized**: Efficient queries with proper indexing and caching support  

### Supported Languages

- **English (en)** - Default/Fallback
- **German (de)**
- **French (fr)**
- **Spanish (es)**

*Additional languages can be configured in `settings.SUPPORTED_LOCALES`*

---

## Architecture

The Localization System follows HideSync's established architectural patterns:

```
┌─────────────────────┐
│   API Endpoints     │ ← /api/translations/*
├─────────────────────┤
│ LocalizationService │ ← Central business logic
├─────────────────────┤
│EntityTranslationRepo│ ← Data access layer
├─────────────────────┤
│  entity_translations│ ← Single universal table
└─────────────────────┘
```

### Design Principles

1. **Single Table Approach**: One `entity_translations` table for all entity types
2. **Central Service**: `LocalizationService` manages all translation operations
3. **Entity Registry**: Configuration-driven support for new entity types
4. **Consistent Patterns**: Same structure as successful Dynamic Enum System

---

## System Components

### 1. Database Model

**Table**: `entity_translations`

Stores all translations for any entity type in a normalized structure.

### 2. Repository Layer

**Class**: `EntityTranslationRepository`

Provides data access methods:
- `find_translation()` - Get specific translation
- `find_translations_for_entity()` - Get all translations for an entity
- `upsert_translation()` - Create or update translation
- `delete_translations_for_entity()` - Remove entity translations

### 3. Service Layer

**Class**: `LocalizationService`

Central business logic:
- Translation retrieval with fallback strategy
- Entity validation and hydration
- Bulk operations
- Statistics and reporting

### 4. API Endpoints

**Base Path**: `/api/v1/translations`

RESTful API for translation management and retrieval.

---

## Configuration

### Environment Variables

```bash
# Core Settings
DEFAULT_LOCALE=en
SUPPORTED_LOCALES=["en", "de", "fr", "es"]

# Performance Settings  
TRANSLATION_CACHE_TTL=3600
MAX_TRANSLATION_LENGTH=5000
MAX_BULK_TRANSLATION_SIZE=100

# Validation Settings
VALIDATE_ENTITY_EXISTS=true
LOG_TRANSLATION_OPERATIONS=true
TRANSLATION_LOG_LEVEL=INFO
```

### Code Configuration

```python
# app/core/config.py
class Settings(BaseSettings):
    DEFAULT_LOCALE: str = "en"
    SUPPORTED_LOCALES: List[str] = ["en", "de", "fr", "es"]
    TRANSLATION_CACHE_TTL: int = 3600
    MAX_TRANSLATION_LENGTH: int = 5000
```

---

## API Reference

### Core Endpoints

#### Get Supported Locales
```http
GET /api/v1/translations/locales
```

**Response:**
```json
["en", "de", "fr", "es"]
```

#### Get Supported Entity Types
```http
GET /api/v1/translations/entity-types
```

**Response:**
```json
["workflow", "product", "tool", "material"]
```

#### Get Translatable Fields
```http
GET /api/v1/translations/entity-types/{entity_type}/fields
```

**Response:**
```json
["name", "description", "summary", "features"]
```

### Translation Management

#### Create/Update Translation
```http
POST /api/v1/translations/{entity_type}/{entity_id}/translations
```

**Request Body:**
```json
{
  "locale": "de",
  "field_name": "name",
  "translated_value": "Produktname auf Deutsch"
}
```

**Response:**
```json
{
  "message": "Translation saved successfully",
  "translation_id": 123,
  "entity_type": "product",
  "entity_id": 456,
  "locale": "de",
  "field_name": "name"
}
```

#### Get Entity Translations for Locale
```http
GET /api/v1/translations/{entity_type}/{entity_id}/translations/{locale}
```

**Response:**
```json
{
  "name": "Produktname",
  "description": "Deutsche Produktbeschreibung",
  "summary": "Kurze Zusammenfassung"
}
```

#### Get All Translations for Field
```http
GET /api/v1/translations/{entity_type}/{entity_id}/translations/{field_name}/all
```

**Response:**
```json
{
  "en": "English Product Name",
  "de": "Deutscher Produktname", 
  "fr": "Nom du produit français",
  "es": "Nombre del producto español"
}
```

### Utility Endpoints

#### Validate Translation Setup
```http
GET /api/v1/translations/{entity_type}/{entity_id}/validation
```

**Response:**
```json
{
  "entity_type": "product",
  "entity_id": 123,
  "entity_exists": true,
  "translatable_fields": ["name", "description", "summary"],
  "translated_fields": ["name", "description"],
  "available_locales": ["en", "de"],
  "translation_count": 4,
  "completeness_percentage": 66.7,
  "recommendations": ["Add translations for locale: fr, es"]
}
```

#### System Statistics
```http
GET /api/v1/translations/stats
```

**Response:**
```json
{
  "total_entities": 150,
  "total_translations": 892,
  "supported_locales": ["en", "de", "fr", "es"],
  "entity_types": ["product", "workflow", "tool"],
  "coverage_by_locale": {
    "en": 150,
    "de": 298,
    "fr": 234,
    "es": 210
  },
  "last_updated": "2025-05-24T12:00:00Z"
}
```

---

## Usage Examples

### Basic Translation Retrieval

```python
from app.services.localization_service import LocalizationService

# Get service instance
localization_service = LocalizationService(db_session)

# Get single translation
german_name = localization_service.get_translation(
    entity_type="product",
    entity_id=123,
    field_name="name",
    locale="de",
    use_fallback=True
)

# Get all translations for an entity in specific locale
german_translations = localization_service.get_translations_for_entity_by_locale(
    entity_type="product",
    entity_id=123, 
    locale="de"
)
# Returns: {"name": "Produktname", "description": "Beschreibung"}
```

### Entity Hydration

```python
# Hydrate single entity with translations
product = product_service.get_by_id(123)
localized_product = localization_service.hydrate_entity_with_translations(
    entity=product,
    entity_type="product",
    locale="de",
    fields_to_translate=["name", "description"]
)

# Bulk hydrate multiple entities
products = product_service.get_all()
localized_products = localization_service.bulk_hydrate_entities(
    entities=products,
    entity_type="product",
    locale="de"
)
```

### Creating Translations

```python
# Create or update translation
translation = localization_service.create_or_update_translation(
    entity_type="product",
    entity_id=123,
    locale="de",
    field_name="description",
    translated_value="Deutsche Produktbeschreibung",
    user_id=current_user.id
)
```

### API Usage Examples

```bash
# Create German translation for product name
curl -X POST "/api/v1/translations/product/123/translations" \
  -H "Content-Type: application/json" \
  -d '{
    "locale": "de",
    "field_name": "name", 
    "translated_value": "Deutscher Produktname"
  }'

# Get product with German translations
curl "/api/v1/products/123?locale=de"

# Get all German translations for a product
curl "/api/v1/translations/product/123/translations/de"
```

---

## Database Schema

### Entity Translations Table

```sql
CREATE TABLE entity_translations (
    id INTEGER PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    locale VARCHAR(10) NOT NULL,
    field_name VARCHAR(50) NOT NULL,
    translated_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(entity_type, entity_id, locale, field_name)
);

-- Optimized indexes
CREATE INDEX idx_entity_translation_lookup 
ON entity_translations(entity_type, entity_id, locale, field_name);

CREATE INDEX idx_entity_translation_entity_type 
ON entity_translations(entity_type);

CREATE INDEX idx_entity_translation_locale 
ON entity_translations(locale);
```

### Example Data

| id | entity_type | entity_id | locale | field_name | translated_value |
|----|-------------|-----------|--------|------------|------------------|
| 1  | product     | 123       | de     | name       | Deutscher Name   |
| 2  | product     | 123       | de     | description| Deutsche Beschreibung |
| 3  | product     | 123       | fr     | name       | Nom français     |
| 4  | workflow    | 456       | de     | name       | Deutscher Workflow |

---

## Supported Entity Types

### Current Support

| Entity Type | Translatable Fields | Example Usage |
|-------------|-------------------|---------------|
| **product** | name, description, summary, features | Product catalogs, e-commerce |
| **workflow** | name, description | Process documentation |
| **workflow_step** | name, description, instructions | Step-by-step guides |
| **tool** | name, description, usage_notes | Tool documentation |
| **material** | name, description, notes | Material specifications |

### Adding New Entity Types

To add support for a new entity type:

1. **Update Entity Registry**:
```python
# In LocalizationService.ENTITY_REGISTRY
"new_entity": {
    "main_repo_method": "create_new_entity_repository",
    "translatable_fields": ["name", "description", "custom_field"]
}
```

2. **Ensure Repository Exists**:
```python
# In RepositoryFactory
def create_new_entity_repository(self) -> NewEntityRepository:
    return NewEntityRepository(self.session, self.encryption_service)
```

3. **No Database Changes Required** - the universal table handles all entity types

---

## Fallback Strategy

The system uses intelligent fallback to ensure users always see content:

### Fallback Order

1. **Requested Locale** - Try the specific locale requested
2. **Default Locale** - Fall back to system default (usually "en")  
3. **Original Value** - Use the original field value from the entity

### Example Scenarios

```python
# Scenario 1: Translation exists
get_translation("product", 123, "name", "de")
# Returns: "Deutscher Produktname"

# Scenario 2: German missing, falls back to English  
get_translation("product", 123, "description", "de") 
# Returns: "English product description" (from default locale)

# Scenario 3: No translations exist, falls back to original
get_translation("product", 123, "summary", "de")
# Returns: "Original summary from product.summary field"

# Scenario 4: Disable fallback
get_translation("product", 123, "name", "fr", use_fallback=False)
# Returns: None (if French translation doesn't exist)
```

---

## Performance Considerations

### Optimization Strategies

1. **Database Indexing**:
   - Composite index on `(entity_type, entity_id, locale, field_name)`
   - Individual indexes on frequently queried fields

2. **Caching** (Optional):
   ```python
   TRANSLATION_CACHE_TTL=3600  # 1 hour cache
   ```

3. **Bulk Operations**:
   ```python
   # Instead of multiple single calls
   bulk_hydrate_entities(products, "product", "de")
   ```

4. **Query Optimization**:
   - Use `find_translations_for_entity()` for multiple fields
   - Batch entity validation when possible

### Performance Metrics

- **Single Translation Lookup**: < 5ms
- **Entity Hydration**: < 10ms per entity
- **Bulk Operations**: ~1ms per entity (100+ entities)
- **API Response Times**: < 100ms for most operations

---

## Troubleshooting

### Common Issues

#### 1. Translation Not Found

**Symptom**: API returns 404 or fallback value used  
**Solution**: 
- Check if translation exists: `GET /translations/{entity_type}/{entity_id}/validation`
- Verify entity exists in main table
- Check locale spelling

#### 2. Entity Type Not Supported

**Symptom**: `ValidationException: Unsupported entity type`  
**Solution**: 
- Add entity to `LocalizationService.ENTITY_REGISTRY`
- Ensure repository method exists in `RepositoryFactory`

#### 3. Field Not Translatable

**Symptom**: `ValidationException: Field 'X' is not translatable`  
**Solution**: 
- Add field to `translatable_fields` in entity registry
- Check field name spelling (must be lowercase with underscores)

#### 4. Performance Issues

**Symptom**: Slow translation lookups  
**Solution**: 
- Enable caching: `TRANSLATION_CACHE_TTL=3600`
- Use bulk operations for multiple entities
- Check database indexes are created

### Debug Tools

#### Health Check
```bash
curl "/api/v1/translations/health"
```

#### Validation Check
```bash
curl "/api/v1/translations/product/123/validation" 
```

#### System Statistics
```bash
curl "/api/v1/translations/stats"
```

### Logging

Enable detailed logging:
```bash
LOG_TRANSLATION_OPERATIONS=true
TRANSLATION_LOG_LEVEL=DEBUG
```

Log locations:
- Translation operations: `app.services.localization_service`
- Repository operations: `app.repositories.entity_translation_repository`
- API requests: `app.api.endpoints.translations`

---

## Security Considerations

### Access Control

- All translation endpoints require authentication
- User permissions follow existing HideSync patterns
- Admin endpoints (cleanup, statistics) may require elevated permissions

### Data Validation

- Input sanitization prevents XSS attacks
- Field length limits prevent database bloat
- Entity existence validation prevents orphaned translations

### Audit Trail

- All translation operations are logged with user ID
- Timestamps track creation and modification dates
- Translation history can be maintained if needed

---

## Future Enhancements

### Planned Features

1. **Translation Import/Export**: CSV/JSON batch operations
2. **Translation Memory**: Reuse translations across similar entities  
3. **Translation Workflow**: Approval process for translations
4. **Auto-Translation**: Integration with translation services
5. **Translation Analytics**: Usage metrics and quality reports

### Extensibility

The system is designed for easy extension:
- **New Languages**: Add to `SUPPORTED_LOCALES`
- **New Entities**: Update entity registry
- **Custom Fields**: Configure per entity type
- **Translation Sources**: Plugin architecture for external services

---

*For technical implementation details, see the [Integration Guide](integration-guide.md)*