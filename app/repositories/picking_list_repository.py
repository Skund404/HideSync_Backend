# File: app/repositories/picking_list_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime

from app.db.models.picking_list import PickingList, PickingListItem
from app.db.models.enums import PickingListStatus
from app.repositories.base_repository import BaseRepository


class PickingListRepository(BaseRepository[PickingList]):
    """
    Repository for PickingList entity operations.

    Handles operations for material picking lists, which are used to
    gather materials needed for projects and sales orders.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the PickingListRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = PickingList

    def get_picking_lists_by_project(self, project_id: str) -> List[PickingList]:
        """
        Get picking lists for a specific project.

        Args:
            project_id (str): ID of the project

        Returns:
            List[PickingList]: List of picking lists for the project
        """
        query = self.session.query(self.model).filter(
            self.model.project_id == project_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_picking_lists_by_status(
        self, status: PickingListStatus, skip: int = 0, limit: int = 100
    ) -> List[PickingList]:
        """
        Get picking lists by status.

        Args:
            status (PickingListStatus): The status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[PickingList]: List of picking lists with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_picking_lists_by_assignee(
        self, assigned_to: str, skip: int = 0, limit: int = 100
    ) -> List[PickingList]:
        """
        Get picking lists assigned to a specific user.

        Args:
            assigned_to (str): Name or ID of the assignee
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[PickingList]: List of picking lists assigned to the user
        """
        query = self.session.query(self.model).filter(
            self.model.assignedTo == assigned_to
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_pending_picking_lists(
        self, skip: int = 0, limit: int = 100
    ) -> List[PickingList]:
        """
        Get pending picking lists.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[PickingList]: List of pending picking lists
        """
        query = self.session.query(self.model).filter(
            self.model.status == PickingListStatus.PENDING
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_in_progress_picking_lists(
        self, skip: int = 0, limit: int = 100
    ) -> List[PickingList]:
        """
        Get picking lists that are in progress.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[PickingList]: List of in-progress picking lists
        """
        query = self.session.query(self.model).filter(
            self.model.status == PickingListStatus.IN_PROGRESS
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_picking_list_status(
        self, picking_list_id: str, status: PickingListStatus
    ) -> Optional[PickingList]:
        """
        Update a picking list's status.

        Args:
            picking_list_id (str): ID of the picking list
            status (PickingListStatus): New status to set

        Returns:
            Optional[PickingList]: Updated picking list if found, None otherwise
        """
        picking_list = self.get_by_id(picking_list_id)
        if not picking_list:
            return None

        picking_list.status = status

        # If status is completed, set completion date
        if status == PickingListStatus.COMPLETED:
            picking_list.completedAt = datetime.now()

        self.session.commit()
        self.session.refresh(picking_list)
        return self._decrypt_sensitive_fields(picking_list)

    def assign_picking_list(
        self, picking_list_id: str, assigned_to: str
    ) -> Optional[PickingList]:
        """
        Assign a picking list to a user.

        Args:
            picking_list_id (str): ID of the picking list
            assigned_to (str): Name or ID of the assignee

        Returns:
            Optional[PickingList]: Updated picking list if found, None otherwise
        """
        picking_list = self.get_by_id(picking_list_id)
        if not picking_list:
            return None

        picking_list.assignedTo = assigned_to

        self.session.commit()
        self.session.refresh(picking_list)
        return self._decrypt_sensitive_fields(picking_list)

    def get_picking_list_with_items(
        self, picking_list_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a picking list with its items.

        Args:
            picking_list_id (str): ID of the picking list

        Returns:
            Optional[Dict[str, Any]]: Dictionary with picking list and items if found, None otherwise
        """
        picking_list = self.get_by_id(picking_list_id)
        if not picking_list:
            return None

        # Get picking list items
        items = (
            self.session.query(PickingListItem)
            .filter(PickingListItem.picking_list_id == picking_list_id)
            .all()
        )

        return {
            "picking_list": self._decrypt_sensitive_fields(picking_list),
            "items": items,
        }


class PickingListItemRepository(BaseRepository[PickingListItem]):
    """
    Repository for PickingListItem entity operations.

    Manages individual items on picking lists, tracking quantities,
    picking status, and material relationships.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the PickingListItemRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = PickingListItem

    def get_items_by_picking_list(self, picking_list_id: str) -> List[PickingListItem]:
        """
        Get items for a specific picking list.

        Args:
            picking_list_id (str): ID of the picking list

        Returns:
            List[PickingListItem]: List of items in the picking list
        """
        query = self.session.query(self.model).filter(
            self.model.picking_list_id == picking_list_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_items_by_material(self, material_id: str) -> List[PickingListItem]:
        """
        Get picking list items for a specific material.

        Args:
            material_id (str): ID of the material

        Returns:
            List[PickingListItem]: List of picking list items for the material
        """
        query = self.session.query(self.model).filter(
            self.model.material_id == material_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_items_by_component(self, component_id: str) -> List[PickingListItem]:
        """
        Get picking list items for a specific component.

        Args:
            component_id (str): ID of the component

        Returns:
            List[PickingListItem]: List of picking list items for the component
        """
        query = self.session.query(self.model).filter(
            self.model.component_id == component_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_items_by_status(self, status: str) -> List[PickingListItem]:
        """
        Get picking list items by status.

        Args:
            status (str): The status to filter by

        Returns:
            List[PickingListItem]: List of picking list items with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_item_quantity_picked(
        self, item_id: str, quantity_picked: int
    ) -> Optional[PickingListItem]:
        """
        Update the quantity picked for an item.

        Args:
            item_id (str): ID of the item
            quantity_picked (int): New quantity picked

        Returns:
            Optional[PickingListItem]: Updated item if found, None otherwise
        """
        item = self.get_by_id(item_id)
        if not item:
            return None

        item.quantity_picked = quantity_picked

        # Update status based on quantity picked
        if item.quantity_picked == 0:
            item.status = "pending"
        elif item.quantity_picked < item.quantity_ordered:
            item.status = "partial"
        else:
            item.status = "complete"

        self.session.commit()
        self.session.refresh(item)
        return self._decrypt_sensitive_fields(item)

    def mark_item_complete(self, item_id: str) -> Optional[PickingListItem]:
        """
        Mark an item as complete.

        Args:
            item_id (str): ID of the item

        Returns:
            Optional[PickingListItem]: Updated item if found, None otherwise
        """
        item = self.get_by_id(item_id)
        if not item:
            return None

        item.status = "complete"
        item.quantity_picked = item.quantity_ordered

        self.session.commit()
        self.session.refresh(item)
        return self._decrypt_sensitive_fields(item)

    def mark_item_partial(
        self, item_id: str, quantity_picked: int
    ) -> Optional[PickingListItem]:
        """
        Mark an item as partially complete.

        Args:
            item_id (str): ID of the item
            quantity_picked (int): Quantity picked so far

        Returns:
            Optional[PickingListItem]: Updated item if found, None otherwise
        """
        item = self.get_by_id(item_id)
        if not item:
            return None

        if quantity_picked >= item.quantity_ordered:
            return self.mark_item_complete(item_id)

        item.status = "partial"
        item.quantity_picked = quantity_picked

        self.session.commit()
        self.session.refresh(item)
        return self._decrypt_sensitive_fields(item)
