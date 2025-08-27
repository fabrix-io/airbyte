from typing import Any, Iterable, Mapping, Optional

import pyodbc

from .base import OdbcStream


class DatabaseMetadataStream(OdbcStream):
    """Stream to get catalog information using ODBC catalog functions."""
    
    @property
    def name(self) -> str:
        return "database_metadata"
    
    @property
    def primary_key(self) -> Optional[str]:
        return "catalog_name"

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "catalog_name": {"type": "string", "description": "Database catalog name"},
                "schema_count": {"type": ["integer"], "description": "Number of schemas in this catalog"},
                "table_count": {"type": ["integer"], "description": "Number of tables in this catalog"},
                "view_count": {"type": ["integer"], "description": "Number of views in this catalog"},
                "procedure_count": {"type": ["integer"], "description": "Number of stored procedures in this catalog"},
                "function_count": {"type": ["integer"], "description": "Number of functions in this catalog"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read catalog information using ODBC getinfo functions."""
        
        try:
            with self._get_odbc_connection() as conn:
                with conn.cursor() as cursor:
                    # Get catalog/database name directly using ODBC getinfo
                    catalog_name = None
                    try:
                        # Try to get catalog name using ODBC constants
                        if hasattr(pyodbc, 'SQL_DATABASE_NAME'):
                            catalog_name = conn.getinfo(pyodbc.SQL_DATABASE_NAME)
                        elif hasattr(pyodbc, 'SQL_CATALOG_NAME'):
                            catalog_name = conn.getinfo(pyodbc.SQL_CATALOG_NAME)
                        else:
                            # Fallback to numeric constants
                            try:
                                catalog_name = conn.getinfo(16)  # SQL_DATABASE_NAME
                            except Exception:
                                catalog_name = conn.getinfo(17)  # SQL_CATALOG_NAME
                    except Exception as catalog_error:
                        self.logger.warning(f"Could not retrieve catalog name: {str(catalog_error)}")
                        catalog_name = self._config.get('database', 'default')
                    
                    # Count objects in the catalog using ODBC catalog functions
                    schema_count = 0
                    table_count = 0
                    view_count = 0
                    procedure_count = 0
                    
                    # Count tables and views
                    try:
                        schemas = set()
                        for row in cursor.tables():
                            table_type = row.table_type
                            schema = row.table_schem
                            
                            if schema:
                                schemas.add(schema)
                            
                            if table_type in ('TABLE', 'BASE TABLE'):
                                table_count += 1
                            elif table_type == 'VIEW':
                                view_count += 1
                        
                        schema_count = len(schemas)
                        
                    except Exception as table_error:
                        self.logger.warning(f"Could not retrieve table information: {str(table_error)}")
                    
                    # Count procedures
                    try:
                        for row in cursor.procedures():
                            procedure_count += 1
                    except Exception as proc_error:
                        self.logger.warning(f"Could not retrieve procedure information: {str(proc_error)}")
                    
                    # Create and yield the catalog record
                    record = {
                        "catalog_name": catalog_name or "default",
                        "schema_count": schema_count,
                        "table_count": table_count,
                        "view_count": view_count,
                        "procedure_count": procedure_count,
                        "function_count": procedure_count,  # Functions often same as procedures in ODBC
                    }
                    yield record
                    
        except Exception as e:
            self.logger.error(f"Error reading database catalog metadata: {str(e)}")
            raise e
