# File: app/repositories/component_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime

from app.db.models.component import Component, ComponentMaterial
from app.db.models.enums import ComponentType
from app.repositories.base_repository import BaseRepository


class ComponentRepository(BaseRepository[Component]):
    """
    Repository for Component entity operations.

    Handles data access for project components, including their
    specifications, relationships with patterns, and material requirements.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ComponentRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Component

    def get_components_by_pattern(
        self, pattern_id: int, skip: int = 0, limit: int = 100
    ) -> List[Component]:
        """
        Get components associated with a specific pattern.

        Args:
            pattern_id (int): ID of the pattern
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Component]: List of components for the pattern
        """
        query = self.session.query(self.model).filter(
            self.model.patternId == pattern_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_components_by_type(
        self, component_type: ComponentType, skip: int = 0, limit: int = 100
    ) -> List[Component]:
        """
        Get components by type.

        Args:
            component_type (ComponentType): The component type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Component]: List of components of the specified type
        """
        query = self.session.query(self.model).filter(
            self.model.componentType == component_type
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_components_by_author(
        self, author_name: str, skip: int = 0, limit: int = 100
    ) -> List[Component]:
        """
        Get components by author.

        Args:
            author_name (str): Name of the component author
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Component]: List of components by the specified author
        """
        query = self.session.query(self.model).filter(
            self.model.authorName == author_name
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_optional_components(
        self, pattern_id: int, skip: int = 0, limit: int = 100
    ) -> List[Component]:
        """
        Get optional components for a pattern.

        Args:
            pattern_id (int): ID of the pattern
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Component]: List of optional components for the pattern
        """
        query = self.session.query(self.model).filter(
            and_(self.model.patternId == pattern_id, self.model.isOptional == True)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def search_components(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[Component]:
        """
        Search for components by name or description.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Component]: List of matching components
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_component_with_materials(
        self, component_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a component with its required materials.

        Args:
            component_id (int): ID of the component

        Returns:
            Optional[Dict[str, Any]]: Dictionary with component and materials if found, None otherwise
        """
        component = self.get_by_id(component_id)
        if not component:
            return None

        # Get component materials
        materials = (
            self.session.query(ComponentMaterial)
            .filter(ComponentMaterial.component_id == component_id)
            .all()
        )

        return {
            "component": self._decrypt_sensitive_fields(component),
            "materials": materials,
        }

    def update_component_position(
        self, component_id: int, position: Dict[str, Any], rotation: int
    ) -> Optional[Component]:
        """
        Update a component's position and rotation.

        Args:
            component_id (int): ID of the component
            position (Dict[str, Any]): New position data
            rotation (int): New rotation value

        Returns:
            Optional[Component]: Updated component if found, None otherwise
        """
        component = self.get_by_id(component_id)
        if not component:
            return None

        component.position = position
        component.rotation = rotation
        component.modifiedAt = datetime.now()

        self.session.commit()
        self.session.refresh(component)
        return self._decrypt_sensitive_fields(component)


class ComponentMaterialRepository(BaseRepository[ComponentMaterial]):
    """
    Repository for ComponentMaterial entity operations.

    Manages the relationships between components and their required materials,
    including quantities, alternatives, and material specifications.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ComponentMaterialRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = ComponentMaterial

    def get_materials_by_component(self, component_id: int) -> List[ComponentMaterial]:
        """
        Get materials required for a specific component.

        Args:
            component_id (int): ID of the component

        Returns:
            List[ComponentMaterial]: List of materials required for the component
        """
        query = self.session.query(self.model).filter(
            self.model.component_id == component_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_components_using_material(
        self, material_id: int
    ) -> List[ComponentMaterial]:
        """
        Get components that use a specific material.

        Args:
            material_id (int): ID of the material

        Returns:
            List[ComponentMaterial]: List of component-material relationships using the material
        """
        query = self.session.query(self.model).filter(
            self.model.material_id == material_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_required_materials(self) -> List[ComponentMaterial]:
        """
        Get all required material relationships.

        Returns:
            List[ComponentMaterial]: List of required component-material relationships
        """
        query = self.session.query(self.model).filter(self.model.isRequired == True)

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_material_quantity(
        self, id: int, quantity: float
    ) -> Optional[ComponentMaterial]:
        """
        Update the quantity of material required for a component.

        Args:
            id (int): ID of the component-material relationship
            quantity (float): New quantity value

        Returns:
            Optional[ComponentMaterial]: Updated relationship if found, None otherwise
        """
        component_material = self.get_by_id(id)
        if not component_material:
            return None

        component_material.quantity = quantity

        self.session.commit()
        self.session.refresh(component_material)
        return self._decrypt_sensitive_fields(component_material)

    def update_alternative_materials(
        self, id: int, alternative_material_ids: List[int]
    ) -> Optional[ComponentMaterial]:
        """
        Update the alternative materials for a component-material relationship.

        Args:
            id (int): ID of the component-material relationship
            alternative_material_ids (List[int]): List of alternative material IDs

        Returns:
            Optional[ComponentMaterial]: Updated relationship if found, None otherwise
        """
        component_material = self.get_by_id(id)
        if not component_material:
            return None

        component_material.alternativeMaterialIds = alternative_material_ids

        self.session.commit()
        self.session.refresh(component_material)
        return self._decrypt_sensitive_fields(component_material)
