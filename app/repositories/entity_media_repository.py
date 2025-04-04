# File: app/repositories/entity_media_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import uuid
import logging
from datetime import datetime

from app.repositories.base_repository import BaseRepository
from app.db.models.entity_media import EntityMedia

logger = logging.getLogger(__name__)


class EntityMediaRepository(BaseRepository[EntityMedia]):
    """
    Repository for EntityMedia operations in the HideSync system.

    This repository manages associations between media assets and various entity types.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the EntityMediaRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = EntityMedia

    def find_by_media_asset_id(self, media_asset_id: str) -> List[EntityMedia]:
        """
        Find all entity media records associated with a specific media asset.

        Args:
            media_asset_id: The ID of the media asset

        Returns:
            List[EntityMedia]: List of entity media records
        """
        return self.session.query(self.model).filter(self.model.media_asset_id == media_asset_id).all()

    def debug_entity_media(self) -> None:
        """Debug function to examine existing entity media records"""
        from sqlalchemy import text

        try:
            # Query to inspect the first record in entity_media table
            query = text("SELECT * FROM entity_media LIMIT 1")
            result = self.session.execute(query).fetchone()

            if result:
                # Log column names and values
                column_names = result.keys()
                column_values = result

                debug_info = "Entity Media structure:\n"
                for i, col in enumerate(column_names):
                    value = column_values[i]
                    value_type = type(value).__name__
                    debug_info += f"  {col}: {value} (Type: {value_type})\n"

                logger.info(debug_info)
            else:
                logger.info("No entity_media records found for inspection")
        except Exception as e:
            logger.error(f"Error in debug_entity_media: {str(e)}")

    def create_entity_media_direct(
            self,
            entity_type: str,
            entity_id: str,
            media_asset_id: str,
            media_type: str = "thumbnail",
            display_order: int = 0,
            caption: Optional[str] = None
    ) -> Optional[EntityMedia]:
        """
        Create entity media using the most direct approach possible.
        First inspects existing records to match structure exactly.
        """
        from sqlalchemy import text
        import uuid
        from datetime import datetime

        # First, debug existing records to understand structure
        self.debug_entity_media()

        try:
            # For supplier entities, try both approaches based on what we've seen
            if entity_type == 'supplier':
                # Try numeric first for suppliers
                try:
                    # Convert to int if it's a UUID format or string digit
                    numeric_id = None

                    if entity_id.startswith('00000000-0000-0000-0000-'):
                        numeric_part = entity_id.split('-')[-1].lstrip('0')
                        if numeric_part:
                            try:
                                numeric_id = int(numeric_part)
                                logger.info(f"Converted supplier UUID to numeric ID: {numeric_id}")
                            except ValueError:
                                pass
                    elif entity_id.isdigit():
                        numeric_id = int(entity_id)
                        logger.info(f"Using supplier numeric ID directly: {numeric_id}")

                    if numeric_id is not None:
                        # Try inserting with numeric entity_id
                        return self._try_create_entity_media(
                            entity_type=entity_type,
                            entity_id=numeric_id,  # Use numeric ID
                            media_asset_id=media_asset_id,
                            media_type=media_type,
                            display_order=display_order,
                            caption=caption
                        )
                except Exception as e:
                    logger.warning(f"Numeric ID approach failed: {str(e)}")
                    # Continue to string approach

            # Default approach with string entity_id
            return self._try_create_entity_media(
                entity_type=entity_type,
                entity_id=entity_id,  # Use string ID
                media_asset_id=media_asset_id,
                media_type=media_type,
                display_order=display_order,
                caption=caption
            )
        except Exception as e:
            logger.error(f"Error in create_entity_media_direct: {str(e)}", exc_info=True)
            self.session.rollback()
            raise

    def _try_create_entity_media(
            self,
            entity_type: str,
            entity_id: Any,  # Could be string or int
            media_asset_id: str,
            media_type: str,
            display_order: int,
            caption: Optional[str]
    ) -> EntityMedia:
        """
        Internal helper to try creating entity media with different approaches.
        """
        import uuid
        from datetime import datetime

        # Generate ID and timestamp
        new_id = str(uuid.uuid4())
        now = datetime.now()

        # Try using a completely direct approach
        try:
            query = """
            INSERT INTO entity_media (
                id, 
                media_asset_id, 
                entity_type, 
                entity_id, 
                media_type, 
                display_order, 
                caption, 
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = [
                new_id,
                media_asset_id,
                entity_type,
                entity_id,
                media_type,
                display_order,
                caption or "",
                now
            ]

            # Use raw database cursor to bypass SQLAlchemy
            connection = self.session.connection()
            raw_conn = connection.connection
            cursor = raw_conn.cursor()
            cursor.execute(query, params)
            raw_conn.commit()

            logger.info(f"Successfully created entity media with direct cursor: {new_id}")

            # Fetch the newly created entity
            created_entity = self.get_by_id(new_id)
            if not created_entity:
                logger.warning(f"Created entity with ID {new_id}, but couldn't retrieve it.")
                # Create a fake entity for return value
                from app.db.models.entity_media import EntityMedia
                entity = EntityMedia()
                entity.id = new_id
                entity.media_asset_id = media_asset_id
                entity.entity_type = entity_type
                entity.entity_id = entity_id
                entity.media_type = media_type
                entity.display_order = display_order
                entity.caption = caption
                entity.created_at = now
                return entity

            return created_entity

        except Exception as e:
            logger.error(f"Direct cursor insert failed: {str(e)}")
            # Continue with SQLAlchemy approach

            try:
                # Use SQLAlchemy text()
                from sqlalchemy import text

                # Create SQL statement with named parameters
                sql = text("""
                INSERT INTO entity_media (
                    id, 
                    media_asset_id, 
                    entity_type, 
                    entity_id, 
                    media_type, 
                    display_order, 
                    caption, 
                    created_at
                ) VALUES (
                    :id, 
                    :media_asset_id, 
                    :entity_type, 
                    :entity_id, 
                    :media_type, 
                    :display_order, 
                    :caption, 
                    :created_at
                )
                """)

                # Execute with parameters
                self.session.execute(sql, {
                    "id": new_id,
                    "media_asset_id": media_asset_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "media_type": media_type,
                    "display_order": display_order,
                    "caption": caption or "",
                    "created_at": now
                })

                self.session.commit()
                logger.info(f"Successfully created entity media with SQLAlchemy text(): {new_id}")

                return self.get_by_id(new_id)

            except Exception as e2:
                logger.error(f"SQLAlchemy text() insert failed: {str(e2)}")
                self.session.rollback()

                # Try with model instance
                try:
                    from app.db.models.entity_media import EntityMedia

                    entity_media = EntityMedia()
                    entity_media.id = new_id
                    entity_media.media_asset_id = media_asset_id
                    entity_media.entity_type = entity_type
                    entity_media.entity_id = entity_id
                    entity_media.media_type = media_type
                    entity_media.display_order = display_order
                    entity_media.caption = caption or ""
                    entity_media.created_at = now

                    self.session.add(entity_media)
                    self.session.commit()

                    logger.info(f"Successfully created entity media with model instance: {new_id}")
                    return entity_media

                except Exception as e3:
                    logger.error(f"Model instance insert failed: {str(e3)}")
                    self.session.rollback()
                    raise

    def create_with_id(self, data: Dict[str, Any]) -> EntityMedia:
        """
        Create a new entity media association with a generated UUID.
        """
        # Generate a UUID for the new association if not provided
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())

        # Ensure entity_id is always a string
        if 'entity_id' in data:
            data['entity_id'] = str(data['entity_id'])
            logger.info(f"Ensured entity_id is string: {data['entity_id']}")

        try:
            return self.create(data)
        except Exception as e:
            logger.error(f"Error in create_with_id: {str(e)}")
            self.session.rollback()
            raise

    def get_by_entity(self, entity_type: str, entity_id: str) -> List[EntityMedia]:
        """
        Get all media associations for a specific entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity

        Returns:
            List of EntityMedia associations for the entity
        """
        # Always ensure entity_id is a string for querying
        entity_id_str = str(entity_id)

        query = self.session.query(self.model).filter(
            self.model.entity_type == entity_type,
            self.model.entity_id == entity_id_str
        ).order_by(self.model.display_order)

        return query.all()

    def get_thumbnail(self, entity_type: str, entity_id: str) -> Optional[EntityMedia]:
        """
        Get the thumbnail media association for a specific entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity

        Returns:
            The thumbnail EntityMedia association for the entity, or None if not found
        """
        # Always ensure entity_id is a string for querying
        entity_id_str = str(entity_id)

        return self.session.query(self.model).filter(
            self.model.entity_type == entity_type,
            self.model.entity_id == entity_id_str,
            self.model.media_type == "thumbnail"
        ).first()

    def update_entity_media(
            self,
            entity_type: str,
            entity_id: str,
            media_asset_id: str,
            media_type: str = "thumbnail",
            display_order: int = 0,
            caption: Optional[str] = None
    ) -> EntityMedia:
        """
        Update or create an entity media association based on the actual model definition.
        """
        try:
            # Always ensure entity_id is a string
            entity_id_str = str(entity_id)

            # Log the entity details for debugging
            logger.info(f"Working with entity: type={entity_type}, id={entity_id_str}, media_type={media_type}")

            # Check if the association already exists
            association = self.session.query(self.model).filter(
                self.model.entity_type == entity_type,
                self.model.entity_id == entity_id_str,
                self.model.media_type == media_type
            ).first()

            if association:
                # Update existing association
                logger.info(f"Updating existing association with ID: {association.id}")
                association.media_asset_id = media_asset_id
                association.display_order = display_order
                association.caption = caption
                association.updated_at = datetime.now()
                self.session.commit()
                return association
            else:
                # Create a new entity media association with a UUID for the ID
                new_id = str(uuid.uuid4())
                logger.info(f"Creating new association with ID: {new_id}")

                # Create the entity media instance directly
                new_association = EntityMedia(
                    id=new_id,
                    media_asset_id=media_asset_id,
                    entity_type=entity_type,
                    entity_id=entity_id_str,  # Explicitly as string
                    media_type=media_type,
                    display_order=display_order,
                    caption=caption,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )

                # Add to session and commit
                self.session.add(new_association)
                self.session.commit()
                logger.info(f"Successfully created association with ID: {new_id}")

                return new_association
        except Exception as e:
            logger.error(f"Error in update_entity_media: {str(e)}", exc_info=True)
            self.session.rollback()
            raise

    def remove_entity_media(self, entity_type: str, entity_id: str, media_type: Optional[str] = None) -> bool:
        """
        Remove media associations for an entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity
            media_type: Optional type of media to remove (if None, removes all)

        Returns:
            True if associations were removed, False otherwise
        """
        # Always ensure entity_id is a string for querying
        entity_id_str = str(entity_id)

        query = self.session.query(self.model).filter(
            self.model.entity_type == entity_type,
            self.model.entity_id == entity_id_str
        )

        if media_type:
            query = query.filter(self.model.media_type == media_type)

        count = query.delete(synchronize_session=False)
        self.session.commit()

        return count > 0

    def direct_sql_add_entity_media(
            self,
            entity_type: str,
            entity_id: str,
            media_asset_id: str,
            media_type: str = "thumbnail",
            display_order: int = 0,
            caption: Optional[str] = None
    ) -> Optional[EntityMedia]:
        """
        Add entity media using direct SQL to bypass ORM complexities.
        """
        from sqlalchemy import text
        import uuid
        from datetime import datetime

        try:
            # Generate IDs
            new_id = str(uuid.uuid4())
            uuid_value = str(uuid.uuid4())

            # Always use string for entity_id
            entity_id_str = str(entity_id)

            # Check if we already have an association
            check_sql = text("""
                SELECT id FROM entity_media 
                WHERE entity_type = :entity_type 
                AND entity_id = :entity_id 
                AND media_type = :media_type
            """)

            result = self.session.execute(
                check_sql,
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id_str,
                    "media_type": media_type
                }
            ).fetchone()

            if result:
                # Update existing with minimal fields
                existing_id = result[0]
                update_sql = text("""
                    UPDATE entity_media SET
                    media_asset_id = :media_asset_id,
                    display_order = :display_order,
                    caption = :caption,
                    updated_at = :updated_at
                    WHERE id = :id
                """)

                params = {
                    "id": existing_id,
                    "media_asset_id": media_asset_id,
                    "display_order": display_order,
                    "caption": caption if caption is not None else "",
                    "updated_at": datetime.utcnow().isoformat()
                }

                self.session.execute(update_sql, params)
                self.session.commit()

                # Return the updated entity
                return self.get_by_id(existing_id)
            else:
                # Insert new record with minimal required fields
                now = datetime.utcnow().isoformat()

                # Try inserting with the essential fields ONLY
                insert_sql = text("""
                    INSERT INTO entity_media (
                        id, media_asset_id, entity_type, entity_id, media_type, 
                        display_order, caption, created_at, updated_at
                    ) VALUES (
                        :id, :media_asset_id, :entity_type, :entity_id, :media_type,
                        :display_order, :caption, :created_at, :updated_at
                    )
                """)

                params = {
                    "id": new_id,
                    "media_asset_id": media_asset_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id_str,
                    "media_type": media_type,
                    "display_order": display_order,
                    "caption": caption if caption is not None else "",
                    "created_at": now,
                    "updated_at": now
                }

                try:
                    self.session.execute(insert_sql, params)
                    self.session.commit()
                    logger.info(f"Successfully created entity media with ID {new_id}")
                    return self.get_by_id(new_id)
                except Exception as e:
                    logger.error(f"First insert attempt failed: {str(e)}")
                    self.session.rollback()

                    # If that fails, try with additional fields that might be needed
                    # by inheritance but not explicitly defined in the model
                    try:
                        insert_sql = text("""
                            INSERT INTO entity_media (
                                id, media_asset_id, entity_type, entity_id, media_type, 
                                display_order, caption, created_at, updated_at, is_active
                            ) VALUES (
                                :id, :media_asset_id, :entity_type, :entity_id, :media_type,
                                :display_order, :caption, :created_at, :updated_at, :is_active
                            )
                        """)

                        params["is_active"] = True

                        self.session.execute(insert_sql, params)
                        self.session.commit()
                        logger.info(f"Second attempt with is_active succeeded for ID {new_id}")
                        return self.get_by_id(new_id)
                    except Exception as e2:
                        logger.error(f"Second insert attempt failed: {str(e2)}")
                        self.session.rollback()

                        # One final attempt with uuid column included
                        try:
                            insert_sql = text("""
                                INSERT INTO entity_media (
                                    id, media_asset_id, entity_type, entity_id, media_type, 
                                    display_order, caption, created_at, updated_at, is_active, uuid
                                ) VALUES (
                                    :id, :media_asset_id, :entity_type, :entity_id, :media_type,
                                    :display_order, :caption, :created_at, :updated_at, :is_active, :uuid
                                )
                            """)

                            params["uuid"] = uuid_value

                            self.session.execute(insert_sql, params)
                            self.session.commit()
                            logger.info(f"Third attempt with uuid succeeded for ID {new_id}")
                            return self.get_by_id(new_id)
                        except Exception as e3:
                            logger.error(f"Third insert attempt failed: {str(e3)}")
                            self.session.rollback()
                            raise

        except Exception as e:
            logger.error(f"Error in direct_sql_add_entity_media: {str(e)}", exc_info=True)
            self.session.rollback()
            raise