# File: app/api/v1/endpoints/products.py

import logging
from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
    Body,
)
from sqlalchemy.orm import Session

# --- Application Imports ---
# Import the CORRECT dependency injectors from deps.py
from app.api.deps import (
    get_current_active_user,
    get_product_service,
    # PermissionsChecker, # Uncomment if you implement permission checks
)
from app.db.session import get_db
from app.schemas.product import (
    ProductCreate,
    ProductList,
    ProductResponse,
    ProductUpdate,
    ProductFilter,
)
# ProductService will be injected via the dependency
from app.services.product_service import ProductService
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    BusinessRuleException,
    HideSyncException, # Import if service layer might raise it directly to endpoint
)

# --- Router Setup ---
router = APIRouter()
logger = logging.getLogger(__name__)

# --- API Endpoints ---

@router.get(
    "/",
    response_model=ProductList,
    summary="List Products",
    description="Retrieve a list of products with filtering and pagination.",
    # dependencies=[Depends(PermissionsChecker(["product:read"]))], # Optional: Add permissions
)
def list_products(
    *,
    # Use the imported get_product_service from deps.py
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of records to return"
    ),
    # --- Filtering Parameters (match frontend and ProductFilter schema) ---
    search_query: Optional[str] = Query(None, alias="searchQuery", description="Search by name, SKU, description"),
    status: Optional[List[str]] = Query(None, description="Filter by inventory status (e.g., IN_STOCK)"),
    product_type: Optional[List[str]] = Query(None, alias="productType", description="Filter by product type (e.g., WALLET)"),
    storage_location: Optional[str] = Query(None, alias="storageLocation", description="Filter by storage location"),
    # Parse date range using alias matching frontend 'dateAddedRange[from]' pattern
    date_from: Optional[str] = Query(None, alias="dateAddedRange[from]", description="Start date for date added (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, alias="dateAddedRange[to]", description="End date for date added (YYYY-MM-DD)"),
    # Parse price range using alias matching frontend 'priceRange[min]' pattern
    min_price: Optional[float] = Query(None, alias="priceRange[min]", ge=0, description="Minimum selling price"),
    max_price: Optional[float] = Query(None, alias="priceRange[max]", ge=0, description="Maximum selling price"),
    # Add other filters as needed, e.g., pattern_id, project_id
    pattern_id: Optional[int] = Query(None, alias="patternId", ge=1, description="Filter by pattern ID"),
    project_id: Optional[int] = Query(None, alias="projectId", ge=1, description="Filter by project ID"),

) -> ProductList:
    """
    Endpoint to retrieve a list of products with filtering and pagination.
    Matches the filters used by the `useFilteredProducts` hook or similar frontend logic.
    """
    logger.info(
        f"Listing products request received. User: {getattr(current_user, 'id', 'N/A')}. Skip: {skip}, Limit: {limit}, Filters: "
        f"search='{search_query}', status={status}, type={product_type}, loc='{storage_location}', "
        f"date={date_from}-{date_to}, price={min_price}-{max_price}, pattern={pattern_id}, project={project_id}"
    )

    # --- Construct Filter Object ---
    # Ensure ProductFilter schema aligns with these parameters and aliases
    try:
        filters = ProductFilter(
            productType=product_type,
            status=status,
            priceRange={"min": min_price, "max": max_price} if min_price is not None or max_price is not None else None,
            dateAddedRange={"from": date_from, "to": date_to} if date_from or date_to else None,
            searchQuery=search_query,
            storageLocation=storage_location,
            # Add any other filters defined in ProductFilter schema here
            # pattern_id=pattern_id, # Example if added to schema
            # project_id=project_id, # Example if added to schema
        )
    except Exception as e: # Catch potential Pydantic validation errors during filter creation
         logger.warning(f"Error constructing ProductFilter: {e}", exc_info=True)
         raise HTTPException(
              status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
              detail=f"Invalid filter parameters provided: {e}"
         )

    try:
        # Call the service method responsible for fetching paginated/filtered data
        paginated_data = product_service.list_products_paginated(
            skip=skip, limit=limit, filters=filters
        )

        items_orm = paginated_data['items']
        total = paginated_data['total']
        size = limit
        pages = (total + size - 1) // size if size > 0 else 0
        current_page = (skip // size) + 1

        logger.info(f"Found {total} products matching criteria. Returning page {current_page}/{pages}.")

        # Convert ORM items to response schema items
        # Use model_validate for Pydantic v2
        items_response = [ProductResponse.model_validate(item) for item in items_orm]

        return ProductList(
            items=items_response,
            total=total,
            page=current_page,
            size=size,
            pages=pages
        )

    except ValidationException as e:
        logger.warning(f"Validation error listing products: {e.errors}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except Exception as e:
        logger.error(f"Unexpected error listing products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving products.",
        )

@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
    description="Create a new product record along with its initial inventory details.",
    # dependencies=[Depends(PermissionsChecker(["product:create"]))], # Optional: Add permissions
)
def create_product(
    *,
    product_in: ProductCreate, # Use ProductCreate schema for input validation
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    """
    Endpoint to create a new product. Accepts product details and optional
    initial inventory quantity and location via the ProductCreate schema.
    """
    user_id = getattr(current_user, 'id', None)
    logger.info(f"Create product request received for SKU: {product_in.sku} by user: {user_id}")
    try:
        # The service method now handles creating the product AND its inventory record
        created_product_orm = product_service.create_product(
            product_in=product_in, user_id=user_id
        )
        logger.info(f"Product and initial inventory created successfully for Product ID: {created_product_orm.id}")

        # The ORM object returned by the service should have the inventory loaded
        # due to the service logic (session.refresh or eager loading).
        # Convert ORM object to response schema using Pydantic v2 method
        return ProductResponse.model_validate(created_product_orm)

    except ValidationException as e:
        logger.warning(f"Validation error creating product: {e.errors}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except BusinessRuleException as e: # E.g., SKU already exists
        logger.warning(f"Business rule violation creating product '{product_in.sku}': {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e.detail)
        )
    except HideSyncException as e: # Catch potential errors from inventory creation within service
        logger.error(f"Internal error creating product '{product_in.sku}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating product '{product_in.sku}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the product.",
        )

@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get Product by ID",
    description="Retrieve a single product by its unique ID, including its current inventory status.",
    # dependencies=[Depends(PermissionsChecker(["product:read"]))], # Optional: Add permissions
)
def get_product(
    *,
    product_id: int = Path(..., ge=1, description="The ID of the product to retrieve"),
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    """
    Endpoint to retrieve a specific product by its ID.
    The response includes fields populated from the associated inventory record.
    """
    logger.info(f"Get product request received for ID: {product_id} by user: {getattr(current_user, 'id', 'N/A')}")
    try:
        # Service method should ensure inventory is loaded for the response schema
        product_orm = product_service.get_product_by_id(product_id=product_id, load_inventory=True)
        if not product_orm:
            # Raise specific exception caught below
            raise EntityNotFoundException("Product", product_id)

        logger.info(f"Product ID {product_id} found.")
        # Convert ORM object to response schema using Pydantic v2 method
        return ProductResponse.model_validate(product_orm)

    except EntityNotFoundException:
        logger.warning(f"Product not found with ID: {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found."
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving product ID {product_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the product.",
        )

@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update Product",
    description="Update an existing product's details. Does not update inventory quantity directly.",
    # dependencies=[Depends(PermissionsChecker(["product:update"]))], # Optional: Add permissions
)
def update_product(
    *,
    product_id: int = Path(..., ge=1, description="The ID of the product to update"),
    product_in: ProductUpdate, # Use ProductUpdate schema for partial updates
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    """
    Endpoint to update an existing product.
    Note: Inventory quantity and status are managed via inventory endpoints/services, not here.
    Updating reorder_point might trigger inventory status re-evaluation via the service.
    """
    user_id = getattr(current_user, 'id', None)
    logger.info(f"Update product request received for ID: {product_id} by user: {user_id}. Data: {product_in.model_dump(exclude_unset=True)}")
    try:
        updated_product_orm = product_service.update_product(
            product_id=product_id, product_update=product_in, user_id=user_id
        )
        logger.info(f"Product ID {product_id} updated successfully.")
        # Convert ORM object to response schema using Pydantic v2 method
        return ProductResponse.model_validate(updated_product_orm)

    except EntityNotFoundException:
        logger.warning(f"Attempted to update non-existent product ID: {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found."
        )
    except ValidationException as e:
        logger.warning(f"Validation error updating product ID {product_id}: {e.errors}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except BusinessRuleException as e: # E.g., trying to update to an existing SKU
        logger.warning(f"Business rule violation updating product ID {product_id}: {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e.detail)
        )
    except HideSyncException as e: # Catch potential errors from inventory status re-evaluation
        logger.error(f"Internal error updating product ID {product_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error updating product ID {product_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the product.",
        )

@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Product",
    description="Delete a product record and its associated inventory record.",
    # dependencies=[Depends(PermissionsChecker(["product:delete"]))], # Optional: Add permissions
)
def delete_product(
    *,
    product_id: int = Path(..., ge=1, description="The ID of the product to delete"),
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Endpoint to delete a product.
    This will also attempt to delete the associated inventory record via the service layer.
    Returns 204 No Content on successful deletion.
    """
    user_id = getattr(current_user, 'id', None)
    logger.info(f"Delete product request received for ID: {product_id} by user: {user_id}")
    try:
        deleted = product_service.delete_product(product_id=product_id, user_id=user_id)
        if not deleted:
             # Should be caught by EntityNotFoundException, but as a safeguard
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found or deletion failed.")

        logger.info(f"Product ID {product_id} deleted successfully.")
        # Return None explicitly for 204 No Content response
        return None

    except EntityNotFoundException:
        logger.warning(f"Attempted to delete non-existent product ID: {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found."
        )
    except BusinessRuleException as e: # E.g., cannot delete if associated with active orders
        logger.warning(f"Business rule violation deleting product ID {product_id}: {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e.detail)
        )
    except HideSyncException as e: # Catch potential errors from inventory deletion within service
        logger.error(f"Internal error deleting product ID {product_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting product ID {product_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the product.",
        )

# Potential Future Endpoints (Examples)
# @router.post("/{product_id}/calculate-cost", ...)
# def trigger_cost_calculation(...):
#     pass

# @router.get("/by-sku/{sku}", ...)
# def get_product_by_sku(...):
#     pass