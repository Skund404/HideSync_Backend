# app/services/dynamic_material_service.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.base_service import BaseService
from app.db.models.dynamic_material import (
    DynamicMaterial, MaterialPropertyValue, PropertyDefinition, MaterialType
)
from app.repositories.dynamic_material_repository import DynamicMaterialRepository
from app.core.exceptions import EntityNotFoundException, InsufficientInventoryException, ValidationException


class DynamicMaterialService(BaseService[DynamicMaterial]):
    """
    Service for managing dynamic materials in the Material Management System.

    Provides functionality for:
    - Creating and updating materials with dynamic properties
    - Inventory management for materials
    - Searching and filtering materials
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            property_service=None,
            material_type_service=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
    ):
        """
        Initialize DynamicMaterialService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            property_service: Optional PropertyDefinitionService for property validation
            material_type_service: Optional MaterialTypeService for type information
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session
        self.repository = repository or DynamicMaterialRepository(session)
        self.property_service = property_service
        self.material_type_service = material_type_service
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    def get_materials(
            self,
            skip: int = 0,
            limit: int = 100,
            material_type_id: Optional[int] = None,
            search: Optional[str] = None,
            status: Optional[str] = None,
            tags: Optional[List[str]] = None,
            **filters
    ) -> Tuple[List[DynamicMaterial], int]:
        """
        Get materials with filtering and pagination.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            material_type_id: Optional filter by material type
            search: Optional search string for names and descriptions
            status: Optional filter by status
            tags: Optional list of tag names to filter by
            **filters: Additional filters

        Returns:
            Tuple of (list of materials, total count)
        """
        return self.repository.list_with_properties(
            skip=skip,
            limit=limit,
            material_type_id=material_type_id,
            search=search,
            status=status,
            tags=tags,
            **filters
        )

    def get_material(self, material_id: int) -> Optional[DynamicMaterial]:
        """
        Get a material by ID.

        Args:
            material_id: ID of the material

        Returns:
            Material if found, None otherwise
        """
        return self.repository.get_by_id_with_properties(material_id)

    def get_material_by_sku(self, sku: str) -> Optional[DynamicMaterial]:
        """
        Get a material by SKU.

        Args:
            sku: SKU of the material

        Returns:
            Material if found, None otherwise
        """
        materials = self.repository.list(sku=sku)
        return materials[0] if materials else None

    def create_material(self, data: Dict[str, Any], created_by: Optional[int] = None) -> DynamicMaterial:
        """
        Create a new material with property values.

        Args:
            data: Material data including property values
            created_by: Optional ID of user creating the material

        Returns:
            Created material

        Raises:
            ValidationException: If material data is invalid
            EntityNotFoundException: If material type not found
        """
        # Add created_by if provided
        if created_by:
            data["created_by"] = created_by

        # Validate required fields
        required_fields = ["material_type_id", "name", "unit"]
        for field in required_fields:
            if not data.get(field):
                raise ValidationException(f"Field '{field}' is required")

        # Get material type to validate property values
        material_type_id = data.get("material_type_id")
        material_type = None
        if self.material_type_service:
            material_type = self.material_type_service.get_material_type(material_type_id)
        else:
            # Fallback to direct query
            material_type = self.session.query(MaterialType).get(material_type_id)

        if not material_type:
            raise EntityNotFoundException(f"Material type with ID {material_type_id} not found")

        # Set default status if not provided
        if not data.get("status"):
            data["status"] = "in_stock"

        # Set default quantity if not provided
        if "quantity" not in data:
            data["quantity"] = 0

        # Set default reorder_point if not provided
        if "reorder_point" not in data:
            data["reorder_point"] = 0

        # Validate and format property values
        property_values = data.get("property_values", [])
        if self.property_service:
            # Get type properties
            type_properties = []
            for mat_type_prop in material_type.properties:
                prop_def = self.property_service.get_property_definition(mat_type_prop.property_id)
                if prop_def:
                    type_properties.append((mat_type_prop, prop_def))

            # Check required properties
            for type_prop, prop_def in type_properties:
                if type_prop.is_required and not any(pv.get("property_id") == prop_def.id for pv in property_values):
                    raise ValidationException(f"Required property '{prop_def.name}' missing")

            # Validate property values
            validated_properties = []
            for property_value in property_values:
                property_id = property_value.get("property_id")

                # Skip if property is not part of this material type
                if not any(tp.property_id == property_id for tp, _ in type_properties):
                    continue

                value = property_value.get("value")

                # Find property definition
                prop_def = next((pd for _, pd in type_properties if pd.id == property_id), None)
                if not prop_def:
                    continue

                # Validate value
                if not self.property_service.validate_property_value(property_id, value):
                    raise ValidationException(f"Invalid value for property '{prop_def.name}'")

                validated_properties.append({
                    "property_id": property_id,
                    "value": value
                })

            # Update property values with validated ones
            data["property_values"] = validated_properties

        with self.transaction():
            # Create material with property values
            material = self.repository.create_with_properties(data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("materials:*")
                if material_type_id:
                    self.cache_service.invalidate_pattern(f"materials:type:{material_type_id}:*")

            return material

    def update_material(self, id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Optional[
        DynamicMaterial]:
        """
        Update an existing material.

        Args:
            id: ID of the material to update
            data: Updated material data
            user_id: Optional ID of the user performing the update

        Returns:
            Updated material if found, None otherwise

        Raises:
            ValidationException: If material data is invalid
        """
        with self.transaction():
            # Get existing material
            material = self.repository.get_by_id_with_properties(id)
            if not material:
                return None

            # Cannot change material type
            if "material_type_id" in data and data["material_type_id"] != material.material_type_id:
                raise ValidationException("Cannot change material type")

            # Validate property values if provided
            if "property_values" in data and self.property_service:
                property_values = data["property_values"]

                # Get material type properties
                material_type = material.material_type
                type_properties = []
                for mat_type_prop in material_type.properties:
                    prop_def = self.property_service.get_property_definition(mat_type_prop.property_id)
                    if prop_def:
                        type_properties.append((mat_type_prop, prop_def))

                # Check required properties
                for type_prop, prop_def in type_properties:
                    if type_prop.is_required and not any(
                            pv.get("property_id") == prop_def.id for pv in property_values):
                        # Check if there's an existing value
                        existing_value = next((pv for pv in material.property_values if pv.property_id == prop_def.id),
                                              None)
                        if not existing_value:
                            raise ValidationException(f"Required property '{prop_def.name}' missing")

                # Validate property values
                validated_properties = []
                for property_value in property_values:
                    property_id = property_value.get("property_id")

                    # Skip if property is not part of this material type
                    if not any(tp.property_id == property_id for tp, _ in type_properties):
                        continue

                    value = property_value.get("value")

                    # Find property definition
                    prop_def = next((pd for _, pd in type_properties if pd.id == property_id), None)
                    if not prop_def:
                        continue

                    # Validate value
                    if not self.property_service.validate_property_value(property_id, value):
                        raise ValidationException(f"Invalid value for property '{prop_def.name}'")

                    validated_properties.append({
                        "property_id": property_id,
                        "value": value
                    })

                # Update property values with validated ones
                data["property_values"] = validated_properties

            # Update material
            updated_material = self.repository.update_with_properties(id, data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"materials:{id}")
                self.cache_service.invalidate_pattern("materials:*")
                self.cache_service.invalidate_pattern(f"materials:type:{material.material_type_id}:*")

            return updated_material

    def delete_material(self, id: int) -> bool:
        """
        Delete a material.

        Args:
            id: ID of the material to delete

        Returns:
            True if deleted, False otherwise
        """
        with self.transaction():
            # Get material
            material = self.repository.get_by_id(id)
            if not material:
                return False

            # Get material type ID for cache invalidation
            material_type_id = material.material_type_id

            # Delete material
            result = self.repository.delete(id)

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate(f"materials:{id}")
                self.cache_service.invalidate_pattern("materials:*")
                self.cache_service.invalidate_pattern(f"materials:type:{material_type_id}:*")

            return result

    def adjust_stock(
            self,
            material_id: int,
            quantity_change: float,
            notes: Optional[str] = None,
            user_id: Optional[int] = None
    ) -> Optional[DynamicMaterial]:
        """
        Adjust the stock quantity of a material.

        Args:
            material_id: ID of the material
            quantity_change: Quantity to add (positive) or remove (negative)
            notes: Optional notes for this adjustment
            user_id: Optional ID of the user making the adjustment

        Returns:
            Updated material

        Raises:
            EntityNotFoundException: If material not found
            InsufficientInventoryException: If adjustment would result in negative inventory
        """
        with self.transaction():
            # Get material
            material = self.repository.get_by_id(material_id)
            if not material:
                raise EntityNotFoundException(f"Material with ID {material_id} not found")

            # Store previous quantity for event
            previous_quantity = material.quantity

            # Calculate new quantity
            new_quantity = previous_quantity + quantity_change

            # Check for negative inventory
            if new_quantity < 0:
                raise InsufficientInventoryException(
                    material_id,
                    abs(quantity_change),
                    previous_quantity,
                    f"Cannot remove {abs(quantity_change)} units when only {previous_quantity} are available"
                )

            # Adjust stock
            material = self.repository.adjust_stock(material_id, quantity_change)

            # Record inventory transaction (if we want to keep a transaction log)
            # self._record_inventory_transaction(
            #     material_id=material_id,
            #     quantity_change=quantity_change,
            #     reason=notes or "Manual inventory adjustment",
            #     user_id=user_id
            # )

            # Emit event if event bus is available
            if self.event_bus:
                self.event_bus.publish({
                    "type": "material.stock_changed",
                    "material_id": material_id,
                    "previous_quantity": previous_quantity,
                    "new_quantity": new_quantity,
                    "change": quantity_change,
                    "reason": notes or "Manual inventory adjustment",
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                })

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"materials:{material_id}")
                self.cache_service.invalidate_pattern("materials:*")
                self.cache_service.invalidate_pattern(f"materials:type:{material.material_type_id}:*")

            return material

    def get_low_stock_materials(self, skip: int = 0, limit: int = 100) -> List[DynamicMaterial]:
        """
        Get materials that are low in stock (below reorder point).

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of materials below their reorder point
        """
        return self.repository.get_low_stock_materials(skip=skip, limit=limit)

    def get_out_of_stock_materials(self, skip: int = 0, limit: int = 100) -> List[DynamicMaterial]:
        """
        Get materials that are out of stock.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of out-of-stock materials
        """
        return self.repository.get_out_of_stock_materials(skip=skip, limit=limit)

    def search_materials(self, query: str, skip: int = 0, limit: int = 100) -> List[DynamicMaterial]:
        """
        Search for materials by name, description, or SKU.

        Args:
            query: Search query string
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of matching materials
        """
        return self.repository.search_materials(query, skip=skip, limit=limit)

    def attach_media(self, material_id: int, media_id: str, is_primary: bool = False) -> Any:
        """
        Attach media to a material.

        Args:
            material_id: ID of the material
            media_id: ID of the media asset
            is_primary: Whether this is the primary media

        Returns:
            Association object if successful

        Raises:
            EntityNotFoundException: If material or media not found
        """
        with self.transaction():
            # Get material
            material = self.repository.get_by_id(material_id)
            if not material:
                raise EntityNotFoundException(f"Material with ID {material_id} not found")

            # Get media asset
            from app.db.models.media_asset import MediaAsset
            media = self.session.query(MediaAsset).get(media_id)
            if not media:
                raise EntityNotFoundException(f"Media asset with ID {media_id} not found")

            # Check if association already exists
            from app.db.models.entity_media import EntityMedia
            existing = self.session.query(EntityMedia).filter(
                EntityMedia.entity_type == "material",
                EntityMedia.entity_id == str(material_id),
                EntityMedia.media_asset_id == media_id
            ).first()

            if existing:
                # Update existing
                if is_primary:
                    # Clear any existing primary
                    self.session.query(EntityMedia).filter(
                        EntityMedia.entity_type == "material",
                        EntityMedia.entity_id == str(material_id),
                        EntityMedia.media_type == "thumbnail"
                    ).update({"media_type": "gallery"})

                    # Set this as primary
                    existing.media_type = "thumbnail"

                self.session.commit()
                return existing
            else:
                # Create new association
                display_order = self.session.query(EntityMedia).filter(
                    EntityMedia.entity_type == "material",
                    EntityMedia.entity_id == str(material_id)
                ).count()

                # If this is primary, clear any existing primary
                if is_primary:
                    self.session.query(EntityMedia).filter(
                        EntityMedia.entity_type == "material",
                        EntityMedia.entity_id == str(material_id),
                        EntityMedia.media_type == "thumbnail"
                    ).update({"media_type": "gallery"})

                # Create association
                association = EntityMedia(
                    id=str(uuid.uuid4()),
                    entity_type="material",
                    entity_id=str(material_id),
                    media_asset_id=media_id,
                    media_type="thumbnail" if is_primary else "gallery",
                    display_order=display_order
                )

                self.session.add(association)
                self.session.commit()

                # Set thumbnail on the material if this is the primary
                if is_primary:
                    material.thumbnail = media.url
                    self.session.commit()

                # Invalidate cache if needed
                if self.cache_service:
                    self.cache_service.invalidate(f"materials:{material_id}")

                return association

    def add_tags(self, material_id: int, tags: List[str]) -> List[Any]:
        """
        Add tags to a material.

        Args:
            material_id: ID of the material
            tags: List of tag names

        Returns:
            List of tags that were added

        Raises:
            EntityNotFoundException: If material not found
        """
        with self.transaction():
            # Get material
            material = self.repository.get_by_id(material_id)
            if not material:
                raise EntityNotFoundException(f"Material with ID {material_id} not found")

            added_tags = []
            from app.db.models.tag import Tag

            for tag_name in tags:
                # Get or create tag
                tag = self.session.query(Tag).filter(Tag.name == tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    self.session.add(tag)
                    self.session.flush()

                # Check if material already has this tag
                if tag not in material.tags:
                    material.tags.append(tag)
                    added_tags.append(tag)

            self.session.commit()

            # Invalidate cache if needed
            if self.cache_service and added_tags:
                self.cache_service.invalidate(f"materials:{material_id}")

            return added_tags

    def remove_tag(self, material_id: int, tag_name: str) -> bool:
        """
        Remove a tag from a material.

        Args:
            material_id: ID of the material
            tag_name: Name of the tag to remove

        Returns:
            True if tag was removed, False otherwise

        Raises:
            EntityNotFoundException: If material not found
        """
        with self.transaction():
            # Get material
            material = self.repository.get_by_id(material_id)
            if not material:
                raise EntityNotFoundException(f"Material with ID {material_id} not found")

            # Find tag
            from app.db.models.tag import Tag
            tag = self.session.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                return False

            # Check if material has this tag
            if tag in material.tags:
                material.tags.remove(tag)
                self.session.commit()

                # Invalidate cache if needed
                if self.cache_service:
                    self.cache_service.invalidate(f"materials:{material_id}")

                return True

            return False