# File: app/repositories/material_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.db.models.material import (
    Material,
    LeatherMaterial,
    HardwareMaterial,
    SuppliesMaterial,
)
from app.db.models.enums import MaterialType, InventoryStatus
from app.repositories.base_repository import BaseRepository


class MaterialRepository(BaseRepository[Material]):
    """
    Repository for Material entity operations.

    Provides methods for accessing and manipulating material data, including
    specialized methods for different material types (leather, hardware, supplies).
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the MaterialRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Material

    def get_materials_by_type(
        self, material_type: MaterialType, skip: int = 0, limit: int = 100
    ) -> List[Material]:
        """
        Get materials by their type.

        Args:
            material_type (MaterialType): The type of material to retrieve
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Material]: List of materials matching the given type
        """
        query = self.session.query(self.model).filter(
            self.model.materialType == material_type
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_materials_by_status(
        self, status: InventoryStatus, skip: int = 0, limit: int = 100
    ) -> List[Material]:
        """
        Get materials by their inventory status.

        Args:
            status (InventoryStatus): The inventory status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Material]: List of materials with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_materials_by_supplier(
        self, supplier_id: int, skip: int = 0, limit: int = 100
    ) -> List[Material]:
        """
        Get materials supplied by a specific supplier.

        Args:
            supplier_id (int): ID of the supplier
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Material]: List of materials from the specified supplier
        """
        query = self.session.query(self.model).filter(
            self.model.supplierId == supplier_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_low_stock_materials(
        self, skip: int = 0, limit: int = 100
    ) -> List[Material]:
        """
        Get materials that are low in stock (below reorder point).

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Material]: List of materials that are low in stock
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.quantity <= self.model.reorderPoint,
                self.model.status != InventoryStatus.DISCONTINUED,
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_inventory_quantity(
        self, material_id: int, quantity_change: float
    ) -> Optional[Material]:
        """
        Update a material's inventory quantity.

        Args:
            material_id (int): ID of the material
            quantity_change (float): Amount to add (positive) or subtract (negative)

        Returns:
            Optional[Material]: Updated material if found, None otherwise
        """
        material = self.get_by_id(material_id)
        if not material:
            return None

        # Update quantity
        new_quantity = material.quantity + quantity_change
        material.quantity = max(0, new_quantity)  # Prevent negative quantities

        # Update status based on new quantity
        if new_quantity <= 0:
            material.status = InventoryStatus.OUT_OF_STOCK
        elif new_quantity <= material.reorderPoint:
            material.status = InventoryStatus.LOW_STOCK
        else:
            material.status = InventoryStatus.IN_STOCK

        self.session.commit()
        self.session.refresh(material)
        return self._decrypt_sensitive_fields(material)

    def search_materials(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[Material]:
        """
        Search for materials by name, description, or supplier.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Material]: List of matching materials
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
                self.model.supplier.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_leather_by_type(
        self, leather_type, skip: int = 0, limit: int = 100
    ) -> List[LeatherMaterial]:
        """
        Get leather materials by their type.

        Args:
            leather_type: The type of leather to retrieve
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[LeatherMaterial]: List of leather materials of the specified type
        """
        query = (
            self.session.query(LeatherMaterial)
            .filter(LeatherMaterial.materialType == MaterialType.LEATHER)
            .filter(LeatherMaterial.leatherType == leather_type)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_hardware_by_type(
        self, hardware_type, skip: int = 0, limit: int = 100
    ) -> List[HardwareMaterial]:
        """
        Get hardware materials by their type.

        Args:
            hardware_type: The type of hardware to retrieve
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[HardwareMaterial]: List of hardware materials of the specified type
        """
        query = (
            self.session.query(HardwareMaterial)
            .filter(HardwareMaterial.materialType == MaterialType.HARDWARE)
            .filter(HardwareMaterial.hardwareType == hardware_type)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]
