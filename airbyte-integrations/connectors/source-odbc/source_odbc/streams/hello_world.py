from typing import Any, Iterable, Mapping, Optional

from .base import OdbcStream


class HelloWorldStream(OdbcStream):
    @property
    def name(self) -> str:
        return "hello_world"
    
    @property
    def primary_key(self) -> Optional[str]:
        return "id"

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Unique identifier"},
                "username": {"type": ["string", "null"], "description": "Current database user"},
                "system_user": {"type": ["string", "null"], "description": "System user identity"},
                "message": {"type": "string", "description": "Hello message for the user"},
                "timestamp": {"type": ["string", "null"], "description": "Current timestamp from database"},
                "database_name": {"type": ["string", "null"], "description": "Name of the connected database"},
                "server_name": {"type": ["string", "null"], "description": "Database server name"},
                "auth_scheme": {"type": ["string", "null"], "description": "Authentication scheme used"},
            }
        }
    
    def read_records(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read identity records to test ODBC connection."""
        
        try:
            conn = self._get_odbc_connection()
            cursor = conn.cursor()
            
            # Query identity information like in your original script
            identity_query = "SELECT SUSER_SNAME(), SYSTEM_USER"
            cursor.execute(identity_query)
            identity_result = cursor.fetchone()
            
            username = identity_result[0] if identity_result and identity_result[0] else "Unknown"
            system_user = identity_result[1] if identity_result and identity_result[1] else "Unknown"
            
            # Create personalized hello message
            hello_message = f"Hello {username}! Successfully connected using Kerberos authentication."
            
            # Create the record
            record = {
                "id": 1,
                "username": username,
                "system_user": system_user,
                "message": hello_message,
                "timestamp": None,
                "database_name": None,
                "server_name": None,
                "auth_scheme": None,
            }
            
            cursor.close()
            conn.close()
            
            # Clean up temporary Kerberos files
            self._cleanup_temp_files()
            
            yield record
                    
        except Exception as e:
            # Clean up on error
            self._cleanup_temp_files()
            self.logger.error(f"Error during hello world stream: {str(e)}")
            # Still yield a basic record even if connection fails
            yield {
                "id": 1,
                "username": None,
                "system_user": None,
                "message": f"Hello World from ODBC connector - Connection test failed: {str(e)}",
                "timestamp": None,
                "database_name": None,
                "server_name": None,
                "auth_scheme": None,
            }
