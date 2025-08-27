from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class ForeignKeysStream(OdbcStream):
    """Stream to get all foreign key constraints for referential integrity."""
    
    @property
    def name(self) -> str:
        return "foreign_keys"
    
    @property
    def primary_key(self) -> Optional[str]:
        return "constraint_object_id"

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "constraint_object_id": {"type": "integer", "description": "Foreign key constraint object ID"},
                "constraint_name": {"type": "string", "description": "Foreign key constraint name"},
                "parent_schema": {"type": "string", "description": "Parent table schema"},
                "parent_table": {"type": "string", "description": "Parent table name"},
                "parent_columns": {"type": "array", "items": {"type": "string"}, "description": "Parent table columns"},
                "referenced_schema": {"type": "string", "description": "Referenced table schema"},
                "referenced_table": {"type": "string", "description": "Referenced table name"},
                "referenced_columns": {"type": "array", "items": {"type": "string"}, "description": "Referenced table columns"},
                "update_referential_action": {"type": "string", "description": "ON UPDATE action"},
                "delete_referential_action": {"type": "string", "description": "ON DELETE action"},
                "is_disabled": {"type": "boolean", "description": "Is constraint disabled"},
                "is_not_for_replication": {"type": "boolean", "description": "Not for replication"},
                "is_not_trusted": {"type": "boolean", "description": "Is not trusted"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read all foreign key constraints."""
        
        try:
            conn = self._get_odbc_connection()
            cursor = conn.cursor()
            
            # Get foreign key basic info
            fk_query = """
            SELECT DISTINCT
                fk.object_id as constraint_object_id,
                fk.name as constraint_name,
                ps.name as parent_schema,
                pt.name as parent_table,
                rs.name as referenced_schema,
                rt.name as referenced_table,
                fk.update_referential_action_desc as update_referential_action,
                fk.delete_referential_action_desc as delete_referential_action,
                fk.is_disabled,
                fk.is_not_for_replication,
                fk.is_not_trusted
            FROM sys.foreign_keys fk
            INNER JOIN sys.tables pt ON fk.parent_object_id = pt.object_id
            INNER JOIN sys.schemas ps ON pt.schema_id = ps.schema_id
            INNER JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id
            INNER JOIN sys.schemas rs ON rt.schema_id = rs.schema_id
            WHERE pt.is_ms_shipped = 0
            ORDER BY ps.name, pt.name, fk.name
            """
            
            cursor.execute(fk_query)
            foreign_keys = cursor.fetchall()
            
            # Get column mappings for each foreign key
            for fk_row in foreign_keys:
                # Get column mappings
                columns_query = """
                SELECT 
                    pc.name as parent_column,
                    rc.name as referenced_column
                FROM sys.foreign_key_columns fkc
                INNER JOIN sys.columns pc ON fkc.parent_object_id = pc.object_id AND fkc.parent_column_id = pc.column_id
                INNER JOIN sys.columns rc ON fkc.referenced_object_id = rc.object_id AND fkc.referenced_column_id = rc.column_id
                WHERE fkc.constraint_object_id = ?
                ORDER BY fkc.constraint_column_id
                """
                
                cursor.execute(columns_query, fk_row.constraint_object_id)
                column_mappings = cursor.fetchall()
                
                parent_columns = [mapping.parent_column for mapping in column_mappings]
                referenced_columns = [mapping.referenced_column for mapping in column_mappings]
                
                record = {
                    "constraint_object_id": fk_row.constraint_object_id,
                    "constraint_name": fk_row.constraint_name,
                    "parent_schema": fk_row.parent_schema,
                    "parent_table": fk_row.parent_table,
                    "parent_columns": parent_columns,
                    "referenced_schema": fk_row.referenced_schema,
                    "referenced_table": fk_row.referenced_table,
                    "referenced_columns": referenced_columns,
                    "update_referential_action": fk_row.update_referential_action,
                    "delete_referential_action": fk_row.delete_referential_action,
                    "is_disabled": bool(fk_row.is_disabled),
                    "is_not_for_replication": bool(fk_row.is_not_for_replication),
                    "is_not_trusted": bool(fk_row.is_not_trusted),
                }
                yield record
            
            cursor.close()
            conn.close()
            self._connection_manager.cleanup_temp_files()
                    
        except Exception as e:
            self._connection_manager.cleanup_temp_files()
            self.logger.error(f"Error reading foreign keys: {str(e)}")
            raise e
