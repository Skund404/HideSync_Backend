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
    Body, # Keep Body if used elsewhere, not needed for new endpoints
)
from sqlalchemy.orm import Session # Keep if used elsewhere

# --- Application Imports ---
from app.api.deps import (
    get_current_active_user,
    get_product_service,
    # PermissionsChecker, # Uncomment if needed
)
# from app.db.session import get_db # Remove if not used directly
from app.schemas.product import (
    ProductCreate,
    ProductList,
    ProductResponse,
    ProductUpdate,
    ProductFilter,
)
from app.services.product_service import ProductService
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    BusinessRuleException,
    HideSyncException,
)
from app.db.models.product import Product

# --- Router Setup ---
router = APIRouter()
logger = logging.getLogger(__name__)

# --- Existing API Endpoints ---

@router.get(
    "/",
    response_model=ProductList,
    summary="List Products",
    description="Retrieve a list of products with filtering and pagination.",
    # dependencies=[Depends(PermissionsChecker(["product:read"]))], # Optional permissions
)
def list_products(
    *,
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    # --- Filtering Parameters ---
    search_query: Optional[str] = Query(None, alias="searchQuery", description="Search by name, SKU, description"),
    status: Optional[List[str]] = Query(None, description="Filter by inventory status (e.g., IN_STOCK)"),
    product_type: Optional[List[str]] = Query(None, alias="productType", description="Filter by product type (e.g., WALLET)"),
    storage_location: Optional[str] = Query(None, alias="storageLocation", description="Filter by storage location"),
    date_from: Optional[str] = Query(None, alias="dateAddedRange[from]", description="Start date for date added (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, alias="dateAddedRange[to]", description="End date for date added (YYYY-MM-DD)"),
    min_price: Optional[float] = Query(None, alias="priceRange[min]", ge=0, description="Minimum selling price"),
    max_price: Optional[float] = Query(None, alias="priceRange[max]", ge=0, description="Maximum selling price"),
    pattern_id: Optional[int] = Query(None, alias="patternId", ge=1, description="Filter by pattern ID"),
    project_id: Optional[int] = Query(None, alias="projectId", ge=1, description="Filter by project ID"),
) -> ProductList:
    """
    Endpoint to retrieve a list of products with filtering and pagination.
    """
    user_id_for_log = getattr(current_user, 'id', 'N/A')
    logger.info(
        f"Listing products request received. User: {user_id_for_log}. Skip: {skip}, Limit: {limit}, Filters: "
        f"search='{search_query}', status={status}, type={product_type}, loc='{storage_location}', "
        f"date={date_from}-{date_to}, price={min_price}-{max_price}, pattern={pattern_id}, project={project_id}"
    )

    # Construct Filter Object using Pydantic model
    try:
        filters = ProductFilter(
            productType=product_type,
            status=status,
            priceRange={"min": min_price, "max": max_price} if min_price is not None or max_price is not None else None,
            dateAddedRange={"from": date_from, "to": date_to} if date_from or date_to else None,
            searchQuery=search_query,
            storageLocation=storage_location,
            patternId=pattern_id,
            projectId=project_id,
        )
        logger.debug(f"Constructed ProductFilter: {filters.model_dump(exclude_none=True)}")
    except Exception as e: # Catch potential Pydantic validation errors during filter creation
         logger.warning(f"Error constructing ProductFilter: {e}", exc_info=True)
         # Use status module correctly
         raise HTTPException(
              status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
              detail=f"Invalid filter parameters provided: {str(e)}"
         )

    try:
        # Call the service method responsible for fetching paginated/filtered data
        # This now returns a dictionary {'items': List[Product], 'total': int}
        # Ensure the Product objects have the 'inventory' relationship loaded via joinedload in the repo
        paginated_data = product_service.list_products_paginated(
            skip=skip, limit=limit, filters=filters
        )

        items_orm: List[Product] = paginated_data.get('items', []) # Type hint for clarity
        total = paginated_data.get('total', 0)
        size = limit
        pages = (total + size - 1) // size if size > 0 else 0
        current_page = (skip // size) + 1

        logger.info(f"Repository returned {len(items_orm)} products. Total matching: {total}. Preparing page {current_page}/{pages}.")

        # --- Prepare items for Response Model Validation ---
        items_response = []
        for item_orm in items_orm:
            # Check if inventory relationship is loaded (it should be due to joinedload)
            if not hasattr(item_orm, 'inventory') or item_orm.inventory is None:
                logger.warning(f"Inventory data missing for Product ID {item_orm.id}. Setting defaults for response.")
                inventory_quantity = 0.0
                inventory_status = None
                inventory_location = None
            else:
                inventory_quantity = item_orm.inventory.quantity
                inventory_status = item_orm.inventory.status
                inventory_location = item_orm.inventory.storage_location

            # Prepare data dictionary mapping ORM attributes to Response schema fields
            # Pydantic's from_attributes=True handles most direct mappings.
            # We primarily need to ensure fields from the relationship are added.
            product_data_for_response = {
                **item_orm.__dict__, # Start with ORM object's dict (might include internal state)
                # Override/add fields from the relationship
                'quantity': inventory_quantity,
                'status': inventory_status,
                'storage_location': inventory_location,
                # Ensure hybrid properties like profit_margin are calculated if needed
                # Pydantic's from_attributes should pick up hybrid properties automatically
            }
             # Clean internal SQLAlchemy state if it interferes
            product_data_for_response.pop('_sa_instance_state', None)

            # Try to validate the constructed dictionary against the response schema
            try:
                response_item = ProductResponse.model_validate(product_data_for_response)
                items_response.append(response_item)
            except Exception as validation_err:
                 # Log detailed error if validation fails for a specific item
                 logger.error(f"Pydantic validation failed for product ID {item_orm.id}: {validation_err}", exc_info=True)
                 logger.debug(f"Data passed for validation: {product_data_for_response}")
                 # Option: Skip the item causing issues
                 # continue
                 # Option: Raise a 500 error immediately, indicates data inconsistency
                 raise HTTPException(
                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                     detail=f"Failed to serialize product data for ID {item_orm.id}. Please check server logs."
                 )

        # --- End Preparing Items ---

        # Construct the final paginated response
        return ProductList(
            items=items_response,
            total=total,
            page=current_page,
            size=size,
            pages=pages
        )

    except ValidationException as e:
        # This catches validation errors during filter construction mainly
        logger.warning(f"Validation error during product listing setup: {e.errors}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except HTTPException as http_exc:
         # Re-raise HTTPExceptions that occurred during item validation loop
         raise http_exc
    except Exception as e:
        # Generic catch-all for unexpected errors
        logger.error(f"Unexpected error listing products: {e}", exc_info=True)
        # Use the status module correctly here
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving products.",
        )

@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
    description="Create a new product record. SKU is optional and will be auto-generated if omitted.",
    # dependencies=[Depends(PermissionsChecker(["product:create"]))],
)

@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
    description="Create a new product record. SKU is optional and will be auto-generated if omitted.",
    # dependencies=[Depends(PermissionsChecker(["product:create"]))],
)
def create_product(
    *,
    product_in: ProductCreate,
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    """
    Endpoint to create a new product. Accepts product details.
    SKU is optional; if not provided, the backend will generate one.
    """
    user_id = getattr(current_user, 'id', None)
    provided_sku_for_logging = product_in.sku if product_in.sku else 'None (Auto-Generate)'
    logger.info(f"Create product request received. User: {user_id}. Provided SKU: '{provided_sku_for_logging}'")
    try:
        # Service method creates Product and Inventory, returns Product ORM obj
        # The refresh inside the service *should* have loaded the relationship
        created_product_orm: Product = product_service.create_product(
            product_in=product_in, user_id=user_id
        )
        logger.info(f"Product and initial inventory created successfully. Product ID: {created_product_orm.id}, SKU: {created_product_orm.sku}")

        # --- Explicitly Prepare Data for Response Validation ---
        # Even after refresh, sometimes direct validation needs help.
        # Check if inventory was loaded by the refresh in the service
        if not hasattr(created_product_orm, 'inventory') or created_product_orm.inventory is None:
            # This indicates a problem with the refresh or relationship setup
            logger.error(f"CRITICAL: Inventory relationship not loaded on product {created_product_orm.id} after creation and refresh.")
            # Fallback or raise error:
            inventory_quantity = 0.0
            inventory_status = None
            inventory_location = None
            # Optionally raise an exception here as data is incomplete for the response
            # raise HTTPException(status_code=500, detail="Failed to prepare product response data.")
        else:
            inventory_quantity = created_product_orm.inventory.quantity
            inventory_status = created_product_orm.inventory.status
            inventory_location = created_product_orm.inventory.storage_location
            logger.debug(f"Inventory details loaded for response: Qty={inventory_quantity}, Status={inventory_status}, Loc={inventory_location}")


        # Construct the dictionary matching ProductResponse fields
        response_data = {
            **created_product_orm.__dict__, # Get attributes from the ORM object
            'quantity': inventory_quantity,
            'status': inventory_status,
            'storage_location': inventory_location,
            # Pydantic should handle hybrid properties like profit_margin if using from_attributes
            # but ensure they don't rely on fields not present in __dict__
            # If needed, calculate them explicitly: 'profit_margin': created_product_orm.profit_margin
        }
        response_data.pop('_sa_instance_state', None) # Clean internal state

        # Validate the constructed dictionary
        try:
             validated_response = ProductResponse.model_validate(response_data)
             return validated_response
        except Exception as validation_err:
             logger.error(f"Pydantic validation failed for newly created product ID {created_product_orm.id}: {validation_err}", exc_info=True)
             logger.debug(f"Data passed for validation: {response_data}")
             raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail=f"Failed to serialize newly created product data."
             )
        # --- End Explicit Data Preparation ---

    except ValidationException as e:
        logger.warning(f"Validation error creating product: {e.errors}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except BusinessRuleException as e:
        error_message = str(getattr(e, 'details', e))
        logger.warning(f"Business rule violation creating product (Provided SKU: '{provided_sku_for_logging}'): {error_message}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=error_message
        )
    except HideSyncException as e:
        logger.error(f"Internal error creating product (Provided SKU: '{provided_sku_for_logging}'): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating product (Provided SKU: '{provided_sku_for_logging}'): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the product.",
        )

@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get Product by ID",
    description="Retrieve a single product by its unique ID.",
    # dependencies=[Depends(PermissionsChecker(["product:read"]))],
)
def get_product(
    *,
    product_id: int = Path(..., ge=1, description="The ID of the product to retrieve"),
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    # ... (implementation as before) ...
    logger.info(f"Get product request received for ID: {product_id} by user: {getattr(current_user, 'id', 'N/A')}")
    try:
        product_orm = product_service.get_product_by_id(product_id=product_id, load_inventory=True)
        if not product_orm:
            raise EntityNotFoundException("Product", product_id)
        logger.info(f"Product ID {product_id} found.")
        return ProductResponse.model_validate(product_orm)
    except EntityNotFoundException as e:
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
    description="Update an existing product's details.",
    # dependencies=[Depends(PermissionsChecker(["product:update"]))],
)
def update_product(
        *,
        product_id: int = Path(..., ge=1),
        product_in: ProductUpdate,
        product_service: ProductService = Depends(get_product_service),
        current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    """
    Endpoint to update an existing product.
    Refetches the product with inventory loaded before returning response.
    """
    user_id = getattr(current_user, 'id', None)
    logger.info(
        f"Update product request received for ID: {product_id} by user: {user_id}. Data: {product_in.model_dump(exclude_unset=True)}")
    try:
        # 1. Call service update method (this handles DB update and commit)
        #    The returned object here might not have relationships loaded reliably yet.
        updated_product_orm_from_service = product_service.update_product(
            product_id=product_id, product_update=product_in, user_id=user_id
        )
        # EntityNotFoundException is handled if product didn't exist

        logger.info(f"Product ID {product_id} update committed successfully by service.")

        # --- FIX: Fetch again with loaded relationships for response ---
        # This ensures the data for the response object is complete and fresh.
        logger.debug(f"Refetching product {product_id} with inventory for response.")
        refreshed_product_orm = product_service.get_product_by_id(product_id=product_id, load_inventory=True)
        if not refreshed_product_orm:
            # This would be highly unusual if the update succeeded
            logger.error(f"CRITICAL: Could not retrieve product {product_id} immediately after successful update.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to retrieve product details after update.")
        # --- END REFETCH ---

        # --- Prepare data with manual status normalization ---
        product_data_dict = refreshed_product_orm.to_dict()

        # Manual normalization of status if needed
        if 'status' in product_data_dict and product_data_dict['status']:
            # If status is a string in uppercase format, convert to lowercase
            if isinstance(product_data_dict['status'], str):
                product_data_dict['status'] = product_data_dict['status'].lower()
            # If status is an enum object, ensure we get the value
            elif hasattr(product_data_dict['status'], 'value'):
                product_data_dict['status'] = product_data_dict['status'].value

        try:
            validated_response = ProductResponse.model_validate(product_data_dict)
            logger.info(f"Successfully prepared response for updated product {product_id}.")
            return validated_response
        except Exception as validation_err:
            logger.error(
                f"Pydantic validation failed for updated product ID {refreshed_product_orm.id}: {validation_err}",
                exc_info=True)
            logger.debug(f"Data that failed validation: {product_data_dict}")

            # Attempt a more direct approach if to_dict() method is problematic
            try:
                # Manually construct the response data
                manual_data = {
                    "id": refreshed_product_orm.id,
                    "name": refreshed_product_orm.name,
                    "sku": refreshed_product_orm.sku,
                    "product_type": refreshed_product_orm.product_type,
                    "description": refreshed_product_orm.description,
                    "materials": refreshed_product_orm.materials,
                    "color": refreshed_product_orm.color,
                    "dimensions": refreshed_product_orm.dimensions,
                    "weight": refreshed_product_orm.weight,
                    "pattern_id": refreshed_product_orm.pattern_id,
                    "reorder_point": refreshed_product_orm.reorder_point,
                    "selling_price": refreshed_product_orm.selling_price,
                    "total_cost": refreshed_product_orm.total_cost,
                    "thumbnail": refreshed_product_orm.thumbnail,
                    "notes": refreshed_product_orm.notes,
                    "batch_number": refreshed_product_orm.batch_number,
                    "customizations": refreshed_product_orm.customizations,
                    "project_id": refreshed_product_orm.project_id,
                    "cost_breakdown": refreshed_product_orm.cost_breakdown,
                    "profit_margin": getattr(refreshed_product_orm, 'profit_margin', None),
                    "created_at": getattr(refreshed_product_orm, 'created_at', None),
                    "updated_at": getattr(refreshed_product_orm, 'updated_at', None),
                    "last_sold": getattr(refreshed_product_orm, 'last_sold', None),
                    "sales_velocity": getattr(refreshed_product_orm, 'sales_velocity', None),
                }

                # Add inventory-related fields with careful normalization
                if hasattr(refreshed_product_orm, 'inventory') and refreshed_product_orm.inventory:
                    manual_data["quantity"] = refreshed_product_orm.inventory.quantity

                    # Handle status with special care - ensure it's lowercase string value
                    status_value = refreshed_product_orm.inventory.status
                    if hasattr(status_value, 'value'):
                        manual_data["status"] = status_value.value  # Get string value from enum
                    elif isinstance(status_value, str):
                        manual_data["status"] = status_value.lower()  # Ensure lowercase
                    else:
                        manual_data["status"] = None  # Default if unhandled type

                    manual_data["storage_location"] = refreshed_product_orm.inventory.storage_location
                else:
                    # Default inventory values if relationship not loaded
                    manual_data["quantity"] = 0.0
                    manual_data["status"] = "out_of_stock"  # Safe default
                    manual_data["storage_location"] = None

                validated_response = ProductResponse.model_validate(manual_data)
                logger.info(f"Successfully prepared response using manual approach for product {product_id}.")
                return validated_response
            except Exception as manual_err:
                logger.error(f"Manual approach also failed for product ID {refreshed_product_orm.id}: {manual_err}",
                             exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to serialize updated product data. Technical details: {str(manual_err)}"
                )
        # --- End Prepare Data ---

    # --- Exception Handling ---
    except EntityNotFoundException as e:
        logger.warning(f"Attempted to update non-existent product ID: {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found."
        )
    except ValidationException as e:
        logger.warning(f"Validation error updating product ID {product_id}: {e.errors}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except BusinessRuleException as e:
        error_message = str(getattr(e, 'details', e))
        logger.warning(f"Business rule violation updating product ID {product_id}: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=error_message
        )
    except HideSyncException as e:  # Catch internal service errors
        logger.error(f"Internal service error updating product ID {product_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except HTTPException as http_exc:  # Re-raise HTTP exceptions from validation block
        raise http_exc
    except Exception as e:  # Catch unexpected errors
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
    # dependencies=[Depends(PermissionsChecker(["product:delete"]))],
)
def delete_product(
    *,
    product_id: int = Path(..., ge=1, description="The ID of the product to delete"),
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    # ... (implementation as before, with corrected exception handling) ...
    user_id = getattr(current_user, 'id', None)
    logger.info(f"Delete product request received for ID: {product_id} by user: {user_id}")
    try:
        deleted = product_service.delete_product(product_id=product_id, user_id=user_id)
        if not deleted:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found or deletion failed.")
        logger.info(f"Product ID {product_id} deleted successfully.")
        return None
    except EntityNotFoundException as e:
        logger.warning(f"Attempted to delete non-existent product ID: {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found."
        )
    except BusinessRuleException as e:
        error_message = str(getattr(e, 'details', e))
        logger.warning(f"Business rule violation deleting product ID {product_id}: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=error_message
        )
    except HideSyncException as e:
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

# --- NEW ENDPOINT: Get Product by SKU ---
@router.get(
    "/by-sku/{sku}",
    response_model=ProductResponse,
    summary="Get Product by SKU",
    description="Retrieve a single product by its unique SKU.",
    # dependencies=[Depends(PermissionsChecker(["product:read"]))], # Optional permissions
    tags=["products"], # Optional: Group endpoints in Swagger UI
)
def get_product_by_sku(
    *,
    sku: str = Path(..., description="The SKU of the product to retrieve"),
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    """
    Endpoint to retrieve a specific product by its SKU.
    """
    logger.info(f"Get product by SKU request received for SKU: '{sku}' by user: {getattr(current_user, 'id', 'N/A')}")
    try:
        # Service method should ensure inventory is loaded if needed by ProductResponse
        # Assuming get_product_by_sku in service handles necessary loading or
        # the response model doesn't strictly need eager loaded inventory here.
        # If inventory *is* needed, the service method needs adjustment or we fetch again here.
        # Let's assume the service's get_product_by_sku fetches the necessary relations.
        product_orm = product_service.get_product_by_sku(sku=sku) # Service returns Optional[Product]
        if not product_orm:
            logger.warning(f"Product not found with SKU: '{sku}'")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with SKU '{sku}' not found."
            )

        logger.info(f"Product found for SKU '{sku}'. ID: {product_orm.id}")
        return ProductResponse.model_validate(product_orm)

    except Exception as e:
        logger.error(f"Unexpected error retrieving product by SKU '{sku}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the product by SKU.",
        )


# --- NEW ENDPOINT: Trigger Cost Calculation ---
@router.post(
    "/{product_id}/calculate-cost",
    response_model=ProductResponse, # Return the updated product
    summary="Calculate Product Cost",
    description="Triggers the recalculation of the product's cost based on current material prices, labor rates, etc.",
    # dependencies=[Depends(PermissionsChecker(["product:update", "product:calculate_cost"]))], # Optional, more specific permission
    tags=["products"], # Optional: Group endpoints
    status_code=status.HTTP_200_OK, # Use 200 OK as it returns the updated resource state
)
def trigger_cost_calculation(
    *,
    product_id: int = Path(..., ge=1, description="The ID of the product to calculate costs for"),
    product_service: ProductService = Depends(get_product_service),
    current_user: Any = Depends(get_current_active_user),
) -> ProductResponse:
    """
    Endpoint to trigger the recalculation of a product's cost breakdown and total cost.
    Returns the updated product information.
    """
    user_id = getattr(current_user, 'id', None)
    logger.info(f"Trigger cost calculation request received for Product ID: {product_id} by user: {user_id}")
    try:
        # 1. Call the service method to calculate and *save* the costs
        #    This method might raise exceptions if dependencies (pattern, materials) are missing.
        cost_breakdown_result = product_service.calculate_cost_breakdown(product_id=product_id)
        # Optional: Log the breakdown details if needed
        # logger.debug(f"Cost breakdown calculated for product {product_id}: {cost_breakdown_result}")

        # 2. Fetch the *updated* product data to return the full response
        #    The calculate_cost_breakdown service method should have already committed the changes.
        updated_product_orm = product_service.get_product_by_id(product_id=product_id, load_inventory=True)
        if not updated_product_orm:
             # Should not happen if calculate_cost_breakdown succeeded, but defensive check
             logger.error(f"Product {product_id} not found after successful cost calculation.")
             raise EntityNotFoundException("Product", product_id)

        logger.info(f"Cost calculation successful for product ID {product_id}. New total cost: {updated_product_orm.total_cost}")
        return ProductResponse.model_validate(updated_product_orm)

    except EntityNotFoundException as e:
        # This could be raised by calculate_cost_breakdown if product/pattern/material not found,
        # or by get_product_by_id if something went wrong after calculation.
        error_message = str(getattr(e, 'details', e))
        logger.warning(f"Entity not found during cost calculation for product ID {product_id}: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not calculate cost: {error_message}"
        )
    except (HideSyncException, BusinessRuleException, ValidationException) as e:
         # Catch specific exceptions that calculate_cost_breakdown might raise
         error_message = str(getattr(e, 'details', e))
         logger.error(f"Error during cost calculation for product ID {product_id}: {error_message}", exc_info=True)
         # Use 400 Bad Request or 500 Internal Server Error depending on the exception type
         status_code = status.HTTP_400_BAD_REQUEST if isinstance(e, (ValidationException, BusinessRuleException)) else status.HTTP_500_INTERNAL_SERVER_ERROR
         raise HTTPException(
             status_code=status_code,
             detail=f"Cost calculation failed: {error_message}"
         )
    except Exception as e:
        logger.error(f"Unexpected error during cost calculation for product ID {product_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during cost calculation.",
        )