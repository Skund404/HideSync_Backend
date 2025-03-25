from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.analytics import (
    DashboardSummary,
    FinancialSummary,
    RevenueSummary,
    InventoryStockLevels,
    SupplierPerformance,
    CustomerLifetimeValue
)
from app.services.dashboard_service import DashboardService
from app.services.report_service import ReportService
from app.services.sale_service import SaleService
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard_summary(
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user),
        use_cache: bool = True
):
    """
    Get dashboard summary data including projects, inventory, sales and customers.
    """
    service = DashboardService(session=session)
    return service.get_dashboard_summary(use_cache=use_cache)


@router.get("/financial/summary", response_model=FinancialSummary)
def get_financial_summary(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "month",
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
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
            "period": period
        }
    )

    return report.get("data", {})


@router.get("/financial/revenue", response_model=RevenueSummary)
def get_revenue_analysis(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_by: str = "month",
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
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
            "group_by": group_by
        }
    )

    return report.get("data", {})


@router.get("/inventory/stock-levels", response_model=InventoryStockLevels)
def get_stock_level_analysis(
        threshold_percentage: float = 20.0,
        item_type: Optional[str] = None,
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
):
    """
    Get inventory stock level analysis with low stock alerts and distribution.
    """
    service = DashboardService(session=session)
    inventory_data = service.get_inventory_overview()

    # Return relevant parts of the inventory overview
    return {
        "timestamp": inventory_data.get("timestamp", datetime.now().isoformat()),
        "materials_to_reorder": inventory_data.get("materials_to_reorder", 0),
        "low_stock_materials": inventory_data.get("low_stock_materials", []),
        "material_counts": inventory_data.get("material_counts", {}),
        "material_stock_distribution": inventory_data.get("material_stock_distribution", [])
    }


@router.get("/suppliers/performance", response_model=SupplierPerformance)
def get_supplier_performance(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        supplier_id: Optional[int] = None,
        material_type: Optional[str] = None,
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
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
            "material_type": material_type
        }
    )

    return report.get("data", {})


@router.get("/customers/lifetime-value", response_model=CustomerLifetimeValue)
def get_customer_lifetime_value(
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
):
    """
    Get customer lifetime value metrics and customer segmentation data.
    """
    service = CustomerService(session=session)
    analytics = service.get_customer_analytics()

    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_customers": analytics.get("total_customers", 0),
            "active_customers": analytics.get("active_customers", 0),
            "new_customers_30d": analytics.get("new_customers_30d", 0),
            "average_lifetime_value": analytics.get("average_lifetime_value", 0)
        },
        "top_customers": analytics.get("top_customers", []),
        "customer_distribution": analytics.get("customer_distribution", {})
    }