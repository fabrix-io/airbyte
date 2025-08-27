from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class IndexesStream(OdbcStream):
    """Stream to get all indexes for performance recreation."""
    
    @property
    def name(self) -> str:
        return "indexes"
    
    @property
    def primary_key(self) -> Optional[str]:
        return ["object_id", "index_id"]

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "object_id": {"type": "integer", "description": "Table object ID"},
                "index_id": {"type": "integer", "description": "Index ID"},
                "schema_name": {"type": "string", "description": "Schema name"},
                "table_name": {"type": "string", "description": "Table name"},
                "index_name": {"type": ["string", "null"], "description": "Index name"},
                "index_type": {"type": "string", "description": "Index type"},
                "is_unique": {"type": "boolean", "description": "Is unique index"},
                "is_primary_key": {"type": "boolean", "description": "Is primary key index"},
                "is_clustered": {"type": "boolean", "description": "Is clustered index"},
                "fill_factor": {"type": ["integer", "null"], "description": "Fill factor"},
                "is_padded": {"type": "boolean", "description": "Is padded"},
                "is_disabled": {"type": "boolean", "description": "Is disabled"},
                "allow_row_locks": {"type": "boolean", "description": "Allow row locks"},
                "allow_page_locks": {"type": "boolean", "description": "Allow page locks"},
                "data_compression_desc": {"type": ["string", "null"], "description": "Data compression"},
                "key_columns": {"type": "array", "items": {"type": "string"}, "description": "Key column names"},
                "included_columns": {"type": "array", "items": {"type": "string"}, "description": "Included column names"},
                "filter_definition": {"type": ["string", "null"], "description": "Filter condition"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read all indexes."""
        
        try:
            conn = self._get_odbc_connection()
            cursor = conn.cursor()
            
            # First get index basic info
            index_query = """
            SELECT 
                i.object_id,
                i.index_id,
                s.name as schema_name,
                t.name as table_name,
                i.name as index_name,
                i.type_desc as index_type,
                i.is_unique,
                i.is_primary_key,
                CASE WHEN i.type = 1 THEN 1 ELSE 0 END as is_clustered,
                i.fill_factor,
                i.is_padded,
                i.is_disabled,
                i.allow_row_locks,
                i.allow_page_locks,
                ISNULL(p.data_compression_desc, 'NONE') as data_compression_desc,
                i.filter_definition
            FROM sys.indexes i
            INNER JOIN sys.tables t ON i.object_id = t.object_id
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            LEFT JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
            WHERE t.is_ms_shipped = 0 AND i.type > 0  -- Exclude heaps
            ORDER BY s.name, t.name, i.index_id
            """
            
            cursor.execute(index_query)
            indexes = cursor.fetchall()
            
            # Get column information for each index
            for index_row in indexes:
                # Get key columns
                key_columns_query = """
                SELECT c.name
                FROM sys.index_columns ic
                INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE ic.object_id = ? AND ic.index_id = ? AND ic.is_included_column = 0
                ORDER BY ic.key_ordinal
                """
                
                cursor.execute(key_columns_query, index_row.object_id, index_row.index_id)
                key_columns = [row.name for row in cursor.fetchall()]
                
                # Get included columns
                included_columns_query = """
                SELECT c.name
                FROM sys.index_columns ic
                INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE ic.object_id = ? AND ic.index_id = ? AND ic.is_included_column = 1
                ORDER BY ic.index_column_id
                """
                
                cursor.execute(included_columns_query, index_row.object_id, index_row.index_id)
                included_columns = [row.name for row in cursor.fetchall()]
                
                record = {
                    "object_id": index_row.object_id,
                    "index_id": index_row.index_id,
                    "schema_name": index_row.schema_name,
                    "table_name": index_row.table_name,
                    "index_name": index_row.index_name,
                    "index_type": index_row.index_type,
                    "is_unique": bool(index_row.is_unique),
                    "is_primary_key": bool(index_row.is_primary_key),
                    "is_clustered": bool(index_row.is_clustered),
                    "fill_factor": index_row.fill_factor if index_row.fill_factor > 0 else None,
                    "is_padded": bool(index_row.is_padded),
                    "is_disabled": bool(index_row.is_disabled),
                    "allow_row_locks": bool(index_row.allow_row_locks),
                    "allow_page_locks": bool(index_row.allow_page_locks),
                    "data_compression_desc": index_row.data_compression_desc,
                    "key_columns": key_columns,
                    "included_columns": included_columns,
                    "filter_definition": index_row.filter_definition,
                }
                yield record
            
            cursor.close()
            conn.close()
            self._cleanup_temp_files()
                    
        except Exception as e:
            self._cleanup_temp_files()
            self.logger.error(f"Error reading indexes: {str(e)}")
            raise e
