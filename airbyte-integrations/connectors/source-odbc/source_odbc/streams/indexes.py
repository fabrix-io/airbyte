from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class IndexesStream(OdbcStream):
    """Stream to get all indexes for performance recreation."""
    
    @property
    def name(self) -> str:
        return "indexes"
    
    @property
    def primary_key(self) -> Optional[str]:
        return ["table_catalog", "table_schema", "table_name", "index_name"]

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "table_catalog": {"type": ["string", "null"], "description": "Database catalog name"},
                "table_schema": {"type": "string", "description": "Schema name"},
                "table_name": {"type": "string", "description": "Table name"},
                "index_name": {"type": ["string", "null"], "description": "Index name"},
                "non_unique": {"type": ["boolean", "null"], "description": "Is non-unique index (0=unique, 1=non-unique)"},
                "index_qualifier": {"type": ["string", "null"], "description": "Index qualifier"},
                "ordinal_position": {"type": ["integer", "null"], "description": "Column position in index"},
                "column_name": {"type": ["string", "null"], "description": "Column name"},
                "asc_or_desc": {"type": ["string", "null"], "description": "Sort sequence (A=ascending, D=descending)"},
                "cardinality": {"type": ["integer", "null"], "description": "Index cardinality"},
                "pages": {"type": ["integer", "null"], "description": "Number of pages used by index"},
                "filter_condition": {"type": ["string", "null"], "description": "Filter condition"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read all indexes using ODBC catalog functions, querying each table individually."""
        
        try:
            with self._get_odbc_connection() as conn:
                with conn.cursor() as cursor:
                    # First get all tables using the same approach as TablesStream
                    tables = []
                    for table_row in cursor.tables():
                        table_type = getattr(table_row, 'table_type', '')
                        if table_type in ('TABLE', 'BASE TABLE', 'VIEW', 'SYSTEM TABLE'):
                            tables.append({
                                'catalog': getattr(table_row, 'table_cat', ''),
                                'schema': getattr(table_row, 'table_schem', ''),
                                'name': getattr(table_row, 'table_name', '')
                            })
                    
                    # Now get indexes for each table
                    for table in tables:
                        try:
                            # Query statistics for this specific table
                            catalog = table['catalog'] or ''
                            schema = table['schema'] or ''
                            table_name = table['name'] or ''
                            
                            for row in cursor.statistics(catalog=catalog, schema=schema, table=table_name):
                                # Filter out table statistics (type SQL_TABLE_STAT) and only include index statistics
                                index_type = getattr(row, 'type', None)
                                if index_type not in (0, None):  # 0 = SQL_TABLE_STAT, we want index stats
                                    record = {
                                        "table_catalog": getattr(row, 'table_cat', None),
                                        "table_schema": getattr(row, 'table_schem', None),
                                        "table_name": getattr(row, 'table_name', None),
                                        "index_name": getattr(row, 'index_name', None),
                                        "non_unique": getattr(row, 'non_unique', None),
                                        "index_qualifier": getattr(row, 'index_qualifier', None),
                                        "ordinal_position": getattr(row, 'ordinal_position', None),
                                        "column_name": getattr(row, 'column_name', None),
                                        "asc_or_desc": getattr(row, 'asc_or_desc', None),
                                        "cardinality": getattr(row, 'cardinality', None),
                                        "pages": getattr(row, 'pages', None),
                                        "filter_condition": getattr(row, 'filter_condition', None),
                                    }
                                    yield record
                        except Exception as table_error:
                            # Log error for this specific table but continue with others
                            self.logger.warning(f"Could not get indexes for table {schema}.{table_name}: {str(table_error)}")
                            continue
                    
        except Exception as e:
            self.logger.error(f"Error reading indexes: {str(e)}")
            raise e
