# app/api/v1/endpoints/analytics.py

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta

from app.api import deps
from app.schemas.analytics import (
    DashboardSummary,
    FinancialSummary,
    RevenueSummary,
    InventoryStockLevels,
    SupplierPerformance,
    CustomerLifetimeValue,
    PricingCalculatorInputs,  # Import new input schema
    PricingCalculatorResults  # Import new output schema
)
from app.services.dashboard_service import DashboardService
from app.services.report_service import ReportService
from app.services.sale_service import SaleService
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=DashboardSummary,
    summary="Get Dashboard Summary",
    description="Retrieves a summary of key metrics for the dashboard.",
)
def get_dashboard_summary(
    session: Session = Depends(deps.get_db),
    current_user: dict = Depends(deps.get_current_user),
    use_cache: bool = True,
):
    """
    Get dashboard summary data including projects, inventory, sales and customers.
    """
    service = DashboardService(session=session)
    return service.get_dashboard_summary(use_cache=use_cache)


@router.get(
    "/financial/summary",
    response_model=FinancialSummary,
    summary="Get Financial Summary",
    description="Retrieves a financial summary including revenue, expenses, and profit trends over a specified period.",
)
def get_financial_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "month",
    session: Session = Depends(deps.get_db),
    current_user: dict = Depends(deps.get_current_user),
):
    """
    Get financial summary data with revenue, expenses and profit trends.
    """
    # Convert string dates to datetime if provided
    start_date_obj = datetime.fromisoformat(start_date) if start_date else None
    end_date_obj = datetime.fromisoformat(end_date) if end_date else None

    service = ReportService(session=session)
    report = service.generate_report(
        report_type="financial_summary",
        parameters={
            "start_date": start_date_obj,
            "end_date": end_date_obj,
            "period": period,
        },
    )

    # Handle potential case where report generation fails or returns unexpected structure
    if not report or "data" not in report:
        logger.error(
            "Failed to generate or retrieve valid data for financial summary report."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve financial summary data.",
        )

    return report.get("data", {})


@router.get(
    "/financial/revenue",
    response_model=RevenueSummary,
    summary="Get Revenue Analysis",
    description="Retrieves detailed revenue analysis data, optionally grouped by different dimensions like month, product, or customer.",
)
def get_revenue_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: str = "month",
    session: Session = Depends(deps.get_db),
    current_user: dict = Depends(deps.get_current_user),
):
    """
    Get detailed revenue analysis data grouped by various dimensions.
    """
    # Convert string dates to datetime if provided
    start_date_obj = datetime.fromisoformat(start_date) if start_date else None
    end_date_obj = datetime.fromisoformat(end_date) if end_date else None

    service = ReportService(session=session)
    report = service.generate_report(
        report_type="sales_analysis",
        parameters={
            "start_date": start_date_obj,
            "end_date": end_date_obj,
            "group_by": group_by,
        },
    )

    # Handle potential case where report generation fails or returns unexpected structure
    if not report or "data" not in report:
        logger.error(
            "Failed to generate or retrieve valid data for revenue analysis report."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve revenue analysis data.",
        )

    return report.get("data", {})


@router.post(
    "/financial/calculate-pricing",
    response_model=PricingCalculatorResults,
    status_code=status.HTTP_200_OK,
    summary="Calculate Suggested Product Pricing",
    description="Calculates suggested product pricing based on costs, overhead, fees, and desired profit margin.",
)
def calculate_pricing(
    inputs: PricingCalculatorInputs,
    session: Session = Depends(
        deps.get_db
    ),  # Kept for consistency, though not used directly in calc
    current_user: dict = Depends(deps.get_current_user),
) -> PricingCalculatorResults:
    """
    Calculates suggested product pricing based on various inputs.

    - **materialCost**: Cost of materials per unit (>= 0).
    - **hardwareCost**: Cost of hardware per unit (>= 0).
    - **laborHours**: Labor hours per unit (>= 0).
    - **laborRate**: Cost per hour of labor (>= 0).
    - **overhead**: Overhead percentage (e.g., 20 for 20%) (>= 0).
    - **targetMargin**: Desired profit margin percentage (0 <= margin < 100).
    - **shippingCost**: Optional shipping cost per unit (>= 0, default 0).
    - **packagingCost**: Optional packaging cost per unit (>= 0, default 0).
    - **platformFees**: Optional platform fee percentage (0 <= fee < 100, default 0).
    - **marketingCost**: Optional fixed marketing cost per unit (>= 0, default 0).

    Returns calculated costs, break-even price, suggested price, and profit.
    """
    try:
        # --- Input Validation (handled by Pydantic, but double-check critical ones) ---
        # Pydantic already ensures >= 0 and < 100 where specified via Field constraints.

        # --- Calculations ---
        direct_cost = (
            inputs.materialCost
            + inputs.hardwareCost
            + (inputs.laborHours * inputs.laborRate)
        )
        cost_with_overhead = direct_cost * (1 + inputs.overhead / 100.0)
        total_base_cost = (
            cost_with_overhead + inputs.packagingCost + inputs.marketingCost
        )

        # --- Break-Even Calculation ---
        break_even_denominator = 1.0 - (inputs.platformFees / 100.0)
        # Use a small epsilon to avoid floating point issues near 100%
        if break_even_denominator <= 1e-9:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Platform fees cannot be 100% or more, as it makes break-even calculation impossible.",
            )
        break_even_price = (
            total_base_cost + inputs.shippingCost
        ) / break_even_denominator

        # --- Suggested Price Calculation ---
        suggested_price_denominator = (
            1.0
            - (inputs.targetMargin / 100.0)
            - (inputs.platformFees / 100.0)
        )
        # Use a small epsilon to avoid floating point issues near 100%
        if suggested_price_denominator <= 1e-9:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The sum of Target Margin and Platform Fees cannot be 100% or more.",
            )
        suggested_price = (
            total_base_cost + inputs.shippingCost
        ) / suggested_price_denominator

        # --- Profit Calculation ---
        # Profit = Revenue - Total Costs (including fees and shipping)
        # Profit = SuggestedPrice * (1 - PlatformFees/100) - TotalBaseCost - ShippingCost
        profit_at_suggested = (
            suggested_price * (1 - inputs.platformFees / 100.0)
            - total_base_cost
            - inputs.shippingCost
        )

        # --- Return Results ---
        return PricingCalculatorResults(
            totalCost=total_base_cost,  # Cost before shipping and platform fees
            breakEvenPrice=break_even_price,
            suggestedPrice=suggested_price,
            profitAtSuggested=profit_at_suggested,
        )

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions (like our 400s)
        raise http_exc
    except Exception as e:
        # Catch any unexpected errors during calculation
        logger.error(f"Error calculating pricing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during price calculation: {e}",
        )


@router.get(
    "/inventory/stock-levels",
    response_model=InventoryStockLevels,
    summary="Get Inventory Stock Level Analysis",
    description="Provides an analysis of current inventory stock levels, highlighting items needing reorder.",
)
def get_stock_level_analysis(
    threshold_percentage: float = Query(
        20.0, ge=0, le=100, description="Threshold percentage for low stock."
    ),
    item_type: Optional[str] = Query(
        None, description="Filter by item type (e.g., 'material', 'product')."
    ),
    session: Session = Depends(deps.get_db),
    current_user: dict = Depends(deps.get_current_user),
):
    """
    Get inventory stock level analysis with low stock alerts and distribution.
    Note: This endpoint currently reuses data from the dashboard service's
    inventory overview. Filtering parameters might not be fully applied yet.
    """
    # TODO: Enhance this endpoint to fully utilize threshold_percentage and item_type
    # by potentially calling a dedicated inventory analysis service method.
    service = DashboardService(session=session)
    try:
        inventory_data = service.get_inventory_overview()
    except Exception as e:
        logger.error(f"Error fetching inventory overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve inventory data.",
        )

    # Return relevant parts of the inventory overview
    # This structure assumes get_inventory_overview provides these keys.
    # Add error handling or default values if keys might be missing.
    return {
        "timestamp": inventory_data.get(
            "timestamp", datetime.now().isoformat()
        ),
        "materials_to_reorder": inventory_data.get(
            "materials_to_reorder", 0
        ),
        "low_stock_materials": inventory_data.get("low_stock_materials", []),
        "material_counts": inventory_data.get("material_counts", {}),
        "material_stock_distribution": inventory_data.get(
            "material_stock_distribution", []
        ),
    }


@router.get(
    "/suppliers/performance",
    response_model=SupplierPerformance,
    summary="Get Supplier Performance Analysis",
    description="Retrieves performance metrics for suppliers, such as delivery times and quality ratings.",
)
def get_supplier_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_id: Optional[int] = None,
    material_type: Optional[str] = None,
    session: Session = Depends(deps.get_db),
    current_user: dict = Depends(deps.get_current_user),
):
    """
    Get supplier performance metrics including delivery times and quality ratings.
    """
    # Convert string dates to datetime if provided
    start_date_obj = datetime.fromisoformat(start_date) if start_date else None
    end_date_obj = datetime.fromisoformat(end_date) if end_date else None

    service = ReportService(session=session)
    report = service.generate_report(
        report_type="supplier_performance",
        parameters={
            "start_date": start_date_obj,
            "end_date": end_date_obj,
            "supplier_id": supplier_id,
            "material_type": material_type,
        },
    )

    # Handle potential case where report generation fails or returns unexpected structure
    if not report or "data" not in report:
        logger.error(
            "Failed to generate or retrieve valid data for supplier performance report."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve supplier performance data.",
        )

    return report.get("data", {})


@router.get(
    "/customers/lifetime-value",
    response_model=CustomerLifetimeValue,
    summary="Get Customer Lifetime Value Analysis",
    description="Retrieves metrics related to customer lifetime value (CLV) and customer segmentation.",
)
def get_customer_lifetime_value(
    session: Session = Depends(deps.get_db),
    current_user: dict = Depends(deps.get_current_user),
):
    """
    Get customer lifetime value metrics and customer segmentation data.
    """
    service = CustomerService(session=session)
    try:
        analytics = service.get_customer_analytics()
    except Exception as e:
        logger.error(f"Error fetching customer analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve customer analytics data.",
        )

    # Ensure analytics dictionary has expected keys or provide defaults
    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_customers": analytics.get("total_customers", 0),
            "active_customers": analytics.get("active_customers", 0),
            "new_customers_30d": analytics.get("new_customers_30d", 0),
            "average_lifetime_value": analytics.get(
                "average_lifetime_value", 0.0
            ),
        },
        "top_customers": analytics.get("top_customers", []),
        "customer_distribution": analytics.get("customer_distribution", {}),
    }
