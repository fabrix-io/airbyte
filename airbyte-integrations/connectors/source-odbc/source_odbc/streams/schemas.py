from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class SchemasStream(OdbcStream):
    """Stream to get all database schemas."""
    
    @property
    def name(self) -> str:
        return "schemas"
    
    @property
    def primary_key(self) -> Optional[str]:
        return "schema_id"

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "schema_id": {"type": "integer", "description": "Schema ID"},
                "schema_name": {"type": "string", "description": "Schema name"},
                "principal_id": {"type": ["integer", "null"], "description": "Schema owner principal ID"},
                "principal_name": {"type": ["string", "null"], "description": "Schema owner name"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read all database schemas."""
        
        try:
            conn = self._get_odbc_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                s.schema_id,
                s.name as schema_name,
                s.principal_id,
                p.name as principal_name
            FROM sys.schemas s
            LEFT JOIN sys.database_principals p ON s.principal_id = p.principal_id
            ORDER BY s.name
            """
            
            cursor.execute(query)
            
            for row in cursor:
                record = {
                    "schema_id": row.schema_id,
                    "schema_name": row.schema_name,
                    "principal_id": row.principal_id,
                    "principal_name": row.principal_name,
                }
                yield record
            
            cursor.close()
            conn.close()
                    
        except Exception as e:
            self.logger.error(f"Error reading schemas: {str(e)}")
            raise e
