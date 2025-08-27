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
                "table_catalog": {"type": "string", "description": "Database catalog name"},
                "table_schema": {"type": "string", "description": "Schema name"},
                "table_name": {"type": "string", "description": "Table name"},
                "column_name": {"type": "string", "description": "Column name"},
                "ordinal_position": {"type": ["integer"], "description": "Column position in table"},
                "column_default": {"type": "string", "description": "Default value"},
                "is_nullable": {"type": "string", "description": "YES if nullable, NO if not"},
                "data_type": {"type": "string", "description": "Data type name"},
                "character_maximum_length": {"type": ["integer"], "description": "Maximum character length"},
                "numeric_precision": {"type": ["integer"], "description": "Numeric precision"},
                "numeric_scale": {"type": ["integer"], "description": "Numeric scale"},
                "datetime_precision": {"type": ["integer"], "description": "DateTime precision"},
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
                            table_type = table_row.table_type
                            if table_type in ('TABLE', 'BASE TABLE', 'VIEW'):
                                tables.append({
                                    'catalog': table_row.table_cat,
                                    'schema': table_row.table_schem,
                                    'name': table_row.table_name
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
                                yield {
                                    "table_catalog": col_row.table_cat,
                                    "table_schema": col_row.table_schem,
                                    "table_name": col_row.table_name,
                                    "column_name": col_row.column_name,
                                    "ordinal_position": col_row.ordinal_position,
                                    "column_default": col_row.column_def,
                                    "is_nullable": "YES" if col_row.nullable == 1 else "NO",
                                    "data_type": col_row.type_name,
                                    "character_maximum_length": col_row.column_size if getattr(col_row, 'type_name', '').lower() in ('varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext') else None,
                                    "numeric_precision": col_row.column_size if col_row.type_name.lower() in ('decimal', 'numeric', 'float', 'real', 'int', 'bigint', 'smallint', 'tinyint') else None,
                                    "numeric_scale": col_row.decimal_digits if col_row.type_name.lower() in ('decimal', 'numeric') else None,
                                    "datetime_precision": col_row.decimal_digits if col_row.type_name.lower() in ('datetime', 'datetime2', 'time', 'timestamp') else None,
                                }
                                
                        except Exception as col_error:
                            self.logger.warning(f"Could not retrieve columns for table {table['schema']}.{table['name']}: {str(col_error)}")
                            continue
                    
        except Exception as e:
            self.logger.error(f"Error reading columns: {str(e)}")
            raise e
