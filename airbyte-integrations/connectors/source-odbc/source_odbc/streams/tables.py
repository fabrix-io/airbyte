from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class TablesStream(OdbcStream):
    """Stream to get all database tables and their metadata."""
    
    @property
    def name(self) -> str:
        return "tables"
    
    @property
    def primary_key(self) -> Optional[str]:
        return "object_id"

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "object_id": {"type": "integer", "description": "Table object ID"},
                "schema_name": {"type": "string", "description": "Schema name"},
                "table_name": {"type": "string", "description": "Table name"},
                "full_table_name": {"type": "string", "description": "Schema.Table name"},
                "table_type": {"type": "string", "description": "Table type (BASE TABLE, VIEW, etc.)"},
                "create_date": {"type": ["string", "null"], "description": "Table creation date"},
                "modify_date": {"type": ["string", "null"], "description": "Table last modification date"},
                "row_count": {"type": ["integer", "null"], "description": "Approximate row count"},
                "has_clustered_index": {"type": "boolean", "description": "Has clustered index"},
                "has_primary_key": {"type": "boolean", "description": "Has primary key"},
                "is_replicated": {"type": "boolean", "description": "Is replicated"},
                "is_published": {"type": "boolean", "description": "Is published for replication"},
                "data_compression_desc": {"type": ["string", "null"], "description": "Data compression type"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read all database tables."""
        
        try:
            with self._get_odbc_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                SELECT 
                    t.object_id,
                    s.name as schema_name,
                    t.name as table_name,
                    s.name + '.' + t.name as full_table_name,
                    CASE 
                        WHEN t.type = 'U' THEN 'BASE TABLE'
                        WHEN t.type = 'V' THEN 'VIEW'
                        ELSE t.type_desc
                    END as table_type,
                    t.create_date,
                    t.modify_date,
                    ISNULL(p.rows, 0) as row_count,
                    CAST(CASE WHEN EXISTS(
                        SELECT 1 FROM sys.indexes i 
                        WHERE i.object_id = t.object_id AND i.type = 1
                    ) THEN 1 ELSE 0 END AS BIT) as has_clustered_index,
                    CAST(CASE WHEN EXISTS(
                        SELECT 1 FROM sys.key_constraints kc 
                        WHERE kc.parent_object_id = t.object_id AND kc.type = 'PK'
                    ) THEN 1 ELSE 0 END AS BIT) as has_primary_key,
                    t.is_replicated,
                    t.is_published,
                    ISNULL(p.data_compression_desc, 'NONE') as data_compression_desc
                FROM sys.tables t
                INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
                LEFT JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0, 1)
                WHERE t.is_ms_shipped = 0
                ORDER BY s.name, t.name
                """
                
                cursor.execute(query)
                
                for row in cursor:
                    record = {
                        "object_id": row.object_id,
                        "schema_name": row.schema_name,
                        "table_name": row.table_name,
                        "full_table_name": row.full_table_name,
                        "table_type": row.table_type,
                        "create_date": str(row.create_date) if row.create_date else None,
                        "modify_date": str(row.modify_date) if row.modify_date else None,
                        "row_count": row.row_count,
                        "has_clustered_index": bool(row.has_clustered_index),
                        "has_primary_key": bool(row.has_primary_key),
                        "is_replicated": bool(row.is_replicated),
                        "is_published": bool(row.is_published),
                        "data_compression_desc": row.data_compression_desc,
                    }
                    yield record
                    
        except Exception as e:
            self.logger.error(f"Error reading tables: {str(e)}")
            raise e
