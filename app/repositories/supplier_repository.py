# File: app/repositories/supplier_repository.py

from typing import List, Optional, Dict, Any, Generator
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, text
import logging
import json # Import json for handling materialCategories

from app.db.models.supplier import Supplier
from app.db.models.enums import SupplierStatus
from app.repositories.base_repository import BaseRepository
from app.core.exceptions import DatabaseException

# Set up logger for this module
logger = logging.getLogger(__name__)
# Example: Set higher level for noisy libraries if needed
# logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

class SupplierRepository(BaseRepository[Supplier]):
    """
    Repository for Supplier entity operations with memory-efficient implementations
    and enhanced logging.
    """

    def __init__(self, session: Session, encryption_service=None):
        """Initialize the repository with session and optional encryption service."""
        super().__init__(session, encryption_service)
        self.model = Supplier
        logger.debug(f"SupplierRepository initialized with session ID: {id(session)}")

    def list(self, **filters) -> List[Supplier]:
        """
        List suppliers with optional filtering, logging details.

        Args:
            **filters: Optional filters including:
                - name: Filter by supplier name
                - status: Filter by supplier status
                - category: Filter by supplier category
                - skip: Number of records to skip (pagination)
                - limit: Page size (pagination)

        Returns:
            List[Supplier]: List of suppliers matching the criteria

        Raises:
            DatabaseException: If a database error occurs
        """
        logger.debug(f"Listing suppliers with filters: {filters}")
        try:
            # Extract pagination parameters
            skip = filters.get("skip", 0)
            limit = filters.get("limit", 100)
            logger.debug(f"Pagination - Skip: {skip}, Limit: {limit}")

            # --- SQLCipher Path ---
            try:
                from app.db.session import EncryptionManager, use_sqlcipher
                from app.core.config import settings
                import os

                if not use_sqlcipher:
                    logger.info("SQLCipher not enabled, using standard SQLAlchemy approach for list.")
                    return self._list_with_sqlalchemy(skip, limit, filters)

                logger.info("Using direct SQLCipher approach for list.")
                db_path = os.path.abspath(settings.DATABASE_PATH)
                logger.debug(f"Database path: {db_path}")

                sqlcipher = EncryptionManager.get_sqlcipher_module()
                conn = sqlcipher.connect(db_path)
                cursor = conn.cursor()
                logger.debug("SQLCipher connection established.")

                key_pragma_value = EncryptionManager.format_key_for_pragma()
                logger.debug(f"Configuring SQLCipher with key format: {key_pragma_value}")
                cursor.execute(f"PRAGMA key = {key_pragma_value};")
                cursor.execute("PRAGMA cipher_page_size = 4096;")
                cursor.execute("PRAGMA kdf_iter = 256000;")
                cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
                cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
                logger.debug("SQLCipher PRAGMAs executed.")

                # Verify table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='suppliers';")
                if not cursor.fetchone():
                    logger.error("Table 'suppliers' not found in database via SQLCipher.")
                    conn.close()
                    raise DatabaseException(message="Table 'suppliers' not found.", entity_type="Supplier")
                logger.debug("Table 'suppliers' confirmed to exist.")

                # Build query
                sql_parts = ["SELECT * FROM suppliers WHERE 1=1"]
                params = []
                filter_clauses = []

                if "name" in filters and filters["name"]:
                    filter_clauses.append("name LIKE ?") # Use LIKE for flexibility? Or = ?
                    params.append(f"%{filters['name']}%") # Adjust if using =

                if "status" in filters and filters["status"]:
                    filter_clauses.append("status = ?")
                    params.append(str(filters["status"])) # Ensure string for comparison

                if "category" in filters and filters["category"]:
                    filter_clauses.append("category = ?")
                    params.append(filters["category"])

                if filter_clauses:
                    sql_parts.append("AND " + " AND ".join(filter_clauses))

                sql_parts.append("ORDER BY id ASC") # Add default ordering for consistent pagination
                sql_parts.append("LIMIT ? OFFSET ?")
                params.extend([limit, skip])

                final_sql = " ".join(sql_parts)
                logger.info(f"Executing Supplier List Query: {final_sql} with params: {params}")

                cursor.execute(final_sql, params)

                column_names = [column[0] for column in cursor.description]
                logger.debug(f"Retrieved columns: {column_names}")
                rows = cursor.fetchall()
                logger.info(f"Fetched {len(rows)} raw rows from database.")

                # Convert rows to Supplier model instances
                entities = []
                for row_index, row in enumerate(rows):
                    supplier = Supplier()
                    row_data = {}
                    for i, column_name in enumerate(column_names):
                        value = row[i]
                        row_data[column_name] = value # Store raw data for logging
                        if hasattr(supplier, column_name):
                            try:
                                # Handle potential JSON string for material_categories
                                if column_name == 'material_categories' and isinstance(value, str):
                                    try:
                                        deserialized_value = json.loads(value)
                                        setattr(supplier, column_name, deserialized_value)
                                        logger.debug(f"Row {row_index}: Successfully deserialized material_categories for supplier ID {row_data.get('id', 'N/A')}")
                                    except json.JSONDecodeError:
                                        logger.warning(f"Row {row_index}: Failed to deserialize material_categories '{value}' for supplier ID {row_data.get('id', 'N/A')}. Setting as empty list.")
                                        setattr(supplier, column_name, [])
                                # Handle potential Enum conversion for status
                                elif column_name == 'status' and value is not None:
                                     try:
                                         enum_value = SupplierStatus(value.lower()) # Ensure lowercase matches enum
                                         setattr(supplier, column_name, enum_value)
                                     except ValueError:
                                         logger.warning(f"Row {row_index}: Invalid status value '{value}' from DB for supplier ID {row_data.get('id', 'N/A')}. Setting attribute as raw value.")
                                         setattr(supplier, column_name, value) # Set raw value if enum fails
                                else:
                                    setattr(supplier, column_name, value)
                            except Exception as set_err:
                                logger.error(f"Row {row_index}: Error setting attribute '{column_name}' with value '{value}' (type: {type(value).__name__}) for supplier ID {row_data.get('id', 'N/A')}: {set_err}")
                        else:
                             logger.warning(f"Row {row_index}: Column '{column_name}' from DB not found in Supplier model. Skipping.")

                    entities.append(supplier)
                    if row_index < 5: # Log details for first few rows
                       logger.debug(f"Row {row_index} Data: {row_data}")
                       logger.debug(f"Converted Entity {row_index} (__dict__): {supplier.__dict__}")


                if entities and logger.isEnabledFor(logging.DEBUG):
                    # Log a sample of the populated entities after conversion
                    sample_entity = entities[0]
                    log_dict = {k: v for k, v in sample_entity.__dict__.items() if not k.startswith('_')} # Avoid internal SQLAlchemy attrs
                    logger.debug(f"Sample populated entity (ID: {getattr(sample_entity, 'id', 'N/A')}): {log_dict}")

                conn.close()
                logger.info(f"Successfully retrieved and processed {len(entities)} suppliers via SQLCipher.")

                # Decrypt sensitive fields if necessary (assuming _decrypt_sensitive_fields handles None)
                decrypted_entities = [self._decrypt_sensitive_fields(entity) for entity in entities]
                logger.debug("Sensitive fields decrypted (if applicable).")
                return decrypted_entities

            # --- SQLAlchemy Fallback Path ---
            except ImportError as e:
                logger.error(f"SQLCipher import error: {e}. Falling back to SQLAlchemy approach for list.")
                return self._list_with_sqlalchemy(skip, limit, filters)

        # --- General Exception Handling ---
        except Exception as e:
            logger.exception(f"Unexpected error listing suppliers with filters {filters}: {e}") # Use logger.exception to include traceback
            raise DatabaseException(
                message=f"Error retrieving suppliers: {str(e)}",
                entity_type="Supplier"
            )

    def exists_by_name(self, name: str) -> bool:
        """Check if a supplier with the given name exists."""
        logger.debug(f"Checking existence of supplier by name: '{name}'")
        if not name:
            logger.warning("exists_by_name called with empty name.")
            return False
        try:
            # Using text() for direct SQL, adaptable for SQLCipher/SQLAlchemy
            query = text("SELECT 1 FROM suppliers WHERE name = :name LIMIT 1")
            result = self.session.execute(query, {"name": name}).scalar_one_or_none()
            exists = result is not None
            logger.debug(f"Supplier name '{name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.exception(f"Error checking if supplier exists by name '{name}': {e}")
            # Depending on requirements, you might want to re-raise or return False
            # Returning False might hide database issues. Consider re-raising.
            # raise DatabaseException(message=f"Error checking supplier existence by name: {e}", entity_type="Supplier")
            return False # Current behavior


    def _list_with_sqlalchemy(self, skip: int, limit: int, filters: Dict[str, Any]) -> List[Supplier]:
        """SQLAlchemy fallback implementation for listing suppliers."""
        logger.info(f"Using SQLAlchemy ORM to list suppliers. Skip: {skip}, Limit: {limit}, Filters: {filters}")
        try:
            query = self.session.query(self.model)

            if "name" in filters and filters["name"]:
                logger.debug(f"Applying SQLAlchemy filter: name LIKE '%{filters['name']}%'")
                query = query.filter(self.model.name.ilike(f"%{filters['name']}%")) # Use ilike for case-insensitive

            if "status" in filters and filters["status"]:
                 try:
                     # Attempt to convert filter value to the Enum type if it's not already
                     status_enum = filters["status"]
                     if isinstance(status_enum, str):
                          status_enum = SupplierStatus(filters["status"].lower())
                     logger.debug(f"Applying SQLAlchemy filter: status == {status_enum}")
                     query = query.filter(self.model.status == status_enum)
                 except ValueError:
                     logger.warning(f"Invalid status value '{filters['status']}' provided for SQLAlchemy filter. Skipping status filter.")

            if "category" in filters and filters["category"]:
                logger.debug(f"Applying SQLAlchemy filter: category == '{filters['category']}'")
                query = query.filter(self.model.category == filters["category"])

            # Apply ordering and pagination
            query = query.order_by(self.model.id.asc()) # Add default ordering
            query = query.offset(skip).limit(limit)

            logger.debug(f"Executing SQLAlchemy query: {query.statement.compile(compile_kwargs={'literal_binds': True})}") # Log compiled query (use with caution in prod)
            entities = query.all()
            logger.info(f"SQLAlchemy query returned {len(entities)} entities.")

            if entities and logger.isEnabledFor(logging.DEBUG):
                 sample_entity = entities[0]
                 log_dict = {k: v for k, v in sample_entity.__dict__.items() if not k.startswith('_')}
                 logger.debug(f"Sample SQLAlchemy entity (ID: {getattr(sample_entity, 'id', 'N/A')}): {log_dict}")


            decrypted_entities = [self._decrypt_sensitive_fields(entity) for entity in entities]
            logger.debug("Sensitive fields decrypted via SQLAlchemy path (if applicable).")
            return decrypted_entities

        except Exception as e:
            logger.exception(f"Error in SQLAlchemy list method with filters {filters}: {e}")
            raise DatabaseException(
                message=f"Error retrieving suppliers with SQLAlchemy: {str(e)}",
                entity_type="Supplier"
            )


    def count(self, **filters) -> int:
        """
        Count total number of suppliers matching the given filters, with logging.

        Args:
            **filters: Optional filters to apply

        Returns:
            int: Total count of suppliers
        """
        logger.debug(f"Counting suppliers with filters: {filters}")
        try:
            # --- SQLCipher Path ---
            try:
                from app.db.session import EncryptionManager, use_sqlcipher
                from app.core.config import settings
                import os

                db_path = os.path.abspath(settings.DATABASE_PATH)

                if use_sqlcipher:
                    logger.info("Using direct SQLCipher approach for count.")
                    sqlcipher = EncryptionManager.get_sqlcipher_module()
                    conn = sqlcipher.connect(db_path)
                    cursor = conn.cursor()
                    logger.debug("SQLCipher connection established for count.")

                    key = EncryptionManager.get_key()
                    cursor.execute(f"PRAGMA key = \"x'{key}'\";") # Use recommended hex format
                    cursor.execute("PRAGMA cipher_page_size = 4096;")
                    cursor.execute("PRAGMA kdf_iter = 256000;")
                    cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
                    cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
                    logger.debug("SQLCipher PRAGMAs executed for count.")

                    # Build query with WHERE clauses based on filters
                    sql_parts = ["SELECT COUNT(*) FROM suppliers WHERE 1=1"]
                    params = []
                    filter_clauses = []

                    if "name" in filters and filters["name"]:
                        filter_clauses.append("name LIKE ?")
                        params.append(f"%{filters['name']}%")

                    if "status" in filters and filters["status"]:
                        filter_clauses.append("status = ?")
                        params.append(str(filters["status"]).lower()) # Ensure lowercase for comparison

                    if "category" in filters and filters["category"]:
                        filter_clauses.append("category = ?")
                        params.append(filters["category"])

                    if filter_clauses:
                        sql_parts.append("AND " + " AND ".join(filter_clauses))

                    final_sql = " ".join(sql_parts)
                    logger.info(f"Executing Supplier Count Query: {final_sql} with params: {params}")

                    cursor.execute(final_sql, params)
                    result = cursor.fetchone()
                    count = result[0] if result else 0
                    logger.info(f"SQLCipher count query returned: {count}")

                    cursor.close()
                    conn.close()
                    logger.debug("SQLCipher connection closed for count.")
                    return count

                # --- SQLAlchemy Path ---
                else:
                    logger.info("Using SQLAlchemy ORM approach for count.")
                    from sqlalchemy import func, select

                    count_query = select(func.count(self.model.id)).select_from(self.model) # Count specific column like id

                    # Apply filters similar to _list_with_sqlalchemy
                    if "name" in filters and filters["name"]:
                         logger.debug(f"Applying SQLAlchemy count filter: name LIKE '%{filters['name']}%'")
                         count_query = count_query.where(self.model.name.ilike(f"%{filters['name']}%"))

                    if "status" in filters and filters["status"]:
                         try:
                             status_enum = filters["status"]
                             if isinstance(status_enum, str):
                                 status_enum = SupplierStatus(filters["status"].lower())
                             logger.debug(f"Applying SQLAlchemy count filter: status == {status_enum}")
                             count_query = count_query.where(self.model.status == status_enum)
                         except ValueError:
                             logger.warning(f"Invalid status value '{filters['status']}' provided for SQLAlchemy count filter. Skipping status filter.")

                    if "category" in filters and filters["category"]:
                         logger.debug(f"Applying SQLAlchemy count filter: category == '{filters['category']}'")
                         count_query = count_query.where(self.model.category == filters["category"])

                    logger.debug(f"Executing SQLAlchemy count query: {count_query.compile(compile_kwargs={'literal_binds': True})}")
                    result = self.session.execute(count_query).scalar_one_or_none() # Use scalar_one_or_none
                    count = result if result is not None else 0
                    logger.info(f"SQLAlchemy count query returned: {count}")
                    return count

            except ImportError:
                logger.warning("SQLCipher/SQLAlchemy import error in count, using fallback counting.")
                # Fallback: list all and count (less efficient)
                all_suppliers = self.list(**filters) # Reuse list logic
                count = len(all_suppliers)
                logger.info(f"Count fallback: listed {count} suppliers.")
                return count

        except Exception as e:
            logger.exception(f"Error counting suppliers with filters {filters}: {e}")
            raise DatabaseException(
                message=f"Error counting suppliers: {str(e)}",
                entity_type="Supplier"
            )


    # stream_all method (add logging if needed)
    def stream_all(self, batch_size=50, **filters) -> Generator[Supplier, None, None]:
        """Stream all suppliers in memory-efficient batches."""
        logger.info(f"Streaming all suppliers with batch size {batch_size} and filters: {filters}")
        offset = 0
        total_yielded = 0
        while True:
            logger.debug(f"Streaming batch: Offset={offset}, Limit={batch_size}")
            batch = self.list(skip=offset, limit=batch_size, **filters)
            if not batch:
                logger.debug("Streaming finished: No more batches.")
                break

            logger.debug(f"Yielding {len(batch)} suppliers from batch.")
            for supplier in batch:
                yield supplier
                total_yielded += 1

            offset += len(batch) # More robust way to increment offset

            # Add safeguard for very large datasets or potential infinite loops
            if len(batch) < batch_size:
                 logger.debug("Streaming finished: Last batch was smaller than batch size.")
                 break
            if offset > 100000: # Example safeguard limit
                 logger.warning("Streaming stopped: Reached safeguard limit of 100,000 records.")
                 break
        logger.info(f"Finished streaming. Total suppliers yielded: {total_yielded}")

    # search_suppliers and _search_suppliers_direct_sql (add logging)
    def search_suppliers(self, query_str: str, skip: int = 0, limit: int = 100) -> List[Supplier]:
        """Search for suppliers by name, contact, or email with logging."""
        logger.info(f"Searching suppliers for '{query_str}'. Skip: {skip}, Limit: {limit}")
        if not query_str:
            logger.warning("Search called with empty query string. Returning empty list.")
            return []
        try:
            # Using SQLAlchemy ORM search
            search_term = f"%{query_str}%"
            search_filter = or_(
                self.model.name.ilike(search_term),
                self.model.contact_name.ilike(search_term),
                self.model.email.ilike(search_term)
            )
            search_query = self.session.query(self.model).filter(search_filter)

            # Apply ordering and pagination
            search_query = search_query.order_by(self.model.id.asc())
            search_query = search_query.offset(skip).limit(limit)

            logger.debug(f"Executing SQLAlchemy search query: {search_query.statement.compile(compile_kwargs={'literal_binds': True})}")
            entities = search_query.all()
            logger.info(f"Supplier search for '{query_str}' returned {len(entities)} results via ORM.")

            decrypted_entities = [self._decrypt_sensitive_fields(entity) for entity in entities]
            return decrypted_entities

        except MemoryError as me: # Catch specific MemoryError first
            logger.error(f"Memory error during ORM supplier search for '{query_str}': {me}. Falling back to direct SQL.")
            return self._search_suppliers_direct_sql(query_str, skip, limit)
        except Exception as e:
            logger.exception(f"Error during ORM supplier search for '{query_str}': {e}")
            # Optionally fallback or re-raise
            # return self._search_suppliers_direct_sql(query_str, skip, limit) # Fallback on any error?
            raise DatabaseException(
                message=f"Error searching suppliers: {str(e)}",
                entity_type="Supplier"
            )

    def _search_suppliers_direct_sql(self, query_str: str, skip: int = 0, limit: int = 100) -> List[Supplier]:
        """Fallback search implementation using direct SQL with logging."""
        logger.warning(f"Using direct SQL search fallback for query '{query_str}'. Skip: {skip}, Limit: {limit}")
        sql = """
            SELECT * FROM suppliers
            WHERE name LIKE :query OR contact_name LIKE :query OR email LIKE :query
            ORDER BY id ASC
            LIMIT :limit OFFSET :skip
            """
        params = { "query": f"%{query_str}%", "limit": limit, "skip": skip }
        entities = []
        try:
            logger.info(f"Executing Direct SQL Search Query: {sql} with params: {params}")
            # Need to handle SQLCipher connection if required here too
            from app.db.session import EncryptionManager, use_sqlcipher
            from app.core.config import settings
            import os

            if use_sqlcipher:
                # Similar connection logic as in list() method
                db_path = os.path.abspath(settings.DATABASE_PATH)
                sqlcipher = EncryptionManager.get_sqlcipher_module()
                conn = sqlcipher.connect(db_path)
                cursor = conn.cursor()
                key = EncryptionManager.get_key()
                cursor.execute(f"PRAGMA key = \"x'{key}'\";")
                # Add other pragmas if necessary...
                cursor.execute(sql, params)
                column_names = [column[0] for column in cursor.description]
                rows = cursor.fetchall()
                conn.close()
                logger.info(f"Direct SQL search returned {len(rows)} raw rows.")

                # Convert rows to Supplier model instances
                for row in rows:
                    supplier = Supplier()
                    for i, column_name in enumerate(column_names):
                         value = row[i]
                         if hasattr(supplier, column_name):
                             # Add JSON/Enum handling as in list() method
                             if column_name == 'material_categories' and isinstance(value, str):
                                 try: setattr(supplier, column_name, json.loads(value))
                                 except: setattr(supplier, column_name, [])
                             elif column_name == 'status' and value is not None:
                                 try: setattr(supplier, column_name, SupplierStatus(value.lower()))
                                 except: setattr(supplier, column_name, value)
                             else:
                                 setattr(supplier, column_name, value)
                    entities.append(supplier)
            else:
                # Standard SQLAlchemy session execute
                result = self.session.execute(text(sql), params)
                # Convert MappingResult to model instances
                for row in result.mappings(): # Use .mappings() for dict-like rows
                    supplier = Supplier()
                    for key, value in row.items():
                        if hasattr(supplier, key):
                             # Add JSON/Enum handling as in list() method
                            if key == 'material_categories' and isinstance(value, str):
                                try: setattr(supplier, key, json.loads(value))
                                except: setattr(supplier, key, [])
                            elif key == 'status' and value is not None:
                                try: setattr(supplier, key, SupplierStatus(value.lower()))
                                except: setattr(supplier, key, value)
                            else:
                                setattr(supplier, key, value)
                    entities.append(supplier)
                logger.info(f"Direct SQL search via SQLAlchemy session returned {len(entities)} entities.")


            decrypted_entities = [self._decrypt_sensitive_fields(entity) for entity in entities]
            return decrypted_entities

        except Exception as e:
            logger.exception(f"Error in direct SQL supplier search for '{query_str}': {e}")
            # Avoid raising another exception here if it's already a fallback
            return [] # Return empty list on fallback failure