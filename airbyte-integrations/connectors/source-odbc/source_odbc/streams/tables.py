from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class TablesStream(OdbcStream):

    @property
    def name(self) -> str:
        return "tables"
    
    @property
    def primary_key(self) -> Optional[str]:
        return ["table_catalog", "table_schema", "table_name"]

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "table_catalog": {"type": ["string", "null"], "description": "Database catalog name"},
                "table_schema": {"type": "string", "description": "Schema name"},
                "table_name": {"type": "string", "description": "Table name"},
                "table_type": {"type": "string", "description": "Table type (BASE TABLE, VIEW, etc.)"},
                "remarks": {"type": ["string", "null"], "description": "Table remarks/description"},
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
                    # Use ODBC catalog function to get table information
                    # This is more portable than database-specific system tables
                    for row in cursor.tables():
                        # Filter out system tables and only include user tables and views
                        table_type = getattr(row, 'table_type', '')
                        if table_type in ('TABLE', 'BASE TABLE', 'VIEW', 'SYSTEM TABLE'):
                            record = {
                                "table_catalog": getattr(row, 'table_cat', None),
                                "table_schema": getattr(row, 'table_schem', None),
                                "table_name": getattr(row, 'table_name', None),
                                "table_type": table_type,
                                "remarks": getattr(row, 'remarks', None),
                            }
                            yield record
                    
        except Exception as e:
            self.logger.error(f"Error reading tables: {str(e)}")
            raise e
