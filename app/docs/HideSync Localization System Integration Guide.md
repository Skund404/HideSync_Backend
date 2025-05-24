# HideSync Localization System Integration Guide

**Version:** 2.0  
**Last Updated:** May 24, 2025  
**Target Audience:** HideSync Developers

## Table of Contents

1. [Integration Overview](#integration-overview)
2. [Step-by-Step Integration](#step-by-step-integration)
3. [Service Layer Integration](#service-layer-integration)
4. [API Endpoint Enhancement](#api-endpoint-enhancement)
5. [Database Setup](#database-setup)
6. [Testing Integration](#testing-integration)
7. [Common Integration Patterns](#common-integration-patterns)
8. [Troubleshooting Integration Issues](#troubleshooting-integration-issues)

---

## Integration Overview

This guide shows how to integrate the localization system into existing HideSync services and endpoints. The integration is designed to be **non-breaking** and **gradual** - existing functionality continues to work while new translation capabilities are added.

### Integration Principles

✅ **Non-Breaking**: Existing code continues to work unchanged  
✅ **Opt-In**: Translation is enabled via optional parameters  
✅ **Backward Compatible**: APIs work with and without localization  
✅ **Gradual**: Integrate one service/endpoint at a time  

---

## Step-by-Step Integration

### Phase 1: Core Setup (One-Time)

#### 1.1 Verify Core Files Are in Place

Ensure these files have been added to your project:

```
app/
├── db/models/entity_translation.py
├── repositories/entity_translation_repository.py  
├── services/localization_service.py
├── schemas/entity_translation.py
├── schemas/translation_api.py
├── api/endpoints/translations.py
└── core/config.py (updated)
```

#### 1.2 Update Dependency Injection

Ensure `app/api/deps.py` includes:

```python
from app.services.localization_service import LocalizationService

def get_localization_service(db: Session = Depends(get_db)) -> LocalizationService:
    """Dependency provider for LocalizationService."""
    return LocalizationService(session=db)
```

#### 1.3 Register Translation API Routes

In `app/api/api.py`, add:

```python
from app.api.endpoints import translations

api_router.include_router(
    translations.router,
    prefix="/translations", 
    tags=["translations"]
)
```

#### 1.4 Run Database Migration

Create and run the migration for the `entity_translations` table:

```bash
# Generate migration
alembic revision --autogenerate -m "Add entity translations table"

# Apply migration  
alembic upgrade head
```

### Phase 2: Service Integration (Per Service)

Choose a service to integrate (we'll use `ProductService` as an example).

---

## Service Layer Integration

### Step 1: Update Service Constructor

**File**: `app/services/product_service.py`

**Before:**
```python
class ProductService:
    def __init__(
        self, 
        session: Session,
        repository: ProductRepository,
        inventory_service: InventoryService,
        # ... other dependencies
    ):
        self.session = session
        self.repository = repository
        self.inventory_service = inventory_service
```

**After:**
```python
from typing import Optional
from app.services.localization_service import LocalizationService

class ProductService:
    def __init__(
        self, 
        session: Session,
        repository: ProductRepository,
        inventory_service: InventoryService,
        localization_service: Optional[LocalizationService] = None,
        # ... other dependencies
    ):
        self.session = session
        self.repository = repository
        self.inventory_service = inventory_service
        # Add localization service with lazy initialization
        self.localization_service = localization_service or LocalizationService(session)
```

### Step 2: Add Localized Methods

Add new methods that support localization:

```python
def get_by_id(
    self, 
    product_id: int, 
    locale: Optional[str] = None
) -> Optional[Product]:
    """
    Get product by ID with optional localization.
    
    Args:
        product_id: Product ID
        locale: Optional locale for translations
        
    Returns:
        Product with translations applied if locale provided
    """
    # Get product using existing method
    product = self.repository.get_by_id(product_id)
    
    # Apply translations if locale provided
    if product and locale:
        product = self.localization_service.hydrate_entity_with_translations(
            entity=product,
            entity_type="product",
            locale=locale,
            fields_to_translate=["name", "description", "summary", "features"]
        )
    
    return product

def get_all(
    self,
    skip: int = 0,
    limit: int = 100, 
    locale: Optional[str] = None,
    # ... other filters
) -> List[Product]:
    """
    Get products with optional localization and pagination.
    
    Args:
        skip: Number of products to skip
        limit: Maximum number of products to return
        locale: Optional locale for translations
        
    Returns:
        List of products with translations applied if locale provided
    """
    # Get products using existing method
    products = self.repository.get_all(skip=skip, limit=limit)
    
    # Apply translations if locale provided
    if products and locale:
        products = self.localization_service.bulk_hydrate_entities(
            entities=products,
            entity_type="product",
            locale=locale,
            fields_to_translate=["name", "description", "summary", "features"]
        )
    
    return products

def get_localized_fields(
    self,
    product_id: int,
    locale: str
) -> Dict[str, str]:
    """
    Get all translated fields for a product in specific locale.
    
    Args:
        product_id: Product ID
        locale: Locale code
        
    Returns:
        Dictionary of field_name -> translated_value
    """
    return self.localization_service.get_translations_for_entity_by_locale(
        entity_type="product",
        entity_id=product_id,
        locale=locale
    )

def create_translation(
    self,
    product_id: int,
    locale: str,
    field_name: str,
    translated_value: str,
    user_id: Optional[int] = None
) -> bool:
    """
    Create or update translation for a product field.
    
    Args:
        product_id: Product ID
        locale: Locale code  
        field_name: Field to translate
        translated_value: Translation text
        user_id: User creating the translation
        
    Returns:
        True if successful
    """
    try:
        self.localization_service.create_or_update_translation(
            entity_type="product",
            entity_id=product_id,
            locale=locale,
            field_name=field_name,
            translated_value=translated_value,
            user_id=user_id
        )
        return True
    except Exception as e:
        # Log error appropriately
        return False
```

### Step 3: Update Dependency Injection

**File**: `app/api/deps.py`

**Before:**
```python
def get_product_service(
    db: Session = Depends(get_db),
    inventory_service: InventoryService = Depends(get_inventory_service),
    # ... other dependencies
) -> ProductService:
    product_repo = ProductRepository(session=db)
    return ProductService(
        session=db,
        repository=product_repo,
        inventory_service=inventory_service,
    )
```

**After:**
```python
def get_product_service(
    db: Session = Depends(get_db),
    inventory_service: InventoryService = Depends(get_inventory_service),
    localization_service: LocalizationService = Depends(get_localization_service),
    # ... other dependencies
) -> ProductService:
    product_repo = ProductRepository(session=db)
    return ProductService(
        session=db,
        repository=product_repo,
        inventory_service=inventory_service,
        localization_service=localization_service,
    )
```

---

## API Endpoint Enhancement

### Step 1: Add Locale Parameter to Existing Endpoints

**File**: `app/api/endpoints/products.py`

**Before:**
```python
@router.get("/{product_id}")
def get_product(
    product_id: int = Path(..., description="Product ID"),
    current_user: User = Depends(deps.get_current_active_user),
    product_service: ProductService = Depends(deps.get_product_service)
):
    product = product_service.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
```

**After:**
```python
from typing import Optional

@router.get("/{product_id}")
def get_product(
    product_id: int = Path(..., description="Product ID"),
    locale: Optional[str] = Query(None, description="Locale code for translations (e.g., 'en', 'de')"),
    current_user: User = Depends(deps.get_current_active_user),
    product_service: ProductService = Depends(deps.get_product_service)
):
    """
    Get product by ID with optional localization.
    
    The locale parameter enables translation of product fields to the specified language.
    If no locale is provided, original field values are returned.
    """
    product = product_service.get_by_id(product_id, locale=locale)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
```

### Step 2: Add Translation-Specific Endpoints

Add new endpoints specifically for translation management:

```python
# Add these to your products router

@router.get("/{product_id}/translations/{locale}")
def get_product_translations(
    product_id: int = Path(..., description="Product ID"),
    locale: str = Path(..., description="Locale code"),
    current_user: User = Depends(deps.get_current_active_user),
    product_service: ProductService = Depends(deps.get_product_service)
):
    """Get all translations for a product in specific locale."""
    translations = product_service.get_localized_fields(product_id, locale)
    return {
        "product_id": product_id,
        "locale": locale,
        "translations": translations
    }

@router.post("/{product_id}/translations")
def create_product_translation(
    product_id: int = Path(..., description="Product ID"),
    translation_request: dict = Body(..., example={
        "locale": "de",
        "field_name": "name", 
        "translated_value": "Deutscher Produktname"
    }),
    current_user: User = Depends(deps.get_current_active_user),
    product_service: ProductService = Depends(deps.get_product_service)
):
    """Create or update translation for a product field."""
    success = product_service.create_translation(
        product_id=product_id,
        locale=translation_request["locale"],
        field_name=translation_request["field_name"],
        translated_value=translation_request["translated_value"],
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create translation")
    
    return {"message": "Translation created successfully"}
```

### Step 3: Update List Endpoints

**Before:**
```python
@router.get("/")
def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(deps.get_current_active_user),
    product_service: ProductService = Depends(deps.get_product_service)
):
    return product_service.get_all(skip=skip, limit=limit)
```

**After:**
```python
@router.get("/")
def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    locale: Optional[str] = Query(None, description="Locale code for translations"),
    current_user: User = Depends(deps.get_current_active_user),
    product_service: ProductService = Depends(deps.get_product_service)
):
    """Get products with optional localization and pagination."""
    return product_service.get_all(skip=skip, limit=limit, locale=locale)
```

---

## Database Setup

### Step 1: Create Migration

```python
# Create new migration file
# File: alembic/versions/xxx_add_entity_translations.py

"""Add entity translations table

Revision ID: add_entity_translations
Revises: previous_revision
Create Date: 2025-05-24 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_entity_translations'
down_revision = 'previous_revision'  # Replace with actual

def upgrade() -> None:
    op.create_table(
        'entity_translations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('locale', sa.String(10), nullable=False),
        sa.Column('field_name', sa.String(50), nullable=False),
        sa.Column('translated_value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # Add indexes
    op.create_index('idx_entity_translation_lookup', 'entity_translations', 
                   ['entity_type', 'entity_id', 'locale', 'field_name'])
    op.create_unique_constraint('uq_entity_translation', 'entity_translations',
                               ['entity_type', 'entity_id', 'locale', 'field_name'])

def downgrade() -> None:
    op.drop_table('entity_translations')
```

### Step 2: Run Migration

```bash
# Generate the migration (if using autogenerate)
alembic revision --autogenerate -m "Add entity translations"

# Apply the migration
alembic upgrade head

# Verify migration
alembic current
```

### Step 3: Add Sample Data (Optional)

```python
# Script to add sample translations for testing
# File: scripts/add_sample_translations.py

from app.db.session import get_db
from app.services.localization_service import LocalizationService

def add_sample_translations():
    db = next(get_db())
    localization_service = LocalizationService(db)
    
    # Sample product translations
    sample_translations = [
        {
            "entity_type": "product",
            "entity_id": 1,
            "locale": "de", 
            "field_name": "name",
            "translated_value": "Deutscher Produktname"
        },
        {
            "entity_type": "product", 
            "entity_id": 1,
            "locale": "de",
            "field_name": "description", 
            "translated_value": "Deutsche Produktbeschreibung"
        },
        # Add more sample data...
    ]
    
    for translation_data in sample_translations:
        localization_service.create_or_update_translation(**translation_data)
        
    db.commit()
    print(f"Added {len(sample_translations)} sample translations")

if __name__ == "__main__":
    add_sample_translations()
```

---

## Testing Integration

### Step 1: Unit Tests

Create tests for the service integration:

```python
# File: tests/test_product_service_localization.py

import pytest
from app.services.product_service import ProductService
from app.services.localization_service import LocalizationService

class TestProductServiceLocalization:
    
    def test_get_product_with_locale(self, db_session, sample_product):
        # Setup
        product_service = ProductService(session=db_session)
        localization_service = LocalizationService(db_session)
        
        # Create translation
        localization_service.create_or_update_translation(
            entity_type="product",
            entity_id=sample_product.id,
            locale="de",
            field_name="name",
            translated_value="Deutscher Name"
        )
        
        # Test
        product = product_service.get_by_id(sample_product.id, locale="de")
        
        # Assert
        assert product is not None
        assert product.name == "Deutscher Name"
    
    def test_get_product_without_locale(self, db_session, sample_product):
        # Test that original behavior still works
        product_service = ProductService(session=db_session)
        product = product_service.get_by_id(sample_product.id)
        
        assert product is not None
        assert product.name == sample_product.name  # Original name
```

### Step 2: API Integration Tests

```python
# File: tests/test_product_api_localization.py

import pytest
from fastapi.testclient import TestClient

class TestProductAPILocalization:
    
    def test_get_product_with_locale_parameter(self, client: TestClient, auth_headers, sample_product):
        # Test API endpoint with locale parameter
        response = client.get(
            f"/api/v1/products/{sample_product.id}?locale=de",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        # Add assertions based on expected response structure
    
    def test_create_product_translation(self, client: TestClient, auth_headers, sample_product):
        # Test translation creation endpoint
        translation_data = {
            "locale": "de",
            "field_name": "name",
            "translated_value": "Deutscher Produktname"
        }
        
        response = client.post(
            f"/api/v1/products/{sample_product.id}/translations",
            json=translation_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "Translation created successfully" in response.json()["message"]
```

### Step 3: End-to-End Testing

```bash
# Manual testing with curl

# 1. Test basic endpoint (should work unchanged)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/products/1"

# 2. Test with locale parameter
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/products/1?locale=de"

# 3. Create a translation
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"locale":"de","field_name":"name","translated_value":"Test German Name"}' \
  "http://localhost:8000/api/v1/products/1/translations"

# 4. Test translation endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/translations/product/1/translations/de"
```

---

## Common Integration Patterns

### Pattern 1: Service Method Overloading

Instead of creating new methods, overload existing ones:

```python
# Original method signature
def get_by_id(self, product_id: int) -> Optional[Product]:
    return self.repository.get_by_id(product_id)

# Enhanced method signature (backward compatible)  
def get_by_id(self, product_id: int, locale: Optional[str] = None) -> Optional[Product]:
    product = self.repository.get_by_id(product_id)
    
    if product and locale:
        product = self.localization_service.hydrate_entity_with_translations(
            product, "product", locale
        )
    
    return product
```

### Pattern 2: Decorator-Based Translation

Create a decorator for automatic translation:

```python
from functools import wraps

def with_localization(entity_type: str, fields: List[str]):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, locale: Optional[str] = None, **kwargs):
            result = func(self, *args, **kwargs)
            
            if result and locale and hasattr(self, 'localization_service'):
                if isinstance(result, list):
                    result = self.localization_service.bulk_hydrate_entities(
                        result, entity_type, locale, fields
                    )
                else:
                    result = self.localization_service.hydrate_entity_with_translations(
                        result, entity_type, locale, fields
                    )
            
            return result
        return wrapper
    return decorator

# Usage
class ProductService:
    @with_localization("product", ["name", "description"])
    def get_by_id(self, product_id: int, locale: Optional[str] = None) -> Optional[Product]:
        return self.repository.get_by_id(product_id)
```

### Pattern 3: Response Model Enhancement

Add translation data to response models:

```python
# Enhanced response model
class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    # ... other fields
    
    # Optional translation metadata
    translations: Optional[Dict[str, Dict[str, str]]] = None
    applied_locale: Optional[str] = None

# In endpoint
@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, locale: Optional[str] = None):
    product = product_service.get_by_id(product_id, locale=locale)
    
    response_data = ProductResponse.from_orm(product)
    if locale:
        response_data.applied_locale = locale
        # Optionally include all available translations
        response_data.translations = get_all_translations_for_product(product_id)
    
    return response_data
```

---

## Troubleshooting Integration Issues

### Issue 1: Translation Not Applied

**Symptoms**: API returns original values despite locale parameter

**Diagnosis**:
```python
# Check if translation exists
translations = localization_service.get_translations_for_entity_by_locale(
    "product", product_id, "de"
)
print(f"Available translations: {translations}")

# Check entity registry configuration
supported_types = localization_service.get_supported_entity_types()
print(f"Supported entity types: {supported_types}")
```

**Solutions**:
- Verify translation exists in database
- Check entity type is in `ENTITY_REGISTRY`
- Ensure field name is in `translatable_fields`
- Verify locale is in `SUPPORTED_LOCALES`

### Issue 2: Service Dependency Injection Error

**Symptoms**: `LocalizationService` not injected properly

**Solution**:
```python
# Check dependency registration in deps.py
def get_localization_service(db: Session = Depends(get_db)) -> LocalizationService:
    return LocalizationService(session=db)

# Ensure service constructor accepts optional parameter
def __init__(self, localization_service: Optional[LocalizationService] = None):
    self.localization_service = localization_service or LocalizationService(session)
```

### Issue 3: Database Errors

**Symptoms**: `Table 'entity_translations' doesn't exist`

**Solution**:
```bash
# Check migration status
alembic current

# Apply missing migrations
alembic upgrade head

# Verify table exists
# In database client: SELECT * FROM entity_translations LIMIT 1;
```

### Issue 4: Performance Issues

**Symptoms**: Slow response times after adding localization

**Diagnosis**:
```python
# Check if bulk operations are used
# BAD: Multiple individual calls
for product in products:
    localized = localization_service.hydrate_entity_with_translations(
        product, "product", locale
    )

# GOOD: Single bulk call  
localized_products = localization_service.bulk_hydrate_entities(
    products, "product", locale
)
```

**Solutions**:
- Use bulk operations for multiple entities
- Enable caching: `TRANSLATION_CACHE_TTL=3600`
- Check database indexes are created
- Consider pagination for large result sets

### Issue 5: Fallback Not Working

**Symptoms**: Returns None instead of fallback value

**Diagnosis**:
```python
# Test fallback strategy
translation = localization_service.get_translation(
    "product", 123, "name", "fr", use_fallback=True
)
print(f"Translation result: {translation}")

# Check default locale configuration
print(f"Default locale: {localization_service.default_locale}")
```

**Solution**:
- Ensure `use_fallback=True` (default)
- Verify default locale has translations
- Check original entity has field values

---

## Integration Checklist

### Pre-Integration
- [ ] Core localization files are in place
- [ ] Database migration has been applied
- [ ] Configuration is updated
- [ ] Dependencies are registered

### Service Integration
- [ ] Service constructor accepts `LocalizationService`
- [ ] Localized methods are implemented
- [ ] Dependency injection is updated
- [ ] Backward compatibility is maintained

### API Integration  
- [ ] Endpoints have optional `locale` parameter
- [ ] Translation-specific endpoints are added
- [ ] Error handling is implemented
- [ ] Documentation is updated

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual API testing completed
- [ ] Performance is acceptable

### Deployment
- [ ] Migration applied to target environment
- [ ] Configuration deployed
- [ ] Monitoring/logging configured
- [ ] Rollback plan prepared

---

**Next Steps**: After completing integration for one service, use the same patterns to integrate other services incrementally. The localization system is designed to scale across all your entity types using the same proven patterns.