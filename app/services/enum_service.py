# app/services/enum_service.py
import re
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, insert, update, delete, select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.db.models.dynamic_enum import EnumType, EnumTranslation
from app.schemas.enum import EnumValueRead # Import schema for return type hint if possible

# --- Logger Setup ---
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

class EnumService:
    """
    Service for managing dynamic enumerations and their translations.
    Handles interactions with EnumType, EnumTranslation, and dynamic enum_value_* tables.
    """
    def __init__(self, db: Session):
        """
        Initializes the EnumService.

        Args:
            db (Session): SQLAlchemy database session.
        """
        self.db = db
        logger.debug("EnumService initialized.")

    # --- Read Operations ---

    def _get_enum_type_record(self, enum_system_name: str, raise_not_found: bool = True) -> Optional[EnumType]:
        """Helper to get the EnumType record by system name."""
        record = self.db.query(EnumType).filter(EnumType.system_name == enum_system_name).first()
        if not record and raise_not_found:
             logger.warning(f"Enum type with system_name '{enum_system_name}' not found.")
             raise ValueError(f"Enum type '{enum_system_name}' not found")
        return record

    def get_enum_types(self) -> List[Dict]:
        """Get all registered enum types"""
        logger.info("Executing get_enum_types()")
        try:
            enum_types_orm = self.db.query(EnumType).order_by(EnumType.name).all()
            count = len(enum_types_orm)
            logger.info(f"Raw ORM query for EnumType returned {count} objects.")

            if not enum_types_orm:
                logger.warning("No EnumType records found in 'enum_types'.")
                return []

            result = [{"id": et.id, "name": et.name, "system_name": et.system_name} for et in enum_types_orm]
            logger.info(f"Returning {len(result)} enum types.")
            return result
        except SQLAlchemyError as e:
             logger.exception("SQLAlchemyError occurred while fetching enum types.")
             return [] # Return empty on error
        except Exception as e:
            logger.exception("Unexpected error in get_enum_types.")
            return []

    def get_enum_values(self, enum_system_name: str, locale: str = "en") -> List[Dict]:
        """Get active values for a specific enum type by system_name with translations"""
        logger.info(f"Executing get_enum_values(enum_system_name='{enum_system_name}', locale='{locale}')")
        try:
            enum_type_record = self._get_enum_type_record(enum_system_name, raise_not_found=True) # Raises ValueError if not found
            if not enum_type_record: return [] # Should not be reached if raise_not_found=True

            table_name = enum_type_record.table_name
            if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
                logger.error(f"Invalid table name format for enum '{enum_system_name}': {table_name}")
                raise ValueError(f"Invalid table name format configuration: {table_name}")

            # Use enum_type_record.name for joining with translations table
            sql = text(f"""
            SELECT ev.id, ev.code, ev.display_order, ev.is_system, ev.parent_id, ev.is_active,
                   COALESCE(et.display_text, ev.code) as display_text,
                   et.description
            FROM "{table_name}" ev
            LEFT JOIN enum_translations et ON
                et.enum_type = :enum_type_name AND
                et.enum_value = ev.code AND
                et.locale = :locale
            WHERE ev.is_active = TRUE
            ORDER BY ev.display_order, ev.code
            """) # Added is_active to SELECT

            logger.debug(f"Executing SQL for enum values: {sql} with params enum_type_name='{enum_type_record.name}', locale='{locale}'")

            result_proxy = self.db.execute(sql, {"enum_type_name": enum_type_record.name, "locale": locale})
            values = [dict(row._mapping) for row in result_proxy] # Use ._mapping for SQLAlchemy 2+
            logger.info(f"Found {len(values)} active values for enum '{enum_system_name}' with locale '{locale}'.")
            return values

        except ValueError as e: # Catch specific errors raised internally
             logger.error(f"ValueError in get_enum_values for '{enum_system_name}': {e}")
             raise # Re-raise for endpoint to handle (e.g., 404 for type not found)
        except SQLAlchemyError as e:
             logger.exception(f"SQLAlchemyError fetching values for enum '{enum_system_name}'.")
             raise # Re-raise for endpoint to handle as 500
        except Exception as e:
            logger.exception(f"Unexpected error in get_enum_values for '{enum_system_name}'.")
            raise # Re-raise for endpoint to handle as 500

    def get_all_enums(self, locale: str = "en") -> Dict[str, List[Dict]]:
        """Get all enums with their active values for a specific locale"""
        logger.info(f"Executing get_all_enums(locale='{locale}')")
        enum_types = self.get_enum_types()
        result = {}
        for enum_type_info in enum_types:
            system_name = enum_type_info["system_name"]
            try:
                result[system_name] = self.get_enum_values(system_name, locale)
            except Exception as e:
                # Log error but continue fetching other types
                logger.error(f"Failed to get values for enum type '{system_name}' in get_all_enums: {e}", exc_info=False) # Keep log concise
                result[system_name] = [] # Include empty list for this type on error
        logger.info(f"Returning all enum values for {len(result)} types for locale '{locale}'.")
        return result

    # --- Write Operations ---

    def create_enum_value(self, enum_system_name: str, data: dict) -> Dict:
        """Creates a new value in the specified enum type's dynamic table."""
        logger.info(f"Attempting to create enum value for '{enum_system_name}' with data: {data}")
        try:
            enum_type_record = self._get_enum_type_record(enum_system_name)
            table_name = enum_type_record.table_name
            if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
                 raise ValueError(f"Invalid table name configuration for '{enum_system_name}': {table_name}")

            # Ensure required fields are present (basic check)
            required_fields = ['code', 'display_text'] # 'is_active' defaults to True
            if not all(field in data for field in required_fields):
                 raise ValueError("Missing required fields ('code', 'display_text') for creating enum value.")

            # Prevent creating duplicate codes within the same enum type
            check_sql = text(f'SELECT 1 FROM "{table_name}" WHERE code = :code')
            existing = self.db.execute(check_sql, {"code": data['code']}).scalar()
            if existing:
                 raise ValueError(f"Value code '{data['code']}' already exists for enum type '{enum_system_name}'.")

            # Prepare data for insertion (add defaults if not provided)
            insert_data = {
                "code": data['code'],
                "display_order": data.get('display_order', 0),
                "is_system": data.get('is_system', False),
                "parent_id": data.get('parent_id'),
                "is_active": data.get('is_active', True),
                # Add other columns if your dynamic tables have them (e.g., description_base)
            }

            # Construct and execute INSERT statement using SQLAlchemy Core API for safety
            # Assuming the dynamic table's metadata isn't loaded into SQLAlchemy's MetaData easily,
            # we stick to text() but use parameter binding carefully.
            # NOTE: We cannot easily use ORM's db.add() because the model class is dynamic.
            columns = ", ".join(f'"{col}"' for col in insert_data.keys())
            placeholders = ", ".join(f":{col}" for col in insert_data.keys())
            sql = text(f'INSERT INTO "{table_name}" ({columns}) VALUES ({placeholders}) RETURNING id')

            logger.debug(f"Executing SQL: {sql} with data: {insert_data}")
            result = self.db.execute(sql, insert_data)
            new_id = result.scalar_one() # Get the ID of the newly inserted row
            self.db.commit()
            logger.info(f"Successfully created enum value ID {new_id} for '{enum_system_name}'.")

            # Optionally create default 'en' translation if display_text was provided
            if 'display_text' in data and data['display_text']:
                 try:
                     self.create_or_update_translation(
                         enum_system_name=enum_system_name,
                         value_code=data['code'],
                         data={
                             "locale": "en",
                             "display_text": data['display_text'],
                             "description": data.get('description')
                         }
                     )
                 except Exception as trans_e:
                     # Log translation error but don't fail the whole creation
                     logger.error(f"Failed to create default 'en' translation for new value '{data['code']}': {trans_e}")


            # Fetch and return the newly created record (including potential default translation)
            # This ensures the response matches the Read schema
            new_value = self._get_dynamic_value_by_id(table_name, new_id, enum_type_record.name)
            if not new_value:
                 # Should not happen if insert succeeded, but handle defensively
                 raise RuntimeError("Failed to retrieve newly created enum value.")
            return new_value

        except IntegrityError as e: # Catch potential DB constraint violations
            self.db.rollback()
            logger.error(f"Database integrity error creating enum value for '{enum_system_name}': {e}")
            # Re-raise as ValueError for endpoint to handle as 409 or 400
            raise ValueError(f"Value code '{data.get('code')}' likely already exists.") from e
        except ValueError as e:
             self.db.rollback()
             logger.error(f"ValueError creating enum value for '{enum_system_name}': {e}")
             raise # Re-raise specific ValueErrors
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception(f"SQLAlchemyError creating enum value for '{enum_system_name}'.")
            raise # Re-raise for endpoint
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Unexpected error creating enum value for '{enum_system_name}'.")
            raise

    def update_enum_value(self, enum_system_name: str, value_id: int, data: dict) -> Dict:
        """Updates an existing value in the specified enum type's dynamic table."""
        logger.info(f"Attempting to update enum value ID {value_id} for '{enum_system_name}' with data: {data}")
        if not data:
            raise ValueError("No update data provided.")

        try:
            enum_type_record = self._get_enum_type_record(enum_system_name)
            table_name = enum_type_record.table_name
            if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
                 raise ValueError(f"Invalid table name configuration for '{enum_system_name}': {table_name}")

            # Fetch the existing record to check 'is_system' flag
            existing_value = self._get_dynamic_value_by_id(table_name, value_id, enum_type_record.name, check_active=False)
            if not existing_value:
                raise ValueError(f"Enum value with ID {value_id} not found for type '{enum_system_name}'.")

            # Prevent modification of system values if necessary (relaxing slightly, allow display text/order)
            if existing_value.get('is_system'):
                 allowed_system_updates = {'display_text', 'description', 'display_order', 'is_active'}
                 disallowed_keys = set(data.keys()) - allowed_system_updates
                 if disallowed_keys:
                     raise ValueError(f"Cannot modify fields {disallowed_keys} for system value ID {value_id}.")
                 logger.warning(f"Updating allowed fields for system value ID {value_id}.")

            # Prepare update data - only include fields allowed by EnumValueUpdate schema
            allowed_fields = {'display_text', 'description', 'display_order', 'parent_id', 'is_active'}
            update_payload = {k: v for k, v in data.items() if k in allowed_fields}

            # Handle default 'en' translation update if display_text is provided
            en_translation_data = None
            if 'display_text' in update_payload:
                en_translation_data = {
                    "locale": "en",
                    "display_text": update_payload['display_text'],
                    "description": update_payload.get('description', existing_value.get('description')) # Carry over old desc if not updated
                }
                # Remove display_text/description from direct table update if handled via translation
                # update_payload.pop('display_text', None) # Decide if base table should store 'en' or not
                # update_payload.pop('description', None)

            if not update_payload and not en_translation_data:
                 raise ValueError("No valid fields provided for update.")

            # Update the dynamic value table if there are fields left
            if update_payload:
                set_clauses = ", ".join(f'"{col}" = :{col}' for col in update_payload.keys())
                sql = text(f'UPDATE "{table_name}" SET {set_clauses} WHERE id = :value_id')
                update_payload['value_id'] = value_id # Add id for WHERE clause
                logger.debug(f"Executing SQL: {sql} with data: {update_payload}")
                result = self.db.execute(sql, update_payload)
                if result.rowcount == 0:
                     # Should have been caught by initial check, but double-check
                     raise ValueError(f"Enum value with ID {value_id} not found during UPDATE.")

            # Update 'en' translation if needed
            if en_translation_data:
                 try:
                     self.create_or_update_translation(
                         enum_system_name=enum_system_name,
                         value_code=existing_value['code'], # Use code from existing value
                         data=en_translation_data
                     )
                 except Exception as trans_e:
                     # Log error, but consider if update should fail if translation fails
                     logger.error(f"Failed to update 'en' translation for value ID {value_id}: {trans_e}")
                     # Potentially raise ValueError("Failed to update translation, main update rolled back") if transactional integrity needed


            self.db.commit()
            logger.info(f"Successfully updated enum value ID {value_id} for '{enum_system_name}'.")

            # Fetch and return the updated record
            updated_value = self._get_dynamic_value_by_id(table_name, value_id, enum_type_record.name)
            if not updated_value:
                 raise RuntimeError("Failed to retrieve updated enum value.")
            return updated_value

        except ValueError as e:
             self.db.rollback()
             logger.error(f"ValueError updating enum value ID {value_id} for '{enum_system_name}': {e}")
             raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception(f"SQLAlchemyError updating enum value ID {value_id} for '{enum_system_name}'.")
            raise
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Unexpected error updating enum value ID {value_id} for '{enum_system_name}'.")
            raise

    def delete_enum_value(self, enum_system_name: str, value_id: int) -> None:
        """Deletes a non-system value from the dynamic table and its translations."""
        logger.info(f"Attempting to delete enum value ID {value_id} for '{enum_system_name}'.")
        try:
            enum_type_record = self._get_enum_type_record(enum_system_name)
            table_name = enum_type_record.table_name
            if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
                 raise ValueError(f"Invalid table name configuration for '{enum_system_name}': {table_name}")

            # Fetch the record first to check 'is_system' and get 'code'
            # We need 'code' to delete translations
            select_sql = text(f'SELECT code, is_system FROM "{table_name}" WHERE id = :value_id')
            record_to_delete = self.db.execute(select_sql, {"value_id": value_id}).first()

            if not record_to_delete:
                raise ValueError(f"Enum value with ID {value_id} not found for type '{enum_system_name}'.")

            if record_to_delete.is_system:
                raise ValueError(f"Cannot delete system value ID {value_id} ('{record_to_delete.code}') for type '{enum_system_name}'.")

            value_code = record_to_delete.code

            # Delete from dynamic table
            delete_value_sql = text(f'DELETE FROM "{table_name}" WHERE id = :value_id')
            logger.debug(f"Executing SQL: {delete_value_sql} with value_id: {value_id}")
            result = self.db.execute(delete_value_sql, {"value_id": value_id})
            if result.rowcount == 0:
                 # Should have been caught, but handle defensively
                 raise ValueError(f"Enum value with ID {value_id} not found during DELETE.")

            # Delete associated translations
            delete_trans_sql = text("""
                DELETE FROM enum_translations
                WHERE enum_type = :enum_type_name AND enum_value = :value_code
            """)
            logger.debug(f"Executing SQL: {delete_trans_sql} with enum_type_name='{enum_type_record.name}', value_code='{value_code}'")
            self.db.execute(delete_trans_sql, {"enum_type_name": enum_type_record.name, "value_code": value_code})

            self.db.commit()
            logger.info(f"Successfully deleted enum value ID {value_id} ('{value_code}') and its translations for '{enum_system_name}'.")

        except ValueError as e:
             self.db.rollback()
             logger.error(f"ValueError deleting enum value ID {value_id} for '{enum_system_name}': {e}")
             raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception(f"SQLAlchemyError deleting enum value ID {value_id} for '{enum_system_name}'.")
            raise
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Unexpected error deleting enum value ID {value_id} for '{enum_system_name}'.")
            raise

    def create_or_update_translation(self, enum_system_name: str, value_code: str, data: dict) -> Dict:
        """Creates a new translation or updates an existing one for a given value code and locale."""
        logger.info(f"Creating/updating translation for '{enum_system_name}/{value_code}', locale '{data.get('locale')}'")
        try:
            enum_type_record = self._get_enum_type_record(enum_system_name)
            enum_type_name = enum_type_record.name # Use the name field for translations table

            # Validate locale and display_text are present
            locale = data.get('locale')
            display_text = data.get('display_text')
            if not locale or not display_text:
                 raise ValueError("Missing required fields ('locale', 'display_text') for translation.")

            # Check if the base enum value code exists (optional but good practice)
            # value_exists_sql = text(f'SELECT 1 FROM "{enum_type_record.table_name}" WHERE code = :code')
            # if not self.db.execute(value_exists_sql, {"code": value_code}).scalar():
            #     raise ValueError(f"Enum value code '{value_code}' not found for type '{enum_system_name}'.")

            # Check for existing translation using ORM
            existing_translation = self.db.query(EnumTranslation).filter_by(
                enum_type=enum_type_name,
                enum_value=value_code,
                locale=locale
            ).first()

            if existing_translation:
                # Update existing
                logger.debug(f"Found existing translation ID {existing_translation.id}. Updating.")
                existing_translation.display_text = display_text
                existing_translation.description = data.get('description') # Update description if provided
                self.db.flush() # Flush to get potential errors before commit
                translation_id = existing_translation.id
            else:
                # Create new
                logger.debug("No existing translation found. Creating new.")
                new_translation = EnumTranslation(
                    enum_type=enum_type_name,
                    enum_value=value_code,
                    locale=locale,
                    display_text=display_text,
                    description=data.get('description')
                )
                self.db.add(new_translation)
                self.db.flush() # Flush to get ID and potential errors
                translation_id = new_translation.id

            self.db.commit()
            # Fetch the committed record to return consistent data
            final_translation = self.db.query(EnumTranslation).get(translation_id)
            if not final_translation:
                 raise RuntimeError("Failed to retrieve created/updated translation.")
            logger.info(f"Successfully created/updated translation ID {translation_id}.")
            # Convert ORM object to dictionary for return
            return {
                "id": final_translation.id,
                "enum_type": final_translation.enum_type,
                "enum_value": final_translation.enum_value,
                "locale": final_translation.locale,
                "display_text": final_translation.display_text,
                "description": final_translation.description
            }

        except ValueError as e:
             self.db.rollback()
             logger.error(f"ValueError processing translation for '{enum_system_name}/{value_code}': {e}")
             raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception(f"SQLAlchemyError processing translation for '{enum_system_name}/{value_code}'.")
            raise
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Unexpected error processing translation for '{enum_system_name}/{value_code}'.")
            raise

    def update_translation(self, translation_id: int, data: dict) -> Dict:
        """Updates an existing translation identified by its primary key ID."""
        logger.info(f"Attempting to update translation ID {translation_id} with data: {data}")
        if not data:
            raise ValueError("No update data provided.")

        try:
            translation = self.db.query(EnumTranslation).get(translation_id)
            if not translation:
                raise ValueError(f"Translation with ID {translation_id} not found.")

            # Update allowed fields
            updated = False
            if 'display_text' in data and data['display_text'] is not None:
                translation.display_text = data['display_text']
                updated = True
            if 'description' in data: # Allow setting description to None/empty
                translation.description = data['description']
                updated = True

            if not updated:
                 logger.warning(f"No valid fields provided to update translation ID {translation_id}.")
                 # Return current data without committing if no changes made
                 return {
                    "id": translation.id, "enum_type": translation.enum_type, "enum_value": translation.enum_value,
                    "locale": translation.locale, "display_text": translation.display_text, "description": translation.description
                 }

            self.db.commit()
            self.db.refresh(translation) # Refresh to get latest state
            logger.info(f"Successfully updated translation ID {translation_id}.")
            return {
                "id": translation.id, "enum_type": translation.enum_type, "enum_value": translation.enum_value,
                "locale": translation.locale, "display_text": translation.display_text, "description": translation.description
            }

        except ValueError as e:
             self.db.rollback()
             logger.error(f"ValueError updating translation ID {translation_id}: {e}")
             raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception(f"SQLAlchemyError updating translation ID {translation_id}.")
            raise
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Unexpected error updating translation ID {translation_id}.")
            raise

    def delete_translation(self, translation_id: int) -> None:
        """Deletes an existing translation identified by its primary key ID."""
        logger.info(f"Attempting to delete translation ID {translation_id}.")
        try:
            translation = self.db.query(EnumTranslation).get(translation_id)
            if not translation:
                raise ValueError(f"Translation with ID {translation_id} not found.")

            logger.debug(f"Deleting translation: Type='{translation.enum_type}', Value='{translation.enum_value}', Locale='{translation.locale}'")
            self.db.delete(translation)
            self.db.commit()
            logger.info(f"Successfully deleted translation ID {translation_id}.")

        except ValueError as e:
             self.db.rollback()
             logger.error(f"ValueError deleting translation ID {translation_id}: {e}")
             raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception(f"SQLAlchemyError deleting translation ID {translation_id}.")
            raise
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Unexpected error deleting translation ID {translation_id}.")
            raise

    # --- Helper Methods ---
    def _get_dynamic_value_by_id(self, table_name: str, value_id: int, enum_type_name: str, locale: str = 'en', check_active: bool = True) -> Optional[Dict]:
         """Internal helper to fetch a single dynamic enum value by ID, with optional translation."""
         logger.debug(f"Fetching dynamic value ID {value_id} from table '{table_name}' for type '{enum_type_name}' with locale '{locale}'.")
         try:
            # Construct SQL to fetch the specific value and its 'en' translation
            sql = text(f"""
                SELECT ev.id, ev.code, ev.display_order, ev.is_system, ev.parent_id, ev.is_active,
                       COALESCE(et.display_text, ev.code) as display_text,
                       et.description
                FROM "{table_name}" ev
                LEFT JOIN enum_translations et ON
                    et.enum_type = :enum_type_name AND
                    et.enum_value = ev.code AND
                    et.locale = :locale
                WHERE ev.id = :value_id
                {'AND ev.is_active = TRUE' if check_active else ''}
            """)
            params = {"enum_type_name": enum_type_name, "locale": locale, "value_id": value_id}
            result = self.db.execute(sql, params).first()

            if result:
                 logger.debug(f"Found dynamic value ID {value_id}.")
                 return dict(result._mapping)
            else:
                 logger.warning(f"Dynamic value ID {value_id} not found in table '{table_name}' (active check: {check_active}).")
                 return None
         except Exception as e:
             logger.exception(f"Error in _get_dynamic_value_by_id for ID {value_id}, table {table_name}.")
             return None # Or re-raise