# File: app/services/dashboard_service.py

from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import functools
import logging

from app.core.metrics import record_execution_time, count_calls, timer, counter, gauge

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Service for generating dashboard data and analytics.

    Aggregates data from multiple services to provide a comprehensive
    view of system state and performance.
    """

    def __init__(
        self,
        session: Session,
        service_factory=None,
        cache_service=None,
        metrics_service=None,
    ):
        """
        Initialize dashboard service with dependencies.

        Args:
            session: Database session for persistence operations
            service_factory: Optional service factory for accessing other services
            cache_service: Optional cache service for data caching
            metrics_service: Optional metrics service for performance monitoring
        """
        from app.services.service_factory import ServiceFactory

        self.session = session
        self.service_factory = service_factory or ServiceFactory(session)
        self.cache_service = cache_service
        self.metrics_service = metrics_service

        # Initialize dashboard metrics
        self.dashboard_requests = counter(
            "dashboard.requests.total", "Total dashboard data requests"
        )
        self.dashboard_generation_time = timer(
            "dashboard.generation_time", "Dashboard data generation time in seconds"
        )

        # Create gauges for key metrics
        self.active_projects_gauge = gauge(
            "dashboard.active_projects", "Number of active projects"
        )
        self.pending_orders_gauge = gauge(
            "dashboard.pending_orders", "Number of pending orders"
        )
        self.low_stock_materials_gauge = gauge(
            "dashboard.low_stock_materials", "Number of materials with low stock"
        )
        self.total_customers_gauge = gauge(
            "dashboard.total_customers", "Total number of customers"
        )
        self.monthly_revenue_gauge = gauge(
            "dashboard.monthly_revenue", "Monthly revenue amount"
        )

    @record_execution_time("dashboard_summary")
    @count_calls
    def get_dashboard_summary(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary data.

        Aggregates data from various services including:
        - Projects (active, upcoming, etc.)
        - Materials (inventory status)
        - Sales and financial data
        - Recent activities

        Args:
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary with dashboard summary data
        """
        # Increment dashboard requests counter
        self.dashboard_requests.increment()

        # Check cache first if enabled
        if use_cache and self.cache_service:
            cached = self.cache_service.get("dashboard_summary")
            if cached:
                logger.debug("Returning cached dashboard summary")
                return cached

        # Get services
        try:
            # Time the dashboard generation
            with self.dashboard_generation_time.time():
                material_service = self.service_factory.get_material_service()
                project_service = self.service_factory.get_project_service()
                sale_service = self.service_factory.get_sale_service()
                purchase_service = self.service_factory.get_purchase_service()
                customer_service = self.service_factory.get_customer_service()

                # Build dashboard data
                summary = {
                    "timestamp": datetime.now().isoformat(),
                    "projects": self._get_project_summary(project_service),
                    "materials": self._get_material_summary(material_service),
                    "sales": self._get_sales_summary(sale_service),
                    "purchases": self._get_purchase_summary(purchase_service),
                    "customers": self._get_customer_summary(customer_service),
                    "recent_activity": self._get_recent_activity(),
                }

                # Update metrics gauges
                self.active_projects_gauge.set(
                    summary["projects"].get("active_projects", 0)
                )
                self.pending_orders_gauge.set(summary["sales"].get("pending_orders", 0))
                self.low_stock_materials_gauge.set(
                    summary["materials"].get("materials_to_reorder", 0)
                )
                self.total_customers_gauge.set(
                    summary["customers"].get("total_customers", 0)
                )
                self.monthly_revenue_gauge.set(
                    summary["sales"].get("monthly_revenue", 0)
                )

                # Cache the result
                if self.cache_service:
                    self.cache_service.set(
                        "dashboard_summary", summary, ttl=300
                    )  # 5 minutes TTL

                return summary

        except Exception as e:
            logger.error(f"Error generating dashboard summary: {str(e)}", exc_info=True)
            # Record error in metrics
            counter("dashboard.errors", "Dashboard generation errors").increment()
            # Return partial data or error indication
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "partial_data": True,
            }

    @record_execution_time("projects_overview")
    @count_calls
    def get_projects_overview(self) -> Dict[str, Any]:
        """
        Get detailed projects overview for dashboard.

        Returns:
            Dictionary with projects overview data
        """
        # Check cache
        if self.cache_service:
            cached = self.cache_service.get("dashboard_projects_overview")
            if cached:
                return cached

        # Get project service
        project_service = self.service_factory.get_project_service()

        # Build projects data with more detail than the summary
        try:
            from app.db.models.enums import ProjectStatus

            # Get counts by status
            status_counts = {}

            for status in ProjectStatus:
                count = len(project_service.list(status=status.value))
                status_counts[status.name] = count

            # Get upcoming deadlines for next 14 days
            upcoming_deadlines = project_service.get_projects_due_soon(days=14)

            # Get recently completed projects
            completed_date = datetime.now() - timedelta(days=30)
            recently_completed = project_service.list(
                status=ProjectStatus.COMPLETED.value,
                completed_date_from=completed_date,
                limit=10,
            )

            # Get projects by type
            projects_by_type = project_service.repository.get_projects_by_type()

            result = {
                "timestamp": datetime.now().isoformat(),
                "status_counts": status_counts,
                "total_projects": sum(status_counts.values()),
                "completion_rate": self._calculate_completion_rate(
                    status_counts.get("COMPLETED", 0), sum(status_counts.values())
                ),
                "upcoming_deadlines": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "due_date": p.due_date.isoformat() if p.due_date else None,
                        "customer": (
                            p.customer.name
                            if hasattr(p, "customer") and p.customer
                            else "No customer"
                        ),
                        "days_remaining": (
                            (p.due_date - datetime.now().date()).days
                            if p.due_date
                            else None
                        ),
                        "status": p.status,
                        "type": p.type,
                    }
                    for p in upcoming_deadlines[:10]  # Limit to 10 projects
                ],
                "recently_completed": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "completed_date": (
                            p.completed_date.isoformat() if p.completed_date else None
                        ),
                        "customer": (
                            p.customer.name
                            if hasattr(p, "customer") and p.customer
                            else "No customer"
                        ),
                        "type": p.type,
                    }
                    for p in recently_completed
                ],
                "projects_by_type": projects_by_type,
            }

            # Cache the result
            if self.cache_service:
                self.cache_service.set(
                    "dashboard_projects_overview", result, ttl=600
                )  # 10 minutes TTL

            return result

        except Exception as e:
            logger.error(f"Error generating projects overview: {str(e)}", exc_info=True)
            # Record error in metrics
            counter("dashboard.errors.projects", "Project overview errors").increment()
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    @record_execution_time("inventory_overview")
    @count_calls
    def get_inventory_overview(self) -> Dict[str, Any]:
        """
        Get detailed inventory overview for dashboard.

        Returns:
            Dictionary with inventory overview data
        """
        # Check cache
        if self.cache_service:
            cached = self.cache_service.get("dashboard_inventory_overview")
            if cached:
                return cached

        # Get material service
        material_service = self.service_factory.get_material_service()

        try:
            from app.db.models.enums import MaterialType, InventoryStatus

            # Get low stock materials
            low_stock = material_service.get_low_stock_materials()

            # Get counts by material type
            type_counts = {}
            for material_type in MaterialType:
                count = len(material_service.list(material_type=material_type.value))
                type_counts[material_type.name] = count

            # Get counts by status
            status_counts = {}
            for status in InventoryStatus:
                count = len(material_service.list(status=status.value))
                status_counts[status.name] = count

            # Get most used materials in last 30 days
            date_from = datetime.now() - timedelta(days=30)
            most_used = material_service.repository.get_most_used_materials(
                date_from, limit=10
            )

            # Get recently received materials
            recently_received = material_service.repository.get_recently_received(
                limit=10
            )

            result = {
                "timestamp": datetime.now().isoformat(),
                "materials_to_reorder": len(low_stock),
                "low_stock_materials": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "quantity": m.quantity,
                        "unit": m.unit,
                        "reorder_point": m.reorder_point,
                        "material_type": m.material_type,
                        "percentage": self._calculate_stock_percentage(
                            m.quantity, m.reorder_point
                        ),
                    }
                    for m in low_stock[:10]  # Limit to 10 materials
                ],
                "material_counts": {
                    "by_type": type_counts,
                    "by_status": status_counts,
                    "total": sum(type_counts.values()),
                },
                "most_used_materials": most_used,
                "recently_received": recently_received,
                "material_stock_distribution": self._get_material_stock_distribution(
                    material_service
                ),
            }

            # Update metrics gauge
            self.low_stock_materials_gauge.set(len(low_stock))

            # Cache the result
            if self.cache_service:
                self.cache_service.set(
                    "dashboard_inventory_overview", result, ttl=600
                )  # 10 minutes TTL

            return result

        except Exception as e:
            logger.error(
                f"Error generating inventory overview: {str(e)}", exc_info=True
            )
            # Record error in metrics
            counter(
                "dashboard.errors.inventory", "Inventory overview errors"
            ).increment()
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    @record_execution_time("sales_overview")
    @count_calls
    def get_sales_overview(self) -> Dict[str, Any]:
        """
        Get detailed sales overview for dashboard.

        Returns:
            Dictionary with sales overview data
        """
        # Check cache
        if self.cache_service:
            cached = self.cache_service.get("dashboard_sales_overview")
            if cached:
                return cached

        # Get sale service
        sale_service = self.service_factory.get_sale_service()

        try:
            from app.db.models.enums import SaleStatus, PaymentStatus

            # Get sales counts by status
            status_counts = {}
            for status in SaleStatus:
                count = len(sale_service.list(status=status.value))
                status_counts[status.name] = count

            # Get payment status counts
            payment_counts = {}
            for status in PaymentStatus:
                count = len(sale_service.list(payment_status=status.value))
                payment_counts[status.name] = count

            # Get recent sales
            recent_sales = sale_service.list(
                limit=10, sort_by="created_at", sort_dir="desc"
            )

            # Get monthly sales data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            monthly_sales = sale_service.repository.get_monthly_sales(
                start_date, end_date
            )

            # Get sales by channel
            sales_by_channel = sale_service.repository.get_sales_by_channel()

            # Get top products
            top_products = sale_service.repository.get_top_products(limit=10)

            result = {
                "timestamp": datetime.now().isoformat(),
                "pending_orders": status_counts.get("CONFIRMED", 0)
                + status_counts.get("IN_PRODUCTION", 0),
                "completed_orders": status_counts.get("COMPLETED", 0),
                "status_counts": status_counts,
                "payment_counts": payment_counts,
                "monthly_sales": monthly_sales,
                "sales_by_channel": sales_by_channel,
                "top_products": top_products,
                "recent_sales": [
                    {
                        "id": s.id,
                        "customer_name": (
                            s.customer.name
                            if hasattr(s, "customer") and s.customer
                            else "No customer"
                        ),
                        "created_at": (
                            s.created_at.isoformat()
                            if hasattr(s, "created_at")
                            else None
                        ),
                        "total_amount": s.total_amount,
                        "status": s.status,
                        "payment_status": s.payment_status,
                    }
                    for s in recent_sales
                ],
            }

            # Update metrics gauge
            self.pending_orders_gauge.set(result["pending_orders"])

            # Cache the result
            if self.cache_service:
                self.cache_service.set(
                    "dashboard_sales_overview", result, ttl=600
                )  # 10 minutes TTL

            return result

        except Exception as e:
            logger.error(f"Error generating sales overview: {str(e)}", exc_info=True)
            # Record error in metrics
            counter("dashboard.errors.sales", "Sales overview errors").increment()
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    @record_execution_time("customers_overview")
    @count_calls
    def get_customers_overview(self) -> Dict[str, Any]:
        """
        Get detailed customers overview for dashboard.

        Returns:
            Dictionary with customers overview data
        """
        # Check cache
        if self.cache_service:
            cached = self.cache_service.get("dashboard_customers_overview")
            if cached:
                return cached

        # Get customer service
        customer_service = self.service_factory.get_customer_service()

        try:
            from app.db.models.enums import CustomerStatus, CustomerTier

            # Get customer counts by status
            status_counts = {}
            for status in CustomerStatus:
                count = len(customer_service.list(status=status.value))
                status_counts[status.name] = count

            # Get customer counts by tier
            tier_counts = {}
            for tier in CustomerTier:
                count = len(customer_service.list(tier=tier.value))
                tier_counts[tier.name] = count

            # Get recently active customers
            recently_active = customer_service.get_recently_active_customers(
                days=30, limit=10
            )

            # Get new customers in last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            new_customers = customer_service.list(
                created_at_from=thirty_days_ago,
                limit=10,
                sort_by="created_at",
                sort_dir="desc",
            )

            # Get customer growth over time
            customer_growth = customer_service.repository.get_customer_growth_by_month()

            result = {
                "timestamp": datetime.now().isoformat(),
                "total_customers": sum(status_counts.values()),
                "active_customers": status_counts.get("ACTIVE", 0),
                "status_counts": status_counts,
                "tier_counts": tier_counts,
                "recently_active_customers": recently_active,
                "new_customers": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "email": c.email,
                        "created_at": (
                            c.created_at.isoformat()
                            if hasattr(c, "created_at")
                            else None
                        ),
                        "status": c.status,
                        "tier": c.tier,
                    }
                    for c in new_customers
                ],
                "customer_growth": customer_growth,
            }

            # Update metrics gauge
            self.total_customers_gauge.set(result["total_customers"])

            # Cache the result
            if self.cache_service:
                self.cache_service.set(
                    "dashboard_customers_overview", result, ttl=600
                )  # 10 minutes TTL

            return result

        except Exception as e:
            logger.error(
                f"Error generating customers overview: {str(e)}", exc_info=True
            )
            # Record error in metrics
            counter(
                "dashboard.errors.customers", "Customer overview errors"
            ).increment()
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    @record_execution_time("performance_metrics")
    @count_calls
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get system performance metrics for dashboard.

        Returns:
            Dictionary with performance metrics
        """
        # First check if we have our new metrics system available
        from app.core.metrics import get_registry

        try:
            # Get metrics registry
            registry = get_registry()

            # Collect metrics by category
            http_metrics = {}
            db_metrics = {}
            app_metrics = {}
            service_metrics = {}

            # Process all metrics
            for metric in registry.get_all_metrics():
                name = metric.name
                value = metric.get_value()

                if name.startswith("http."):
                    http_metrics[name] = value
                elif name.startswith("db."):
                    db_metrics[name] = value
                elif name.startswith("hidesync.") or name.startswith("process."):
                    app_metrics[name] = value
                elif name.startswith("dashboard.") or name.startswith("service."):
                    service_metrics[name] = value

            # Build system metrics summary
            return {
                "timestamp": datetime.now().isoformat(),
                "http": http_metrics,
                "database": db_metrics,
                "application": app_metrics,
                "services": service_metrics,
            }

        except Exception as e:
            logger.warning(f"Error getting metrics from registry: {str(e)}")

            # Fall back to old metrics service if available
            if self.metrics_service:
                try:
                    # Get execution times for key operations
                    execution_times = self.metrics_service.get_execution_times()

                    # Get request counts and response times
                    request_metrics = self.metrics_service.get_request_metrics()

                    # Get database query performance
                    db_metrics = self.metrics_service.get_database_metrics()

                    # Get cache hit ratio
                    cache_metrics = self.metrics_service.get_cache_metrics()

                    result = {
                        "timestamp": datetime.now().isoformat(),
                        "execution_times": execution_times,
                        "request_metrics": request_metrics,
                        "database_metrics": db_metrics,
                        "cache_metrics": cache_metrics,
                    }

                    return result

                except Exception as e:
                    logger.error(
                        f"Error generating performance metrics: {str(e)}", exc_info=True
                    )
                    # Record error in metrics
                    counter(
                        "dashboard.errors.performance", "Performance metrics errors"
                    ).increment()
                    return {"timestamp": datetime.now().isoformat(), "error": str(e)}

            return {
                "timestamp": datetime.now().isoformat(),
                "message": "Metrics service not available",
            }

    # Private helper methods

    @record_execution_time("project_summary")
    def _get_project_summary(self, project_service) -> Dict[str, Any]:
        """
        Get project-related summary data.

        Args:
            project_service: Project service instance

        Returns:
            Dictionary with project summary data
        """
        try:
            from app.db.models.enums import ProjectStatus

            # Get count of projects by status
            active_projects = len(
                project_service.list(status=ProjectStatus.IN_PROGRESS.value)
            )
            planning_projects = len(
                project_service.list(status=ProjectStatus.PLANNING.value)
            )
            completed_projects = len(
                project_service.list(status=ProjectStatus.COMPLETED.value)
            )

            # Get upcoming deadlines
            upcoming_deadlines = project_service.get_projects_due_soon(days=7)

            return {
                "active_projects": active_projects,
                "planning_projects": planning_projects,
                "completed_projects": completed_projects,
                "total_projects": active_projects
                + planning_projects
                + completed_projects,
                "completion_rate": self._calculate_completion_rate(
                    completed_projects,
                    active_projects + planning_projects + completed_projects,
                ),
                "upcoming_deadlines": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "due_date": p.due_date.isoformat() if p.due_date else None,
                        "customer": (
                            p.customer.name
                            if hasattr(p, "customer") and p.customer
                            else "No customer"
                        ),
                        "days_remaining": (
                            (p.due_date - datetime.now().date()).days
                            if p.due_date
                            else None
                        ),
                    }
                    for p in upcoming_deadlines[:5]  # Limit to 5 projects
                ],
            }
        except Exception as e:
            logger.error(f"Error getting project summary: {str(e)}", exc_info=True)
            counter(
                "dashboard.errors.project_summary", "Project summary errors"
            ).increment()
            return {"error": str(e)}

    @record_execution_time("material_summary")
    def _get_material_summary(self, material_service) -> Dict[str, Any]:
        """
        Get material-related summary data.

        Args:
            material_service: Material service instance

        Returns:
            Dictionary with material summary data
        """
        try:
            from app.db.models.enums import MaterialType

            # Get low stock materials
            low_stock = material_service.get_low_stock_materials()

            # Get material counts by type
            leather_count = len(
                material_service.list(material_type=MaterialType.LEATHER.value)
            )
            hardware_count = len(
                material_service.list(material_type=MaterialType.HARDWARE.value)
            )
            supplies_count = len(
                material_service.list(material_type=MaterialType.SUPPLIES.value)
            )

            return {
                "materials_to_reorder": len(low_stock),
                "low_stock_materials": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "quantity": m.quantity,
                        "unit": m.unit,
                        "reorder_point": m.reorder_point,
                        "percentage": self._calculate_stock_percentage(
                            m.quantity, m.reorder_point
                        ),
                    }
                    for m in low_stock[:5]  # Limit to 5 materials
                ],
                "material_counts": {
                    "leather": leather_count,
                    "hardware": hardware_count,
                    "supplies": supplies_count,
                    "total": leather_count + hardware_count + supplies_count,
                },
                "material_stock_summary": self._get_material_stock_distribution(
                    material_service
                ),
            }
        except Exception as e:
            logger.error(f"Error getting material summary: {str(e)}", exc_info=True)
            counter(
                "dashboard.errors.material_summary", "Material summary errors"
            ).increment()
            return {"error": str(e)}

    @record_execution_time("sales_summary")
    def _get_sales_summary(self, sale_service) -> Dict[str, Any]:
        """
        Get sales-related summary data.

        Args:
            sale_service: Sale service instance

        Returns:
            Dictionary with sales summary data
        """
        try:
            # Get current month and previous month
            today = datetime.now()
            current_month_start = datetime(today.year, today.month, 1)

            # Get previous month
            if today.month == 1:
                prev_month_start = datetime(today.year - 1, 12, 1)
            else:
                prev_month_start = datetime(today.year, today.month - 1, 1)

            # Get sales for current month
            current_month_sales = sale_service.list(
                created_at_from=current_month_start, created_at_to=today
            )

            # Get sales for previous month
            prev_month_sales = sale_service.list(
                created_at_from=prev_month_start, created_at_to=current_month_start
            )

            # Calculate revenue
            current_month_revenue = sum(
                s.total_amount
                for s in current_month_sales
                if hasattr(s, "total_amount")
            )
            prev_month_revenue = sum(
                s.total_amount for s in prev_month_sales if hasattr(s, "total_amount")
            )

            # Calculate revenue trend
            revenue_trend = 0
            if prev_month_revenue > 0:
                revenue_trend = (
                    (current_month_revenue - prev_month_revenue) / prev_month_revenue
                ) * 100

            # Get pending orders
            from app.db.models.enums import SaleStatus, PaymentStatus

            pending_orders = len(
                sale_service.list(
                    status_in=[
                        SaleStatus.CONFIRMED.value,
                        SaleStatus.IN_PRODUCTION.value,
                        SaleStatus.READY_FOR_DELIVERY.value,
                    ]
                )
            )

            # Get payment pending orders
            payment_pending = len(
                sale_service.list(
                    payment_status_in=[
                        PaymentStatus.PENDING.value,
                        PaymentStatus.DEPOSIT_PENDING.value,
                        PaymentStatus.BALANCE_PENDING.value,
                    ]
                )
            )

            # Get top products
            top_products = sale_service.repository.get_top_products(limit=3)

            # Update monthly revenue gauge
            self.monthly_revenue_gauge.set(current_month_revenue)

            return {
                "pending_orders": pending_orders,
                "payment_pending": payment_pending,
                "monthly_revenue": current_month_revenue,
                "revenue_trend": f"{revenue_trend:.1f}%",
                "top_products": top_products,
            }
        except Exception as e:
            logger.error(f"Error getting sales summary: {str(e)}", exc_info=True)
            counter(
                "dashboard.errors.sales_summary", "Sales summary errors"
            ).increment()
            return {
                "pending_orders": 0,
                "monthly_revenue": 0,
                "revenue_trend": "0%",
                "top_products": [],
                "error": str(e),
            }

    @record_execution_time("purchase_summary")
    def _get_purchase_summary(self, purchase_service) -> Dict[str, Any]:
        """
        Get purchase-related summary data.

        Args:
            purchase_service: Purchase service instance

        Returns:
            Dictionary with purchase summary data
        """
        try:
            from app.db.models.enums import PurchaseStatus

            # Get pending purchases
            pending_purchases = len(
                purchase_service.list(
                    status_in=[
                        PurchaseStatus.PLANNING.value,
                        PurchaseStatus.PENDING_APPROVAL.value,
                        PurchaseStatus.APPROVED.value,
                        PurchaseStatus.ORDERED.value,
                    ]
                )
            )

            # Get current month and previous month
            today = datetime.now()
            current_month_start = datetime(today.year, today.month, 1)

            # Get purchases for current month
            current_month_purchases = purchase_service.list(
                created_at_from=current_month_start, created_at_to=today
            )

            # Calculate spending
            monthly_spending = sum(
                p.total for p in current_month_purchases if hasattr(p, "total")
            )

            # Get upcoming deliveries
            upcoming_deliveries = purchase_service.list(
                status=PurchaseStatus.ORDERED.value,
                delivery_date_from=today,
                delivery_date_to=today + timedelta(days=14),
                sort_by="delivery_date",
                sort_dir="asc",
            )

            return {
                "pending_purchases": pending_purchases,
                "monthly_spending": monthly_spending,
                "upcoming_deliveries": [
                    {
                        "supplier": (
                            p.supplier.name
                            if hasattr(p, "supplier") and p.supplier
                            else "Unknown Supplier"
                        ),
                        "expected_date": (
                            p.delivery_date.isoformat()
                            if hasattr(p, "delivery_date") and p.delivery_date
                            else None
                        ),
                        "items": len(p.items) if hasattr(p, "items") else 0,
                        "total": p.total if hasattr(p, "total") else 0,
                    }
                    for p in upcoming_deliveries[:3]  # Limit to 3 deliveries
                ],
            }
        except Exception as e:
            logger.error(f"Error getting purchase summary: {str(e)}", exc_info=True)
            counter(
                "dashboard.errors.purchase_summary", "Purchase summary errors"
            ).increment()
            return {
                "pending_purchases": 0,
                "monthly_spending": 0,
                "upcoming_deliveries": [],
                "error": str(e),
            }

    @record_execution_time("customer_summary")
    def _get_customer_summary(self, customer_service) -> Dict[str, Any]:
        """
        Get customer-related summary data.

        Args:
            customer_service: Customer service instance

        Returns:
            Dictionary with customer summary data
        """
        try:
            # Get total customers
            total_customers = len(customer_service.list())

            # Get new customers this month
            today = datetime.now()
            month_start = datetime(today.year, today.month, 1)
            new_customers = len(customer_service.list(created_at_from=month_start))

            # Get active customers in last 30 days
            active_customers = len(
                customer_service.get_recently_active_customers(days=30)
            )

            # Get customer tiers
            from app.db.models.enums import CustomerTier

            vip_customers = len(customer_service.list(tier=CustomerTier.VIP.value))

            return {
                "total_customers": total_customers,
                "new_customers_this_month": new_customers,
                "active_customers_30_days": active_customers,
                "vip_customers": vip_customers,
                "customer_activity_rate": (
                    f"{(active_customers / total_customers) * 100:.1f}%"
                    if total_customers > 0
                    else "0%"
                ),
            }
        except Exception as e:
            logger.error(f"Error getting customer summary: {str(e)}", exc_info=True)
            counter(
                "dashboard.errors.customer_summary", "Customer summary errors"
            ).increment()
            return {
                "total_customers": 0,
                "new_customers_this_month": 0,
                "active_customers_30_days": 0,
                "vip_customers": 0,
                "error": str(e),
            }

    @record_execution_time("recent_activity")
    def _get_recent_activity(self) -> List[Dict[str, Any]]:
        """
        Get recent activity across the system.

        Returns:
            List of recent activity items
        """
        # In a real implementation, this would query an activity log or event store
        # For this implementation, we'll return recent activities across different entities
        activities = []

        try:
            # Get project service for recent project activities
            project_service = self.service_factory.get_project_service()

            # Get recent project status changes
            project_history = project_service.repository.get_recent_status_changes(
                limit=5
            )
            for history in project_history:
                activities.append(
                    {
                        "id": f"project_status_{history['id']}",
                        "type": "project_status_change",
                        "title": f"Project Status Change: {history['project_name']}",
                        "description": f"Status changed from {history['previous_status']} to {history['new_status']}",
                        "timestamp": (
                            history["change_date"].isoformat()
                            if isinstance(history["change_date"], datetime)
                            else history["change_date"]
                        ),
                        "entity_id": history["project_id"],
                        "entity_type": "project",
                    }
                )

            # Get material service for recent material activities
            material_service = self.service_factory.get_material_service()

            # Get recent inventory changes
            inventory_changes = (
                material_service.repository.get_recent_inventory_changes(limit=5)
            )
            for change in inventory_changes:
                activities.append(
                    {
                        "id": f"inventory_{change['id']}",
                        "type": "inventory_change",
                        "title": f"Inventory Change: {change['material_name']}",
                        "description": f"{abs(change['quantity_change'])} {change['unit']} "
                        + (
                            "added to"
                            if change["quantity_change"] > 0
                            else "removed from"
                        )
                        + f" inventory - {change['reason']}",
                        "timestamp": (
                            change["transaction_date"].isoformat()
                            if isinstance(change["transaction_date"], datetime)
                            else change["transaction_date"]
                        ),
                        "entity_id": change["material_id"],
                        "entity_type": "material",
                    }
                )

            # Get sale service for recent sales
            sale_service = self.service_factory.get_sale_service()

            # Get recent sales
            recent_sales = sale_service.list(
                limit=5, sort_by="created_at", sort_dir="desc"
            )
            for sale in recent_sales:
                activities.append(
                    {
                        "id": f"sale_{sale.id}",
                        "type": "new_order",
                        "title": f"New Order: {sale.id}",
                        "description": f"Customer: {sale.customer.name if hasattr(sale, 'customer') and sale.customer else 'Unknown'} - ${sale.total_amount if hasattr(sale, 'total_amount') else 0:.2f}",
                        "timestamp": (
                            sale.created_at.isoformat()
                            if hasattr(sale, "created_at") and sale.created_at
                            else datetime.now().isoformat()
                        ),
                        "entity_id": sale.id,
                        "entity_type": "sale",
                    }
                )

            # Sort all activities by timestamp (newest first)
            activities.sort(key=lambda x: x["timestamp"], reverse=True)

            # Return the most recent 10 activities
            return activities[:10]

        except Exception as e:
            logger.error(f"Error getting recent activity: {str(e)}", exc_info=True)
            counter(
                "dashboard.errors.recent_activity", "Recent activity errors"
            ).increment()
            return [
                {
                    "id": "error",
                    "type": "error",
                    "title": "Error retrieving activities",
                    "description": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ]

    def _calculate_completion_rate(self, completed: int, total: int) -> float:
        """
        Calculate project completion rate.

        Args:
            completed: Number of completed projects
            total: Total number of projects

        Returns:
            Completion rate as a percentage
        """
        if total == 0:
            return 0
        return round((completed / total) * 100, 1)

    def _calculate_stock_percentage(self, quantity: float, reorder_point: float) -> int:
        """
        Calculate stock level as percentage of reorder point.

        Args:
            quantity: Current quantity
            reorder_point: Reorder point

        Returns:
            Stock level as a percentage
        """
        if reorder_point == 0:
            return 100
        percentage = (quantity / reorder_point) * 100
        return min(int(percentage), 100)

    def _get_material_stock_distribution(
        self, material_service
    ) -> List[Dict[str, Any]]:
        """
        Get material stock level distribution for visualization.

        Args:
            material_service: Material service instance

        Returns:
            List of material stock level data
        """
        try:
            # Get most critical materials for stock visualization
            materials = material_service.repository.get_most_important_materials(
                limit=5
            )

            result = []
            for material in materials:
                percentage = self._calculate_stock_percentage(
                    material.quantity, material.reorder_point
                )
                status = (
                    "low"
                    if percentage < 50
                    else ("medium" if percentage < 80 else "good")
                )

                result.append(
                    {
                        "name": material.name,
                        "percentage": percentage,
                        "status": status,
                        "material_type": material.material_type,
                    }
                )

            return result

        except Exception as e:
            logger.error(
                f"Error getting material stock distribution: {str(e)}", exc_info=True
            )
            counter(
                "dashboard.errors.stock_distribution", "Stock distribution errors"
            ).increment()
            return []
