import pyodbc

from typing import Any, Optional


class OdbcCursor:
    """A context manager wrapper for pyodbc cursors with automatic resource cleanup."""
    
    def __init__(self, connection: pyodbc.Connection):
        """Initialize the cursor wrapper.
        
        Args:
            connection: The pyodbc connection object to create cursor from
        """
        self._connection = connection
        self._cursor: Optional[pyodbc.Cursor] = None
        self._closed = False
    
    def __enter__(self) -> 'OdbcCursor':
        """Enter the context manager and create the cursor."""
        if self._connection.closed:
            raise RuntimeError("Cannot create cursor from closed connection")
        
        self._cursor = self._connection.cursor()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and clean up cursor resources."""
        self.close()
    
    def close(self):
        """Close the cursor and clean up resources."""
        if not self._closed and self._cursor:
            try:
                self._cursor.close()
            except Exception:
                pass  # Ignore cursor close errors
            finally:
                self._cursor = None
                self._closed = True
    
    @property
    def cursor(self) -> pyodbc.Cursor:
        """Get the underlying pyodbc cursor."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        return self._cursor
    
    def execute(self, query: str, *args, **kwargs) -> 'OdbcCursor':
        """Execute a query on the cursor.
        
        Returns:
            Self to allow method chaining
        """
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        self._cursor.execute(query, *args, **kwargs)
        return self
    
    def executemany(self, query: str, params_seq) -> 'OdbcCursor':
        """Execute a query multiple times with different parameters.
        
        Returns:
            Self to allow method chaining
        """
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        self._cursor.executemany(query, params_seq)
        return self
    
    def fetchone(self) -> Optional[pyodbc.Row]:
        """Fetch one row from the result set."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        return self._cursor.fetchone()
    
    def fetchmany(self, size: Optional[int] = None) -> list[pyodbc.Row]:
        """Fetch multiple rows from the result set."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        if size is None:
            return self._cursor.fetchmany()
        return self._cursor.fetchmany(size)
    
    def fetchall(self) -> list[pyodbc.Row]:
        """Fetch all remaining rows from the result set."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        return self._cursor.fetchall()
    
    def nextset(self) -> Optional[bool]:
        """Skip to the next available result set."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        return self._cursor.nextset()
    
    @property
    def description(self) -> Optional[tuple]:
        """Get the cursor description (column metadata)."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        return self._cursor.description
    
    @property
    def rowcount(self) -> int:
        """Get the number of rows affected by the last execute."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        return self._cursor.rowcount
    
    @property
    def closed(self) -> bool:
        """Check if the cursor is closed."""
        return self._closed or not self._cursor
    
    def __iter__(self):
        """Make the cursor iterable."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        return iter(self._cursor)
    
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying cursor."""
        if self._closed or not self._cursor:
            raise RuntimeError("Cursor has been closed or not initialized")
        
        return getattr(self._cursor, name)
