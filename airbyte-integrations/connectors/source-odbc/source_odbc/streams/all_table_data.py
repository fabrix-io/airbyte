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
        """Read all records from all tables in the database."""
        
        try:
            conn = self._get_odbc_connection()
            cursor = conn.cursor()
            
            # First, get all user tables
            tables_query = """
            SELECT s.name as schema_name, t.name as table_name, t.object_id
            FROM sys.tables t
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE t.is_ms_shipped = 0
            ORDER BY s.name, t.name
            """
            
            cursor.execute(tables_query)
            tables = cursor.fetchall()
            
            self.logger.info(f"Found {len(tables)} tables to extract data from")
            
            # Process each table
            for table in tables:
                schema_name = table.schema_name
                table_name = table.table_name
                full_table_name = f"{schema_name}.{table_name}"
                
                try:
                    # Get all records from this table
                    data_query = f"SELECT * FROM [{schema_name}].[{table_name}]"
                    cursor.execute(data_query)
                    
                    # Get column names
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
                            "extracted_at": self._get_current_timestamp()
                        }
                        
                        row_num += 1
                    
                    self.logger.info(f"Extracted {row_num - 1} records from {full_table_name}")
                    
                except Exception as e:
                    self.logger.error(f"Error reading data from table {full_table_name}: {str(e)}")
                    # Continue with next table instead of failing completely
                    continue
            
            cursor.close()
            conn.close()
            self._connection_manager.cleanup_temp_files()
            
        except Exception as e:
            self.logger.error(f"Error reading table data: {str(e)}")
            raise
        finally:
            self._connection_manager.cleanup_temp_files()
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
