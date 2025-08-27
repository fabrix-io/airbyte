from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class ColumnsStream(OdbcStream):
    @property
    def name(self) -> str:
        return "columns"
    
    @property
    def primary_key(self) -> Optional[str]:
        return ["table_catalog", "table_schema", "table_name", "column_name"]

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "table_catalog": {"type": ["string", "null"], "description": "Database catalog name"},
                "table_schema": {"type": "string", "description": "Schema name"},
                "table_name": {"type": "string", "description": "Table name"},
                "column_name": {"type": "string", "description": "Column name"},
                "ordinal_position": {"type": ["integer", "null"], "description": "Column position in table"},
                "column_default": {"type": ["string", "null"], "description": "Default value"},
                "is_nullable": {"type": ["string", "null"], "description": "YES if nullable, NO if not"},
                "data_type": {"type": ["string", "null"], "description": "Data type name"},
                "character_maximum_length": {"type": ["integer", "null"], "description": "Maximum character length"},
                "numeric_precision": {"type": ["integer", "null"], "description": "Numeric precision"},
                "numeric_scale": {"type": ["integer", "null"], "description": "Numeric scale"},
                "datetime_precision": {"type": ["integer", "null"], "description": "DateTime precision"},
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
                    # First get all tables, then get columns for each table
                    # This ensures we have the table context for each column
                    tables = []
                    try:
                        for table_row in cursor.tables():
                            table_type = getattr(table_row, 'table_type', '')
                            if table_type in ('TABLE', 'BASE TABLE', 'VIEW'):
                                tables.append({
                                    'catalog': getattr(table_row, 'table_cat', None),
                                    'schema': getattr(table_row, 'table_schem', None),
                                    'name': getattr(table_row, 'table_name', None)
                                })
                    except Exception as table_error:
                        self.logger.warning(f"Could not retrieve tables for column enumeration: {str(table_error)}")
                    
                    # Get columns for each table
                    for table in tables:
                        try:
                            # Use ODBC columns() catalog function for each table
                            for col_row in cursor.columns(
                                catalog=table['catalog'],
                                schema=table['schema'],
                                table=table['name']
                            ):
                                record = {
                                    "table_catalog": getattr(col_row, 'table_cat', None),
                                    "table_schema": getattr(col_row, 'table_schem', None),
                                    "table_name": getattr(col_row, 'table_name', None),
                                    "column_name": getattr(col_row, 'column_name', None),
                                    "ordinal_position": getattr(col_row, 'ordinal_position', None),
                                    "column_default": getattr(col_row, 'column_def', None),
                                    "is_nullable": "YES" if getattr(col_row, 'nullable', 1) == 1 else "NO",
                                    "data_type": getattr(col_row, 'type_name', None),
                                    "character_maximum_length": getattr(col_row, 'column_size', None) if getattr(col_row, 'type_name', '').lower() in ('varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext') else None,
                                    "numeric_precision": getattr(col_row, 'column_size', None) if getattr(col_row, 'type_name', '').lower() in ('decimal', 'numeric', 'float', 'real', 'int', 'bigint', 'smallint', 'tinyint') else None,
                                    "numeric_scale": getattr(col_row, 'decimal_digits', None) if getattr(col_row, 'type_name', '').lower() in ('decimal', 'numeric') else None,
                                    "datetime_precision": getattr(col_row, 'decimal_digits', None) if getattr(col_row, 'type_name', '').lower() in ('datetime', 'datetime2', 'time', 'timestamp') else None,
                                }
                                yield record
                                
                        except Exception as col_error:
                            self.logger.warning(f"Could not retrieve columns for table {table['schema']}.{table['name']}: {str(col_error)}")
                            continue
                    
        except Exception as e:
            self.logger.error(f"Error reading columns: {str(e)}")
            raise e
