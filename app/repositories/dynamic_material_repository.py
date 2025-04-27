# app/repositories/dynamic_material_repository.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func
from datetime import datetime

from app.db.models.dynamic_material import (
    DynamicMaterial, MaterialPropertyValue, PropertyDefinition,
    MaterialTypeProperty, MaterialType
)
from app.repositories.base_repository import BaseRepository


class DynamicMaterialRepository(BaseRepository[DynamicMaterial]):
    """
    Repository for DynamicMaterial entity operations.
    """

    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = DynamicMaterial

    def list_with_properties(
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
        List materials with their properties, with pagination and filtering.
        Returns both the list of materials and the total count.
        """
        query = self.session.query(self.model)

        # Apply material type filter
        if material_type_id:
            query = query.filter(self.model.material_type_id == material_type_id)

        # Apply search filter
        if search:
            query = query.filter(or_(
                self.model.name.ilike(f"%{search}%"),
                self.model.description.ilike(f"%{search}%"),
                self.model.supplier.ilike(f"%{search}%"),
                self.model.sku.ilike(f"%{search}%")
            ))

        # Apply status filter
        if status:
            query = query.filter(self.model.status == status)

        # Apply tag filter
        if tags and len(tags) > 0:
            # This requires the Tag model to be defined and joined
            from app.db.models.tag import Tag
            for tag_name in tags:
                tag_subquery = self.session.query(Tag.id).filter(Tag.name == tag_name).scalar_subquery()
                query = query.filter(
                    self.model.id.in_(
                        self.session.query(DynamicMaterial.id)
                        .join("tags")
                        .filter(Tag.id == tag_subquery)
                        .scalar_subquery()
                    )
                )

        # Apply other filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        # Get total count before pagination
        total_count = query.count()

        # Apply eager loading of related entities
        query = query.options(
            joinedload(self.model.material_type),
            joinedload(self.model.property_values).joinedload(MaterialPropertyValue.property)
        )

        # Apply pagination
        query = query.order_by(self.model.name).offset(skip).limit(limit)

        # Execute query
        result = query.all()

        return [self._decrypt_sensitive_fields(item) for item in result], total_count

    def get_by_id_with_properties(self, id: int) -> Optional[DynamicMaterial]:
        """
        Get a material by ID with eager loading of related properties.
        """
        item = self.session.query(self.model).filter(
            self.model.id == id
        ).options(
            joinedload(self.model.material_type),
            joinedload(self.model.property_values).joinedload(MaterialPropertyValue.property),
            joinedload(self.model.tags),
            joinedload(self.model.media)
        ).first()

        return self._decrypt_sensitive_fields(item) if item else None

    def create_with_properties(self, data: Dict[str, Any]) -> DynamicMaterial:
        """
        Create a material with its property values.
        """
        # Extract nested data
        property_values_data = data.pop('property_values', [])
        tag_ids = data.pop('tag_ids', [])
        media_ids = data.pop('media_ids', [])

        # Create the material
        material = self.model(**data)
        self.session.add(material)
        self.session.flush()  # Get the ID

        # Create property values
        for prop_value in property_values_data:
            property_id = prop_value.get('property_id')
            if not property_id:
                continue

            # Get property definition to determine data type
            property_def = self.session.query(PropertyDefinition).get(property_id)
            if not property_def:
                continue

            # Create property value with the appropriate value field
            value = prop_value.get('value')
            property_value = MaterialPropertyValue(
                material_id=material.id,
                property_id=property_id
            )

            # Set the value in the appropriate field based on data type
            if property_def.data_type == 'string':
                property_value.value_string = value
            elif property_def.data_type == 'number':
                property_value.value_number = value
            elif property_def.data_type == 'boolean':
                property_value.value_boolean = value
            elif property_def.data_type == 'date':
                property_value.value_date = value
            elif property_def.data_type == 'enum':
                property_value.value_enum_id = value
            elif property_def.data_type == 'file':
                property_value.value_file_id = value
            elif property_def.data_type == 'reference':
                property_value.value_reference_id = value

            self.session.add(property_value)

        # Add tags if provided
        if tag_ids:
            from app.db.models.tag import Tag
            for tag_id in tag_ids:
                tag = self.session.query(Tag).get(tag_id)
                if tag:
                    material.tags.append(tag)

        # Add media if provided
        if media_ids:
            from app.db.models.media_asset import MediaAsset
            for media_id in media_ids:
                media = self.session.query(MediaAsset).get(media_id)
                if media:
                    material.media.append(media)

        self.session.commit()
        self.session.refresh(material)

        return material

    def update_with_properties(self, id: int, data: Dict[str, Any]) -> Optional[DynamicMaterial]:
        """
        Update a material with its property values.
        """
        material = self.get_by_id(id)
        if not material:
            return None

        # Extract nested data
        property_values_data = data.pop('property_values', None)
        tag_ids = data.pop('tag_ids', None)
        media_ids = data.pop('media_ids', None)

        # Update base fields
        for key, value in data.items():
            if hasattr(material, key):
                setattr(material, key, value)

        # Update property values if provided
        if property_values_data is not None:
            # Get existing property values
            existing_values = {
                pv.property_id: pv for pv in material.property_values
            }

            # Process each property value
            for prop_value in property_values_data:
                property_id = prop_value.get('property_id')
                if not property_id:
                    continue

                # Get property definition to determine data type
                property_def = self.session.query(PropertyDefinition).get(property_id)
                if not property_def:
                    continue

                value = prop_value.get('value')
                if property_id in existing_values:
                    # Update existing property value
                    property_value = existing_values[property_id]

                    # Reset all value fields
                    property_value.value_string = None
                    property_value.value_number = None
                    property_value.value_boolean = None
                    property_value.value_date = None
                    property_value.value_enum_id = None
                    property_value.value_file_id = None
                    property_value.value_reference_id = None

                    # Set the appropriate field
                    if property_def.data_type == 'string':
                        property_value.value_string = value
                    elif property_def.data_type == 'number':
                        property_value.value_number = value
                    elif property_def.data_type == 'boolean':
                        property_value.value_boolean = value
                    elif property_def.data_type == 'date':
                        property_value.value_date = value
                    elif property_def.data_type == 'enum':
                        property_value.value_enum_id = value
                    elif property_def.data_type == 'file':
                        property_value.value_file_id = value
                    elif property_def.data_type == 'reference':
                        property_value.value_reference_id = value
                else:
                    # Create new property value
                    property_value = MaterialPropertyValue(
                        material_id=material.id,
                        property_id=property_id
                    )

                    # Set the appropriate field
                    if property_def.data_type == 'string':
                        property_value.value_string = value
                    elif property_def.data_type == 'number':
                        property_value.value_number = value
                    elif property_def.data_type == 'boolean':
                        property_value.value_boolean = value
                    elif property_def.data_type == 'date':
                        property_value.value_date = value
                    elif property_def.data_type == 'enum':
                        property_value.value_enum_id = value
                    elif property_def.data_type == 'file':
                        property_value.value_file_id = value
                    elif property_def.data_type == 'reference':
                        property_value.value_reference_id = value

                    self.session.add(property_value)

        # Update tags if provided
        if tag_ids is not None:
            # Clear existing tags
            material.tags = []

            # Add new tags
            if tag_ids:
                from app.db.models.tag import Tag
                for tag_id in tag_ids:
                    tag = self.session.query(Tag).get(tag_id)
                    if tag:
                        material.tags.append(tag)

        # Update media if provided
        if media_ids is not None:
            # Clear existing media
            material.media = []

            # Add new media
            if media_ids:
                from app.db.models.media_asset import MediaAsset
                for media_id in media_ids:
                    media = self.session.query(MediaAsset).get(media_id)
                    if media:
                        material.media.append(media)

        self.session.commit()
        self.session.refresh(material)

        return material

    def get_low_stock_materials(self, skip: int = 0, limit: int = 100) -> List[DynamicMaterial]:
        """
        Get materials that are low in stock (below reorder point).
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.quantity <= self.model.reorder_point,
                self.model.quantity > 0,
                self.model.status != "discontinued"
            )
        )

        # Apply eager loading
        query = query.options(
            joinedload(self.model.material_type),
            joinedload(self.model.property_values).joinedload(MaterialPropertyValue.property)
        )

        # Apply pagination
        query = query.order_by(self.model.name).offset(skip).limit(limit)

        # Execute query
        result = query.all()

        return [self._decrypt_sensitive_fields(item) for item in result]

    def get_out_of_stock_materials(self, skip: int = 0, limit: int = 100) -> List[DynamicMaterial]:
        """
        Get materials that are out of stock.
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.quantity <= 0,
                self.model.status != "discontinued"
            )
        )

        # Apply eager loading
        query = query.options(
            joinedload(self.model.material_type),
            joinedload(self.model.property_values).joinedload(MaterialPropertyValue.property)
        )

        # Apply pagination
        query = query.order_by(self.model.name).offset(skip).limit(limit)

        # Execute query
        result = query.all()

        return [self._decrypt_sensitive_fields(item) for item in result]

    def search_materials(self, query_text: str, skip: int = 0, limit: int = 100) -> List[DynamicMaterial]:
        """
        Search for materials by name, description, or SKU.
        """
        query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query_text}%"),
                self.model.description.ilike(f"%{query_text}%"),
                self.model.sku.ilike(f"%{query_text}%"),
                self.model.supplier.ilike(f"%{query_text}%")
            )
        )

        # Apply eager loading
        query = query.options(
            joinedload(self.model.material_type),
            joinedload(self.model.property_values).joinedload(MaterialPropertyValue.property)
        )

        # Apply pagination
        query = query.order_by(self.model.name).offset(skip).limit(limit)

        # Execute query
        result = query.all()

        return [self._decrypt_sensitive_fields(item) for item in result]

    def adjust_stock(self, material_id: int, quantity_change: float) -> Optional[DynamicMaterial]:
        """
        Adjust the stock quantity of a material.
        """
        material = self.get_by_id(material_id)
        if not material:
            return None

        # Update quantity
        new_quantity = material.quantity + quantity_change
        material.quantity = max(0, new_quantity)  # Prevent negative quantities

        # Update status based on quantity
        if new_quantity <= 0:
            material.status = "out_of_stock"
        elif new_quantity <= material.reorder_point:
            material.status = "low_stock"
        else:
            material.status = "in_stock"

        self.session.commit()
        self.session.refresh(material)

        return material