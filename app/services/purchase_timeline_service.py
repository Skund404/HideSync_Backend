# File: app/services/purchase_timeline_service.py
"""
Purchase timeline service for the HideSync system.

This module provides functionality for tracking and visualizing purchases over time,
including scheduled deliveries, purchase planning based on inventory levels,
and historical purchase analysis.

The service generates timeline views of upcoming deliveries, helps identify
purchase patterns, and recommends inventory replenishment based on usage rates
and current stock levels.
"""

from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import logging
import calendar
import uuid

from app.services.base_service import BaseService
from app.db.models.purchase import Purchase, PurchaseItem
from app.db.models.enums import PurchaseStatus, MaterialType
from app.repositories.purchase_repository import PurchaseRepository
from app.core.exceptions import (
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
)
from app.schemas.purchase_timeline import (
    PurchasePlan,
    PurchasePlanItem,
    PurchaseTimeline,
    PurchaseTimelinePeriod,
    PurchaseTimelineItem,
)

logger = logging.getLogger(__name__)


class PurchaseTimelineService(BaseService):
    """
    Service for managing purchase timelines and planning in the HideSync system.

    Provides functionality for:
    - Generating purchase timelines across different time periods
    - Planning inventory purchases based on current stock and usage
    - Visualizing upcoming deliveries and historical purchases
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        supplier_service=None,
        material_service=None,
        inventory_service=None,
    ):
        """
        Initialize PurchaseTimelineService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            supplier_service: Optional supplier service for supplier data
            material_service: Optional material service for material data
            inventory_service: Optional inventory service for inventory levels
        """
        self.session = session
        self.repository = repository or PurchaseRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.supplier_service = supplier_service
        self.material_service = material_service
        self.inventory_service = inventory_service

    def get_purchase_timeline(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period: str = "month",
        supplier_id: Optional[int] = None,
    ) -> PurchaseTimeline:
        """
        Generate a purchase timeline for the specified date range.

        Args:
            start_date: Start date for the timeline (defaults to 3 months ago)
            end_date: End date for the timeline (defaults to 3 months from now)
            period: Time period for grouping ('day', 'week', 'month', 'quarter')
            supplier_id: Optional supplier ID to filter by

        Returns:
            PurchaseTimeline with purchases grouped by time periods

        Raises:
            ValidationException: If the period is invalid
        """
        # Set default date range if not provided
        today = date.today()
        if not start_date:
            start_date = today - timedelta(days=90)
        if not end_date:
            end_date = today + timedelta(days=90)

        # Validate period
        valid_periods = ["day", "week", "month", "quarter"]
        if period not in valid_periods:
            raise ValidationException(
                f"Invalid period: {period}",
                {"period": [f"Must be one of: {', '.join(valid_periods)}"]},
            )

        # Get purchases in date range
        purchases = self._get_purchases_in_range(start_date, end_date, supplier_id)

        # Group purchases by period
        periods = self._group_purchases_by_period(
            purchases, start_date, end_date, period
        )

        # Get unique suppliers
        suppliers = list(
            set(
                purchase.supplier
                for purchase in purchases
                if hasattr(purchase, "supplier")
            )
        )

        # Create timeline
        timeline = PurchaseTimeline(
            periods=periods,
            total_purchases=len(purchases),
            total_amount=sum(
                purchase.total for purchase in purchases if hasattr(purchase, "total")
            ),
            date_range_start=start_date,
            date_range_end=end_date,
            suppliers=suppliers,
        )

        return timeline

    def create_purchase_plan(
        self,
        min_stock_days: int = 30,
        supplier_id: Optional[int] = None,
        material_type: Optional[str] = None,
        include_pending: bool = True,
    ) -> PurchasePlan:
        """
        Create a purchase plan based on current inventory levels.

        Analyzes current inventory levels, usage rates, and pending deliveries
        to generate a recommended purchase plan.

        Args:
            min_stock_days: Minimum number of days of stock to maintain
            supplier_id: Optional supplier ID to filter by
            material_type: Optional material type to filter by
            include_pending: Whether to include pending purchases in calculations

        Returns:
            PurchasePlan with recommended purchases

        Raises:
            ValidationException: If the parameters are invalid
        """
        if not self.inventory_service or not self.material_service:
            raise BusinessRuleException(
                "Cannot create purchase plan: required services unavailable",
                "PURCHASE_PLAN_001",
                {"service_dependencies": ["inventory_service", "material_service"]},
            )

        # Get current inventory levels
        inventory_items = self.inventory_service.get_all_material_inventory()

        # Filter by material type if specified
        if material_type:
            inventory_items = [
                item
                for item in inventory_items
                if hasattr(item, "material_type")
                and item.material_type == material_type
            ]

        # Get pending purchases if included
        pending_purchases = []
        if include_pending:
            pending_statuses = [
                PurchaseStatus.ORDERED.value,
                PurchaseStatus.ACKNOWLEDGED.value,
                PurchaseStatus.PROCESSING.value,
                PurchaseStatus.SHIPPED.value,
                PurchaseStatus.IN_TRANSIT.value,
            ]
            pending_purchases = self.repository.list(status_in=pending_statuses)

        # Calculate purchase plan items
        plan_items = []
        for inventory_item in inventory_items:
            # Skip if no material ID
            if not hasattr(inventory_item, "item_id") or not inventory_item.item_id:
                continue

            material_id = inventory_item.item_id

            # Get material details
            material = self.material_service.get_by_id(material_id)
            if not material:
                continue

            # Skip if filtered by supplier and not matching
            if (
                supplier_id
                and hasattr(material, "supplier_id")
                and material.supplier_id != supplier_id
            ):
                continue

            # Get material attributes
            material_name = (
                material.name
                if hasattr(material, "name")
                else f"Material {material_id}"
            )
            material_type = (
                material.material_type
                if hasattr(material, "material_type")
                else "Unknown"
            )
            current_stock = (
                inventory_item.quantity if hasattr(inventory_item, "quantity") else 0
            )
            min_stock_level = (
                material.reorder_point if hasattr(material, "reorder_point") else 0
            )
            unit = material.unit if hasattr(material, "unit") else "PIECE"

            # Get supplier details
            supplier_id = (
                material.supplier_id if hasattr(material, "supplier_id") else None
            )
            supplier_name = None
            if supplier_id and self.supplier_service:
                supplier = self.supplier_service.get_by_id(supplier_id)
                if supplier:
                    supplier_name = supplier.name if hasattr(supplier, "name") else None

            # Calculate usage rate and days until stockout
            usage_rate = self._calculate_usage_rate(material_id)
            days_until_stockout = None
            if usage_rate > 0:
                days_until_stockout = int(current_stock / usage_rate)

            # Calculate pending deliveries for this material
            pending_quantity = 0
            if include_pending:
                for purchase in pending_purchases:
                    items = self.repository.get_purchase_items(purchase.id)
                    for item in items:
                        if (
                            hasattr(item, "material_id")
                            and item.material_id == material_id
                        ):
                            pending_quantity += item.quantity

            # Calculate recommended order quantity
            recommended_quantity = 0
            if days_until_stockout is not None and days_until_stockout < min_stock_days:
                # Calculate quantity needed to reach min_stock_days
                needed_stock = usage_rate * min_stock_days
                recommended_quantity = needed_stock - (current_stock + pending_quantity)
                if recommended_quantity < 0:
                    recommended_quantity = 0
            elif min_stock_level > 0 and current_stock < min_stock_level:
                # Use reorder point if available
                recommended_quantity = min_stock_level - (
                    current_stock + pending_quantity
                )
                if recommended_quantity < 0:
                    recommended_quantity = 0

            # Skip if no order needed
            if recommended_quantity <= 0:
                continue

            # Calculate estimated cost
            estimated_cost = None
            if hasattr(material, "cost") and material.cost:
                estimated_cost = material.cost * recommended_quantity

            # Get last purchase info
            last_purchase_date = None
            last_purchase_price = None
            # This would require additional repository methods to implement

            # Create plan item
            plan_item = PurchasePlanItem(
                material_id=material_id,
                material_name=material_name,
                material_type=material_type,
                current_stock=current_stock,
                min_stock_level=min_stock_level,
                recommended_order_quantity=recommended_quantity,
                unit=unit,
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                estimated_cost=estimated_cost,
                last_purchase_date=last_purchase_date,
                last_purchase_price=last_purchase_price,
                days_until_stockout=days_until_stockout,
                usage_rate=usage_rate,
                priority=self._calculate_priority(
                    days_until_stockout, min_stock_level, current_stock
                ),
            )

            plan_items.append(plan_item)

        # Group by supplier
        supplier_breakdown = {}
        recommended_purchases = {}

        for item in plan_items:
            supplier_name = item.supplier_name or "Unknown Supplier"

            # Add to supplier breakdown
            if supplier_name not in supplier_breakdown:
                supplier_breakdown[supplier_name] = 0
                recommended_purchases[supplier_name] = []

            if item.estimated_cost:
                supplier_breakdown[supplier_name] += item.estimated_cost

            recommended_purchases[supplier_name].append(item)

        # Calculate total estimated cost
        total_estimated_cost = sum(
            item.estimated_cost for item in plan_items if item.estimated_cost
        )

        # Create purchase plan
        plan = PurchasePlan(
            items=plan_items,
            total_estimated_cost=total_estimated_cost,
            supplier_breakdown=supplier_breakdown,
            recommended_purchases=recommended_purchases,
        )

        return plan

    def _get_purchases_in_range(
        self, start_date: date, end_date: date, supplier_id: Optional[int] = None
    ) -> List[Purchase]:
        """
        Get purchases within a date range.

        Args:
            start_date: Start date
            end_date: End date
            supplier_id: Optional supplier ID to filter by

        Returns:
            List of purchases within the date range
        """
        filters = {
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "sort_by": "date",
            "sort_dir": "asc",
        }

        if supplier_id:
            filters["supplier_id"] = supplier_id

        return self.repository.list(**filters)

    def _group_purchases_by_period(
        self, purchases: List[Purchase], start_date: date, end_date: date, period: str
    ) -> List[PurchaseTimelinePeriod]:
        """
        Group purchases by time period.

        Args:
            purchases: List of purchases to group
            start_date: Start date of the timeline
            end_date: End date of the timeline
            period: Time period for grouping ('day', 'week', 'month', 'quarter')

        Returns:
            List of timeline periods with grouped purchases
        """
        # Create period ranges
        period_ranges = self._create_period_ranges(start_date, end_date, period)

        # Initialize periods with empty purchase lists
        periods = []
        for period_name, period_start, period_end in period_ranges:
            periods.append(
                PurchaseTimelinePeriod(
                    period_name=period_name,
                    start_date=period_start,
                    end_date=period_end,
                    items=[],
                    total_amount=0,
                    item_count=0,
                )
            )

        # Assign purchases to periods
        for purchase in purchases:
            # Skip if no date or not a datetime
            if not hasattr(purchase, "date") or not isinstance(purchase.date, datetime):
                continue

            purchase_date = purchase.date.date()

            # Find the right period
            for period_data in periods:
                if (
                    purchase_date >= period_data.start_date
                    and purchase_date <= period_data.end_date
                ):
                    # Create timeline item
                    timeline_item = self._create_timeline_item(purchase)
                    if timeline_item:
                        period_data.items.append(timeline_item)
                        period_data.total_amount += timeline_item.total
                        period_data.item_count += 1
                    break

        return periods

    def _create_period_ranges(
        self, start_date: date, end_date: date, period: str
    ) -> List[Tuple[str, date, date]]:
        """
        Create date ranges for the specified period.

        Args:
            start_date: Start date
            end_date: End date
            period: Time period ('day', 'week', 'month', 'quarter')

        Returns:
            List of (period_name, period_start, period_end) tuples
        """
        ranges = []
        current_date = start_date

        while current_date <= end_date:
            if period == "day":
                period_name = current_date.strftime("%Y-%m-%d")
                period_start = current_date
                period_end = current_date
                current_date = current_date + timedelta(days=1)

            elif period == "week":
                # Get week start (Monday) and end (Sunday)
                week_start = current_date - timedelta(days=current_date.weekday())
                week_end = week_start + timedelta(days=6)
                period_name = f"Week {current_date.strftime('%U')}, {current_date.year}"
                period_start = max(week_start, start_date)
                period_end = min(week_end, end_date)
                current_date = week_end + timedelta(days=1)

            elif period == "month":
                # Get month start and end
                month_start = date(current_date.year, current_date.month, 1)
                last_day = calendar.monthrange(current_date.year, current_date.month)[1]
                month_end = date(current_date.year, current_date.month, last_day)
                period_name = current_date.strftime("%B %Y")
                period_start = max(month_start, start_date)
                period_end = min(month_end, end_date)

                # Move to next month
                if current_date.month == 12:
                    current_date = date(current_date.year + 1, 1, 1)
                else:
                    current_date = date(current_date.year, current_date.month + 1, 1)

            elif period == "quarter":
                # Get quarter start and end
                quarter = (current_date.month - 1) // 3 + 1
                quarter_start = date(current_date.year, (quarter - 1) * 3 + 1, 1)
                if quarter == 4:
                    quarter_end = date(current_date.year, 12, 31)
                else:
                    quarter_end = date(
                        current_date.year,
                        quarter * 3,
                        calendar.monthrange(current_date.year, quarter * 3)[1],
                    )
                period_name = f"Q{quarter} {current_date.year}"
                period_start = max(quarter_start, start_date)
                period_end = min(quarter_end, end_date)

                # Move to next quarter
                if quarter == 4:
                    current_date = date(current_date.year + 1, 1, 1)
                else:
                    current_date = date(current_date.year, quarter * 3 + 1, 1)

            ranges.append((period_name, period_start, period_end))

            # Break if we've gone past the end date
            if current_date > end_date:
                break

        return ranges

    def _create_timeline_item(
        self, purchase: Purchase
    ) -> Optional[PurchaseTimelineItem]:
        """
        Create a timeline item from a purchase.

        Args:
            purchase: Purchase to convert

        Returns:
            Timeline item or None if invalid purchase
        """
        if not hasattr(purchase, "id") or not hasattr(purchase, "total"):
            return None

        # Get supplier
        supplier = (
            purchase.supplier if hasattr(purchase, "supplier") else "Unknown Supplier"
        )

        # Get delivery date
        delivery_date = None
        if hasattr(purchase, "delivery_date") and purchase.delivery_date:
            if isinstance(purchase.delivery_date, datetime):
                delivery_date = purchase.delivery_date.date()
            elif isinstance(purchase.delivery_date, date):
                delivery_date = purchase.delivery_date
            elif isinstance(purchase.delivery_date, str):
                try:
                    delivery_date = datetime.fromisoformat(
                        purchase.delivery_date
                    ).date()
                except ValueError:
                    delivery_date = date.today()  # Fallback
        else:
            delivery_date = date.today()  # Fallback

        # Get status
        status = purchase.status if hasattr(purchase, "status") else "UNKNOWN"

        # Get items summary
        items = {}
        purchase_items = self.repository.get_purchase_items(purchase.id)
        for item in purchase_items:
            if hasattr(item, "name") and hasattr(item, "quantity"):
                items[item.name] = item.quantity

        # Create timeline item
        timeline_item = PurchaseTimelineItem(
            id=str(uuid.uuid4()),
            purchase_id=str(purchase.id),
            supplier=supplier,
            delivery_date=delivery_date,
            status=status,
            items=items,
            total=purchase.total,
        )

        return timeline_item

    def _calculate_usage_rate(self, material_id: int) -> float:
        """
        Calculate the daily usage rate for a material.

        Args:
            material_id: ID of the material

        Returns:
            Daily usage rate (units per day)
        """
        # This would normally analyze inventory transactions
        # over the past X days to calculate usage
        # Simplified implementation returns a placeholder value
        return 0.1  # Default usage rate

    def _calculate_priority(
        self,
        days_until_stockout: Optional[int],
        min_stock_level: float,
        current_stock: float,
    ) -> str:
        """
        Calculate priority level based on stock status.

        Args:
            days_until_stockout: Number of days until stockout
            min_stock_level: Minimum stock level
            current_stock: Current stock level

        Returns:
            Priority level ("HIGH", "MEDIUM", "LOW")
        """
        if days_until_stockout is not None:
            if days_until_stockout <= 7:
                return "HIGH"
            elif days_until_stockout <= 14:
                return "MEDIUM"
            else:
                return "LOW"
        elif min_stock_level > 0:
            ratio = current_stock / min_stock_level
            if ratio <= 0.5:
                return "HIGH"
            elif ratio <= 0.75:
                return "MEDIUM"
            else:
                return "LOW"
        else:
            return "LOW"
