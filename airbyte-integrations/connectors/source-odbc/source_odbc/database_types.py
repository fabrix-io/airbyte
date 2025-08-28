from enum import Enum

from .authentication_types import AuthenticationType


class DatabaseType(Enum):
    """Enumeration of supported database types."""
    
    SQL_SERVER = "SqlServer"
    POSTGRESQL = "PostgreSQL"
    # Future database types can be added here:
    # ORACLE = "Oracle"
    # MYSQL = "MySQL"
    # SQLITE = "SQLite"
    
    @classmethod
    def from_string(cls, value: str) -> "DatabaseType":
        value_lower = value.lower()
        for db_type in cls:
            if db_type.value.lower() == value_lower:
                return db_type
            
        raise ValueError(f"Unsupported database type: {value}. Supported types are: {[db.value for db in cls]}")
        
    def get_default_port(self) -> int:
        """Get the default port for this database type."""
        port_mapping = {
            self.SQL_SERVER: 1433,
            self.POSTGRESQL: 5432,
        }
        return port_mapping[self]
    
    def get_default_auth_type(self) -> AuthenticationType:
        auth_mapping = {
            self.SQL_SERVER: AuthenticationType.ACTIVE_DIRECTORY_KERBEROS,
            self.POSTGRESQL: AuthenticationType.SQL_SERVER_AUTHENTICATION,
        }
        return auth_mapping[self]