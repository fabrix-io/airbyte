from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional

from airbyte_cdk.sources.streams import Stream

from ..connection import OdbcConnectionManager



class OdbcStream(Stream, ABC):
    """Base stream class for ODBC connections."""

    def __init__(self, config: Mapping[str, Any]):
        """
        Initialize the stream with ODBC configuration.
        
        :param config: Configuration dictionary containing ODBC connection parameters.
        """
        super().__init__()
        self._config = config
        self._connection_manager = OdbcConnectionManager()

    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def primary_key(self) -> Optional[str]:
        ...
    
    @abstractmethod
    def get_json_schema(self) -> Mapping[str, Any]:
        ...

    def _get_odbc_connection(self) -> Any:
        """Create an ODBC connection using the shared connection manager."""
        return self._connection_manager.get_odbc_connection(self._config)
