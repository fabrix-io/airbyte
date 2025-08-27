from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class DatabaseMetadataStream(OdbcStream):
    """Stream to get database metadata and settings."""
    
    @property
    def name(self) -> str:
        return "database_metadata"
    
    @property
    def primary_key(self) -> Optional[str]:
        return "database_name"

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "database_name": {"type": "string", "description": "Database name"},
                "database_id": {"type": "integer", "description": "Database ID"},
                "collation_name": {"type": ["string", "null"], "description": "Database collation"},
                "create_date": {"type": ["string", "null"], "description": "Database creation date"},
                "compatibility_level": {"type": ["integer", "null"], "description": "Compatibility level"},
                "state_desc": {"type": ["string", "null"], "description": "Database state"},
                "is_read_only": {"type": "boolean", "description": "Is database read-only"},
                "is_auto_close_on": {"type": "boolean", "description": "Auto close setting"},
                "is_auto_shrink_on": {"type": "boolean", "description": "Auto shrink setting"},
                "recovery_model_desc": {"type": ["string", "null"], "description": "Recovery model"},
                "page_verify_option_desc": {"type": ["string", "null"], "description": "Page verify option"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read database metadata."""
        
        try:
            conn = self._get_odbc_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                name as database_name,
                database_id,
                collation_name,
                create_date,
                compatibility_level,
                state_desc,
                is_read_only,
                is_auto_close_on,
                is_auto_shrink_on,
                recovery_model_desc,
                page_verify_option_desc
            FROM sys.databases 
            WHERE name = DB_NAME()
            """
            
            cursor.execute(query)
            
            for row in cursor:
                record = {
                    "database_name": row.database_name,
                    "database_id": row.database_id,
                    "collation_name": row.collation_name,
                    "create_date": str(row.create_date) if row.create_date else None,
                    "compatibility_level": row.compatibility_level,
                    "state_desc": row.state_desc,
                    "is_read_only": bool(row.is_read_only),
                    "is_auto_close_on": bool(row.is_auto_close_on),
                    "is_auto_shrink_on": bool(row.is_auto_shrink_on),
                    "recovery_model_desc": row.recovery_model_desc,
                    "page_verify_option_desc": row.page_verify_option_desc,
                }
                yield record
            
            cursor.close()
            conn.close()
            self._cleanup_temp_files()
                    
        except Exception as e:
            self._cleanup_temp_files()
            self.logger.error(f"Error reading database metadata: {str(e)}")
            raise e
