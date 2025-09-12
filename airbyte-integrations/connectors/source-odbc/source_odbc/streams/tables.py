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
                "table_catalog": {"type": "string", "description": "Database catalog name"},
                "table_schema": {"type": "string", "description": "Schema name"},
                "table_name": {"type": "string", "description": "Table name"},
                "table_type": {"type": "string", "description": "Table type (BASE TABLE, VIEW, etc.)"},
                "remarks": {"type": "string", "description": "Table remarks/description"},
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
                    for row in cursor.tables():
                        yield {
                            "table_catalog": row.table_cat,
                            "table_schema": row.table_schem,
                            "table_name": row.table_name,
                            "table_type": row.table_type,
                            "remarks": row.remarks,
                        }
                    
        except Exception as e:
            self.logger.error(f"Error reading tables: {str(e)}")
            raise e
