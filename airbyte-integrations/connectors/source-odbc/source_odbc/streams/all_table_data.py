import logging
from decimal import Decimal
from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class AllTableDataStream(OdbcStream):
    """Stream that contains all records from all tables in the database."""
    
    @property
    def name(self) -> str:
        return "all_table_data"
    
    @property
    def primary_key(self) -> Optional[str]:
        # No primary key for this combined stream
        return None

    def get_json_schema(self) -> Mapping[str, Any]:
        """Get JSON schema for the combined table data stream."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "source_table_schema": {
                    "type": "string",
                    "description": "Schema name of the source table"
                },
                "source_table_name": {
                    "type": "string", 
                    "description": "Name of the source table"
                },
                "source_table_full_name": {
                    "type": "string",
                    "description": "Full table name (schema.table)"
                },
                "record_data": {
                    "type": "object",
                    "description": "The actual record data from the table",
                    "additionalProperties": True
                },
                "row_number": {
                    "type": "integer",
                    "description": "Row number within the source table"
                },
                "extracted_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp when the record was extracted"
                }
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
                    # First, get all user tables using ODBC catalog function
                    tables = []
                    try:
                        for table_row in cursor.tables():
                            table_type = table_row.table_type
                            if table_type in ('TABLE', 'BASE TABLE'):  # Only actual tables, not views
                                tables.append({
                                    'catalog': table_row.table_cat,
                                    'schema': table_row.table_schem,
                                    'name': table_row.table_name
                                })
                    except Exception as table_error:
                        self.logger.warning(f"Could not retrieve tables for data extraction: {str(table_error)}")
                        return
                    
                    self.logger.info(f"Found {len(tables)} tables to extract data from")
                    
                    for table in tables:
                        schema_name = table['schema']
                        table_name = table['name']
                        catalog_name = table['catalog']
                        
                        # Create full table name (handle different database quoting styles)
                        if catalog_name:
                            full_table_name = f"{catalog_name}.{schema_name}.{table_name}"
                        else:
                            full_table_name = f"{schema_name}.{table_name}"
                        
                        try:
                            # Build a generic SELECT query that works across databases
                            # Use proper quoting that works with most databases
                            if schema_name and schema_name.lower() != 'dbo':
                                quoted_table = f'"{schema_name}"."{table_name}"'
                            else:
                                quoted_table = f'"{table_name}"'
                            
                            data_query = f"SELECT * FROM {quoted_table}"
                            cursor.execute(data_query)
                            
                            # Get column names from cursor description
                            columns = [column[0] for column in cursor.description]
                            
                            # Track row number within this table
                            row_num = 1
                            
                            for row in cursor:
                                # Convert row to dictionary
                                record_data = {}
                                for i, value in enumerate(row):
                                    column_name = columns[i]
                                    
                                    # Convert special types to JSON-serializable values
                                    if value is not None:
                                        if hasattr(value, 'isoformat'):  # datetime objects
                                            record_data[column_name] = value.isoformat()
                                        elif isinstance(value, (bytes, bytearray)):  # binary data
                                            record_data[column_name] = value.hex()
                                        elif isinstance(value, Decimal):  # decimal/numeric types
                                            record_data[column_name] = float(value)
                                        else:
                                            record_data[column_name] = value
                                    else:
                                        record_data[column_name] = None
                                
                                # Yield the combined record with metadata
                                yield {
                                    "source_table_schema": schema_name,
                                    "source_table_name": table_name,
                                    "source_table_full_name": full_table_name,
                                    "record_data": record_data,
                                    "row_number": row_num,
                                }
                                
                                row_num += 1
                                
                        except Exception as table_error:
                            self.logger.warning(f"Error reading table {full_table_name}: {str(table_error)}")
                            # Try alternative quoting strategy
                            try:
                                if schema_name and schema_name.lower() != 'dbo':
                                    alt_quoted_table = f'[{schema_name}].[{table_name}]'
                                else:
                                    alt_quoted_table = f'[{table_name}]'
                                
                                alt_data_query = f"SELECT * FROM {alt_quoted_table}"
                                cursor.execute(alt_data_query)
                                
                                # Get column names from cursor description
                                columns = [column[0] for column in cursor.description]
                                
                                # Track row number within this table
                                row_num = 1
                                
                                for row in cursor:
                                    # Convert row to dictionary
                                    record_data = {}
                                    for i, value in enumerate(row):
                                        column_name = columns[i]
                                        
                                        # Convert special types to JSON-serializable values
                                        if value is not None:
                                            if hasattr(value, 'isoformat'):  # datetime objects
                                                record_data[column_name] = value.isoformat()
                                            elif isinstance(value, (bytes, bytearray)):  # binary data
                                                record_data[column_name] = value.hex()
                                            elif isinstance(value, Decimal):  # decimal/numeric types
                                                record_data[column_name] = float(value)
                                            else:
                                                record_data[column_name] = value
                                        else:
                                            record_data[column_name] = None
                                    
                                    # Yield the combined record with metadata
                                    yield {
                                        "source_table_schema": schema_name,
                                        "source_table_name": table_name,
                                        "source_table_full_name": full_table_name,
                                        "record_data": record_data,
                                        "row_number": row_num,
                                    }
                                    
                                    row_num += 1
                                    
                            except Exception as alt_error:
                                self.logger.error(f"Failed to read table {full_table_name} with both quoting strategies: {str(alt_error)}")
                                # Continue with next table instead of failing completely
                                continue
                            
        except Exception as e:
            self.logger.error(f"Error reading table data: {str(e)}")
            raise e
    