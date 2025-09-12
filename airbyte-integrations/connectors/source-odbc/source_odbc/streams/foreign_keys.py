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
                "pk_table_catalog": {"type": "string", "description": "Primary key table catalog"},
                "pk_table_schema": {"type": "string", "description": "Primary key table schema"},
                "pk_table_name": {"type": "string", "description": "Primary key table name"},
                "pk_column_name": {"type": "string", "description": "Primary key column name"},
                "fk_table_catalog": {"type": "string", "description": "Foreign key table catalog"},
                "fk_table_schema": {"type": "string", "description": "Foreign key table schema"},
                "fk_table_name": {"type": "string", "description": "Foreign key table name"},
                "fk_column_name": {"type": "string", "description": "Foreign key column name"},
                "key_seq": {"type": "integer", "description": "Sequence number of column in multi-column foreign key"},
                "update_rule": {"type": ["integer"], "description": "Action for UPDATE rule"},
                "delete_rule": {"type": ["integer"], "description": "Action for DELETE rule"},
                "fk_name": {"type": "string", "description": "Foreign key constraint name"},
                "pk_name": {"type": "string", "description": "Primary key constraint name"},
                "deferrability": {"type": ["integer"], "description": "Deferrability of the foreign key"},
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
                        table_type = table_row.table_type
                        if table_type in ('TABLE', 'BASE TABLE'):  # Only user tables for FKs
                            tables.append({
                                'catalog': table_row.table_cat,
                                'schema': table_row.table_schem,
                                'name': table_row.table_name
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
                                yield {
                                    "pk_table_catalog": row.pktable_cat,
                                    "pk_table_schema": row.pktable_schem,
                                    "pk_table_name": row.pktable_name,
                                    "pk_column_name": row.pkcolumn_name,
                                    "fk_table_catalog": row.fktable_cat,
                                    "fk_table_schema": row.fktable_schem,
                                    "fk_table_name": row.fktable_name,
                                    "fk_column_name": row.fkcolumn_name,
                                    "key_seq": row.key_seq,
                                    "update_rule": row.update_rule,
                                    "delete_rule": row.delete_rule,
                                    "fk_name": row.fk_name,
                                    "pk_name": row.pk_name,
                                    "deferrability": row.deferrability,
                                }
                        except Exception as table_error:
                            self.logger.warning(f"Could not get foreign keys for table {schema}.{table_name}: {str(table_error)}")
                            continue
                    
        except Exception as e:
            self.logger.error(f"Error reading foreign keys: {str(e)}")
            raise e
