from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class ForeignKeysStream(OdbcStream):
    """Stream to get all foreign key constraints for referential integrity."""
    
    @property
    def name(self) -> str:
        return "foreign_keys"
    
    @property
    def primary_key(self) -> Optional[str]:
        return ["pk_table_catalog", "pk_table_schema", "pk_table_name", "fk_table_catalog", "fk_table_schema", "fk_table_name", "key_seq"]

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "pk_table_catalog": {"type": ["string", "null"], "description": "Primary key table catalog"},
                "pk_table_schema": {"type": "string", "description": "Primary key table schema"},
                "pk_table_name": {"type": "string", "description": "Primary key table name"},
                "pk_column_name": {"type": "string", "description": "Primary key column name"},
                "fk_table_catalog": {"type": ["string", "null"], "description": "Foreign key table catalog"},
                "fk_table_schema": {"type": "string", "description": "Foreign key table schema"},
                "fk_table_name": {"type": "string", "description": "Foreign key table name"},
                "fk_column_name": {"type": "string", "description": "Foreign key column name"},
                "key_seq": {"type": "integer", "description": "Sequence number of column in multi-column foreign key"},
                "update_rule": {"type": ["integer", "null"], "description": "Action for UPDATE rule"},
                "delete_rule": {"type": ["integer", "null"], "description": "Action for DELETE rule"},
                "fk_name": {"type": ["string", "null"], "description": "Foreign key constraint name"},
                "pk_name": {"type": ["string", "null"], "description": "Primary key constraint name"},
                "deferrability": {"type": ["integer", "null"], "description": "Deferrability of the foreign key"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read all foreign key constraints using ODBC catalog functions."""
        
        try:
            with self._get_odbc_connection() as conn:
                with conn.cursor() as cursor:
                    # First get all tables using the same approach as other streams
                    tables = []
                    for table_row in cursor.tables():
                        table_type = getattr(table_row, 'table_type', '')
                        if table_type in ('TABLE', 'BASE TABLE'):  # Only user tables for FKs
                            tables.append({
                                'catalog': getattr(table_row, 'table_cat', ''),
                                'schema': getattr(table_row, 'table_schem', ''),
                                'name': getattr(table_row, 'table_name', '')
                            })
                    
                    # Now get foreign keys for each table
                    for table in tables:
                        try:
                            catalog = table['catalog']
                            schema = table['schema']
                            table_name = table['name']
                            
                            # Query foreign keys where this table is the foreign key table
                            for row in cursor.foreignKeys(
                                foreignCatalog=catalog,     # This specific table's catalog
                                foreignSchema=schema,       # This specific table's schema
                                foreignTable=table_name     # This specific table
                            ):
                                record = {
                                    "pk_table_catalog": getattr(row, 'pktable_cat', None),
                                    "pk_table_schema": getattr(row, 'pktable_schem', None),
                                    "pk_table_name": getattr(row, 'pktable_name', None),
                                    "pk_column_name": getattr(row, 'pkcolumn_name', None),
                                    "fk_table_catalog": getattr(row, 'fktable_cat', None),
                                    "fk_table_schema": getattr(row, 'fktable_schem', None),
                                    "fk_table_name": getattr(row, 'fktable_name', None),
                                    "fk_column_name": getattr(row, 'fkcolumn_name', None),
                                    "key_seq": getattr(row, 'key_seq', None),
                                    "update_rule": getattr(row, 'update_rule', None),
                                    "delete_rule": getattr(row, 'delete_rule', None),
                                    "fk_name": getattr(row, 'fk_name', None),
                                    "pk_name": getattr(row, 'pk_name', None),
                                    "deferrability": getattr(row, 'deferrability', None),
                                }
                                yield record
                        except Exception as table_error:
                            # Log error for this specific table but continue with others
                            self.logger.warning(f"Could not get foreign keys for table {schema}.{table_name}: {str(table_error)}")
                            continue
                    
        except Exception as e:
            self.logger.error(f"Error reading foreign keys: {str(e)}")
            raise e
