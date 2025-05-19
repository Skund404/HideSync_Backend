# app/repositories/preset_repository.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.repositories.base_repository import BaseRepository
from app.db.models.preset import MaterialPreset, PresetApplication, PresetApplicationError


class PresetRepository(BaseRepository[MaterialPreset]):
    """Repository for material presets."""

    def __init__(self, session: Session):
        super().__init__(MaterialPreset, session)

    def list_presets(
            self,
            skip: int = 0,
            limit: int = 100,
            search: Optional[str] = None,
            user_id: Optional[int] = None,
            is_public: Optional[bool] = None,
            tags: Optional[List[str]] = None,
    ) -> Tuple[List[MaterialPreset], int]:
        """
        List presets with filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Optional search string for name and description
            user_id: Optional filter by creator
            is_public: Optional filter by public status
            tags: Optional filter by tags

        Returns:
            Tuple of (list of presets, total count)
        """
        query = self.session.query(self.model)

        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    self.model.name.ilike(search_term),
                    self.model.description.ilike(search_term),
                    self.model.author.ilike(search_term)
                )
            )

        if user_id is not None:
            query = query.filter(self.model.created_by == user_id)

        if is_public is not None:
            query = query.filter(self.model.is_public == is_public)

        if tags:
            # Filter by tags in the config JSON
            for tag in tags:
                # This is a simplified approach - in a real implementation, 
                # you might need a more sophisticated JSON querying mechanism
                # depending on your database
                query = query.filter(self.model._config.like(f'%"{tag}"%'))

        # Get total count before pagination
        total = query.count()

        # Apply pagination
        query = query.order_by(self.model.created_at.desc())
        query = query.offset(skip).limit(limit)

        # Execute query
        presets = query.all()

        return presets, total

    def create_preset_application(
            self,
            preset_id: int,
            user_id: int,
            options_used: Dict[str, Any],
            stats: Dict[str, int]
    ) -> PresetApplication:
        """
        Create a record of a preset application.

        Args:
            preset_id: ID of the preset
            user_id: ID of the user
            options_used: Options used for application
            stats: Statistics of created/updated entities

        Returns:
            Created application record
        """
        application = PresetApplication(
            preset_id=preset_id,
            user_id=user_id,
            options_used=options_used,
            created_property_definitions=stats.get("created_property_definitions", 0),
            updated_property_definitions=stats.get("updated_property_definitions", 0),
            created_material_types=stats.get("created_material_types", 0),
            updated_material_types=stats.get("updated_material_types", 0),
            created_materials=stats.get("created_materials", 0),
            error_count=stats.get("error_count", 0)
        )

        self.session.add(application)
        self.session.flush()

        return application

    def add_application_error(
            self,
            application_id: int,
            error_type: str,
            error_message: str,
            entity_type: Optional[str] = None,
            entity_name: Optional[str] = None
    ) -> PresetApplicationError:
        """
        Add an error record for a preset application.

        Args:
            application_id: ID of the application
            error_type: Type of error
            error_message: Error message
            entity_type: Optional type of entity that caused the error
            entity_name: Optional name of entity that caused the error

        Returns:
            Created error record
        """
        error = PresetApplicationError(
            application_id=application_id,
            error_type=error_type,
            error_message=error_message,
            entity_type=entity_type,
            entity_name=entity_name
        )

        self.session.add(error)
        self.session.flush()

        return error

    def get_application_errors(self, application_id: int) -> List[PresetApplicationError]:
        """
        Get errors for a preset application.

        Args:
            application_id: ID of the application

        Returns:
            List of error records
        """
        return self.session.query(PresetApplicationError).filter(
            PresetApplicationError.application_id == application_id
        ).all()