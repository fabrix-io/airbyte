import os
import sys
import tempfile
import textwrap
from binascii import unhexlify
from typing import Any, List, Mapping, Optional, Tuple

import pyodbc
from airbyte_cdk import AbstractSource
from airbyte_cdk.sources.streams import Stream
from impacket.krb5 import constants
from impacket.krb5.ccache import CCache
from impacket.krb5.kerberosv5 import getKerberosTGT
from impacket.krb5.types import Principal

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
        self._temp_files = []  # Track temporary files for cleanup

    def check_connection(self, logger, config: Mapping[str, Any]) -> Tuple[bool, Optional[str]]:
        try:
            conn = self._get_odbc_connection(config)
            # Simple test query to verify connection
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return True, None

        except Exception as e:
            return False, f"Error connecting to ODBC server: {str(e)}"
        finally:
            # Cleanup temporary files
            self._cleanup_temp_files()

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """Return all available streams."""
        
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

    def _cleanup_temp_files(self):
        """Clean up temporary Kerberos files."""
        for file_path in self._temp_files:
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception:
                    pass  # Ignore cleanup errors
        self._temp_files.clear()

    def _setup_kerberos_config(self, realm: str, kdc_host: str) -> Tuple[str, str]:
        """Setup Kerberos configuration."""
        krb5_conf = textwrap.dedent(f"""
        [libdefaults]
          default_realm = {realm}
          dns_lookup_kdc = false
          dns_lookup_realm = false
          rdns = false
          ticket_lifetime = 24h
          forwardable = true
          udp_preference_limit = 1

        [realms]
          {realm} = {{
            kdc = {kdc_host}
            admin_server = {kdc_host}
          }}

        [domain_realm]
          .compute-1.amazonaws.com = {realm}
          compute-1.amazonaws.com = {realm}
          .{realm.lower()} = {realm}
          {realm.lower()} = {realm}
        """).strip() + "\n"
        
        krb5_path = tempfile.mktemp(prefix="krb5_", suffix=".conf")
        with open(krb5_path, "w") as f:
            f.write(krb5_conf)
        os.environ["KRB5_CONFIG"] = krb5_path
        self._temp_files.append(krb5_path)
        
        # Set up credential cache
        ccache_path = tempfile.mktemp(prefix="krbcc_", suffix=".ccache")
        os.environ["KRB5CCNAME"] = f"FILE:{ccache_path}"
        os.environ["KRB5_CCNAME"] = f"FILE:{ccache_path}"
        self._temp_files.append(ccache_path)
        
        return krb5_path, ccache_path

    def _authenticate_with_kerberos(self, username: str, password: str, realm: str, kdc_host: str) -> str:
        """Use impacket for pure Python Kerberos authentication."""
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
            self._temp_files.append(ccache_path)
        
        # Create and save ccache
        cc = CCache()
        cc.fromTGT(tgt, old_session_key, session_key)
        cc.saveFile(ccache_path)
        
        # Set proper permissions (important for security)
        os.chmod(ccache_path, 0o600)
        
        return ccache_path

    def _get_database_drivers(self, database_type: str) -> List[str]:
        """Get list of preferred drivers for a database type, in order of preference."""
        driver_preferences = {
            "SqlServer": [
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server", 
                "ODBC Driver 13 for SQL Server",
                "ODBC Driver 11 for SQL Server",
                "SQL Server Native Client 11.0",
                "SQL Server Native Client 10.0",
                "FreeTDS",  # Open-source driver, available on more architectures
                "SQL Server"
            ],
            # Future database types can be added here:
            # "Oracle": [
            #     "Oracle in OraClient19Home1",
            #     "Oracle in OraClient18Home1", 
            #     "Oracle in OraClient12Home1",
            #     "Oracle ODBC Driver"
            # ],
            # "PostgreSQL": [
            #     "PostgreSQL Unicode",
            #     "PostgreSQL ANSI"
            # ],
            # "MySQL": [
            #     "MySQL ODBC 8.0 Unicode Driver",
            #     "MySQL ODBC 8.0 ANSI Driver",
            #     "MySQL ODBC 5.3 Unicode Driver",
            #     "MySQL ODBC 5.3 ANSI Driver"
            # ]
        }
        
        return driver_preferences.get(database_type, [])

    def _auto_detect_driver(self, database_type: str, available_drivers: List[str]) -> str:
        preferred_drivers = self._get_database_drivers(database_type)
        
        # Try each preferred driver in order
        for driver in preferred_drivers:
            if driver in available_drivers:
                return driver
        
        # If no preferred driver found, raise an error with helpful info
        raise ValueError(
            f"No compatible ODBC driver found for {database_type}. "
            f"Preferred drivers: {preferred_drivers}. "
            f"Available drivers: {available_drivers}. "
            f"Please install a compatible ODBC driver."
        )

    def _get_odbc_connection(self, config: Mapping[str, Any]) -> Any:
        """Create an ODBC connection with database-specific driver auto-detection."""
        
        server = config['server']
        database = config['database']
        database_type = config.get('database_type', 'SqlServer')
        username = config['username']
        password = config['password']
        port = config.get('port', 1433)
        auth_type = config.get('authentication_type', 'ActiveDirectory')
        timeout = config.get('connection_timeout', 30)
        
        # Kerberos-specific parameters
        realm = config.get('realm')
        kdc_host = config.get('kdc_host')

        # Setup Kerberos authentication if required
        if auth_type == "ActiveDirectoryKerberos":
            if not realm or not kdc_host:
                raise ValueError("realm and kdc_host are required for ActiveDirectoryKerberos authentication")
            
            # Setup Kerberos configuration and authenticate
            krb5_path, ccache_path = self._setup_kerberos_config(realm, kdc_host)
            actual_ccache = self._authenticate_with_kerberos(username, password, realm, kdc_host)

        # Get available drivers
        available_drivers = pyodbc.drivers()
        
        # Auto-detect driver if not specified
        driver = self._auto_detect_driver(database_type, available_drivers)

        # Try multiple drivers if the first one fails
        drivers_to_try = [driver]
        if driver != self._get_database_drivers(database_type)[0]:
            # Add other preferred drivers as fallbacks
            other_drivers = [d for d in self._get_database_drivers(database_type) 
                           if d != driver and d in available_drivers]
            drivers_to_try.extend(other_drivers)

        last_error = None
        
        for current_driver in drivers_to_try:
            try:
                # Build connection string for this driver
                conn_str_parts = [
                    f"DRIVER={{{current_driver}}}",
                    f"SERVER={server},{port}" if port != 1433 else f"SERVER={server}",
                    f"DATABASE={database}",
                ]
                
                # Add authentication based on type
                if auth_type in ("ActiveDirectory", "ActiveDirectoryPassword"):
                    conn_str_parts.extend([
                        f"UID={username}",
                        f"PWD={password}",
                        "Authentication=ActiveDirectoryPassword"
                    ])
                elif auth_type == "ActiveDirectoryIntegrated" or auth_type == "ActiveDirectoryKerberos":
                    # For Kerberos, we use Trusted_Connection which relies on the Kerberos ticket
                    conn_str_parts.append("Trusted_Connection=Yes")
                else:  # SqlServerAuthentication
                    conn_str_parts.extend([
                        f"UID={username}",
                        f"PWD={password}"
                    ])
                
                # Add security settings
                conn_str_parts.append("Encrypt=yes")
                conn_str_parts.append("TrustServerCertificate=yes")
                
                conn_str = ';'.join(conn_str_parts)

                # Try to connect with this driver
                connection = pyodbc.connect(
                    conn_str,
                    timeout=timeout,
                    autocommit=True
                )
                
                return connection
                
            except Exception as e:
                last_error = e
                continue
        
        # If we get here, all drivers failed
        raise Exception(
            f"Failed to connect with any available driver for {database_type}. "
            f"Tried drivers: {drivers_to_try}. "
            f"Last error: {str(last_error)}"
        )
