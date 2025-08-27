import pyodbc

from typing import Callable, Optional


class OdbcConnection:
    def __init__(self, connection: 'pyodbc.Connection', temp_files: list, cleanup_func: Optional[Callable] = None):
        """Initialize the ODBC connection wrapper.
        
        Args:
            connection: The pyodbc connection object
            temp_files: List of temporary files to clean up
            cleanup_func: Optional cleanup function to call on exit
        """
        self._connection = connection
        self._temp_files = temp_files
        self._cleanup_func = cleanup_func
        self._closed = False
    
    def __enter__(self):
        """Enter the context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and clean up resources."""
        self.close()
    
    def close(self):
        """Close the connection and clean up temporary files."""
        if not self._closed:
            try:
                if self._connection and not self._connection.closed:
                    self._connection.close()
            except Exception:
                pass  # Ignore connection close errors
            
            # Clean up temporary files using the cleanup function
            if self._cleanup_func:
                try:
                    self._cleanup_func()
                except Exception:
                    pass  # Ignore cleanup errors
            
            self._closed = True
    
    @property
    def connection(self) -> pyodbc.Connection:
        """Get the underlying pyodbc connection."""
        if self._closed:
            raise RuntimeError("Connection has been closed")
        return self._connection
    
    def execute(self, query: str, *args, **kwargs):
        """Execute a query on the connection."""
        if self._closed:
            raise RuntimeError("Connection has been closed")
        return self._connection.execute(query, *args, **kwargs)
    
    def cursor(self):
        """Get a cursor from the connection."""
        if self._closed:
            raise RuntimeError("Connection has been closed")
        return self._connection.cursor()
    
    def commit(self):
        """Commit the current transaction."""
        if self._closed:
            raise RuntimeError("Connection has been closed")
        return self._connection.commit()
    
    def rollback(self):
        """Rollback the current transaction."""
        if self._closed:
            raise RuntimeError("Connection has been closed")
        return self._connection.rollback()
    
    @property
    def closed(self) -> bool:
        """Check if the connection is closed."""
        return self._closed or (self._connection and self._connection.closed)
    
    def __getattr__(self, name):
        """Delegate attribute access to the underlying connection."""
        if self._closed:
            raise RuntimeError("Connection has been closed")
        return getattr(self._connection, name)
