# File: app/repositories/material_repository.py

import re # Import re for snake_case conversion
from typing import List, Optional, Dict, Any, Union, Type
from datetime import datetime
from enum import Enum # Import Enum base class

# Import modern SQLAlchemy components
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session, joinedload

from app.repositories.base_repository import BaseRepository
from app.db.models.material import (
    Material,
    LeatherMaterial,
    HardwareMaterial,
    SuppliesMaterial,
    WoodMaterial
)
# Ensure InventoryStatus is imported if used for filtering
from app.db.models.enums import InventoryStatus
# Import Supplier if needed for relationship loading/filtering
from app.db.models.supplier import Supplier


class MaterialRepository(BaseRepository[Material]):
    """
    Repository for material-related database operations using modern select() syntax.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the repository with database session and Material model.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for sensitive data handling
        """
        # Explicitly pass the Material model to the base constructor
        super().__init__(session=session, model=Material, encryption_service=encryption_service)

    def _prepare_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare data for entity creation/update.
        Converts camelCase keys to snake_case.

        Args:
            data: Input data dictionary (camelCase keys)

        Returns:
            Prepared data dictionary (snake_case keys)
        """
        prepared = {}
        for key, value in data.items():
             # Convert camelCase to snake_case
             snake_key = re.sub(r'(?<!^)(?=[A-Z])', '_', key).lower()
             prepared[snake_key] = value
        return prepared

    def _filter_to_model_columns(self, data: Dict[str, Any], model_cls: Type[Material]) -> Dict[str, Any]:
        """Filters a dictionary to include only keys that are columns in the model."""
        model_columns = {c.name for c in model_cls.__table__.columns}
        return {k: v for k, v in data.items() if k in model_columns}

    # --- Create methods ---
    # These methods prepare data, ensure the correct type, filter keys,
    # add to session, and flush. Commit should happen in the service layer transaction.

    def create_leather(self, data: Dict[str, Any]) -> LeatherMaterial:
        """Prepares and adds a new leather material to the session."""
        prepared_data = self._prepare_data(data)
        prepared_data['material_type'] = 'leather' # Ensure correct discriminator
        filtered_data = self._filter_to_model_columns(prepared_data, LeatherMaterial)
        leather = LeatherMaterial(**filtered_data)
        self.session.add(leather)
        self.session.flush() # Flush to assign ID if needed before commit
        return leather

    def create_hardware(self, data: Dict[str, Any]) -> HardwareMaterial:
        """Prepares and adds a new hardware material to the session."""
        prepared_data = self._prepare_data(data)
        prepared_data['material_type'] = 'hardware'
        filtered_data = self._filter_to_model_columns(prepared_data, HardwareMaterial)
        hardware = HardwareMaterial(**filtered_data)
        self.session.add(hardware)
        self.session.flush()
        return hardware

    def create_supplies(self, data: Dict[str, Any]) -> SuppliesMaterial:
        """Prepares and adds a new supplies material to the session."""
        prepared_data = self._prepare_data(data)
        prepared_data['material_type'] = 'supplies'
        filtered_data = self._filter_to_model_columns(prepared_data, SuppliesMaterial)
        supplies = SuppliesMaterial(**filtered_data)
        self.session.add(supplies)
        self.session.flush()
        return supplies

    def create_wood(self, data: Dict[str, Any]) -> WoodMaterial:
        """Prepares and adds a new wood material to the session."""
        prepared_data = self._prepare_data(data)
        prepared_data['material_type'] = 'wood'
        filtered_data = self._filter_to_model_columns(prepared_data, WoodMaterial)
        wood = WoodMaterial(**filtered_data)
        self.session.add(wood)
        self.session.flush()
        return wood

    # --- Read/Query methods ---

    def get_by_id_with_supplier(self, entity_id: int) -> Optional[Material]:
        """
        Get material by ID with supplier information eagerly loaded.

        Args:
            entity_id: Material ID

        Returns:
            Material model instance with supplier_rel loaded, or None.
        """
        stmt = (
            select(Material)
            .options(joinedload(Material.supplier_rel)) # Eager load supplier
            .where(Material.id == entity_id)
        )
        # Use BaseRepository's _decrypt_sensitive_fields if needed, or handle in service
        material = self.session.execute(stmt).scalar_one_or_none()
        return self._decrypt_sensitive_fields(material) if material else None


    def get_materials_by_status(
        self, status: Union[InventoryStatus, List[InventoryStatus]], skip: int = 0, limit: int = 100
    ) -> List[Material]:
        """
        Get materials by inventory status using modern select().

        Args:
            status: Status or list of statuses to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of materials with the specified status(es)
        """
        stmt = select(Material)

        if isinstance(status, list):
            # Ensure comparing against enum values if necessary
            status_values = [s for s in status] # Assume already enum objects
            stmt = stmt.where(Material.status.in_(status_values))
        elif isinstance(status, Enum):
            stmt = stmt.where(Material.status == status)
        else:
             # Handle case where status might be passed as string - attempt conversion
             try:
                 status_enum = InventoryStatus(status)
                 stmt = stmt.where(Material.status == status_enum)
             except ValueError:
                 # Log warning or raise error for invalid status string
                 print(f"Warning: Invalid status string '{status}' provided.") # Replace with logger
                 return []

        stmt = stmt.offset(skip).limit(limit)
        results = self.session.execute(stmt)
        entities = results.scalars().all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_low_stock_materials(self) -> List[Material]:
        """
        Get materials with quantity below or at reorder point using modern select().

        Returns:
            List of materials with low stock
        """
        stmt = select(Material).where(
            or_(
                Material.status == InventoryStatus.LOW_STOCK,
                Material.status == InventoryStatus.OUT_OF_STOCK,
                # Ensure reorder_point is not None before comparing
                and_(
                    Material.reorder_point != None,
                    Material.reorder_point > 0,
                    Material.quantity <= Material.reorder_point,
                ),
            )
        )
        results = self.session.execute(stmt)
        entities = results.scalars().all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def find_by_storage_location(self, location_name: str) -> List[Material]:
        """
        Find materials by storage location name (assuming string field).

        Args:
            location_name: Storage location name string.

        Returns:
            List of materials at the location
        """
        # Filter by the string 'storage_location' field based on the model definition
        stmt = select(Material).where(Material.storage_location == location_name)

        results = self.session.execute(stmt)
        entities = results.scalars().all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]


    def search_materials(
        self, query: str, skip: int = 0, limit: int = 20
    ) -> List[Material]:
        """
        Search materials by query string across multiple fields using modern select().

        Args:
            query: Search query string
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of materials matching the search
        """
        search_term = f"%{query}%"
        stmt = select(Material).where(
             or_(
                 Material.name.ilike(search_term),
                 Material.description.ilike(search_term),
                 Material.sku.ilike(search_term),
                 # Assuming 'supplier' on Material is just a string name field
                 # If it can be NULL, handle that if needed (e.g., filter(Material.supplier != None, ...))
                 Material.supplier.ilike(search_term),
                 # Add other relevant string fields here if desired
             )
         ).offset(skip).limit(limit)

        results = self.session.execute(stmt)
        entities = results.scalars().all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    # --- Other methods ---

    def get_material_usages(
        self,
        material_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Placeholder: Get usage records for a material.
        Actual implementation requires querying an inventory transaction table.
        """
        # This should query a related InventoryTransaction model/table
        # Example conceptual query (replace with actual model/columns):
        # stmt = select(InventoryTransaction).where(InventoryTransaction.material_id == material_id)
        # if start_date: stmt = stmt.where(InventoryTransaction.transaction_date >= start_date)
        # if end_date: stmt = stmt.where(InventoryTransaction.transaction_date <= end_date)
        # transactions = self.session.execute(stmt).scalars().all()
        # return [t.to_dict() for t in transactions] # Assuming a to_dict() method
        print(f"Placeholder: Fetching usage for material {material_id}") # Replace with logger
        return [] # Return empty list for now

    # Note: Update and Delete operations are typically handled by the BaseRepository methods
    # unless specific Material logic (like checking dependencies) is required.