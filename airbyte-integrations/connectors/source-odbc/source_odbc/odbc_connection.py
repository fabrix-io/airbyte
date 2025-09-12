import os

import pyodbc

from .odbc_cursor import OdbcCursor


class OdbcConnection:
    def __init__(self, connection: 'pyodbc.Connection', temp_files: list[str]):
        """Initialize the ODBC connection wrapper.
        
        Args:
            connection: The pyodbc connection object
            temp_files: List of temporary files to clean up when this connection closes
        """
        self._connection = connection
        self._temp_files = temp_files.copy()  # Create a copy to avoid shared references
        self._closed = False
    
    def __enter__(self):
        """Enter the context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and clean up resources."""
        self.close()
    
    def _cleanup_temp_files(self):
        """Clean up this connection's temporary files."""
        for file_path in self._temp_files:
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception:
                    pass  # Ignore cleanup errors
        self._temp_files.clear()

    def close(self):
        """Close the connection and clean up temporary files."""
        if not self._closed:
            try:
                if self._connection and not self._connection.closed:
                    self._connection.close()
            except Exception:
                pass  # Ignore connection close errors
            
            # Clean up this connection's temporary files
            self._cleanup_temp_files()
            
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
    
    def cursor(self) -> OdbcCursor:
        """Get a cursor context manager from the connection.
        
        Returns:
            OdbcCursor: A context manager that automatically handles cursor lifecycle
            
        Example:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM table")
                rows = cursor.fetchall()
        """
        if self._closed:
            raise RuntimeError("Connection has been closed")
        return OdbcCursor(self._connection)
    
    def raw_cursor(self) -> pyodbc.Cursor:
        """Get a raw pyodbc cursor from the connection.
        
        Note: This bypasses the context manager. Use cursor() instead for automatic cleanup.
        
        Returns:
            pyodbc.Cursor: Raw cursor object
        """
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
