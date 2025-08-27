from decimal import Decimal
from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class TableDataStream(OdbcStream):
    """Dynamic stream to read data from a specific table."""
    
    def __init__(self, config: Mapping[str, Any], schema_name: str, table_name: str):
        """
        Initialize table data stream for a specific table.
        
        :param config: Configuration dictionary containing ODBC connection parameters.
        :param schema_name: Schema name of the table
        :param table_name: Name of the table to read
        """
        super().__init__(config)
        self.schema_name = schema_name
        self.table_name = table_name
        self.full_table_name = f"{schema_name}.{table_name}"
        self._table_schema = None
    
    @property
    def name(self) -> str:
        return f"table_data_{self.schema_name}_{self.table_name}".lower().replace(' ', '_')
    
    @property
    def primary_key(self) -> Optional[str]:
        # We'll determine this dynamically from the table schema
        return None

    def get_json_schema(self) -> Mapping[str, Any]:
        """Get JSON schema based on the actual table structure."""
        if self._table_schema is None:
            self._discover_table_schema()
        
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": self._table_schema,
        }
    
    def _discover_table_schema(self):
        """Discover the table schema from the database."""
        try:
            conn = self._get_odbc_connection()
            cursor = conn.cursor()
            
            # Get column information
            schema_query = """
            SELECT 
                c.name as column_name,
                ty.name as data_type,
                c.max_length,
                c.precision,
                c.scale,
                c.is_nullable
            FROM sys.columns c
            INNER JOIN sys.tables t ON c.object_id = t.object_id
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            INNER JOIN sys.types ty ON c.user_type_id = ty.user_type_id
            WHERE s.name = ? AND t.name = ?
            ORDER BY c.column_id
            """
            
            cursor.execute(schema_query, self.schema_name, self.table_name)
            columns = cursor.fetchall()
            
            schema_properties = {}
            
            for col in columns:
                # Map SQL Server types to JSON Schema types
                json_type = self._map_sql_type_to_json_type(col.data_type)
                
                column_def = {
                    "type": json_type if not col.is_nullable else [json_type, "null"],
                    "description": f"Column {col.column_name} ({col.data_type})"
                }
                
                # Add format information for certain types
                if col.data_type in ['datetime', 'datetime2', 'date', 'time']:
                    if json_type == "string":
                        column_def["format"] = "date-time" if 'datetime' in col.data_type else "date" if col.data_type == 'date' else "time"
                
                schema_properties[col.column_name] = column_def
            
            self._table_schema = schema_properties
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error discovering schema for {self.full_table_name}: {str(e)}")
            self._table_schema = {}
    
    def _map_sql_type_to_json_type(self, sql_type: str) -> str:
        """Map SQL Server data types to JSON Schema types."""
        type_mapping = {
            # String types
            'varchar': 'string',
            'nvarchar': 'string',
            'char': 'string',
            'nchar': 'string',
            'text': 'string',
            'ntext': 'string',
            
            # Numeric types
            'int': 'integer',
            'bigint': 'integer',
            'smallint': 'integer',
            'tinyint': 'integer',
            'bit': 'boolean',
            'decimal': 'number',
            'numeric': 'number',
            'float': 'number',
            'real': 'number',
            'money': 'number',
            'smallmoney': 'number',
            
            # Date/time types
            'datetime': 'string',
            'datetime2': 'string',
            'date': 'string',
            'time': 'string',
            'datetimeoffset': 'string',
            'smalldatetime': 'string',
            
            # Binary types
            'binary': 'string',
            'varbinary': 'string',
            'image': 'string',
            
            # Other types
            'uniqueidentifier': 'string',
            'xml': 'string',
            'geography': 'string',
            'geometry': 'string',
        }
        
        return type_mapping.get(sql_type.lower(), 'string')
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read all records from the table."""
        
        try:
            conn = self._get_odbc_connection()
            cursor = conn.cursor()
            
            # Simple SELECT * query - could be optimized with pagination in the future
            query = f"SELECT * FROM [{self.schema_name}].[{self.table_name}]"
            
            cursor.execute(query)
            
            # Get column names
            columns = [column[0] for column in cursor.description]
            
            for row in cursor:
                # Convert row to dictionary
                record = {}
                for i, value in enumerate(row):
                    column_name = columns[i]
                    
                    # Convert special types to string representation
                    if value is not None:
                        if hasattr(value, 'isoformat'):  # datetime objects
                            record[column_name] = value.isoformat()
                        elif isinstance(value, (bytes, bytearray)):  # binary data
                            record[column_name] = value.hex()
                        elif isinstance(value, Decimal):  # decimal/numeric types
                            record[column_name] = float(value)
                        else:
                            record[column_name] = value
                    else:
                        record[column_name] = None
                
                yield record
            
            cursor.close()
            conn.close()
            self._cleanup_temp_files()
                    
        except Exception as e:
            self._cleanup_temp_files()
            self.logger.error(f"Error reading data from {self.full_table_name}: {str(e)}")
            raise e
