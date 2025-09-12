from typing import Any, Mapping, Optional, Tuple

from airbyte_cdk import AbstractSource
from airbyte_cdk.sources.streams import Stream

from .connection import OdbcConnectionManager
from .streams import (
    DatabaseMetadataStream,
    SchemasStream,
    TablesStream,
    ColumnsStream,
    IndexesStream,
    ForeignKeysStream,
    AllTableDataStream,
)


class SourceOdbc(AbstractSource):
    def __init__(self):
        super().__init__()
        self._connection_manager = OdbcConnectionManager()

    def check_connection(self, logger, config: Mapping[str, Any]) -> Tuple[bool, Optional[str]]:
        try:
            with self._connection_manager.get_odbc_connection(config) as conn:
                # Simple test query to verify connection
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            return True, None

        except Exception as e:
            return False, f"Error connecting to ODBC server: {str(e)}"

    def streams(self, config: Mapping[str, Any]) -> list[Stream]:
        streams = [
            DatabaseMetadataStream(config=config),
            SchemasStream(config=config),
            TablesStream(config=config),
            ColumnsStream(config=config),
            IndexesStream(config=config),
            ForeignKeysStream(config=config),
            AllTableDataStream(config=config)
        ]
        
        return streams
