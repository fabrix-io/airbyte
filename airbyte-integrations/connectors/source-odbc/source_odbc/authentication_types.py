from enum import Enum


class AuthenticationType(Enum):
    ACTIVE_DIRECTORY = "ActiveDirectory"
    SQL_SERVER_AUTHENTICATION = "SqlServerAuthentication"
    ACTIVE_DIRECTORY_INTEGRATED = "ActiveDirectoryIntegrated"
    ACTIVE_DIRECTORY_PASSWORD = "ActiveDirectoryPassword"
    ACTIVE_DIRECTORY_KERBEROS = "ActiveDirectoryKerberos"
    
    @classmethod
    def from_string(cls, value: str) -> "AuthenticationType":
        for auth_type in cls:
            if auth_type.value == value:
                return auth_type
            
        raise ValueError(f"Unsupported authentication type: {value}. Supported types are: {[auth.value for auth in cls]}")
        
    def __str__(self) -> str:
        return self.value
