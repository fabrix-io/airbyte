from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class SchemasStream(OdbcStream):
    """Stream to get all database schemas."""
    
    @property
    def name(self) -> str:
        return "schemas"
    
    @property
    def primary_key(self) -> Optional[str]:
        return "table_schema"

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "table_catalog": {"type": ["string", "null"], "description": "Database catalog name"},
                "table_schema": {"type": "string", "description": "Schema name"},
                "table_name": {"type": ["string", "null"], "description": "Table name (null for schema info)"},
                "table_type": {"type": ["string", "null"], "description": "Table type"},
                "remarks": {"type": ["string", "null"], "description": "Schema remarks/description"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        try:
            with self._get_odbc_connection() as conn:
                with conn.cursor() as cursor:
                    # Use ODBC catalog function to get schema information
                    # This is more portable than INFORMATION_SCHEMA across different databases
                    schemas_seen = set()
                    
                    for row in cursor.tables():
                        # Extract unique schema names
                        schema_name = getattr(row, 'table_schem', None)
                        if schema_name and schema_name not in schemas_seen:
                            schemas_seen.add(schema_name)
                            
                            record = {
                                "table_catalog": getattr(row, 'table_cat', None),
                                "table_schema": schema_name,
                                "table_name": None,  # Not applicable for schema info
                                "table_type": "SCHEMA",
                                "remarks": getattr(row, 'remarks', None),
                            }
                            yield record
                    
        except Exception as e:
            self.logger.error(f"Error reading schemas: {str(e)}")
            raise e
