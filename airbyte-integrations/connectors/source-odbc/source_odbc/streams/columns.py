from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class ColumnsStream(OdbcStream):
    """Stream to get all table columns with complete schema information."""
    
    @property
    def name(self) -> str:
        return "columns"
    
    @property
    def primary_key(self) -> Optional[str]:
        return ["object_id", "column_id"]

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "object_id": {"type": "integer", "description": "Table object ID"},
                "column_id": {"type": "integer", "description": "Column ID"},
                "schema_name": {"type": "string", "description": "Schema name"},
                "table_name": {"type": "string", "description": "Table name"},
                "column_name": {"type": "string", "description": "Column name"},
                "data_type": {"type": "string", "description": "Data type name"},
                "max_length": {"type": ["integer", "null"], "description": "Maximum length"},
                "precision": {"type": ["integer", "null"], "description": "Numeric precision"},
                "scale": {"type": ["integer", "null"], "description": "Numeric scale"},
                "is_nullable": {"type": "boolean", "description": "Is nullable"},
                "is_identity": {"type": "boolean", "description": "Is identity column"},
                "is_computed": {"type": "boolean", "description": "Is computed column"},
                "default_definition": {"type": ["string", "null"], "description": "Default value definition"},
                "collation_name": {"type": ["string", "null"], "description": "Column collation"},
                "is_primary_key": {"type": "boolean", "description": "Is part of primary key"},
                "is_foreign_key": {"type": "boolean", "description": "Is part of foreign key"},
                "ordinal_position": {"type": "integer", "description": "Column position in table"},
                "full_data_type": {"type": "string", "description": "Complete data type definition"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read all table columns."""
        
        try:
            with self._get_odbc_connection() as conn:
                with conn.cursor() as cursor:
                    query = """
                    SELECT 
                        c.object_id,
                        c.column_id,
                        s.name as schema_name,
                        t.name as table_name,
                        c.name as column_name,
                        ty.name as data_type,
                        c.max_length,
                        c.precision,
                        c.scale,
                        c.is_nullable,
                        c.is_identity,
                        c.is_computed,
                        dc.definition as default_definition,
                        c.collation_name,
                        CAST(CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS BIT) as is_primary_key,
                        CAST(CASE WHEN fk.parent_column_id IS NOT NULL THEN 1 ELSE 0 END AS BIT) as is_foreign_key,
                        c.column_id as ordinal_position,
                        CASE 
                            WHEN ty.name IN ('varchar', 'nvarchar', 'char', 'nchar', 'binary', 'varbinary') THEN
                                ty.name + '(' + CASE WHEN c.max_length = -1 THEN 'MAX' ELSE CAST(c.max_length AS VARCHAR) END + ')'
                            WHEN ty.name IN ('decimal', 'numeric') THEN
                                ty.name + '(' + CAST(c.precision AS VARCHAR) + ',' + CAST(c.scale AS VARCHAR) + ')'
                            WHEN ty.name IN ('float') THEN
                                ty.name + '(' + CAST(c.precision AS VARCHAR) + ')'
                            ELSE ty.name
                        END as full_data_type
                    FROM sys.columns c
                    INNER JOIN sys.tables t ON c.object_id = t.object_id
                    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
                    INNER JOIN sys.types ty ON c.user_type_id = ty.user_type_id
                    LEFT JOIN sys.default_constraints dc ON c.object_id = dc.parent_object_id AND c.column_id = dc.parent_column_id
                    LEFT JOIN (
                        SELECT kc.parent_object_id, ic.column_id
                        FROM sys.key_constraints kc
                        INNER JOIN sys.index_columns ic ON kc.parent_object_id = ic.object_id AND kc.unique_index_id = ic.index_id
                        WHERE kc.type = 'PK'
                    ) pk ON c.object_id = pk.parent_object_id AND c.column_id = pk.column_id
                    LEFT JOIN sys.foreign_key_columns fk ON c.object_id = fk.parent_object_id AND c.column_id = fk.parent_column_id
                    WHERE t.is_ms_shipped = 0
                    ORDER BY s.name, t.name, c.column_id
                    """
                    
                    cursor.execute(query)
                    
                    for row in cursor:
                        record = {
                            "object_id": row.object_id,
                            "column_id": row.column_id,
                            "schema_name": row.schema_name,
                            "table_name": row.table_name,
                            "column_name": row.column_name,
                            "data_type": row.data_type,
                            "max_length": row.max_length if row.max_length != -1 else None,
                            "precision": row.precision,
                            "scale": row.scale,
                            "is_nullable": bool(row.is_nullable),
                            "is_identity": bool(row.is_identity),
                            "is_computed": bool(row.is_computed),
                            "default_definition": row.default_definition,
                            "collation_name": row.collation_name,
                            "is_primary_key": bool(row.is_primary_key),
                            "is_foreign_key": bool(row.is_foreign_key),
                            "ordinal_position": row.ordinal_position,
                            "full_data_type": row.full_data_type,
                        }
                        yield record
                    
        except Exception as e:
            self.logger.error(f"Error reading columns: {str(e)}")
            raise e
