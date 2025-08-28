import os
import tempfile
import textwrap

import pyodbc

from binascii import unhexlify
from typing import Any, List, Mapping, Tuple

from impacket.krb5 import constants
from impacket.krb5.ccache import CCache
from impacket.krb5.kerberosv5 import getKerberosTGT
from impacket.krb5.types import Principal

from .authentication_types import AuthenticationType
from .database_types import DatabaseType
from .odbc_connection import OdbcConnection


class OdbcConnectionManager:
    
    def setup_kerberos_config(self, realm: str, kdc_host: str, temp_files: List[str]) -> Tuple[str, str]:
        #TODO: This should be a connection configuration!!!!
        krb5_conf = textwrap.dedent(f"""
        [libdefaults]
          default_realm = {realm}
          dns_lookup_kdc = false
          dns_lookup_realm = false
          rdns = false
          ticket_lifetime = 24h
          forwardable = false
          udp_preference_limit = 1

        [realms]
          {realm.upper()} = {{
            kdc = {kdc_host}
            admin_server = {kdc_host}
          }}

        [domain_realm]
          .{realm.lower()} = {realm.upper()}
          {realm.lower()} = {realm.upper()}
        """).strip() + "\n"
        
        krb5_path = tempfile.mktemp(prefix="krb5_", suffix=".conf")
        with open(krb5_path, "w") as f:
            f.write(krb5_conf)
        os.environ["KRB5_CONFIG"] = krb5_path
        temp_files.append(krb5_path)
        
        # Set up credential cache
        ccache_path = tempfile.mktemp(prefix="krbcc_", suffix=".ccache")
        os.environ["KRB5CCNAME"] = f"FILE:{ccache_path}"
        os.environ["KRB5_CCNAME"] = f"FILE:{ccache_path}"
        temp_files.append(ccache_path)
        
        return krb5_path, ccache_path

    def authenticate_with_kerberos(self, username: str, password: str, realm: str, kdc_host: str, temp_files: List[str]) -> str:
        client = Principal(username, type=constants.PrincipalNameType.NT_PRINCIPAL.value)
        
        tgt, cipher, old_session_key, session_key = getKerberosTGT(
            clientName=client,
            password=password,
            domain=realm,
            lmhash=unhexlify(b""),
            nthash=unhexlify(b""),
            aesKey=None,
            kdcHost=kdc_host
        )

        # Save to ccache file
        ccache_path = os.environ.get("KRB5CCNAME", "").replace("FILE:", "")
        if not ccache_path:
            ccache_path = tempfile.mktemp(prefix="impacket_", suffix=".ccache")
            os.environ["KRB5CCNAME"] = f"FILE:{ccache_path}"
            os.environ["KRB5_CCNAME"] = f"FILE:{ccache_path}"
            temp_files.append(ccache_path)
        
        # Create and save ccache
        cc = CCache()
        cc.fromTGT(tgt, old_session_key, session_key)
        cc.saveFile(ccache_path)
        
        # Set proper permissions (important for security)
        os.chmod(ccache_path, 0o600)
        
        return ccache_path

    @staticmethod
    def get_database_drivers(database_type: DatabaseType) -> List[str]:
        driver_preferences = {
            DatabaseType.SQL_SERVER: [
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server", 
                "ODBC Driver 13 for SQL Server",
                "ODBC Driver 11 for SQL Server",
                "SQL Server Native Client 11.0",
                "SQL Server Native Client 10.0",
                "FreeTDS",  # Open-source driver, available on more architectures
                "SQL Server"
            ],
            DatabaseType.POSTGRESQL: [
                "PostgreSQL Unicode",
                "PostgreSQL ANSI",
                "PostgreSQL Unicode(x64)",
                "PostgreSQL ANSI(x64)"
            ],
            # Future database types can be added here:
            # DatabaseType.ORACLE: [
            #     "Oracle in OraClient19Home1",
            #     "Oracle in OraClient18Home1", 
            #     "Oracle in OraClient12Home1",
            #     "Oracle ODBC Driver"
            # ],
            # DatabaseType.MYSQL: [
            #     "MySQL ODBC 8.0 Unicode Driver",
            #     "MySQL ODBC 8.0 ANSI Driver",
            #     "MySQL ODBC 5.3 Unicode Driver",
            #     "MySQL ODBC 5.3 ANSI Driver"
            # ]
        }
        
        return driver_preferences.get(database_type, [])

    @staticmethod
    def auto_detect_driver(database_type: DatabaseType, available_drivers: List[str]) -> str:
        """Auto-detect the best available driver for the database type."""
        preferred_drivers = OdbcConnectionManager.get_database_drivers(database_type)
        
        # Try each preferred driver in order
        for driver in preferred_drivers:
            if driver in available_drivers:
                return driver
        
        # If no preferred driver found, raise an error with helpful info
        raise ValueError(
            f"No compatible ODBC driver found for {database_type.value}. "
            f"Preferred drivers: {preferred_drivers}. "
            f"Available drivers: {available_drivers}. "
            f"Please install a compatible ODBC driver."
        )

    def get_odbc_connection(self, config: Mapping[str, Any]) -> OdbcConnection:
        """Create an ODBC connection context manager with database-specific driver auto-detection."""
        
        server = config['server']
        database = config['database']
        database_type = DatabaseType.from_string(config['database_type'])
        username = config['username']
        password = config['password']
        
        # Set default port based on database type
        port = config.get('port', database_type.get_default_port())
        
        # Set default authentication type based on database type
        auth_type_str = config.get('authentication_type', database_type.get_default_auth_type().value)
        auth_type = AuthenticationType.from_string(auth_type_str)
        
        timeout = config.get('connection_timeout', 60)
        
        # Kerberos-specific parameters
        realm = config.get('realm')
        kdc_host = config.get('kdc_host')

        # Track temp files for this specific connection
        connection_temp_files = []

        try:
            if auth_type == AuthenticationType.ACTIVE_DIRECTORY_INTEGRATED:
                if not realm or not kdc_host:
                    raise ValueError("realm and kdc_host are required for ActiveDirectoryIntegrated authentication")
                
                # Setup Kerberos configuration and authenticate
                krb5_path, ccache_path = self.setup_kerberos_config(realm, kdc_host, connection_temp_files)
                actual_ccache = self.authenticate_with_kerberos(username, password, realm, kdc_host, connection_temp_files)

            # Get available drivers
            available_drivers = pyodbc.drivers()
            
            # Auto-detect driver if not specified
            driver = self.auto_detect_driver(database_type, available_drivers)

            # Try multiple drivers if the first one fails
            drivers_to_try = [driver]
            if driver != self.get_database_drivers(database_type)[0]:
                # Add other preferred drivers as fallbacks
                other_drivers = [d for d in self.get_database_drivers(database_type) 
                               if d != driver and d in available_drivers]
                drivers_to_try.extend(other_drivers)

            last_error = None
            
            for current_driver in drivers_to_try:
                try:
                    # Build connection string for this driver
                    conn_str_parts = []
                    
                    if database_type == DatabaseType.POSTGRESQL:
                        # PostgreSQL connection string format
                        conn_str_parts = [
                            f"DRIVER={{{current_driver}}}",
                            f"SERVER={server}",
                            f"PORT={port}",
                            f"DATABASE={database}",
                            f"UID={username}",
                            f"PWD={password}",
                        ]
                        
                        # Add PostgreSQL-specific SSL settings if needed
                        conn_str_parts.append("SSLMode=prefer")
                        
                    else:  # SQL Server and other databases
                        conn_str_parts = [
                            f"DRIVER={{{current_driver}}}",
                            f"SERVER={server},{port}" if port != 1433 else f"SERVER={server}",
                            f"DATABASE={database}",
                        ]
                        
                        # Add authentication based on type
                        if auth_type == AuthenticationType.ACTIVE_DIRECTORY_PASSWORD:
                            conn_str_parts.extend([
                                f"UID={username}",
                                f"PWD={password}",
                                "Authentication=ActiveDirectoryPassword"
                            ])
                        elif auth_type == AuthenticationType.ACTIVE_DIRECTORY_INTEGRATED:
                            # For Integrated, we use Trusted_Connection which relies on the Kerberos ticket
                            conn_str_parts.append("Trusted_Connection=Yes")
                        elif auth_type == AuthenticationType.SQL_SERVER_AUTHENTICATION:
                            conn_str_parts.extend([
                                f"UID={username}",
                                f"PWD={password}"
                            ])
                        
                        # Add security settings for SQL Server
                        conn_str_parts.append("Encrypt=yes")
                        conn_str_parts.append("TrustServerCertificate=yes")
                    
                    conn_str = ';'.join(conn_str_parts)

                    # Try to connect with this driver
                    connection = pyodbc.connect(
                        conn_str,
                        timeout=timeout,
                        autocommit=True
                    )
                    
                    # Return the connection wrapped in our context manager
                    return OdbcConnection(connection, connection_temp_files)
                    
                except Exception as e:
                    last_error = e
                    continue
            
            # If we get here, all drivers failed
            raise Exception(
                f"Failed to connect with any available driver for {database_type.value}. "
                f"Tried drivers: {drivers_to_try}. "
                f"Last error: {str(last_error)}"
            )

        except Exception as e:
            # Cleanup temp files for this connection on error
            self._cleanup_connection_temp_files(connection_temp_files)
            raise e

    @staticmethod
    def _cleanup_connection_temp_files(temp_files: List[str]):
        """Clean up temporary files for a specific connection."""
        for file_path in temp_files:
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception:
                    pass  # Ignore cleanup errors
