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
    Body, # Import Body if needed for specific update/create patterns
)
from sqlalchemy.orm import Session

# --- Application Imports ---
from app.api.deps import get_current_active_user, PermissionsChecker # Adjust permissions as needed
from app.db.session import get_db
from app.schemas.product import ( # Assuming schemas are in schemas/product.py
    ProductCreate,
    ProductList,
    ProductResponse,
    ProductUpdate,
    ProductFilter, # Make sure this schema exists and matches frontend needs
)
from app.services.product_service import ProductService # Assuming service exists
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    BusinessRuleException,
)

# --- Router Setup ---
router = APIRouter()
logger = logging.getLogger(__name__)

# --- Dependency for Product Service ---
def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    """Dependency injector for ProductService."""
    return ProductService(db)

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
    # Optional: Add date range parsing
    date_from: Optional[str] = Query(None, alias="dateAddedRange[from]", description="Start date for date added (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, alias="dateAddedRange[to]", description="End date for date added (YYYY-MM-DD)"),
    # Optional: Add price range parsing
    min_price: Optional[float] = Query(None, alias="priceRange[min]", ge=0, description="Minimum selling price"),
    max_price: Optional[float] = Query(None, alias="priceRange[max]", ge=0, description="Maximum selling price"),
) -> ProductList:
    """
    Endpoint to retrieve a list of products with filtering and pagination.
    Matches the filters used by the `useFilteredProducts` hook.
    """
    logger.info(
        f"Listing products request received. Skip: {skip}, Limit: {limit}, Filters: "
        f"search='{search_query}', status={status}, type={product_type}, loc='{storage_location}', "
        f"date={date_from}-{date_to}, price={min_price}-{max_price}"
    )

    # --- Construct Filter Object ---
    # Ensure ProductFilter schema aligns with these parameters
    filters = ProductFilter(
        productType=product_type,
        status=status,
        priceRange={"min": min_price, "max": max_price} if min_price is not None or max_price is not None else None,
        dateAddedRange={"from": date_from, "to": date_to} if date_from or date_to else None,
        searchQuery=search_query,
        storageLocation=storage_location,
    )

    try:
        # Call the service method responsible for fetching paginated/filtered data
        paginated_data = product_service.list_products_paginated(
            skip=skip, limit=limit, filters=filters
        )
        logger.info(f"Found {paginated_data['total']} products matching criteria.")
        return ProductList(**paginated_data) # Unpack dict to match schema

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
    description="Create a new product record.",
    # dependencies=[Depends(PermissionsChecker(["product:create"]))], # Optional: Add permissions
)
def create_product(
    *,
    product_in: ProductCreate, # Use ProductCreate schema for input validation
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    """
    Endpoint to create a new product.
    """
    logger.info(f"Create product request received for SKU: {product_in.sku} by user: {current_user.id}")
    try:
        created_product = product_service.create_product(
            product_in=product_in, user_id=current_user.id
        )
        logger.info(f"Product created successfully with ID: {created_product.id}")
        return created_product
    except ValidationException as e:
        logger.warning(f"Validation error creating product: {e.errors}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except BusinessRuleException as e: # E.g., SKU already exists
        logger.warning(f"Business rule violation creating product: {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e.detail)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating product: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the product.",
        )

@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get Product by ID",
    description="Retrieve a single product by its unique ID.",
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
    """
    logger.info(f"Get product request received for ID: {product_id}")
    try:
        product = product_service.get_product_by_id(product_id=product_id)
        logger.info(f"Product ID {product_id} found.")
        return product
    except EntityNotFoundException:
        logger.warning(f"Product not found with ID: {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
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
    description="Update an existing product's details.",
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
    """
    logger.info(f"Update product request received for ID: {product_id} by user: {current_user.id}")
    try:
        updated_product = product_service.update_product(
            product_id=product_id, product_update=product_in, user_id=current_user.id
        )
        logger.info(f"Product ID {product_id} updated successfully.")
        return updated_product
    except EntityNotFoundException:
        logger.warning(f"Attempted to update non-existent product ID: {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
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
    description="Delete a product record.",
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
    Returns 204 No Content on successful deletion.
    """
    logger.info(f"Delete product request received for ID: {product_id} by user: {current_user.id}")
    try:
        product_service.delete_product(product_id=product_id, user_id=current_user.id)
        logger.info(f"Product ID {product_id} deleted successfully.")
        return None # Important: Return None for 204 status code
    except EntityNotFoundException:
        logger.warning(f"Attempted to delete non-existent product ID: {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    except BusinessRuleException as e: # E.g., cannot delete if associated with active orders
        logger.warning(f"Business rule violation deleting product ID {product_id}: {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e.detail)
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting product ID {product_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the product.",
        )