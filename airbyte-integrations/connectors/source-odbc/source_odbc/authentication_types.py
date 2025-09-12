from enum import Enum


class AuthenticationType(Enum):
    # Docs: https://learn.microsoft.com/en-us/sql/connect/odbc/using-azure-active-directory?view=sql-server-ver17
    SQL_SERVER_AUTHENTICATION = "SqlPassword"
    ACTIVE_DIRECTORY_INTEGRATED = "ActiveDirectoryIntegrated" # Kerberos
    ACTIVE_DIRECTORY_PASSWORD = "ActiveDirectoryPassword"
    
    @classmethod
    def from_string(cls, value: str) -> "AuthenticationType":
        for auth_type in cls:
            if auth_type.value == value:
                return auth_type
            
        raise ValueError(f"Unsupported authentication type: {value}. Supported types are: {[auth.value for auth in cls]}")
        
    def __str__(self) -> str:
        return self.value
